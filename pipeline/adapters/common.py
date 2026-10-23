"""
common.py: the shared schema, HTTP session, dates and file helpers for every adapter.

Each adapter module has one function, fetch(ctx) -> SourceResult. The result carries the rows
in the common schema plus any series or headline figures the source publishes. Adapters never
raise: a failure becomes status "failed" with the reason, so one bad source never stops the run.
"""
from __future__ import annotations
import datetime as dt
import json, os, re, time
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache")
SAMPLES = os.path.join(ROOT, "samples")
SNAPSHOTS = os.path.join(ROOT, "snapshots")
UA = "OutbreakLensPipeline/2.0 (+https://outbreaklens.com; hello@outbreaklens.com)"

# The common schema, in column order. same_as and record_type are additions to the brief's list.
COLUMNS = [
    "event_id", "record_type", "source", "source_url", "source_updated", "fetched_at",
    "category", "disease", "serotype_or_strain",
    "country_iso3", "country_name", "admin1", "admin2", "place_as_published", "place_level", "lat", "lon",
    "species", "population_type", "date_start", "date_confirmed", "date_reported",
    "outbreaks", "cases", "deaths", "status", "notes", "same_as",
]
PLACE_LEVELS = ("country", "admin1", "admin2", "settlement")
POPULATION_TYPES = ("domestic", "wild", "mixed", "")
STATUSES = ("ongoing", "resolved", "unknown")
RECORD_TYPES = ("event", "case", "aggregate")


def row(**kw) -> dict:
    """A record with every schema column present. Unknown keys are an error, to catch typos."""
    extra = set(kw) - set(COLUMNS)
    if extra:
        raise KeyError("not in schema: %s" % ", ".join(sorted(extra)))
    r = {c: "" for c in COLUMNS}
    r.update({k: ("" if v is None else v) for k, v in kw.items()})
    if not r["status"]:
        r["status"] = "unknown"
    return r


@dataclass
class SourceResult:
    key: str                      # short adapter name, e.g. "wahis"
    name: str                     # the source as cited, e.g. "WOAH WAHIS"
    url: str                      # the page or endpoint read
    status: str = "failed"        # live | fallback | failed | stub
    rows: list = field(default_factory=list)
    series: list = field(default_factory=list)      # weekly series for aggregates.json
    headlines: list = field(default_factory=list)   # headline figures for latest.json
    extras: dict = field(default_factory=dict)      # anything else other steps need (not published)
    fetched_at: str = ""
    source_updated: str = ""
    http: int | None = None
    error: str = ""
    notes: list = field(default_factory=list)
    licence: str = ""
    attribution: str = ""

    def summary(self) -> dict:
        return {"key": self.key, "name": self.name, "url": self.url, "status": self.status,
                "rows": len(self.rows), "fetched_at": self.fetched_at, "source_updated": self.source_updated,
                "http": self.http, "error": self.error, "notes": self.notes, "licence": self.licence,
                "attribution": self.attribution}


class Context:
    """Run settings shared by the adapters."""

    def __init__(self, today: dt.date | None = None, weeks: int = 12, offline: bool = False,
                 wahis_max_fetch: int = 450, delay: float = 0.6):
        self.today = today or dt.date.today()
        self.weeks = weeks
        self.offline = offline
        self.wahis_max_fetch = wahis_max_fetch
        self.delay = delay
        monday = self.today - dt.timedelta(days=self.today.weekday())
        self.window_start = monday - dt.timedelta(weeks=weeks - 1)   # Monday of the first week shown
        self.window_end = self.today
        self.session = make_session()

    def week_starts(self):
        return [self.window_start + dt.timedelta(weeks=i) for i in range(self.weeks)]


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=2, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["GET", "POST"]), respect_retry_after_header=True)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": UA})
    return s


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------- dates ----------
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}


def iso_date(v) -> str:
    """Any common date form to YYYY-MM-DD, or "" when it cannot be read."""
    if v in (None, ""):
        return ""
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    s = str(v).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return _safe(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{2,4})$", s)   # 21.10.2026, 21/10/26 (day first)
    if m:
        y = int(m.group(3))
        y = y + 2000 if y < 100 else y
        return _safe(y, int(m.group(2)), int(m.group(1)))
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", s)   # 21 October 2026
    if m and m.group(2).lower() in MONTHS:
        return _safe(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    return ""


def _safe(y, mth, d):
    try:
        return dt.date(y, mth, d).isoformat()
    except ValueError:
        return ""


def iso_week(d: str) -> str:
    if not d:
        return ""
    y, w, _ = dt.date.fromisoformat(d).isocalendar()
    return "%d-W%02d" % (y, w)


def week_monday(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return (x - dt.timedelta(days=x.weekday())).isoformat()


# ---------- files ----------
def save_text(folder: str, name: str, text: str | bytes) -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    mode = "wb" if isinstance(text, bytes) else "w"
    with open(path, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as f:
        f.write(text)
    return path


def save_json(folder: str, name: str, obj) -> str:
    return save_text(folder, name, json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False))


def load_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def sample_path(name: str) -> str:
    return os.path.join(SAMPLES, name)


def polite_sleep(ctx: Context, seconds: float | None = None):
    time.sleep(ctx.delay if seconds is None else seconds)


def to_int(v):
    """'1,290 (+1)' -> 1290. Returns None when there is no number."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"\d[\d,]*", str(v))
    return int(m.group(0).replace(",", "")) if m else None


WORD_NUMBERS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
for _i, _t in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), 2):
    WORD_NUMBERS[_t] = _i * 10


def words_to_int(s: str):
    """'Forty-two' or 'forty two' -> 42, '17' -> 17, 'a'/'one' -> 1."""
    s = s.strip().lower().replace("-", " ")
    if re.fullmatch(r"\d[\d,]*", s):
        return int(s.replace(",", ""))
    if s in ("a", "an"):
        return 1
    total = 0
    for part in s.split():
        if part not in WORD_NUMBERS:
            return None
        total += WORD_NUMBERS[part]
    return total


_DOMESTIC = re.compile(r"^(cattle|sheep|goats?|sheep/goats.*|swine|pigs?|domestic pigs|dogs?|cats?|equidae|horses?|"
                       r"donkeys?|camels?|buffaloe?s|birds|poultry|chickens?|ducks?|turkeys?|geese|alpacas?|llamas?|"
                       r"captive birds|bison)$", re.I)
_WILD = re.compile(r"wild|fox|jackal|wolf|bat|raccoon|badger|deer|boar|swan|goose|gull|eagle|wigeon|teal|mallard|"
                   r"jay|crow|magpie|pigeon|dove|hawk|falcon|owl|buzzard|heron|stork|crane|pelican|cormorant|"
                   r"skunk|otter|seal|marten|polecat|hedgehog|squirrel|antelope|kudu|impala|buffalo \(cape\)", re.I)


def infer_population(species) -> str:
    """'domestic', 'wild' or 'mixed' from species names, or '' when unclear."""
    kinds = set()
    for s in species or []:
        s = s.strip()
        if not s:
            continue
        if _DOMESTIC.match(s):
            kinds.add("domestic")
        elif _WILD.search(s):
            kinds.add("wild")
        else:
            return ""
    if kinds == {"domestic"}:
        return "domestic"
    if kinds == {"wild"}:
        return "wild"
    return "mixed" if kinds else ""
