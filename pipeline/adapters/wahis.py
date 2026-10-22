"""
wahis.py: WOAH WAHIS immediate notifications and follow-up reports.

Reads the same public JSON the WAHIS home page uses (the alert Worker's request shape):
  POST https://wahis.woah.org/api/v1/pi/event/filtered-list   one row per event, newest report first
  GET  https://wahis.woah.org/api/v1/pi/review/report/<id>/all-information   one report

The list is paged back to the start of the window. For each in-scope event the latest report is
fetched once and cached by report id (a validated report does not change), so a weekly run only
fetches events that have a new report. The latest report holds the event's full outbreak list,
cumulative case totals and status.

Premises rule: WAHIS publishes a point for each outbreak. The point is used only to find the
region that contains it. It is never written to an output, and records are placed at the region's
centre or the country's centre.
"""
from __future__ import annotations
import collections, datetime as dt, os

from adapters.common import (CACHE, SAMPLES, SourceResult, row, now_utc, iso_date, iso_week, load_json, save_json,
                             polite_sleep, to_int)
import categories, geo

NAME = "WOAH WAHIS"
LIST_URL = "https://wahis.woah.org/api/v1/pi/event/filtered-list?language=en"
REPORT_URL = "https://wahis.woah.org/api/v1/pi/review/report/%s/all-information?language=en"
EVENT_URL = "https://wahis.woah.org/#/in-event/%s/dashboard"
LICENCE = ("WAHIS Terms of Use and Conditions: viewing, downloading, storing, reproducing, adapting and translating "
           "the data are permitted with acknowledgement of WOAH as the source and the WOAH disclaimer.")
DISCLAIMER = ("The World Organisation for Animal Health (WOAH) bears no responsibility for the integrity or accuracy of "
              "the data contained herein, in particular due, but not limited to, any deletion, manipulation, or "
              "reformatting of data that may have occurred beyond its control.")
BODY = {"animalTypes": [], "countries": [], "eventIds": [], "eventStartDate": None, "eventStatuses": [],
        "firstDiseases": [], "reasons": [], "reportIds": [], "reportStatuses": [], "reportTypes": [],
        "secondDiseases": [], "sortColumn": "submissionDate", "sortOrder": "desc", "submissionDate": None,
        "typeStatuses": [], "pageNumber": 0, "pageSize": 100}
REPORT_CACHE = os.path.join(CACHE, "wahis", "reports")
LIST_SAMPLE = os.path.join(SAMPLES, "wahis_list.json")
STATUS = {"ongoing": "ongoing", "on-going": "ongoing", "resolved": "resolved", "stable": "ongoing",
          "closed": "resolved"}


def _list(ctx, res):
    """Page the event list back to the window start. Returns the rows and where they came from."""
    rows, page = [], 0
    while page < 20:
        body = dict(BODY, pageNumber=page)
        r = ctx.session.post(LIST_URL, json=body, timeout=60,
                             headers={"Accept": "application/json", "Content-Type": "application/json"})
        res.http = r.status_code
        r.raise_for_status()
        data = r.json()
        got = data.get("list") or []
        rows += got
        if not got or (got[-1].get("submissionDate") or "")[:10] < ctx.window_start.isoformat():
            break
        page += 1
        polite_sleep(ctx)
    return rows


def _report(ctx, rid, budget):
    path = os.path.join(REPORT_CACHE, "%s.json" % rid)
    cached = load_json(path)
    if cached:
        return cached, "cache"
    if ctx.offline or budget["left"] <= 0:
        return None, "skipped"
    budget["left"] -= 1
    r = ctx.session.get(REPORT_URL % rid, timeout=60, headers={"Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    if (data.get("report") or {}).get("reportStatus", {}).get("keyValue") == "Validated":
        save_json(REPORT_CACHE, "%s.json" % rid, data)
    polite_sleep(ctx)
    return data, "live"


def _place(iso3, outbreak):
    """Region for one outbreak: from its point if given, else its admin division name, else the country."""
    p = geo.admin1_by_point(outbreak.get("latitude"), outbreak.get("longitude"), iso3)
    if not p:
        p = geo.admin1_by_name(iso3, outbreak.get("adminDivision") or "")
    return p or geo.country_level(iso3)


def _pop(quant, disease):
    flags = {q.get("isWild") for q in quant if q.get("isWild") is not None}
    if flags == {True}:
        return "wild"
    if flags == {False}:
        return "domestic"
    if flags == {True, False}:
        return "mixed"
    d = (disease or "").lower()
    if "(poultry)" in d:
        return "domestic"
    return ""


def fetch(ctx) -> "SourceResult":
    res = SourceResult("wahis", NAME, "https://wahis.woah.org/", licence=LICENCE,
                       attribution="Source: World Organisation for Animal Health (WOAH), WAHIS. " + DISCLAIMER)
    res.fetched_at = now_utc()
    try:
        if ctx.offline:
            raise RuntimeError("offline run")
        listing = _list(ctx, res)
        res.status = "live"
        save_json(SAMPLES, "wahis_list.json", {"captured_at": res.fetched_at, "list": listing})
    except Exception as e:   # fall back to the last good list
        saved = load_json(LIST_SAMPLE)
        if not saved:
            res.status, res.error = "failed", "list request failed: %s" % e
            return res
        listing = saved["list"]
        res.status, res.error = "fallback", "list request failed (%s); used the list saved %s" % (e, saved["captured_at"])

    start = ctx.window_start.isoformat()
    scoped = []
    for r in listing:
        if (r.get("submissionDate") or "")[:10] < start:
            continue
        cat = categories.categorise(r.get("disease"))
        if cat and not r.get("isAquatic"):
            scoped.append((cat, r))
    res.notes.append("%d events in the list since %s, %d in the eight categories" % (
        sum(1 for r in listing if (r.get("submissionDate") or "")[:10] >= start), start, len(scoped)))

    budget = {"left": ctx.wahis_max_fetch}
    got = collections.Counter()
    weekly = collections.defaultdict(lambda: collections.Counter())   # (cat, iso3) -> week -> outbreaks
    map_units, points = [], []
    latest_update = ""
    for cat, lr in scoped:
        eid, rid = lr["eventId"], lr["reportId"]
        try:
            rep, how = _report(ctx, rid, budget)
        except Exception as e:
            rep, how = None, "error"
            res.notes.append("report %s for event %s failed: %s" % (rid, eid, e))
        got[how] += 1
        ev = (rep or {}).get("event") or {}
        rp = (rep or {}).get("report") or {}
        c = (ev.get("country") or {})
        iso3 = c.get("isoCode") or ""
        cinfo = geo.country(iso3) or geo.country(lr.get("country") or "")
        if cinfo:
            iso3 = cinfo[0]
        disease_full = ((ev.get("disease") or {}).get("name") or lr.get("disease") or "").strip()
        sub = ((ev.get("subType") or {}).get("disease") or {}).get("name") or lr.get("subType") or ""
        if sub in ("None", "Pending", "Untyped or partially typed"):
            sub = "" if sub == "None" else sub.lower()
        status_txt = ((ev.get("eventStatus") or {}).get("keyValue") or lr.get("eventStatus") or "").lower()
        reported = rp.get("reportedOn") or lr.get("submissionDate") or ""
        latest_update = max(latest_update, reported)
        outbreaks = (rep or {}).get("outbreaks") or []
        quant = ((rep or {}).get("quantitativeData") or {}).get("totals") or []
        places = []
        for ob in outbreaks:
            pl = _place(iso3, ob)
            d = iso_date(ob.get("startDate")) or iso_date(reported)
            places.append((pl, d))
            if d >= start:
                weekly[(cat, iso3)][iso_week(d)] += 1
            if ob.get("latitude") is not None and ob.get("longitude") is not None:
                # kept in memory only, to match EMPRES-i and GOV.UK records to this event; never written out
                points.append({"event_id": "wahis-%s" % eid, "iso3": iso3, "category": cat, "date": d,
                               "lat": ob["latitude"], "lon": ob["longitude"],
                               "ref": (ob.get("nationalReference") or "").strip()})
        # one map unit per region and week, counting outbreaks that started in the window
        units = collections.defaultdict(lambda: {"count": 0, "date": ""})
        for pl, d in places:
            if d and d >= start:
                k = (pl["admin1"], pl["admin2"], pl["level"], pl["lat"], pl["lon"], iso_week(d))
                units[k]["count"] += 1
                units[k]["date"] = max(units[k]["date"], d)
        for (a1, a2, lvl, la, lo, wk), u in units.items():
            map_units.append({"event_id": "wahis-%s" % eid, "category": cat, "country_iso3": iso3, "admin1": a1,
                              "admin2": a2, "place_level": lvl, "lat": la, "lon": lo, "week": wk, "date": u["date"],
                              "count": u["count"], "unit": "outbreak"})
        # the event row: one place if every outbreak is in the same region, otherwise the country
        distinct = {(p["admin1"], p["admin2"], p["level"]) for p, _ in places}
        if len(distinct) == 1:
            pl = places[0][0]
        else:
            pl = geo.country_level(iso3)
        by_region = collections.Counter(p["admin2"] or p["admin1"] or "unplaced" for p, _ in places)
        published = sorted({(ob.get("adminDivision") or "").strip() for ob in outbreaks} - {""})
        pub = "; ".join(published[:12]) + ("; and %d more" % (len(published) - 12) if len(published) > 12 else "")
        cases = [q.get("cases") for q in quant if q.get("cases") is not None]
        deaths = [q.get("deaths") for q in quant if q.get("deaths") is not None]
        species = sorted({(q.get("speciesName") or "").strip() for q in quant} - {""})
        notes = []
        if rp:
            notes.append("Latest report: %s number %s, submitted %s." % (
                "immediate notification" if (rp.get("reportNumber") or 0) == 0 else "follow-up report",
                rp.get("reportNumber"), iso_date(rp.get("reportedOn"))))
        reason = ((ev.get("reason") or {}).get("translation") or lr.get("reason") or "").strip()
        if reason:
            notes.append("Reason: %s." % reason)
        if len(distinct) > 1:
            notes.append("Outbreaks by region: " + "; ".join("%s %d" % kv for kv in by_region.most_common(15)) + ".")
        if outbreaks:
            notes.append("WAHIS gives a point for each outbreak. OutbreakLens does not publish it and shows the region.")
        if not rep:
            notes.append("Report detail not fetched in this run, so places and counts are missing.")
        res.rows.append(row(
            event_id="wahis-%s" % eid, record_type="event", source=NAME, source_url=EVENT_URL % eid,
            source_updated=reported, fetched_at=res.fetched_at, category=cat,
            disease=categories.short_disease(disease_full), serotype_or_strain=sub,
            country_iso3=iso3, country_name=geo.country_name(iso3) if iso3 else (lr.get("country") or ""),
            admin1=pl["admin1"], admin2=pl["admin2"], place_as_published=pub, place_level=pl["level"],
            lat=pl["lat"], lon=pl["lon"], species="; ".join(species), population_type=_pop(quant, disease_full),
            date_start=iso_date(ev.get("startedOn") or lr.get("eventStartDate")), date_confirmed=iso_date(ev.get("confirmOn")),
            date_reported=iso_date(reported), outbreaks=len(outbreaks) if rep else "",
            cases=sum(cases) if cases else "", deaths=sum(deaths) if deaths else "",
            status=STATUS.get(status_txt, "unknown"), notes=" ".join(notes)))

    res.notes.append("report detail: %d from cache, %d fetched, %d skipped (fetch budget), %d failed" % (
        got["cache"], got["live"], got["skipped"], got["error"]))
    res.source_updated = latest_update
    weeks = [iso_week(d.isoformat()) for d in ctx.week_starts()]
    series = {}
    for (cat, iso3), wk in weekly.items():
        s = series.setdefault(cat, {"total": [0] * len(weeks), "by_country": {}})
        vals = [wk.get(w, 0) for w in weeks]
        if any(vals):
            s["by_country"][iso3] = vals
            s["total"] = [a + b for a, b in zip(s["total"], vals)]
    res.series.append({"id": "wahis-outbreaks", "source": NAME, "source_url": "https://wahis.woah.org/",
                       "metric": "Outbreaks by start date, from WOAH immediate notifications and follow-up reports",
                       "unit": "outbreaks", "date_basis": "outbreak start date", "geography": "world",
                       "fetched_at": res.fetched_at, "source_updated": latest_update, "weeks": weeks,
                       "by_category": series,
                       "caveat": "Recent weeks fill in as countries report. An event's outbreaks are counted once, "
                                 "from its latest report."})
    # headline: in-scope events with a new report in the last 7 days
    week_ago = (ctx.today - dt.timedelta(days=7)).isoformat()
    recent = [r for c, r in scoped if iso_date(r.get("submissionDate")) > week_ago]
    res.headlines.append({"id": "wahis-recent", "label": "WOAH events with a new report in the last 7 days",
                          "value": len(recent), "unit": "events",
                          "detail": "%d were new immediate notifications" % sum(1 for r in recent if r.get("reportType") == "IN"),
                          "countries": len({r.get("country") for r in recent}),
                          "as_of": iso_date(latest_update), "source": NAME, "source_url": "https://wahis.woah.org/",
                          "fetched_at": res.fetched_at})
    res.extras["map_units"] = map_units
    res.extras["outbreak_points"] = points
    return res
