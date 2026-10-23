"""
adis.py: the EU Animal Disease Information System (ADIS) weekly outbreak report.

https://webgate.ec.europa.eu/tracesnt/adis/public/notification/outbreaks-weekly-report returns a PDF
that the European Commission replaces every week. Each run stores the PDF and the parsed rows under
snapshots/adis/, named by the reporting period, so the history builds up week by week.

The PDF has:
  - a matrix of outbreaks by disease (rows) and country (columns), with the date of the last
    outbreak submitted for each cell
  - summary tables by country and disease, listing species and the smallest administrative division
  - reference tables of disease abbreviations and country codes

One row is written per country and disease in the matrix. ADIS lists municipalities or districts,
not premises. They go in the notes; the record is placed at the country's centre.
"""
from __future__ import annotations
import collections, glob, io, json, os, re

from adapters.common import SNAPSHOTS, SourceResult, row, now_utc, iso_date, save_text, save_json, load_json, infer_population
import categories, geo

NAME = "EU ADIS"
URL = "https://webgate.ec.europa.eu/tracesnt/adis/public/notification/outbreaks-weekly-report"
LICENCE = ("European Commission reuse policy (Decision 2011/833/EU): reuse is allowed with appropriate credit and an "
           "indication of changes. Commission content is licensed under CC BY 4.0.")
SNAP = os.path.join(SNAPSHOTS, "adis")
DATE_RX = re.compile(r"^\d{2}/\d{2}/\d{2}(\d{2})?$")
REF_RX = re.compile(r"^[A-Z]{2}-[A-Z]|^\d{4}-\d{5}|^[A-Z(]+[A-Z().]*-\d{4}|^\d{5}|^[A-Z]{2,}[A-Z().-]*-?$|-\d{4}-")


def _period(text):
    m = re.search(r"Weekly Notification:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4}).*?created on\s*(\d{2}/\d{2}/\d{4})", text)
    if not m:
        raise ValueError("reporting period not found in the PDF")
    return iso_date(m.group(1)), iso_date(m.group(2)), iso_date(m.group(3))


def _lines(words, tol=2.5):
    rows = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and abs(rows[-1][0] - w["top"]) <= tol:
            rows[-1][1].append(w)
        else:
            rows.append([w["top"], [w]])
    return [(t, sorted(ws, key=lambda w: w["x0"])) for t, ws in rows]


def _matrix(page):
    words = page.extract_words()
    hdr = [w for w in words if re.fullmatch(r"[A-Z]{2}", w["text"]) and w["x0"] > 200]
    if not hdr:
        return []
    htop = min(w["top"] for w in hdr)
    cols = [((w["x0"] + w["x1"]) / 2, w["text"]) for w in hdr if abs(w["top"] - htop) < 3]
    first_x = min(c for c, _ in cols)

    def col(x, tol):
        c = min(cols, key=lambda c: abs(c[0] - x))
        return c[1] if abs(c[0] - x) <= tol else None

    slash_tops = collections.Counter(round(w["top"]) for w in words if w["text"] == "/" and w["x0"] > first_x - 20)
    out = []
    for y, n in sorted(slash_tops.items()):
        if n < 3 or y <= htop + 5:
            continue
        label = [w for w in words if w["x1"] < first_x - 15 and abs(w["top"] - y) <= 9]
        label = " ".join(w["text"] for w in sorted(label, key=lambda w: (round(w["top"]), w["x0"])))
        nums = [w for w in words if re.fullmatch(r"\d+", w["text"]) and y - 12 <= w["top"] <= y - 3]
        dates = [w for w in words if DATE_RX.match(w["text"]) and y + 3 <= w["top"] <= y + 12]
        cells = {}
        for w in nums:
            c = col((w["x0"] + w["x1"]) / 2, 12)
            if c:
                cells.setdefault(c, {})["n"] = int(w["text"])
        for w in dates:
            c = col((w["x0"] + w["x1"]) / 2, 16)
            if c:
                cells.setdefault(c, {})["date"] = iso_date(w["text"])
        out.append({"label": label.strip(), "cells": cells})
    return out


def _summary(page):
    """Rows of the per-country summary tables, split by the ruled lines."""
    hs = sorted({round(l["top"]) for l in page.lines if abs(l["top"] - l["bottom"]) < 1})
    vs = sorted({round(l["x0"]) for l in page.lines if abs(l["x0"] - l["x1"]) < 1})
    if len(vs) < 5 or len(hs) < 2:
        return []
    words = page.extract_words()
    out = []
    bands = [(hs[i], hs[i + 1]) for i in range(len(hs) - 1)]
    if hs[-1] < page.height - 60:   # last row runs to the bottom margin when it continues on the next page
        bands.append((hs[-1], page.height - 50))
    for top, bottom in bands:
        if top < 115:   # page title and column headings
            continue
        cell = lambda a, b: [w for w in words if a - 1 <= w["x0"] < b and top < w["top"] < bottom]
        country = " ".join(w["text"] for t, ws in _lines(cell(vs[0], vs[1])) for w in ws)
        dis_lines = [" ".join(w["text"] for w in ws) for t, ws in _lines(cell(vs[1], vs[2]))]
        species = [" ".join(w["text"] for w in ws) for t, ws in _lines(cell(vs[2], vs[3]))]
        admin_lines = _lines(cell(vs[3], vs[4] + 200))
        admins, last = [], None
        for t, ws in admin_lines:
            txt = " ".join(w["text"] for w in ws)
            if last is not None and t - last < 10 and admins:
                admins[-1] += " " + txt
            else:
                admins.append(txt)
            last = t
        label, refs = [], []
        for ln in dis_lines:
            if re.match(r"^[A-Z]{2}-[A-Z]", ln) or re.match(r"^[A-Z0-9(][A-Z0-9().-]*-\d", ln) or re.match(r"^\d", ln) \
                    or (refs and re.match(r"^[A-Z][A-Z().]+-", ln)):
                refs.append(ln)
            elif refs:
                refs.append(ln)
            else:
                label.append(ln)
        ref_text = "".join(refs).replace(" ", "")
        out.append({"country": country.strip(), "label": " ".join(label).strip(),
                    "refs": [r for r in ref_text.split(",") if r], "species": species, "admin": admins})
    return out


def _reference(pdf):
    countries, diseases = {}, {}
    for page in pdf.pages:
        t = page.extract_text() or ""
        if "Reference data - Countries" in t:
            for m in re.finditer(r"^([A-Z]{2}) ([A-Z]{3}) (.+)$", t, re.M):
                countries[m.group(1)] = (m.group(2), m.group(3).strip())
        if "Reference data - Diseases" in t:
            for ln in t.splitlines():
                m = re.match(r"^([A-Z][A-Z0-9().-]*(?:\.[A-Z]+)?) (.+)$", ln.strip())
                if m and m.group(1) not in ("ADIS", "The", "Abbreviation", "Reference"):
                    diseases[" ".join(m.group(2).split())] = m.group(1)
    return countries, diseases


def _norm_label(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _population(label):
    l = label.lower()
    if "wild boar" in l or "wild birds" in l:
        return "wild", "Wild boar" if "boar" in l else "Wild birds"
    if "domestic pigs" in l:
        return "domestic", "Domestic pigs"
    if "captive birds" in l:
        return "domestic", "Captive birds"
    if "(poultry)" in l:
        return "domestic", "Poultry"
    return "", ""


def parse(pdf_bytes):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        first = "\n".join((p.extract_text() or "") for p in pdf.pages[:2])
        start, end, created = _period(first)
        countries, diseases = _reference(pdf)
        matrix, summary = [], []
        for p in pdf.pages:
            t = p.extract_text() or ""
            if "Total of outbreaks by disease" in t:
                matrix += _matrix(p)
            elif "Summary of diseases" in t:
                summary += _summary(p)
    # join summary rows that continue on the next page (no disease label)
    joined = []
    for s in summary:
        if not s["label"] and joined:
            joined[-1]["refs"] += s["refs"]
            joined[-1]["species"] += s["species"]
            joined[-1]["admin"] += s["admin"]
        else:
            joined.append(s)
    return {"period_start": start, "period_end": end, "created": created, "countries": countries,
            "diseases": diseases, "matrix": matrix, "summary": joined}


def fetch(ctx) -> SourceResult:
    res = SourceResult("adis", NAME, URL, licence=LICENCE,
                       attribution="Source: European Commission, ADIS weekly outbreak report. © European Union.")
    res.fetched_at = now_utc()
    parsed, pdf = None, None
    try:
        if ctx.offline:
            raise RuntimeError("offline run")
        r = ctx.session.get(URL, timeout=90)
        res.http = r.status_code
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            raise ValueError("response is not a PDF")
        pdf = r.content
        parsed = parse(pdf)
        res.status = "live"
    except Exception as e:
        snaps = sorted(glob.glob(os.path.join(SNAP, "*.json")))
        if not snaps:
            res.status, res.error = "failed", str(e)
            return res
        parsed = load_json(snaps[-1])
        res.status, res.error = "fallback", "download failed (%s); used the stored week %s" % (e, os.path.basename(snaps[-1]))
    stem = "%s_%s" % (parsed["period_start"], parsed["period_end"])
    if pdf is not None:
        save_text(SNAP, stem + ".pdf", pdf)
        save_json(SNAP, stem + ".json", parsed)
    res.source_updated = parsed["created"]

    summ = {}
    for s in parsed["summary"]:
        summ[(_norm_label(s["country"]), _norm_label(s["label"]))] = s
    cnames = {k: v for k, v in parsed["countries"].items()}
    weekly = collections.defaultdict(collections.Counter)
    for m in parsed["matrix"]:
        label = m["label"]
        dis, _, typ = label.partition(" / ")
        cat = categories.categorise(dis)
        if not cat:
            continue
        pop, sp_default = _population(dis)
        abbrev = parsed["diseases"].get(" ".join(dis.split())) or re.sub(r"[^A-Z]", "", dis.upper())[:8]
        for iso2, cell in m["cells"].items():
            n = cell.get("n")
            if not n:
                continue
            iso3, cname = cnames.get(iso2, (None, None))
            c = geo.country(iso3 or iso2)
            if not c:
                res.notes.append("country code %s not recognised" % iso2)
                continue
            s = summ.get((_norm_label(cname or c[1]), _norm_label(label))) or {}
            species = s.get("species") or ([sp_default] if sp_default else [])
            pop = pop or infer_population(species)
            notes = ["Outbreaks in the ADIS week %s to %s. Last outbreak submitted %s." % (
                parsed["period_start"], parsed["period_end"], cell.get("date") or "not given")]
            if s.get("admin"):
                notes.append("Smallest administrative divisions listed: %s." % "; ".join(s["admin"]))
            if s.get("refs") and len(s["refs"]) != n:
                notes.append("The summary table lists %d outbreak references." % len(s["refs"]))
            eid = "adis-%s-%s-%s%s" % (parsed["period_start"].replace("-", ""), iso2, abbrev, ("-" + typ) if typ else "")
            eid = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", eid.lower())).strip("-")
            res.rows.append(row(
                event_id=eid, record_type="aggregate", source=NAME, source_url=URL, source_updated=parsed["created"],
                fetched_at=res.fetched_at, category=cat, disease=categories.short_disease(dis.replace("A.S.F.", "African swine fever")),
                serotype_or_strain=typ.strip(), country_iso3=c[0], country_name=c[1], place_level="country",
                lat=c[2], lon=c[3], species="; ".join(species), population_type=pop,
                date_start=parsed["period_start"], date_reported=cell.get("date") or parsed["period_end"],
                outbreaks=n, status="unknown", notes=" ".join(notes)))
            res.rows[-1]["_adis_admin"] = s.get("admin") or []
            weekly[cat][c[0]] += n
    # history from every stored week
    periods = []
    for path in sorted(glob.glob(os.path.join(SNAP, "*.json"))):
        p = load_json(path) or {}
        tot = collections.defaultdict(lambda: collections.Counter())
        for m in p.get("matrix", []):
            dis = m["label"].partition(" / ")[0]
            cat = categories.categorise(dis)
            if not cat:
                continue
            for iso2, cell in m["cells"].items():
                iso3 = (p.get("countries", {}).get(iso2) or [iso2])[0]
                tot[cat][iso3] += cell.get("n") or 0
        periods.append({"start": p.get("period_start"), "end": p.get("period_end"), "created": p.get("created"),
                        "by_category": {k: {"total": sum(v.values()), "by_country": dict(v)} for k, v in tot.items()}})
    res.series.append({"id": "adis-weekly", "source": NAME, "source_url": URL, "unit": "outbreaks",
                       "metric": "Outbreaks in the ADIS weekly report, by reporting week (Thursday to Wednesday)",
                       "date_basis": "ADIS reporting week", "geography": "ADIS reporting countries",
                       "fetched_at": res.fetched_at, "source_updated": parsed["created"], "periods": periods,
                       "caveat": "History starts with the first stored week. ADIS replaces the report each week."})
    total = sum(sum(v.values()) for v in weekly.values())
    res.headlines.append({"id": "adis-week", "label": "Outbreaks in the EU ADIS weekly report",
                          "value": total, "unit": "outbreaks",
                          "detail": "%s to %s, in the eight categories, %d countries" % (
                              parsed["period_start"], parsed["period_end"],
                              len({c for v in weekly.values() for c in v})),
                          "by_category": {k: sum(v.values()) for k, v in weekly.items()},
                          "as_of": parsed["created"], "source": NAME, "source_url": URL, "fetched_at": res.fetched_at})
    res.extras["period"] = (parsed["period_start"], parsed["period_end"])
    res.notes.append("week %s to %s: %d matrix rows, %d summary rows, %d rows in scope" % (
        parsed["period_start"], parsed["period_end"], len(parsed["matrix"]), len(parsed["summary"]), len(res.rows)))
    return res
