# OutbreakLens live data pipeline

Reads official animal-disease data from seven public sources, cleans it to one row per event, case or
published total, tags each row with one of eight disease categories, links rows that describe the same
event, and writes open files for the website's map, Numbers page and Data page.

```
adapters (7 sources) -> clean (validate, de-duplicate, link, hold) -> outputs (CSV, JSON, GeoJSON)
```

## Quick start

```bash
pip install -r requirements.txt
python3 run.py              # live run, last 12 weeks, writes data/
python3 run.py --offline    # no network: stored snapshots and saved copies only
```

Then, from the repository root, `python3 -I build_site.py --prelaunch` copies `pipeline/data/` into
`website/assets/data/` and builds `map.html`, `analytics.html` (Numbers) and `data.html`.

The first live run takes about 7 minutes, because WAHIS report details are fetched one at a time with a
pause between requests. Later runs reuse `cache/` and take under a minute.

Options: `--only wahis,adis` (writes to `cache/partial-run/`, never to `data/`), `--weeks 8`,
`--wahis-max-fetch 450` (cap on new WAHIS requests per run), `--outdir`.

## Sources

| Adapter | Source | What it reads | If it fails |
|---|---|---|---|
| `wahis` | WOAH WAHIS | `POST /api/v1/pi/event/filtered-list` (the alert Worker's request shape), then `GET /api/v1/pi/review/report/<id>/all-information` for each in-scope event's latest report, cached by report id | the last saved list (`samples/wahis_list.json`) and cached reports |
| `govuk_bluetongue` | GOV.UK, Bluetongue: latest situation | Content API: nation totals, county and local authority tables, daily update notes, risk and zones | `snapshots/govuk-bluetongue/latest.raw.json` |
| `govuk_birdflu` | GOV.UK, Bird flu: latest situation in England | Content API (follows the old /government/news redirect): cases this season, UK season table, risk levels, prevention zone or housing order | `snapshots/govuk-birdflu/latest.raw.json` |
| `adis` | EU ADIS weekly outbreak report | the weekly PDF: outbreak matrix, species and administrative divisions | the latest stored week in `snapshots/adis/` |
| `empres_i` | FAO EMPRES-i | the public CSV `getLatestEventsByDate?start_date=&end_date=` listed in FAO's data catalogue | `cache/empres_i/latest.csv` |
| `ie_dafm` | DAFM, gov.ie, Bluetongue virus | herd cases by county | `samples/ie_dafm_bluetongue.json` (a WebFetch copy) |
| `fi_ruokavirasto` | Ruokavirasto, ASF cases in Finland | wild boar cases by date and municipality | `samples/fi_ruokavirasto_asf.json` |

Every adapter returns rows in the common schema with `fetched_at` and `source_url`, plus any weekly
series and headline figures the source publishes. One failing source never stops the run. See
`notes.md` for what each source yields and why.

## Outputs (data/)

| File | What it holds |
|---|---|
| `events.csv` | every row, one per event, case or published total |
| `<category>.csv` | the same rows for each category: bird-flu, bluetongue, asf, fmd, sheep-goat-pox, lsd, newcastle-disease, other |
| `dictionary.csv` | what each column means |
| `aggregates.json` | weekly counts by category and country for the last 12 weeks, kept separate for each source |
| `latest.json` | headline numbers, each with source, date and link, plus each source's status |
| `map.geojson` | map points at country, region or county centres, with counts by ISO week and the population type (domestic, wild, mixed or blank) |
| `tables.json` | country tables for the Numbers page (wild and domestic counts over the 12 weeks, the latest ADIS week for ASF, national bluetongue tables), built from the same de-duplicated records as the map |
| `run_status.json` | what each source returned, links added, validation issues |

## Rules built in

- **Places.** Records are placed at the centre of a country, region (Natural Earth first-level unit) or
  UK county, Irish county or Finnish region. WAHIS and EMPRES-i publish outbreak points; the pipeline
  uses a point only to find the region that contains it and never writes the point out. Published place
  text is kept at settlement level at most, and any place text that looks like a premises (farm, holding,
  postcode) is removed during validation.
- **Linking, not merging.** Rows from different sources that describe the same event are linked in
  `same_as` (rules R1 to R5 in `clean.py`): case reference, point and date match, ADIS week overlap, and
  national-source overlap. Every figure stays traceable to its own source.
- **Validation.** Dates must be YYYY-MM-DD and not in the future, country codes must be ISO 3166-1
  alpha-3, categories must be one of the eight, numbers must be whole and not negative.
- **Editorial hold.** UK records of pig diseases are kept out of the public files and written to
  `cache/held/` for review by hand.

## Geography

`geo/build_geo.py` builds `geo/countries.csv`, `geo/admin1.csv` and `geo/local_areas.csv` from Natural
Earth (public domain). Re-run it after adding a county or municipality to the `LOCAL` table.

## What is committed and what stays local

Committed: code, `geo/`, `samples/` (no coordinates), `snapshots/` (parsed weekly ADIS JSON, dated
GOV.UK snapshots and the last good GOV.UK page) and `data/`. Local only (`.gitignore`): `cache/`
(WAHIS reports and the EMPRES-i CSV, which hold outbreak points), the ADIS PDFs and the held rows.

## Running it weekly

Run `python3 run.py` then rebuild the site. The WAHIS adapter identifies itself
(`OutbreakLensPipeline/2.0 (+https://outbreaklens.com; hello@outbreaklens.com)`), waits 0.6 seconds
between requests and caches every validated report, so a weekly run makes about 100 to 120 WAHIS requests.
