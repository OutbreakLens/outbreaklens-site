"""
fi_ruokavirasto_asf.py: Finland, Finnish Food Authority (Ruokavirasto), ASF cases in wild boar.

https://www.ruokavirasto.fi/en/animals/animal-health-and-diseases/animal-diseases/pigs/african-swine-fever-asf/asf-in-finland-2026/asf-cases-in-finland/
has a table: case number, number of animals ("Occasion" in English, "Kpl" in Finnish), date of
confirmation and municipality, with a total row.

One row is written per case. The municipality is kept as published. The record is placed at the
centre of its region (maakunta), so the map stays at region level.
"""
from __future__ import annotations
import collections, re

from bs4 import BeautifulSoup

import os

from adapters.common import SAMPLES, SourceResult, row, now_utc, iso_date, iso_week, to_int, save_json, load_json
import geo

NAME = "Ruokavirasto (Finnish Food Authority)"
URL = ("https://www.ruokavirasto.fi/en/animals/animal-health-and-diseases/animal-diseases/pigs/african-swine-fever-asf/"
       "asf-in-finland-2026/asf-cases-in-finland/")
LICENCE = ("Ruokavirasto: materials may be used and linked to with the source named. Use for commercial purposes "
           "must be agreed separately with the Finnish Food Authority.")


def parse(text):
    soup = BeautifulSoup(text, "lxml")
    title = (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
    mod = re.search(r"Page last updated\s*(\d{1,2})/(\d{1,2})/(\d{4})", soup.get_text(" ", strip=True))
    updated = "%s-%02d-%02d" % (mod.group(3), int(mod.group(1)), int(mod.group(2))) if mod else ""
    rows, total = [], None
    for tbl in soup.find_all("table"):
        head = [c.get_text(" ", strip=True).lower() for c in tbl.find_all("tr")[0].find_all(["th", "td"])]
        if not head or not any("municipality" in h or "kunta" in h for h in head):
            continue
        for tr in tbl.find_all("tr")[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if not cells:
                continue
            if cells[0].lower().startswith(("total", "yhteens")):
                total = to_int(cells[1])
                continue
            if len(cells) >= 4 and to_int(cells[0]) is not None:
                rows.append({"case": to_int(cells[0]), "animals": to_int(cells[1]) or 1, "date": iso_date(cells[2]),
                             "municipality": cells[3].strip()})
    if not rows:
        raise ValueError("case table not found")
    return {"title": title, "updated": updated, "rows": rows, "total": total}


def fetch(ctx) -> SourceResult:
    res = SourceResult("fi_ruokavirasto", NAME, URL, licence=LICENCE,
                       attribution="Source: Finnish Food Authority (Ruokavirasto).")
    res.fetched_at = now_utc()
    try:
        if ctx.offline:
            raise RuntimeError("offline run")
        r = ctx.session.get(URL, timeout=45)
        res.http = r.status_code
        r.raise_for_status()
        data = parse(r.text)
        res.status = "live"
        save_json(SAMPLES, "fi_ruokavirasto_asf.json", dict(data, captured_at=res.fetched_at))   # last good table
    except Exception as e:
        data = load_json(os.path.join(SAMPLES, "fi_ruokavirasto_asf.json"))
        if not data:
            res.status, res.error = "failed", str(e)
            return res
        res.status, res.error = "fallback", "request failed (%s); used the table saved %s" % (e, data.get("captured_at", "")[:10])
    res.source_updated = data["updated"]
    weekly = collections.Counter()
    unplaced = set()
    for c in data["rows"]:
        pl = geo.local_area("FIN", c["municipality"])
        if not pl:
            unplaced.add(c["municipality"])
            pl = geo.country_level("FIN")
        res.rows.append(row(
            event_id="fi-ruokavirasto-asf-2026-case-%03d" % c["case"], record_type="case", source=NAME, source_url=URL,
            source_updated=data["updated"], fetched_at=res.fetched_at, category="asf", disease="African swine fever",
            country_iso3="FIN", country_name="Finland", admin1=pl["admin1"], admin2=c["municipality"],
            place_as_published=c["municipality"], place_level=pl["level"], lat=pl["lat"], lon=pl["lon"],
            species="Wild boar", population_type="wild", date_confirmed=c["date"], date_reported=c["date"],
            outbreaks=1, cases=c["animals"], status="unknown",
            notes="Case %d. Municipality as published; placed at the centre of %s." % (c["case"], pl["admin1"] or "Finland")))
        if c["date"]:
            weekly[iso_week(c["date"])] += c["animals"]
    if unplaced:
        res.notes.append("municipalities not in geo/local_areas.csv, placed at country level: %s" % ", ".join(sorted(unplaced)))
    latest = max(data["rows"], key=lambda c: (c["date"], c["case"]))
    animals = sum(c["animals"] for c in data["rows"])
    if data["total"] is not None and data["total"] != animals:
        res.notes.append("table total %s differs from the sum of rows %s" % (data["total"], animals))
    res.headlines.append({"id": "fi-asf-wild-boar", "label": "African swine fever in wild boar in Finland, 2026",
                          "value": data["total"] if data["total"] is not None else animals, "unit": "wild boar",
                          "detail": "%d cases. Latest confirmed %s in %s." % (len(data["rows"]), latest["date"], latest["municipality"]),
                          "cases": len(data["rows"]), "latest_date": latest["date"], "latest_municipality": latest["municipality"],
                          "municipalities": sorted({c["municipality"] for c in data["rows"]}),
                          "as_of": data["updated"], "source": NAME, "source_url": URL, "fetched_at": res.fetched_at})
    weeks = [iso_week(d.isoformat()) for d in ctx.week_starts()]
    res.series.append({"id": "fi-asf-wild-boar", "source": NAME, "source_url": URL, "unit": "wild boar",
                       "metric": "Wild boar confirmed with ASF in Finland each week", "date_basis": "date of confirmation",
                       "geography": "Finland", "fetched_at": res.fetched_at, "source_updated": data["updated"],
                       "weeks": weeks, "by_category": {"asf": {"total": [weekly.get(w, 0) for w in weeks],
                                                               "by_country": {"FIN": [weekly.get(w, 0) for w in weeks]}}},
                       "caveat": ""})
    return res
