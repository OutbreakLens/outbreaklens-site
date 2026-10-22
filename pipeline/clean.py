"""
clean.py: validate, de-duplicate and link the rows from every adapter.

validate()   checks dates, ISO codes, categories, numbers and places, and blanks any published
             place text that looks like a premises (the premises rule)
dedupe()     keeps one row per event_id (the most recently fetched)
link()       fills same_as with the ids of rows in other sources that describe the same event,
             using the documented rules below. Rows are never merged, so every figure stays
             traceable to its own source.
hold()       editorial rule: UK records of pig diseases (African swine fever, foot-and-mouth
             disease, classical swine fever, Aujeszky's disease, swine vesicular disease) are
             kept out of the public files and written to cache/held/ for the editor to review
             by hand before anything is published.

Linking rules (each link is symmetric):
  R1 reference  GOV.UK bird flu case reference = WAHIS outbreak national reference
  R2 point      EMPRES-i event and WAHIS outbreak in the same country and category, start dates
                within 1 day, points within 5 km (points are used here only, never published)
  R3 week       ADIS weekly row and WAHIS event: same country, category and compatible
                population, with a WAHIS report on or after the start of the ADIS week
  R4 national   national-source rows (GOV.UK, DAFM, Ruokavirasto) and WAHIS events in the same
                country and category with outbreaks in the national source's area and period
  R5 national   national-source rows and ADIS rows in the same country and category, where the
                national date falls in or up to 14 days before the ADIS week, or the ADIS
                administrative divisions name the national row's county
"""
from __future__ import annotations
import collections, datetime as dt, math, re

from adapters.common import COLUMNS, PLACE_LEVELS, POPULATION_TYPES, STATUSES, RECORD_TYPES
import categories, geo

DATE_COLS = ("date_start", "date_confirmed", "date_reported")
NUM_COLS = ("outbreaks", "cases", "deaths")
NATIONAL = {"GOV.UK (Defra and APHA)", "DAFM (gov.ie)", "Ruokavirasto (Finnish Food Authority)"}
# words and codes that point to a premises, not an area
PREMISES = re.compile(r"\b(farm|farms|premises|holding|steading|ranch|estate|hof|ferme|granja|fazenda|ltd|limited|"
                      r"llp|plc|cph|ip ?\d+)\b|\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b", re.I)
SWINE_OTHER = re.compile(r"classical swine fever|aujeszky|swine vesicular", re.I)


def validate(rows, today: dt.date):
    issues = []
    out = []
    latest_ok = (today + dt.timedelta(days=1)).isoformat()
    for r in rows:
        rid = r.get("event_id") or "(no id)"
        if r.get("category") not in categories.SLUGS:
            issues.append((rid, "category %r not one of the eight; row dropped" % r.get("category")))
            continue
        if not r.get("country_iso3") or not geo.valid_iso3(r["country_iso3"]):
            issues.append((rid, "country code %r not valid; row dropped" % r.get("country_iso3")))
            continue
        for c in DATE_COLS:
            v = r.get(c) or ""
            if v and (not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) or not ("1990-01-01" <= v <= latest_ok)):
                issues.append((rid, "%s %r not a valid date; blanked" % (c, v)))
                r[c] = ""
        for c in NUM_COLS:
            v = r.get(c)
            if v in ("", None):
                r[c] = ""
                continue
            try:
                n = int(v)
                if n < 0:
                    raise ValueError
                r[c] = n
            except (TypeError, ValueError):
                issues.append((rid, "%s %r not a whole number; blanked" % (c, v)))
                r[c] = ""
        for c in ("lat", "lon"):
            v = r.get(c)
            if v in ("", None):
                r[c] = ""
                continue
            try:
                f = round(float(v), 2)
                if (c == "lat" and abs(f) > 90) or (c == "lon" and abs(f) > 180):
                    raise ValueError
                r[c] = f
            except (TypeError, ValueError):
                issues.append((rid, "%s %r out of range; blanked" % (c, v)))
                r[c] = ""
        if r.get("place_level") not in PLACE_LEVELS:
            issues.append((rid, "place_level %r unknown; set to country" % r.get("place_level")))
            r["place_level"] = "country"
        if r["lat"] == "" and r["place_level"] != "country":
            issues.append((rid, "no centre for %s; placed at country level" % (r.get("admin2") or r.get("admin1"))))
            c = geo.country(r["country_iso3"])
            r.update(place_level="country", lat=c[2] if c else "", lon=c[3] if c else "")
        if r.get("population_type") not in POPULATION_TYPES:
            r["population_type"] = ""
        if r.get("status") not in STATUSES:
            r["status"] = "unknown"
        if r.get("record_type") not in RECORD_TYPES:
            issues.append((rid, "record_type %r unknown" % r.get("record_type")))
        if r.get("place_as_published") and PREMISES.search(r["place_as_published"]):
            issues.append((rid, "place text looked like a premises and was removed: %r" % r["place_as_published"]))
            r["place_as_published"] = ""
        out.append(r)
    return out, issues


def dedupe(rows):
    by_id, dups = {}, 0
    for r in rows:
        k = r["event_id"]
        if k in by_id:
            dups += 1
            if (r.get("fetched_at") or "") < (by_id[k].get("fetched_at") or ""):
                continue
        by_id[k] = r
    return list(by_id.values()), dups


def _km(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _compatible(a, b):
    return not a or not b or a == b or "mixed" in (a, b)


def link(rows, wahis_points, adis_period=None):
    """Fill same_as. wahis_points: outbreak points kept in memory by the WAHIS adapter."""
    edges = collections.defaultdict(set)
    rule_counts = collections.Counter()

    def add(a, b, rule):
        if a != b and b not in edges[a]:
            edges[a].add(b)
            edges[b].add(a)
            rule_counts[rule] += 1

    by_src = collections.defaultdict(list)
    for r in rows:
        by_src[r["source"]].append(r)
    wahis_rows = {r["event_id"]: r for r in by_src.get("WOAH WAHIS", [])}
    pts = collections.defaultdict(list)
    refs = {}
    for p in wahis_points:
        if p["event_id"] not in wahis_rows:
            continue
        pts[(p["iso3"], p["category"])].append(p)
        if p.get("ref"):
            refs[re.sub(r"\W", "", p["ref"].upper())] = p["event_id"]

    # R1 reference
    for r in rows:
        ref = r.get("_ref")
        if ref and re.sub(r"\W", "", ref.upper()) in refs:
            add(r["event_id"], refs[re.sub(r"\W", "", ref.upper())], "R1 reference")
    # R2 point (EMPRES-i to WAHIS)
    for r in by_src.get("FAO EMPRES-i", []):
        try:
            la, lo = (float(x) for x in r.get("_point") or ("", ""))
        except ValueError:
            continue
        best = None
        for p in pts.get((r["country_iso3"], r["category"]), []):
            if not p["date"] or not r["date_start"]:
                continue
            dd = abs((dt.date.fromisoformat(p["date"]) - dt.date.fromisoformat(r["date_start"])).days)
            if dd > 1:
                continue
            d = _km(la, lo, float(p["lat"]), float(p["lon"]))
            if d <= 5 and (best is None or (dd, d) < best[0]):
                best = ((dd, d), p["event_id"])
        if best:
            add(r["event_id"], best[1], "R2 point")
    # R3 ADIS week to WAHIS event
    w_by = collections.defaultdict(list)
    for w in wahis_rows.values():
        w_by[(w["country_iso3"], w["category"])].append(w)
    for a in by_src.get("EU ADIS", []):
        for w in w_by.get((a["country_iso3"], a["category"]), []):
            if _compatible(a["population_type"], w["population_type"]) and (w["date_reported"] or "") >= a["date_start"]:
                add(a["event_id"], w["event_id"], "R3 week")
    # R4 national to WAHIS: the WAHIS event has outbreaks in the national source's area and period
    w_places = collections.defaultdict(set)   # event -> set of (admin1, admin2) of its outbreaks, from the points
    w_dates = collections.defaultdict(list)
    for p in wahis_points:
        w_dates[p["event_id"]].append(p["date"])
    for r in rows:
        if r["source"] not in NATIONAL:
            continue
        for w in w_by.get((r["country_iso3"], r["category"]), []):
            if not _compatible(r["population_type"], w["population_type"]):
                continue
            if r["source"] == "GOV.UK (Defra and APHA)" and r["category"] == "bird-flu":
                continue   # bird flu cases link only by case reference (R1)
            if r["country_iso3"] == "GBR" and w["admin1"] and w["admin1"] not in geo.UK_NATIONS:
                continue   # for example the Isle of Man, which GOV.UK does not count
            if r["record_type"] == "case":   # a single case: WAHIS outbreak dates within two weeks either side
                d = dt.date.fromisoformat(r["date_confirmed"] or r["date_reported"])
                start, end = (d - dt.timedelta(days=14)).isoformat(), (d + dt.timedelta(days=14)).isoformat()
            else:
                start = r["date_start"] or "0000"
                end = r["date_reported"] or "9999"
            if any(start <= d <= end for d in w_dates.get(w["event_id"], [])) or not w_dates.get(w["event_id"]):
                add(r["event_id"], w["event_id"], "R4 national")
    # R5 national to ADIS
    for a in by_src.get("EU ADIS", []):
        lo = (dt.date.fromisoformat(a["date_start"]) - dt.timedelta(days=14)).isoformat()
        hi = a["date_reported"] or a["date_start"]
        names = {geo.norm(x) for x in a.get("_adis_admin") or []}
        for r in rows:
            if r["source"] not in NATIONAL or (r["country_iso3"], r["category"]) != (a["country_iso3"], a["category"]):
                continue
            d = r["date_confirmed"] or r["date_reported"]
            if r["record_type"] == "aggregate":
                if names and geo.norm(r["place_as_published"]) in names:
                    add(r["event_id"], a["event_id"], "R5 national")
            elif d and lo <= d <= hi:
                add(r["event_id"], a["event_id"], "R5 national")
    for r in rows:
        ids = sorted(edges.get(r["event_id"], ()))
        r["same_as"] = "; ".join(ids[:20]) + ("; +%d more" % (len(ids) - 20) if len(ids) > 20 else "")
    return dict(rule_counts), edges


def hold(rows):
    keep, held = [], []
    for r in rows:
        swine = r["category"] in ("asf", "fmd") or (r["category"] == "other" and SWINE_OTHER.search(r.get("disease") or ""))
        if r["country_iso3"] == "GBR" and swine:
            held.append(r)
        else:
            keep.append(r)
    return keep, held


def public(r):
    """The row as published: schema columns only, internal keys dropped."""
    return {c: r.get(c, "") for c in COLUMNS}
