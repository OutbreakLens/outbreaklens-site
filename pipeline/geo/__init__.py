"""
geo: place records at country, region or county level.

Lookups use three small files built by geo/build_geo.py from Natural Earth (public domain):
countries.csv, admin1.csv and local_areas.csv. Point lookups (used only to find the region
that contains a source's point, never to plot the point) load the Natural Earth region
polygons from cache/geo/, downloading them once if needed.

Every centre returned here is rounded to 0.01 degrees and marks an area. Nothing in this
module returns or stores a premises location.
"""
from __future__ import annotations
import csv, json, os, re, unicodedata, urllib.request
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "cache", "geo")
NE_ADMIN1_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
                 "ne_10m_admin_1_states_provinces.geojson")
UK_NATIONS = ("England", "Scotland", "Wales", "Northern Ireland")


def norm(s: str) -> str:
    """Lower case, no accents, no punctuation, single spaces."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ").replace("’", "'")
    s = re.sub(r"[^a-z0-9']+", " ", s).replace("'", "")
    return re.sub(r"\s+", " ", s).strip()


# words that often trail a region name in one source but not another
_SUFFIX = re.compile(r"\b(province|provincia|region|oblast|voivodeship|wojewodztwo|county|prefecture|governorate|"
                     r"state|department|departement|district|municipality|krai|kraj|okrug|republic of|city of|"
                     r"autonomous community|comunidad autonoma)\b")


def loose(s: str) -> str:
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", norm(s))).strip()


def _read(name):
    with open(os.path.join(HERE, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(v):
    return float(v) if v not in (None, "") else None


@lru_cache(maxsize=1)
def countries():
    rows = _read("countries.csv")
    by_iso3 = {r["iso3"]: r for r in rows}
    by_name = {}
    for r in rows:
        for a in r["aliases"].split("|") + [r["name"]]:
            if a:
                by_name.setdefault(norm(a), r["iso3"])
    return by_iso3, by_name


def country(name_or_code: str):
    """Return (iso3, name, lat, lon) for a country name or ISO2/ISO3 code, or None."""
    if not name_or_code:
        return None
    by_iso3, by_name = countries()
    s = name_or_code.strip()
    iso3 = None
    if len(s) == 3 and s.upper() in by_iso3:
        iso3 = s.upper()
    elif len(s) == 2 and s.isalpha():
        iso3 = next((k for k, r in by_iso3.items() if r["iso2"] == s.upper()), None)
    if not iso3:
        iso3 = by_name.get(norm(s))
    if not iso3:   # WAHIS style "China (People's Rep. of)": try the part before the bracket
        base = norm(re.sub(r"\(.*?\)", "", s))
        iso3 = by_name.get(base)
    if not iso3:
        try:
            import pycountry
            iso3 = pycountry.countries.search_fuzzy(s)[0].alpha_3
        except Exception:
            iso3 = None
    if not iso3 or iso3 not in by_iso3:
        return None
    r = by_iso3[iso3]
    return iso3, r["name"], _f(r["lat"]), _f(r["lon"])


def country_name(iso3: str) -> str:
    r = countries()[0].get(iso3)
    return r["name"] if r else iso3


def valid_iso3(code: str) -> bool:
    if code in countries()[0]:
        return True
    try:
        import pycountry
        return pycountry.countries.get(alpha_3=code) is not None
    except Exception:
        return False


@lru_cache(maxsize=1)
def admin1_table():
    rows = _read("admin1.csv")
    exact, lo = {}, {}
    for r in rows:
        for n in r["names"].split("|") + [r["name"]]:
            if not n:
                continue
            exact.setdefault((r["iso3"], norm(n)), []).append(r)
            lo.setdefault((r["iso3"], loose(n)), []).append(r)
    return rows, exact, lo


def _rec(r, via):
    """A place record from an admin1.csv row. For the UK the Natural Earth unit is a county or
    council area, so it becomes admin2 and the nation becomes admin1."""
    lat, lon = _f(r["lat"]), _f(r["lon"])
    if r["iso3"] == "GBR" and r["unit"] in UK_NATIONS:
        return {"admin1": r["unit"], "admin2": r["name"], "level": "admin2", "lat": lat, "lon": lon, "via": via}
    return {"admin1": r["name"], "admin2": "", "level": "admin1", "lat": lat, "lon": lon, "via": via}


def admin1_by_name(iso3: str, name: str):
    """Match a published region name to a Natural Earth first-level unit in the same country."""
    if not name:
        return None
    _, exact, lo = admin1_table()
    hits = exact.get((iso3, norm(name))) or lo.get((iso3, loose(name)))
    if hits and len({h["adm1_code"] for h in hits}) == 1:
        return _rec(hits[0], "name")
    return None


# Published names that are not council areas themselves, and the council area used instead.
CANONICAL = {"isle of lewis": "Na h-Eileanan Siar", "western isles": "Na h-Eileanan Siar",
             "city of bristol": "Bristol", "county durham": "Durham"}


@lru_cache(maxsize=1)
def local_table():
    out = {}
    for r in _read("local_areas.csv"):
        out[(r["iso3"], norm(r["name"]))] = r
    return out


def local_area(iso3: str, name: str):
    """A county or council area as GOV.UK, DAFM or Ruokavirasto publish it."""
    clean = re.sub(r"\s*\((?!solihull)[^)]*\)\s*$", "", name or "", flags=re.I).strip()   # drop Welsh names in brackets
    r = local_table().get((iso3, norm(name))) or local_table().get((iso3, norm(clean)))
    if not r:
        return None
    lat, lon = _f(r["lat"]), _f(r["lon"])
    canon = CANONICAL.get(norm(r["name"]), r["name"])
    if iso3 == "GBR" and r["name"] in UK_NATIONS:
        return {"admin1": r["name"], "admin2": "", "level": "admin1", "lat": lat, "lon": lon, "via": "local"}
    if iso3 == "GBR":
        return {"admin1": r["admin1"], "admin2": canon, "level": "admin2", "lat": lat, "lon": lon, "via": "local"}
    if iso3 == "FIN":   # municipality published, placed at its region
        return {"admin1": r["admin1"], "admin2": r["name"], "level": "admin1", "lat": lat, "lon": lon, "via": "local"}
    return {"admin1": r["name"], "admin2": "", "level": "admin1", "lat": lat, "lon": lon, "via": "local"}


# ---------- point in region (used only to find the region; the point itself is never kept) ----------
_INDEX = {}


def _load_polygons():
    if "tree" in _INDEX:
        return _INDEX
    from shapely.geometry import shape
    from shapely.strtree import STRtree
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, os.path.basename(NE_ADMIN1_URL))
    if not os.path.exists(path):
        req = urllib.request.Request(NE_ADMIN1_URL, headers={"User-Agent": "OutbreakLensPipeline/2.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
            f.write(r.read())
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    by_code = {r["adm1_code"]: r for r in admin1_table()[0]}
    geoms, recs = [], []
    for feat in gj["features"]:
        code = feat["properties"].get("adm1_code")
        if code in by_code and feat.get("geometry"):
            geoms.append(shape(feat["geometry"]).buffer(0))
            recs.append(by_code[code])
    _INDEX.update(tree=STRtree(geoms), geoms=geoms, recs=recs)
    return _INDEX


def admin1_by_point(lat, lon, iso3=None):
    """Return the region containing a point, or the nearest region within about 10 km (coastal points)."""
    if lat is None or lon is None:
        return None
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    try:
        from shapely.geometry import Point
        idx = _load_polygons()
    except Exception:
        return None
    pt = Point(lon, lat)
    ok = (lambda i: True) if not iso3 else (lambda i: idx["recs"][i]["iso3"] in ALSO_REPORTED_BY.get(iso3, {iso3}))
    cands = [i for i in idx["tree"].query(pt) if idx["geoms"][i].contains(pt) and ok(i)]
    if not cands:   # coastal or border points: the nearest region of the same country within about 25 km
        near = [i for i in idx["tree"].query(pt.buffer(0.25)) if ok(i) and idx["geoms"][i].distance(pt) <= 0.25]
        near.sort(key=lambda i: idx["geoms"][i].distance(pt))
        cands = near[:1]
    if not cands:
        return None
    return _rec(idx["recs"][cands[0]], "point")


# Places a country reports for that Natural Earth treats as separate countries.
ALSO_REPORTED_BY = {"GBR": {"GBR", "IMN", "JEY", "GGY"}, "FRA": {"FRA", "MCO"}, "ESP": {"ESP", "GIB"},
                    "DNK": {"DNK", "FRO", "GRL"}, "NLD": {"NLD", "ABW", "CUW", "SXM"}, "NZL": {"NZL", "COK", "NIU"},
                    "CHN": {"CHN", "HKG", "MAC"}, "FIN": {"FIN", "ALA"}, "AUS": {"AUS", "NFK"}}


def country_level(iso3):
    c = country(iso3)
    if not c:
        return {"admin1": "", "admin2": "", "level": "country", "lat": None, "lon": None, "via": "none"}
    return {"admin1": "", "admin2": "", "level": "country", "lat": c[2], "lon": c[3], "via": "country"}
