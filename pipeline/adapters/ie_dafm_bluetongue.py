"""
ie_dafm_bluetongue.py: Ireland, Department of Agriculture, Food and the Marine (DAFM), bluetongue.

https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/publications/bluetongue-virus/
has a table of herd cases by county (bovine, ovine, total) "as at" a date.

gov.ie's CloudFront returns HTTP 403 to the container this pipeline was built in. The adapter tries
the live page first. When that fails it uses samples/ie_dafm_bluetongue.json, a copy captured with
WebFetch, and marks the source as "fallback" with the capture date. On a network gov.ie accepts
(a home connection, a GitHub Actions runner), the live parser below runs instead. It was written
against the captured table, not the live HTML, so check its first live run.
"""
from __future__ import annotations
import os, re

from bs4 import BeautifulSoup

from adapters.common import SAMPLES, SourceResult, row, now_utc, iso_date, to_int, load_json
import geo

NAME = "DAFM (gov.ie)"
URL = "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/publications/bluetongue-virus/"
LICENCE = ("Irish public sector information, generally re-usable under the PSI Licence (CC BY 4.0). "
           "DAFM's own statement could not be read from the container: check it.")
SAMPLE = os.path.join(SAMPLES, "ie_dafm_bluetongue.json")


def parse_html(text):
    soup = BeautifulSoup(text, "lxml")
    full = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    for tbl in soup.find_all("table"):
        head = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tbl.find_all("tr")[0].find_all(["th", "td"])]
        if not head or "county" not in head[0].lower() or not any("total" in h.lower() for h in head):
            continue
        rows, totals = [], None
        for tr in tbl.find_all("tr")[1:]:
            cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
            if not cells:
                continue
            nums = [to_int(c) for c in cells[1:]]
            if cells[0].lower().startswith("total"):
                totals = nums
            else:
                rows.append([cells[0]] + nums)
        asat = re.search(r"as at (\d{1,2} \w+ \d{4})", full, re.I)
        upd = re.search(r"Last updated on:?\s*(\d{1,2} \w+ \d{4})", full, re.I)
        sero = re.search(r"serotype that has been detected in Ireland is (\d+)", full, re.I)
        return {"columns": head, "rows": rows, "totals": totals, "counts_as_at": iso_date(asat.group(1)) if asat else "",
                "last_updated": iso_date(upd.group(1)) if upd else "", "serotype": sero.group(1) if sero else ""}
    raise ValueError("county table not found")


def fetch(ctx) -> SourceResult:
    res = SourceResult("ie_dafm", NAME, URL, licence=LICENCE,
                       attribution="Contains Irish Public Sector Information (DAFM, gov.ie).")
    res.fetched_at = now_utc()
    data = None
    try:
        if ctx.offline:
            raise RuntimeError("offline run")
        r = ctx.session.get(URL, timeout=45)
        res.http = r.status_code
        r.raise_for_status()
        data = parse_html(r.text)
        res.status = "live"
    except Exception as e:
        data = load_json(SAMPLE)
        if not data:
            res.status, res.error = "failed", str(e)
            return res
        res.status = "fallback"
        res.error = "live page not readable from here (%s); used the WebFetch copy captured %s" % (
            str(e)[:120], data.get("captured_at", "")[:10])
        res.notes.append(data.get("discrepancy", ""))
    asat = data.get("counts_as_at") or data.get("last_updated") or ""
    res.source_updated = data.get("last_updated") or asat
    cols = [c.lower() for c in data.get("columns", [])]
    sero = data.get("serotype") or ""
    for cells in data["rows"]:
        name, nums = cells[0], cells[1:]
        bov = nums[0] if len(nums) > 0 else None
        ovi = nums[1] if len(nums) > 1 else None
        tot = nums[-1]
        pl = geo.local_area("IRL", name) or geo.country_level("IRL")
        sp = "; ".join(s for s, n in (("Cattle", bov), ("Sheep", ovi)) if n)
        res.rows.append(row(
            event_id="ie-dafm-bt-%s-%s" % (asat[:4] or "season", re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")),
            record_type="aggregate", source=NAME, source_url=URL, source_updated=res.source_updated,
            fetched_at=res.fetched_at, category="bluetongue", disease="Bluetongue",
            serotype_or_strain=("BTV-%s" % sero) if sero else "", country_iso3="IRL", country_name="Ireland",
            admin1=pl["admin1"], place_as_published=name, place_level=pl["level"], lat=pl["lat"], lon=pl["lon"],
            species=sp, population_type="domestic", date_reported=asat, outbreaks=tot, status="ongoing",
            notes="Herd cases as at %s: %s cattle, %s sheep.%s" % (
                asat, bov if bov is not None else "?", ovi if ovi is not None else "?",
                " From a WebFetch copy of the page." if res.status == "fallback" else "")))
    tots = data.get("totals") or []
    res.headlines.append({"id": "ie-bt-herds", "label": "Bluetongue herd cases in Ireland",
                          "value": tots[-1] if tots else sum(r["outbreaks"] for r in res.rows), "unit": "herds",
                          "detail": "%s cattle herds, %s sheep flocks" % (tots[0] if tots else "?", tots[1] if len(tots) > 1 else "?"),
                          "serotype": ("BTV-%s" % sero) if sero else "", "counts_to": asat,
                          "counties": len(res.rows), "as_of": res.source_updated, "source": NAME, "source_url": URL,
                          "fetched_at": res.fetched_at, "status": res.status})
    return res
