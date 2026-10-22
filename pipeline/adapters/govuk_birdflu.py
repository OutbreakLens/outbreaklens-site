"""
govuk_birdflu.py: GOV.UK, Bird flu (avian influenza): latest situation in England (Defra and APHA).

The old address /government/news/bird-flu-avian-influenza-latest-situation-in-england is now a
redirect record. The Content API is followed to the live page, as the alert Worker does:
  https://www.gov.uk/api/content/guidance/bird-flu-avian-influenza-latest-situation-in-england

It writes one row per confirmed case listed under "Latest situation" (strain, place as published,
case reference, date), and headline figures: the UK season summary, risk levels and whether the
page says an Avian Influenza Prevention Zone (AIPZ) or housing order is in force.

Places: the page names a settlement and county ("near Belford, North Northumberland,
Northumberland"). The text is kept as published. The record is placed at the county's centre,
which is less precise than the published settlement.
"""
from __future__ import annotations
import datetime as dt, html, os, re

from bs4 import BeautifulSoup

from adapters.common import SNAPSHOTS, SourceResult, row, now_utc, iso_date, iso_week, save_json, load_json, to_int
import geo

NAME = "GOV.UK (Defra and APHA)"
OLD_PATH = "/government/news/bird-flu-avian-influenza-latest-situation-in-england"
PATH = "/guidance/bird-flu-avian-influenza-latest-situation-in-england"
API = "https://www.gov.uk/api/content"
LICENCE = "Open Government Licence v3.0"
SNAP = os.path.join(SNAPSHOTS, "govuk-birdflu")
CASE_RX = re.compile(
    r"(?P<kind>[Hh]ighly pathogenic avian influenza|[Ll]ow pathogenic(?:ity)? avian influenza|HPAI|LPAI)"
    r"(?:\s*\((?:HPAI|LPAI)\))?\s+(?P<strain>H\dN\d|H\d)\s+(?:has been|was)\s+confirmed\s+(?:in|at|on)\s+"
    r"(?P<what>.+?)\s+(?P<prep>near|in|at)\s+(?P<place>[^()]+?)\s*\((?P<ref>AIV ?\d{4}/\d+)\)"
    r"(?:\s+on\s+(?P<date>\d{1,2} \w+ \d{4}))?")


def _t(node):
    s = re.sub(r"\s+", " ", html.unescape(node.get_text(" ", strip=True)))
    return s.replace("( ", "(").replace(" )", ")").replace(" ,", ",").replace(" .", ".")


def _content(ctx, res, path):
    for _ in range(3):
        r = ctx.session.get(API + path, timeout=45, headers={"Accept": "application/json"})
        res.http = r.status_code
        r.raise_for_status()
        j = r.json()
        if j.get("schema_name") == "redirect" and j.get("redirects"):
            path = j["redirects"][0]["destination"]
            continue
        return j, path
    raise ValueError("too many redirects")


def _place(text):
    """Find the county or council area in 'Belford, North Northumberland, Northumberland'."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    for p in reversed(parts):
        pl = geo.local_area("GBR", p)
        if pl and pl["level"] == "admin2":
            return pl
    for p in reversed(parts):
        pl = geo.local_area("GBR", p)
        if pl:
            return pl
    return geo.country_level("GBR")


def _section(soup, h2_id):
    h = soup.find(id=h2_id)
    out = []
    node = h
    while node is not None:
        node = node.find_next_sibling()
        if node is None or node.name == "h2":
            break
        out.append(node)
    return out


def fetch(ctx) -> SourceResult:
    res = SourceResult("govuk_birdflu", NAME, "https://www.gov.uk" + PATH, licence=LICENCE,
                       attribution="Contains public sector information licensed under the Open Government Licence v3.0. "
                                   "Source: GOV.UK, Bird flu (avian influenza): latest situation in England.")
    res.fetched_at = now_utc()
    try:
        if ctx.offline:
            raise RuntimeError("offline run")
        j, path = _content(ctx, res, OLD_PATH)
        res.url = "https://www.gov.uk" + path
        res.status = "live"
    except Exception as e:
        j = load_json(os.path.join(SNAP, "latest.raw.json"))
        if not j:
            res.status, res.error = "failed", str(e)
            return res
        res.status, res.error = "fallback", "request failed (%s); used the stored copy from %s" % (
            e, (j.get("public_updated_at") or "")[:10])
    updated = j.get("public_updated_at") or ""
    res.source_updated = updated
    soup = BeautifulSoup((j.get("details") or {}).get("body") or "", "lxml")
    page = res.url

    # confirmed cases under "Latest situation", newest first, each under a dated h3
    cases, current = [], ""
    for node in _section(soup, "latest-situation"):
        if node.name == "h3":
            current = iso_date(_t(node))
            continue
        txt = _t(node)
        for m in CASE_RX.finditer(txt):
            cases.append((current, m, txt))
    seen = set()
    weekly = {}
    for heading_date, m, txt in cases:
        ref = m.group("ref").replace(" ", "")
        if ref in seen:
            continue
        seen.add(ref)
        date = iso_date(m.group("date")) or heading_date
        place_text = ("%s %s" % (m.group("prep"), m.group("place").strip())) if m.group("prep") == "near" else m.group("place").strip()
        pl = _place(m.group("place"))
        kind = "Highly pathogenic avian influenza" if m.group("kind").lower().startswith(("h", "hp")) else "Low pathogenic avian influenza"
        what = m.group("what").strip()
        notes = ["Confirmed in %s. GOV.UK case reference %s." % (what, m.group("ref"))]
        if re.search(r"3\s?km protection zone and 10\s?km surveillance zone", txt):
            notes.append("A 3 km protection zone and a 10 km surveillance zone were declared.")
        notes.append("Published at settlement level. Placed at the centre of %s." % (pl["admin2"] or pl["admin1"] or "the UK"))
        slug = re.sub(r"[^a-z0-9]+", "-", ref.lower()).strip("-")
        res.rows.append(row(
            event_id="govuk-ai-%s" % slug, record_type="case", source=NAME, source_url=page, source_updated=updated,
            fetched_at=res.fetched_at, category="bird-flu", disease=kind, serotype_or_strain=m.group("strain"),
            country_iso3="GBR", country_name="United Kingdom", admin1=pl["admin1"], admin2=pl["admin2"],
            place_as_published=place_text, place_level=pl["level"], lat=pl["lat"], lon=pl["lon"],
            species="Poultry" if "poultry" in what.lower() else what, population_type="domestic",
            date_confirmed=date, date_reported=heading_date or date, outbreaks=1, status="unknown",
            notes=" ".join(notes)))
        res.rows[-1]["_ref"] = ref
        if date:
            weekly[iso_week(date)] = weekly.get(iso_week(date), 0) + 1

    # UK season summary table
    summary, season = {}, ""
    for node in _section(soup, "cases"):
        if node.name == "h3" and "summary of confirmed cases in the UK" in _t(node) and not season:
            season = _t(node).split(":")[0].strip()
            tbl = node.find_next_sibling("table")
            if tbl:
                heads = [_t(th) for th in tbl.find_all("tr")[0].find_all(["th", "td"])]
                for tr in tbl.find_all("tr")[1:]:
                    cells = [_t(td) for td in tr.find_all(["th", "td"])]
                    if cells:
                        summary[cells[0]] = {heads[i]: to_int(cells[i]) for i in range(1, min(len(heads), len(cells)))}
    prev = {}
    for node in _section(soup, "cases"):
        if node.name == "table" and "Outbreak season" in _t(node):
            for tr in node.find_all("tr")[1:]:
                cells = [_t(td) for td in tr.find_all(["th", "td"])]
                if len(cells) >= 3:
                    prev[cells[0]] = {"HPAI": to_int(cells[1]), "LPAI": to_int(cells[2])}
    risk_txt = " ".join(_t(n) for n in _section(soup, "risk"))
    wild = re.search(r"risk of HPAI H5 in wild birds in Great Britain is assessed as (\w[\w ]*?) \(", risk_txt)
    poor = re.search(r"assessed as:?\s*(\w[\w ]*?) \(event occurs[^)]*\)\s*\(with (\w+) uncertainty\) where there is suboptimal", risk_txt)
    good = re.search(r"(very low|low|medium|high) \(event occurs[^)]*\)\s*\(with (\w+) uncertainty\) where stringent", risk_txt)
    full = _t(soup)
    in_force = re.search(r"(AIPZ|Avian Influenza Prevention Zone|housing (?:measures|order))[^.]{0,120}"
                         r"\b(?:is|are|remains?|has been|have been) (?:now )?(?:in force|in place|declared|introduced)",
                         full, re.I)
    news = [(_t(a), a.get("href") or "") for n in _section(soup, "news") for a in n.find_all("a")]
    lifted = []
    for title, href in news:
        if re.search(r"lift", title, re.I) and re.search(r"prevention zone|housing", title, re.I):
            when = ""
            if href.startswith("/") or href.startswith("https://www.gov.uk/"):
                try:   # the news item's own date, best effort
                    nj, _ = _content(ctx, SourceResult("x", "x", "x"), href.replace("https://www.gov.uk", ""))
                    when = iso_date(nj.get("first_published_at") or nj.get("public_updated_at"))
                except Exception:
                    when = ""
            lifted.append({"title": title, "date": when})
    if in_force:
        aipz = "The page says: " + in_force.group(0).strip() + "."
    elif lifted:
        def _long(d):
            x = dt.date.fromisoformat(d)
            return "%d %s %d" % (x.day, x.strftime("%B"), x.year)
        aipz = ("The page does not say that an Avian Influenza Prevention Zone (AIPZ) or a housing order is in force in England. Its latest news on "
                "them: %s." % " and ".join("\u2018%s\u2019%s" % (n["title"], (" (%s)" % _long(n["date"])) if n["date"] else "")
                                         for n in lifted))
    else:
        aipz = "The page does not say that an Avian Influenza Prevention Zone (AIPZ) or a housing order is in force in England."
    res.headlines.append({"id": "govuk-ai-season", "label": "HPAI (bird flu) cases confirmed in the UK this season",
                          "value": summary.get("Total") and sum(v or 0 for v in summary["Total"].values()) or len(res.rows),
                          "unit": "cases", "detail": "; ".join("%s: %s" % (k, ", ".join("%s %s" % (kk.replace(" cases", ""), vv)
                                                                                 for kk, vv in v.items()))
                                                             for k, v in summary.items() if k != "Total"),
                          "by_strain": summary.get("Total") or {}, "season": season,
                          "latest_case": max((r["date_confirmed"] for r in res.rows), default=""),
                          "previous_seasons": prev, "as_of": iso_date(updated), "source": NAME, "source_url": page,
                          "fetched_at": res.fetched_at})
    res.headlines.append({"id": "govuk-ai-risk", "label": "HPAI (bird flu) risk levels in Great Britain",
                          "value": wild.group(1) if wild else "", "unit": "risk to wild birds",
                          "wild_birds": wild.group(1) if wild else "not found",
                          "poultry_poor_biosecurity": ("%s (%s uncertainty)" % poor.groups()) if poor else "not found",
                          "poultry_stringent_biosecurity": ("%s (%s uncertainty)" % good.groups()) if good else "not found",
                          "poultry_poor_level": poor.group(1) if poor else "", "poultry_poor_uncertainty": poor.group(2) if poor else "",
                          "poultry_stringent_level": good.group(1) if good else "", "poultry_stringent_uncertainty": good.group(2) if good else "",
                          "aipz_or_housing": aipz, "aipz_in_force": bool(in_force), "aipz_news": lifted,
                          "as_of": iso_date(updated), "source": NAME, "source_url": page, "fetched_at": res.fetched_at})
    weeks = [iso_week(d.isoformat()) for d in ctx.week_starts()]
    res.series.append({"id": "govuk-ai-cases", "source": NAME, "source_url": page, "unit": "cases",
                       "metric": "HPAI (bird flu) cases confirmed in the UK each week (listed on the GOV.UK page)",
                       "date_basis": "date of confirmation", "geography": "United Kingdom", "fetched_at": res.fetched_at,
                       "source_updated": updated, "weeks": weeks,
                       "by_category": {"bird-flu": {"total": [weekly.get(w, 0) for w in weeks],
                                                    "by_country": {"GBR": [weekly.get(w, 0) for w in weeks]}}},
                       "caveat": "Only cases listed under 'Latest situation' this season."})
    res.notes.append("%d cases listed this season; AIPZ or housing order in force: %s" % (len(res.rows), bool(in_force)))
    save_json(SNAP, "latest.raw.json", j)   # the last good page, for offline runs
    save_json(SNAP, "%s.json" % iso_date(updated), {"updated": updated, "fetched_at": res.fetched_at,
                                                     "cases": [{k: r[k] for k in ("event_id", "serotype_or_strain", "place_as_published",
                                                                                  "admin1", "admin2", "date_confirmed")} for r in res.rows],
                                                     "headlines": res.headlines})
    return res
