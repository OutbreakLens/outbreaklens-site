"""
empres_i.py: FAO EMPRES-i+ animal disease events.

The EMPRES-i+ web app (empres-i.apps.fao.org) calls an API that needs a sign-in token, so it is
not used. FAO's data catalogue lists a public CSV for the same events under CC BY 4.0:

  Dataset  "EMPRES-i: Global Animal Disease Events Dashboard"
           https://data.apps.fao.org/catalog/dataset/4849cca2-a2bf-4f1a-8348-ea01a692ff30
  Resource "Latest Reported Events"
           https://europe-west1-fao-empresi.cloudfunctions.net/getLatestEventsByDate
           ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD   (filters on observation date)

Without the two parameters the endpoint returns an old 15,000-row block, so they are always sent.

Premises rule: each EMPRES-i event has a point and a locality name, often a village or a farm
area. OutbreakLens uses the point only to find the region that contains it and publishes the
region, never the point or the locality.
"""
from __future__ import annotations
import collections, csv, io, os

from adapters.common import CACHE, SourceResult, row, now_utc, iso_date, iso_week, save_text
import categories, geo

NAME = "FAO EMPRES-i"
ENDPOINT = "https://europe-west1-fao-empresi.cloudfunctions.net/getLatestEventsByDate"
DATASET = "https://data.apps.fao.org/catalog/dataset/4849cca2-a2bf-4f1a-8348-ea01a692ff30"
LICENCE = ("CC BY 4.0, as listed for the dataset 'EMPRES-i: Global Animal Disease Events Dashboard' in the FAO "
           "data catalogue. FAO's citation form: FAO. [year]. [dataset]. Accessed on [date]. [URL]. Licence: CC-BY-4.0.")
# The saved copy holds exact points, so it lives in cache/ (not committed), never in samples/.
SAMPLE = os.path.join(CACHE, "empres_i", "latest.csv")


def _pop(species: str) -> str:
    kinds = {s.split(" - ")[0].strip().lower() for s in species.split("|") if " - " in s}
    if kinds == {"domestic"}:
        return "domestic"
    if kinds == {"wild"}:
        return "wild"
    if kinds and kinds <= {"domestic", "wild", "captive"}:
        return "mixed" if len(kinds) > 1 else ("domestic" if kinds == {"captive"} else "")
    return ""


def _species(species: str) -> str:
    """'Wild - Wild boar:Sus scrofa(Suidae)' -> 'Wild boar'."""
    out = []
    for s in species.split("|"):
        s = s.strip()
        if not s:
            continue
        name = s.split(" - ", 1)[-1].split(":")[0].strip()
        if name and name not in out:
            out.append(name)
    return "; ".join(out)


def fetch(ctx) -> SourceResult:
    url = "%s?start_date=%s&end_date=%s" % (ENDPOINT, ctx.window_start.isoformat(), ctx.today.isoformat())
    res = SourceResult("empres_i", NAME, url, licence=LICENCE,
                       attribution="Source: FAO EMPRES-i, Global Animal Disease Events Dashboard (CC BY 4.0).")
    res.fetched_at = now_utc()
    text = None
    try:
        if ctx.offline:
            raise RuntimeError("offline run")
        r = ctx.session.get(url, timeout=120, headers={"Accept": "text/csv"})
        res.http = r.status_code
        r.raise_for_status()
        text = r.content.decode("utf-8-sig")
        if not text.startswith('"id_event"') and not text.startswith("id_event"):
            raise ValueError("unexpected response: %r" % text[:80])
        save_text(os.path.dirname(SAMPLE), "latest.csv", text)
        res.status = "live"
    except Exception as e:
        if os.path.exists(SAMPLE):
            with open(SAMPLE, encoding="utf-8") as f:
                text = f.read()
            res.status, res.error = "fallback", "request failed (%s); used the saved copy" % e
        else:
            res.status, res.error = "failed", str(e)
            return res

    rdr = list(csv.DictReader(io.StringIO(text)))
    start = ctx.window_start.isoformat()
    kept = skipped_cat = 0
    weekly = collections.defaultdict(collections.Counter)
    latest = ""
    unplaced = 0
    for r in rdr:
        cat = categories.categorise(r.get("disease"))
        if not cat:
            skipped_cat += 1
            continue
        c = geo.country(r.get("country") or "")
        if not c:
            unplaced += 1
            continue
        iso3 = c[0]
        obs, rep = iso_date(r.get("observation_date")), iso_date(r.get("report_date"))
        latest = max(latest, rep)
        pl = geo.admin1_by_point(r.get("latitude"), r.get("longitude"), iso3) or geo.country_level(iso3)
        sp = r.get("species") or ""
        notes = ["Diagnosis source: %s." % (r.get("diagnosis_source") or "not given"),
                 "EMPRES-i gives a point and a locality. OutbreakLens shows only the region that contains the point."]
        if (r.get("humans_affected") or "").strip() not in ("", "0"):
            notes.append("Humans affected: %s; human deaths: %s." % (r.get("humans_affected"), r.get("humans_deaths") or "0"))
        eid = (r.get("id_event") or "").strip()
        res.rows.append(row(
            event_id="empres-i-%s" % eid, record_type="event", source=NAME, source_url=url, source_updated=rep,
            fetched_at=res.fetched_at, category=cat, disease=r.get("disease") or "",
            serotype_or_strain=(r.get("serotype") or "").strip(), country_iso3=iso3, country_name=c[1],
            admin1=pl["admin1"], admin2=pl["admin2"], place_as_published="", place_level=pl["level"],
            lat=pl["lat"], lon=pl["lon"], species=_species(sp), population_type=_pop(sp), date_start=obs,
            date_confirmed="", date_reported=rep, outbreaks=1, cases="", deaths="",
            status="unknown", notes=" ".join(notes)))
        # kept in memory for matching to WAHIS outbreaks; never written out
        res.rows[-1]["_point"] = (r.get("latitude"), r.get("longitude"))
        res.rows[-1]["_diag_source"] = r.get("diagnosis_source") or ""
        if obs and obs >= start:
            weekly[(cat, iso3)][iso_week(obs)] += 1
        kept += 1
    res.source_updated = latest
    res.notes.append("%d events returned, %d in the eight categories, %d out of scope, %d without a country match" % (
        len(rdr), kept, skipped_cat, unplaced))
    weeks = [iso_week(d.isoformat()) for d in ctx.week_starts()]
    series = {}
    for (cat, iso3), wk in weekly.items():
        s = series.setdefault(cat, {"total": [0] * len(weeks), "by_country": {}})
        vals = [wk.get(w, 0) for w in weeks]
        s["by_country"][iso3] = vals
        s["total"] = [a + b for a, b in zip(s["total"], vals)]
    res.series.append({"id": "empres-i-events", "source": NAME, "source_url": url, "metric": "Events by observation date",
                       "unit": "events", "date_basis": "observation date", "geography": "world",
                       "fetched_at": res.fetched_at, "source_updated": latest, "weeks": weeks, "by_category": series,
                       "caveat": "Most EMPRES-i events come from WOAH reports, so they overlap the WAHIS series. "
                                 "Recent weeks fill in as reports arrive."})
    return res
