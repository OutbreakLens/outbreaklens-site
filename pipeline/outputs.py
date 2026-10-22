"""
outputs.py: write the public files.

  data/events.csv           every row, one per event, case or published aggregate
  data/<category>.csv       the same rows split by the eight categories
  data/dictionary.csv       what each column means
  data/aggregates.json      weekly counts by category and country for the last 12 weeks, per source
  data/latest.json          headline numbers, each with its source and date
  data/map.geojson          points at country, region or county centres for the map
  data/run_status.json      what each source returned in this run

Map rule: where a national source (GOV.UK, DAFM, Ruokavirasto) covers a country and disease,
the map shows the national figures and lists the matching WOAH, EU and FAO records in the
pop-up, so the same outbreak is not drawn twice. EMPRES-i and ADIS records already drawn from
WAHIS are left off the map for the same reason. All of them stay in the CSV files.
"""
from __future__ import annotations
import collections, csv, datetime as dt, json, os

from adapters.common import COLUMNS, iso_week
import categories, clean, geo

DICTIONARY = [
    ("event_id", "text", "Unique id: the source's own id where it has one, with a source prefix (wahis-7918, empres-i-UNFAO-..., adis-<week>-<country>-<disease>, govuk-ai-<case ref>, govuk-bt-<season>-<area>, ie-dafm-bt-..., fi-ruokavirasto-asf-...).", "wahis-7918"),
    ("record_type", "event | case | aggregate", "event: a WOAH or FAO event; case: one confirmed case from a national page; aggregate: a published total for an area or week.", "event"),
    ("source", "text", "Who published the figure.", "WOAH WAHIS"),
    ("source_url", "URL", "Where to check the figure. For WAHIS, the event's page.", "https://wahis.woah.org/#/in-event/7918/dashboard"),
    ("source_updated", "date-time", "When the source last updated the record or page, as the source gives it.", "2026-10-20T15:02:50.583+00:00"),
    ("fetched_at", "date-time (UTC)", "When OutbreakLens read the source.", "2026-10-22T19:32:07Z"),
    ("category", "slug", "One of: bird-flu, bluetongue, asf, fmd, sheep-goat-pox, lsd, newcastle-disease, other.", "bird-flu"),
    ("disease", "text", "Disease as the source names it, shortened (WAHIS's '(Inf. with)' removed).", "High pathogenicity avian influenza viruses (poultry)"),
    ("serotype_or_strain", "text", "Serotype, subtype or strain where given.", "H5N1"),
    ("country_iso3", "ISO 3166-1 alpha-3", "Country code. Kosovo uses XKX.", "GBR"),
    ("country_name", "text", "Country name in GOV.UK style.", "United Kingdom"),
    ("admin1", "text", "First-level area: UK nation, Irish county, Finnish region, or the Natural Earth region elsewhere.", "England"),
    ("admin2", "text", "Second-level area where the record is placed there: UK county or council area, Finnish municipality.", "Northumberland"),
    ("place_as_published", "text", "The place exactly as the source publishes it, at settlement level at most. Blank where the source gives only points or premises detail.", "near Belford, North Northumberland, Northumberland"),
    ("place_level", "country | admin1 | admin2 | settlement", "The level of lat and lon.", "admin2"),
    ("lat", "decimal degrees", "Latitude of the centre of the area at place_level, 2 decimal places. Never a premises.", "55.32"),
    ("lon", "decimal degrees", "Longitude of the centre of the area at place_level, 2 decimal places. Never a premises.", "-2.07"),
    ("species", "text", "Species affected, joined with '; '.", "Poultry"),
    ("population_type", "domestic | wild | mixed", "Kept animals, wild animals or both. Blank when the source does not say.", "domestic"),
    ("date_start", "YYYY-MM-DD", "Event or outbreak start. For aggregates, the start of the period counted.", "2026-10-15"),
    ("date_confirmed", "YYYY-MM-DD", "Date of confirmation where given.", "2026-10-19"),
    ("date_reported", "YYYY-MM-DD", "Latest report date. For aggregates, the date the counts run to.", "2026-10-20"),
    ("outbreaks", "whole number", "Outbreaks or affected premises, herds or epidemiological units. WAHIS: all outbreaks in the event's latest report. GOV.UK bluetongue: confirmed cases (premises). DAFM: herd cases.", "1"),
    ("cases", "whole number", "Animals affected, where given. WAHIS: cumulative cases in the latest report. Ruokavirasto: wild boar.", "1166"),
    ("deaths", "whole number", "Animal deaths, where given.", "1156"),
    ("status", "ongoing | resolved | unknown", "Event status as the source gives it.", "ongoing"),
    ("notes", "text", "Context: report type, reason, how the place was set, caveats.", ""),
    ("same_as", "text", "Ids of rows from other sources that describe the same event, joined with '; ' (up to 20, then '+N more'). Rows are never merged.", "govuk-ai-aiv2026-21"),
]

SHORT_SOURCE = {"WOAH WAHIS": "WOAH WAHIS", "FAO EMPRES-i": "FAO EMPRES-i", "EU ADIS": "EU ADIS",
                "GOV.UK (Defra and APHA)": "GOV.UK", "DAFM (gov.ie)": "DAFM", "Ruokavirasto (Finnish Food Authority)": "Ruokavirasto"}


def _sort_key(r):
    d = max(r.get("date_reported") or "", r.get("date_confirmed") or "", r.get("date_start") or "")
    return (categories.SLUGS.index(r["category"]), "~" if not d else "", -int(d.replace("-", "") or 0), r["source"], r["event_id"])


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(clean.public(r))


def write_tables(out, rows):
    rows = sorted(rows, key=_sort_key)
    write_csv(os.path.join(out, "events.csv"), rows)
    counts = {}
    for slug in categories.SLUGS:
        sub = [r for r in rows if r["category"] == slug]
        write_csv(os.path.join(out, "%s.csv" % slug), sub)
        counts[slug] = len(sub)
    with open(os.path.join(out, "dictionary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["column", "type", "description", "example"])
        w.writerows(DICTIONARY)
    return counts


# ---------- aggregates.json ----------
PRIMARY = {"bird-flu": "wahis-outbreaks", "bluetongue": "govuk-bt-cases", "asf": "wahis-outbreaks",
           "fmd": "wahis-outbreaks", "sheep-goat-pox": "wahis-outbreaks", "lsd": "wahis-outbreaks",
           "newcastle-disease": "wahis-outbreaks", "other": "wahis-outbreaks"}


def write_aggregates(out, ctx, results, generated):
    weeks = [iso_week(d.isoformat()) for d in ctx.week_starts()]
    series = [s for r in results for s in r.series]
    by_id = {s["id"]: s for s in series}
    cats = {}
    for slug, label, scope in categories.CATEGORIES:
        sid = PRIMARY[slug]
        s = by_id.get(sid)
        if not s or slug not in s.get("by_category", {}):
            s = by_id.get("wahis-outbreaks")
            sid = "wahis-outbreaks"
        data = (s or {}).get("by_category", {}).get(slug, {"total": [0] * len(weeks), "by_country": {}})
        top = sorted(((k, sum(v)) for k, v in data.get("by_country", {}).items()), key=lambda kv: -kv[1])[:5]
        cats[slug] = {"label": label, "scope": scope, "series_id": sid, "source": (s or {}).get("source", ""),
                      "source_url": (s or {}).get("source_url", ""), "unit": (s or {}).get("unit", ""),
                      "metric": (s or {}).get("metric", ""), "geography": (s or {}).get("geography", ""),
                      "date_basis": (s or {}).get("date_basis", ""), "source_updated": (s or {}).get("source_updated", ""),
                      "fetched_at": (s or {}).get("fetched_at", ""), "caveat": (s or {}).get("caveat", ""),
                      "total": data.get("total", [0] * len(weeks)),
                      "top_countries": [{"iso3": k, "name": geo.country_name(k), "count": v} for k, v in top if v],
                      "by_area": data.get("by_area", {})}
    doc = {"generated_at": generated,
           "window": {"start": ctx.window_start.isoformat(), "end": ctx.today.isoformat(), "weeks": weeks,
                      "week_starts": [d.isoformat() for d in ctx.week_starts()], "current_week": iso_week(ctx.today.isoformat()),
                      "current_week_partial": True},
           "categories": cats, "series": series,
           "note": "Each series keeps its own source's counting rules. They overlap and must not be added together."}
    with open(os.path.join(out, "aggregates.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


def write_latest(out, ctx, results, rows, generated, counts):
    heads = [h for r in results for h in r.headlines]
    per_cat = {}
    for slug, label, _ in categories.CATEGORIES:
        sub = [r for r in rows if r["category"] == slug]
        dates = [max(r["date_reported"] or "", r["date_confirmed"] or "") for r in sub]
        per_cat[slug] = {"label": label, "rows": len(sub), "countries": len({r["country_iso3"] for r in sub}),
                         "latest_date": max(dates) if dates else ""}
    doc = {"generated_at": generated, "window_start": ctx.window_start.isoformat(), "headlines": heads,
           "categories": per_cat, "sources": [r.summary() for r in results]}
    with open(os.path.join(out, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


# ---------- map.geojson ----------
def _fmt_date(d):
    if not d:
        return ""
    x = dt.date.fromisoformat(d)
    return "%d %s %d" % (x.day, x.strftime("%b"), x.year)


def _place_label(r_or_u, iso3):
    a2, a1 = r_or_u.get("admin2") or "", r_or_u.get("admin1") or ""
    name = geo.country_name(iso3)
    if a2:
        return "%s, %s" % (a2, a1 if iso3 == "GBR" and a1 else name)
    if a1:
        return "%s, %s" % (a1, name)
    return name


def _title(r):
    t = r["disease"]
    if r.get("serotype_or_strain"):
        t += ", " + r["serotype_or_strain"]
    return t


def write_map(out, rows, results, edges):
    """One feature per record and place. Each feature carries counts by ISO week, so the map's time
    filter changes the counts and hides a marker only when it has nothing in the chosen weeks."""
    id2row = {r["event_id"]: r for r in rows}
    national = {r["event_id"] for r in rows if r["source"] in clean.NATIONAL}
    feats = []

    def also(eid):
        """Other sources for the pop-up: one link per source, never EMPRES-i (it mirrors WAHIS)."""
        seen, out_ = set(), []
        for x in sorted(edges.get(eid, ())):
            o = id2row.get(x)
            if not o or o["source"] in (id2row[eid]["source"], "FAO EMPRES-i"):
                continue
            src = SHORT_SOURCE.get(o["source"], o["source"])
            if src not in seen:
                seen.add(src)
                out_.append([src, o["source_url"]])
        return out_

    def feature(fid, r, lat, lon, weeks, unit, place, note, date):
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 2), round(lat, 2)]},
                "properties": {"id": fid, "cat": r["category"], "src": SHORT_SOURCE.get(r["source"], r["source"]),
                               "title": _title(r), "place": place, "date": date, "weeks": dict(sorted(weeks.items())),
                               "unit": unit, "url": r["source_url"], "also": also(r["event_id"]), "note": note}}

    # WAHIS: one feature per event and region, with outbreaks by start week
    wres = next((x for x in results if x.key == "wahis"), None)
    grouped = collections.OrderedDict()
    for u in (wres.extras.get("map_units", []) if wres else []):
        r = id2row.get(u["event_id"])
        if not r or u["lat"] is None:
            continue
        if any(x in national for x in edges.get(u["event_id"], ())):
            if u["country_iso3"] != "GBR" or u["admin1"] in geo.UK_NATIONS:
                continue   # drawn from the national source instead
        k = (u["event_id"], u["admin1"], u["admin2"], u["lat"], u["lon"])
        g = grouped.setdefault(k, {"u": u, "weeks": collections.Counter(), "date": ""})
        g["weeks"][u["week"]] += u["count"]
        g["date"] = max(g["date"], u["date"])
    for (eid, a1, a2, la, lo), g in grouped.items():
        r = id2row[eid]
        feats.append(feature("%s-%s" % (eid, geo.norm(a2 or a1 or "country").replace(" ", "-")), r, la, lo, g["weeks"],
                             "outbreak", _place_label(g["u"], g["u"]["country_iso3"]),
                             "Outbreaks counted by their start date. Latest start %s." % _fmt_date(g["date"]), g["date"]))
    # EMPRES-i events not already in WAHIS or a national source, grouped by region
    groups = collections.defaultdict(list)
    for r in rows:
        if r["source"] == "FAO EMPRES-i" and not edges.get(r["event_id"]) and r["lat"] != "":
            groups[(r["category"], r["country_iso3"], r["admin1"], r["admin2"], r["lat"], r["lon"], r["disease"])].append(r)
    for (cat, iso3, a1, a2, la, lo, dis), grp in groups.items():
        r0 = max(grp, key=lambda r: r["date_start"] or "")
        weeks = collections.Counter(iso_week(g["date_start"] or g["date_reported"]) for g in grp)
        srcs = sorted({(g.get("_diag_source") or "not given") for g in grp})
        feats.append(feature("empres-i-%s-%s-%s" % (iso3.lower(), geo.norm(a2 or a1 or "country").replace(" ", "-"), cat),
                             r0, la, lo, weeks, "event", _place_label(r0, iso3),
                             "EMPRES-i events by observation date, not found in WOAH WAHIS this run. Reported by: %s."
                             % ", ".join(srcs), r0["date_start"] or r0["date_reported"]))
    # ADIS rows not linked to WAHIS or a national source
    for r in rows:
        if r["source"] == "EU ADIS" and not edges.get(r["event_id"]) and r["lat"] != "":
            feats.append(feature(r["event_id"], r, r["lat"], r["lon"], {iso_week(r["date_reported"]): r["outbreaks"] or 0},
                                 "outbreak", r["country_name"], "ADIS week %s to %s." % (
                                     _fmt_date(r["date_start"]), _fmt_date(r["date_reported"])), r["date_reported"]))
    # national sources
    fi = collections.defaultdict(list)
    for r in rows:
        if r["source"] not in clean.NATIONAL or r["lat"] == "":
            continue
        if r["source"] == "GOV.UK (Defra and APHA)" and r["category"] == "bluetongue":
            if not r["admin2"]:
                continue   # nation totals: the county rows are drawn instead
            feats.append(feature(r["event_id"], r, r["lat"], r["lon"], {iso_week(r["date_reported"]): r["outbreaks"] or 0},
                                 "case (premises) this season", _place_label(r, "GBR"),
                                 "Season total, %s to %s. GOV.UK counts a case as a premises." % (
                                     _fmt_date(r["date_start"]), _fmt_date(r["date_reported"])), r["date_reported"]))
        elif r["source"] == "GOV.UK (Defra and APHA)":
            feats.append(feature(r["event_id"], r, r["lat"], r["lon"], {iso_week(r["date_confirmed"]): 1}, "case",
                                 _place_label(r, "GBR"), "Published as %s. Shown at the centre of %s." % (
                                     r["place_as_published"], r["admin2"] or r["admin1"]), r["date_confirmed"]))
        elif r["source"] == "DAFM (gov.ie)":
            feats.append(feature(r["event_id"], r, r["lat"], r["lon"], {iso_week(r["date_reported"]): r["outbreaks"] or 0},
                                 "herd case this season", _place_label(r, "IRL"),
                                 "Herd cases as at %s." % _fmt_date(r["date_reported"]), r["date_reported"]))
        else:
            fi[(r["admin1"], r["lat"], r["lon"])].append(r)
    for (a1, la, lo), grp in fi.items():
        r0 = max(grp, key=lambda r: r["date_confirmed"])
        weeks = collections.Counter()
        for g in grp:
            weeks[iso_week(g["date_confirmed"])] += g["cases"] or 1
        munis = sorted({g["admin2"] for g in grp})
        feats.append(feature("fi-asf-%s" % geo.norm(a1).replace(" ", "-"), r0, la, lo, weeks, "wild boar",
                             "%s, Finland" % a1, "Municipalities: %s. Latest confirmed %s." % (
                                 ", ".join(munis), _fmt_date(r0["date_confirmed"])), r0["date_confirmed"]))
    gj = {"type": "FeatureCollection",
          "properties": {"note": "Points are at the centre of a country, region or county. They never show a farm or other premises.",
                         "units": {"outbreak": "outbreaks", "event": "events", "case": "cases", "wild boar": "wild boar",
                                   "case (premises) this season": "cases (premises) this season",
                                   "herd case this season": "herd cases this season"}},
          "features": sorted(feats, key=lambda f: (f["properties"]["date"] or "", f["properties"]["id"]))}
    with open(os.path.join(out, "map.geojson"), "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False, separators=(",", ":"))
    return collections.Counter(f["properties"]["src"] for f in feats)
