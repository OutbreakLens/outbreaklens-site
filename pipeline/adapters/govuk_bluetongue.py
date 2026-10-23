"""
govuk_bluetongue.py: GOV.UK, Bluetongue: latest situation (Defra and APHA).

Reads the page through the GOV.UK Content API, which returns the page body as HTML with its
change history:  https://www.gov.uk/api/content/guidance/bluetongue-latest-situation

It writes:
  - one row per nation with the season's confirmed cases (premises), to the date the counts run to
  - one row per county (England and Scotland) or local authority (Wales) from the summary tables
  - a weekly series of new cases parsed from the page's daily update notes
  - headline figures: totals, cases under investigation, risk level and zone status

GOV.UK counts premises ("a case is a premises on which bluetongue has been confirmed"), so the
counts go in the outbreaks column and are labelled as cases (premises) on the site.
Each run stores a parsed snapshot under snapshots/govuk-bluetongue/ so county counts can be
compared over time.
"""
from __future__ import annotations
import collections, datetime as dt, html, os, re

from bs4 import BeautifulSoup

from adapters.common import (SNAPSHOTS, SourceResult, row, now_utc, iso_date, iso_week, to_int, words_to_int,
                             save_json, load_json, MONTHS)
import geo

NAME = "GOV.UK (Defra and APHA)"
PAGE = "https://www.gov.uk/guidance/bluetongue-latest-situation"
API = "https://www.gov.uk/api/content/guidance/bluetongue-latest-situation"
LICENCE = "Open Government Licence v3.0"
SNAP = os.path.join(SNAPSHOTS, "govuk-bluetongue")
NATIONS = ("England", "Wales", "Scotland", "Northern Ireland")


def _text(node):
    return re.sub(r"\s+", " ", html.unescape(node.get_text(" ", strip=True))).replace("( ", "(").replace(" )", ")")


def _get(ctx, res):
    r = ctx.session.get(API, timeout=45, headers={"Accept": "application/json"})
    res.http = r.status_code
    r.raise_for_status()
    j = r.json()
    if j.get("schema_name") == "redirect":
        raise ValueError("page is now a redirect")
    return j


def _tables(soup):
    """County tables in the 'Summary of confirmed cases' section, keyed by the h4 above them."""
    out, nation = {}, None
    sec = soup.find(id="summary-of-confirmed-cases")
    node = sec
    period = ""
    while node is not None:
        node = node.find_next_sibling()
        if node is None or node.name == "h2":
            break
        if node.name == "h3":
            nation = None   # "Species involved", "Method of detection" and similar sections end the county tables
        elif node.name == "h4":
            nation = _text(node)
        elif node.name == "p" and nation and re.search(r"\d{4}", _text(node)) and not period:
            period = _text(node)
        elif node.name == "table" and nation in NATIONS:
            rows = []
            for tr in node.find_all("tr")[1:]:
                cells = [_text(td) for td in tr.find_all(["td", "th"])]
                if len(cells) >= 2 and cells[0] and not cells[0].lower().startswith("total"):
                    m = re.search(r"\(([+-]\d+)\)", cells[1])
                    rows.append((cells[0], to_int(cells[1]), int(m.group(1)) if m else 0))
            out[nation] = rows
    return out, period


def _period(period_text, fallback_year):
    """'10 July to midnight 21 October 2026' -> ('2026-07-10', '2026-10-21')."""
    m = re.search(r"(\d{1,2}) (\w+)(?: (\d{4}))? to (?:midnight )?(\d{1,2}) (\w+) (\d{4})", period_text or "")
    if not m:
        return "", ""
    y2 = int(m.group(6))
    y1 = int(m.group(3) or y2)
    try:
        a = dt.date(y1, MONTHS[m.group(2).lower()], int(m.group(1)))
        b = dt.date(y2, MONTHS[m.group(5).lower()], int(m.group(4)))
    except (KeyError, ValueError):
        return "", ""
    return a.isoformat(), b.isoformat()


# ---------- daily notes -> new cases per nation ----------
_NUM = r"\d[\d,]*|(?:[A-Za-z]+(?:[- ](?!new\b|cases?\b)[A-Za-z]+)?)"
_COUNT = re.compile(r"(?P<n>%s)\s+(?:new\s+)?cases?\b" % _NUM)
_ELLIPSIS = re.compile(r"(?P<n>\d[\d,]*|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:new\s+)?(?:cases?\s+)?"
                       r"(?:of [\w-]+\s+)?(?:confirmed\s+)?in\s+(?P<nation>England|Wales|Scotland|Northern Ireland)", re.I)
_NONE = re.compile(r"\b(?:no|none)\s+(?:new\s+)?cases?\b|\bnone in\b", re.I)
_NATION = re.compile(r"England|Wales|Scotland|Northern Ireland")
_DATE_FULL = re.compile(r"\bon (\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December)(?: (\d{4}))?", re.I)
_DATE_RANGE = re.compile(r"between (\d{1,2})(?: \w+)? and (\d{1,2}) (\w+) (\d{4})", re.I)


def parse_note(note, published):
    """Return (reference date, {nation: new cases}) for one change-history note, or None."""
    t = " ".join((note or "").split())
    if not t or not re.search(r"\bcases?\b", t, re.I):
        return None
    pub = dt.date.fromisoformat(published)
    ref = None
    m = _DATE_RANGE.search(t)
    if m and m.group(3).lower() in MONTHS:
        ref = dt.date(int(m.group(4)), MONTHS[m.group(3).lower()], int(m.group(2)))
    else:
        m = _DATE_FULL.search(t)
        if m:
            y = int(m.group(3) or pub.year)
            try:
                ref = dt.date(y, MONTHS[m.group(2).lower()], int(m.group(1)))
            except ValueError:
                ref = None
    if ref is None or not (pub - dt.timedelta(days=5) <= ref <= pub):
        ref = pub - dt.timedelta(days=1)
    counts = {}
    hits = []   # (position, count, nation or None)
    for m in _COUNT.finditer(t):
        n = words_to_int(m.group("n"))
        if n is None or m.group("n").lower() in ("a", "an", "the", "of", "these", "all", "potential"):
            continue
        hits.append((m.start(), n, None))
    for m in _NONE.finditer(t):
        hits.append((m.start(), 0, None))
    for m in _ELLIPSIS.finditer(t):
        n = words_to_int(m.group("n"))
        if n is not None and not any(abs(h[0] - m.start()) < 3 for h in hits):
            hits.append((m.start(), n, m.group("nation")))
    hits.sort()
    nations = [(m.start(), m.group(0)) for m in _NATION.finditer(t)]
    for i, (pos, n, nation) in enumerate(hits):
        if nation is None:
            nxt = hits[i + 1][0] if i + 1 < len(hits) else len(t)
            after = [nm for p, nm in nations if pos < p < nxt]
            if not after:
                continue
            nation = after[0]
        if nation not in counts:
            counts[nation] = n
    if not counts:
        return None
    return ref.isoformat(), counts


def daily_series(history, start_date):
    seen, out = set(), []
    pubs = collections.defaultdict(list)
    for h in sorted(history, key=lambda h: h.get("public_timestamp") or ""):
        ts = h.get("public_timestamp") or ""
        pub = _uk_date(ts)
        p = parse_note(h.get("note"), pub)
        if not p:
            continue
        ref, counts = p
        key = (ref, tuple(sorted(counts.items())))
        same_day = (pub, tuple(sorted(counts.items())))
        if key in seen or (re.match(r"\s*updated\b", h.get("note") or "", re.I) and same_day in pubs[pub]):
            continue   # a repeated note, or an "Updated ..." restatement on the same day
        seen.add(key)
        pubs[pub].append(same_day)
        out.append({"date": ref, "published": pub, "counts": counts})
    return [o for o in out if o["date"] >= start_date]


def _uk_date(ts):
    """GOV.UK timestamps are UTC. Shift by an hour in British Summer Time before taking the date."""
    if not ts:
        return ""
    d = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    y = d.year
    bst_start = max(dt.datetime(y, 3, 31 - i, 1, tzinfo=dt.timezone.utc) for i in range(7)
                    if dt.date(y, 3, 31 - i).weekday() == 6)
    bst_end = max(dt.datetime(y, 10, 31 - i, 1, tzinfo=dt.timezone.utc) for i in range(7)
                  if dt.date(y, 10, 31 - i).weekday() == 6)
    if bst_start <= d < bst_end:
        d = d + dt.timedelta(hours=1)
    return d.date().isoformat()


def fetch(ctx) -> SourceResult:
    res = SourceResult("govuk_bluetongue", NAME, PAGE, licence=LICENCE,
                       attribution="Contains public sector information licensed under the Open Government Licence v3.0. "
                                   "Source: GOV.UK, Bluetongue: latest situation.")
    res.fetched_at = now_utc()
    try:
        if ctx.offline:
            raise RuntimeError("offline run")
        j = _get(ctx, res)
        res.status = "live"
    except Exception as e:
        j = load_json(os.path.join(SNAP, "latest.raw.json"))
        if not j:
            res.status, res.error = "failed", str(e)
            return res
        res.status, res.error = "fallback", "request failed (%s); used the stored copy from %s" % (
            e, (j.get("public_updated_at") or "")[:10])

    updated = j.get("public_updated_at") or j.get("updated_at") or ""
    res.source_updated = updated
    body = (j.get("details") or {}).get("body") or ""
    soup = BeautifulSoup(body, "lxml")
    text = _text(soup)

    m = re.search(r"There have been ([\d,]+) cases of bluetongue serotype 3 \(BTV-3\) or unspecified serotype in the UK "
                  r"in the (\d{4}) to (\d{4}) bluetongue season", text)
    uk_total = to_int(m.group(1)) if m else None
    season = "%s to %s" % (m.group(2), m.group(3)) if m else ""
    nation_totals = {}
    for n in NATIONS:
        mm = re.search(r"([\d,]+) cases? in %s" % n, text)
        if mm:
            nation_totals[n] = to_int(mm.group(1))
    tables, period_text = _tables(soup)
    p_start, p_end = _period(period_text, ctx.today.year)
    inv = re.search(r"There are currently ([\d,]+) potential cases of bluetongue under investigation in Great Britain", text)
    risk_all = re.search(r"all routes\s*[–-]\s*is (\w+)", text)
    risk_air = re.search(r"airborne routes\s*[–-]\s*is (\w+)", text)
    zone = re.search(r"There are bluetongue restricted zones across the whole of ([^.]+)\.", text)
    btv8 = re.search(r"There have been no cases of bluetongue serotype 8", text)
    if not (uk_total and nation_totals):
        res.status, res.error = "failed", "page layout changed: totals not found"
        return res

    season_slug = (season[:4] + "-" + season[-2:]) if season else "season"
    common = dict(record_type="aggregate", source=NAME, source_url=PAGE, source_updated=updated,
                  fetched_at=res.fetched_at, category="bluetongue", disease="Bluetongue",
                  serotype_or_strain="BTV-3 or unspecified", country_iso3="GBR", country_name="United Kingdom",
                  species="Sheep; cattle; and other ruminants (see page)", population_type="domestic",
                  date_start=p_start, date_reported=p_end, status="ongoing")
    for n, v in nation_totals.items():
        pl = geo.local_area("GBR", n)
        res.rows.append(row(event_id="govuk-bt-%s-%s" % (season_slug, re.sub(r"\W+", "-", n.lower())),
                            admin1=n, place_as_published=n, place_level="admin1", lat=pl["lat"], lon=pl["lon"],
                            outbreaks=v, notes="Confirmed cases (premises) in %s in the %s season, to %s. A case is a "
                                               "premises where bluetongue was confirmed." % (n, season, p_end),
                            **common))
    unplaced = []
    for n, items in tables.items():
        for name, count, change in items:
            pl = geo.local_area("GBR", name)
            if not pl:
                unplaced.append(name)
                pl = geo.local_area("GBR", n)
                pl = dict(pl, admin2="", level="admin1")
            clean = re.sub(r"\s*\((?!Solihull)[^)]*\)\s*$", "", name).strip()
            res.rows.append(row(
                event_id="govuk-bt-%s-%s-%s" % (season_slug, re.sub(r"\W+", "-", n.lower()),
                                                re.sub(r"[^a-z0-9]+", "-", clean.lower()).strip("-")),
                admin1=n, admin2=pl["admin2"] and clean, place_as_published=name, place_level=pl["level"],
                lat=pl["lat"], lon=pl["lon"], outbreaks=count,
                notes=("Confirmed cases (premises), %s season to %s. Change since the last update: %+d." % (season, p_end, change))
                if change else "Confirmed cases (premises), %s season to %s." % (season, p_end),
                **common))
    if unplaced:
        res.notes.append("areas without a map centre, placed at the nation: %s" % ", ".join(unplaced))

    # weekly series from the daily notes
    daily = daily_series((j.get("details") or {}).get("change_history") or [], ctx.window_start.isoformat())
    weeks = [iso_week(d.isoformat()) for d in ctx.week_starts()]
    by_nation = {n: [0] * len(weeks) for n in ("England", "Wales", "Scotland")}
    for d in daily:
        w = iso_week(d["date"])
        if w in weeks:
            for n, v in d["counts"].items():
                if n in by_nation:
                    by_nation[n][weeks.index(w)] += v
    total = [sum(v) for v in zip(*by_nation.values())]
    parsed_since_start = sum(sum(d["counts"].values()) for d in daily)
    res.series.append({"id": "govuk-bt-cases", "source": NAME, "source_url": PAGE, "unit": "cases (premises)",
                       "metric": "New bluetongue cases (premises) confirmed each week in Great Britain",
                       "date_basis": "date of confirmation given in the GOV.UK update note",
                       "geography": "Great Britain", "fetched_at": res.fetched_at, "source_updated": updated,
                       "weeks": weeks, "by_category": {"bluetongue": {"total": total, "by_country": {"GBR": total},
                                                                      "by_area": by_nation}},
                       "caveat": "Parsed from the daily update notes on the page. A few notes give no date or "
                                 "repeat a day, so weekly figures may differ slightly from the official totals."})
    res.extras["daily"] = daily
    res.extras["nations"] = nation_totals
    res.extras["period"] = (p_start, p_end)
    res.notes.append("%d daily notes parsed since %s, adding up to %d new cases" % (
        len(daily), ctx.window_start.isoformat(), parsed_since_start))
    hl = {"id": "govuk-bt-total", "label": "Bluetongue cases (premises) confirmed in the UK this season",
          "value": uk_total, "unit": "cases (premises)",
          "detail": ", ".join("%s %s" % (n, "{:,}".format(v)) for n, v in nation_totals.items()),
          "by_area": nation_totals, "season": season, "counts_to": p_end, "as_of": iso_date(updated),
          "source": NAME, "source_url": PAGE, "fetched_at": res.fetched_at,
          "serotype": "BTV-3 or unspecified" + ("; no BTV-8 this season" if btv8 else "")}
    res.headlines.append(hl)
    if inv:
        res.headlines.append({"id": "govuk-bt-investigation", "label": "Potential bluetongue cases under investigation in Great Britain",
                              "value": to_int(inv.group(1)), "unit": "premises", "as_of": iso_date(updated),
                              "source": NAME, "source_url": PAGE, "fetched_at": res.fetched_at})
    res.headlines.append({"id": "govuk-bt-risk", "label": "Risk of bluetongue incursion",
                          "value": (risk_all.group(1) if risk_all else ""), "unit": "risk level",
                          "detail": "All routes %s. Airborne routes %s." % (
                              risk_all.group(1) if risk_all else "not stated", risk_air.group(1) if risk_air else "not stated"),
                          "zone": ("Restricted zone across the whole of %s." % zone.group(1)) if zone else "",
                          "as_of": iso_date(updated), "source": NAME, "source_url": PAGE, "fetched_at": res.fetched_at})
    save_json(SNAP, "%s.json" % iso_date(updated), {"updated": updated, "fetched_at": res.fetched_at, "season": season,
                                                    "counts_to": p_end, "uk_total": uk_total, "nations": nation_totals,
                                                    "areas": tables, "under_investigation": to_int(inv.group(1)) if inv else None})
    save_json(SNAP, "latest.raw.json", j)   # the last good page, for offline runs
    return res
