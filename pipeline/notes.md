# Pipeline notes

What each source yields, what failed and why, the reuse terms found, and what to decide before this
goes to the live site. First written on 22 October 2026 from the build run. The block below is
rewritten by `run.py` on every full run.

<!-- run-status:start -->
Last run: 2026-10-22T22:59:37Z. Window 2026-08-03 to 2026-10-22.

| Source | Status | Rows | Updated by source | Note |
|---|---|---|---|---|
| WOAH WAHIS | live | 317 | 2026-10-22 | 425 events in the list since 2026-08-03, 317 in the eight categories; report detail: 317 from cache, 0 fetched, 0 skipped (fetch budget), 0 failed |
| GOV.UK bluetongue | live | 68 | 2026-10-22 | 76 daily notes parsed since 2026-08-03, adding up to 3193 new cases |
| GOV.UK bird flu | live | 2 | 2026-10-21 | 2 cases listed this season; AIPZ or housing order in force: False |
| EU ADIS | live | 33 | 2026-10-22 | week 2026-10-15 to 2026-10-21: 13 matrix rows, 41 summary rows, 33 rows in scope |
| FAO EMPRES-i | live | 2286 | 2026-10-22 | 2999 events returned, 2286 in the eight categories, 713 out of scope, 0 without a country match |
| DAFM (gov.ie) | fallback | 14 | 2026-10-21 | live page not readable from here (403 Client Error: Forbidden for url: https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/publications/bl); use |
| Ruokavirasto (Finnish Food Authority) | live | 70 | 2026-10-22 |  |

Rows by category: bird-flu 615, bluetongue 179, asf 1289, fmd 222, sheep-goat-pox 198, lsd 95, newcastle-disease 43, other 149.
Links added (same_as): R1 reference 2, R2 point 1844, R3 week 46, R4 national 220, R5 national 19.
Rows held for editorial review: 0. Validation issues: 0.
<!-- run-status:end -->

## Source by source (22 October 2026)

**WOAH WAHIS: live.** The list endpoint the WAHIS home page uses (`/api/v1/pi/event/filtered-list`,
same request body as the alert Worker but all report types) answered from the build container in about
2 seconds a page. It returns one row per event, showing the event's latest report. Paged back to
3 August 2026 it gave 425 events, 317 of them in the eight categories, in 80 countries. The latest
report of each event (`/api/v1/pi/review/report/<id>/all-information`) holds the full outbreak list
with start dates and admin divisions, cumulative case totals and the event status, so one request per
event is enough. The first run made 317 report requests in about 7 minutes; reports are cached by id.
WAHIS publishes a point for every outbreak (37,769 points in this run). The points are used only to find
the containing region and are never written out. Admin divisions vary by country: counties in the UK,
parishes in Latvia (from ADIS). 171 events sit in one region, 141 span several and are placed at the
country centre, 5 are UK counties.

**FAO EMPRES-i: live, through FAO's data catalogue.** The EMPRES-i+ web app is a Flutter app whose API
(`fao-empresi.ew.r.appspot.com`) needs a Firebase sign-in token (HTTP 403 "Token not provided"), so it
is not used. FAO's data catalogue lists a public resource, "Latest Reported Events", for the dataset
"EMPRES-i: Global Animal Disease Events Dashboard" (CC BY 4.0):
`https://europe-west1-fao-empresi.cloudfunctions.net/getLatestEventsByDate`. Without parameters it
returns an old 15,000-row block (observation dates 2020 to 2021). With `start_date` and `end_date` it
returns the window: 2,999 events, 2,286 in scope. 1,844 match a WAHIS outbreak (same country, category
and start date, within 5 km) and are linked, not drawn twice. Most of the rest (about 400) come from
national authorities and appear on the map. EMPRES-i localities can name villages or farm areas, so
they are not published; only the region is.

**EU ADIS: live.** The weekly report URL returns a 10-page PDF (about 420 KB), replaced each week.
Week 15 to 21 October 2026: 162 outbreaks in the eight categories across 20 countries (126 African
swine fever, 121 of them in wild boar), parsed from the matrix by column position and checked against
the per-country summary pages (species, smallest administrative divisions, outbreak references).
Each week's parse is stored in `snapshots/adis/` as JSON; the PDFs stay local. 24 of the 33 rows link
to a WAHIS event for the same country, disease and population.

**GOV.UK bluetongue: live.** Content API, page updated 22 October 2026 at 17:44. 3,441 cases (premises)
in the UK this season (England 2,895, Wales 492, Scotland 54, Northern Ireland 0), counts to midnight on
21 October; 46 potential cases under investigation; county and local authority tables (64 rows). The
weekly series comes from the page's daily update notes: since 3 August they add up to 3,193 cases.
The notes start on 31 July and a few give no date or repeat a day, so the weekly figures may differ
slightly from the official totals; the site says so. Each run stores a dated snapshot of the totals, so
exact weekly differences can replace the parsed notes once a few weeks of snapshots exist.

**GOV.UK bird flu: live.** The old /government/news address is a redirect record; the adapter follows
it to /guidance/... as the alert Worker does. Two cases this season: H5N5 at Ness, Isle of Lewis
(AIV 2026/20, 2 October) and H5N1 near Belford, Northumberland (AIV 2026/21, 19 October). Both link to
WAHIS events by case reference (7873 and 7918). Risk: wild birds medium; poultry low or very low by
biosecurity, high uncertainty. The page does not say an AIPZ or housing order is in force; its latest
news on them: AIPZ lifted (4 June 2026), housing measures lifted (2 April 2026). The adapter reports
"not stated as in force", never "no order", because it infers from the page text.

**DAFM Ireland: fallback.** gov.ie's CloudFront returns HTTP 403 to the container (a block page, not
the proxy). The page was read with WebFetch and the table saved to `samples/ie_dafm_bluetongue.json`:
48 herd cases (45 cattle, 3 sheep) in 14 counties, as at 21 October 2026, BTV-3. The page's background
text also mentions Laois, which is not in the table. The live HTML parser is written but untested
against the real page; check its first run from a network gov.ie accepts.

**Ruokavirasto Finland: live.** 70 cases, 71 wild boar (the Finnish column "Kpl" is the number of
animals), latest confirmed 21 October 2026 in Miehikkälä; municipalities Virolahti, Miehikkälä,
Lappeenranta and Pyhtää, placed at their regions (Kymenlaakso, South Karelia).

## Reuse terms

| Source | Terms found | Commercial reuse |
|---|---|---|
| WOAH WAHIS | WAHIS Terms of Use and Conditions (in the WAHIS app's text bundle): "viewing, downloading, storing, reproducing, adapting, translating" granted; name WOAH as the source, indicate changes and show the WOAH disclaimer (shown on the map, Numbers and Data pages). | Not addressed in the WAHIS terms. woah.org's general site terms forbid commercial use without written permission and the use of "data mining, robots, or similar data-gathering and extraction tools". **Ask WOAH** (information.dept@woah.org) before monetised use or scheduled automated reads. |
| FAO EMPRES-i | CC BY 4.0 for "EMPRES-i: Global Animal Disease Events Dashboard" in the FAO catalogue. | Allowed under CC BY 4.0. **But** another FAO catalogue entry for the same data ("Animal diseases events - EMPRES-i") says CC BY-NC-SA 4.0, and FAO's site terms limit commercial use. Confirm with EMPRES-Animal-Health@fao.org. |
| EU ADIS | European Commission reuse policy (Decision 2011/833/EU), CC BY 4.0, credit and indicate changes. | Allowed. |
| GOV.UK | Open Government Licence v3.0. | Allowed with attribution. |
| DAFM (gov.ie) | Irish PSI is generally under the PSI Licence (CC BY 4.0); DAFM's own statement could not be read from the container. | Probably allowed; confirm. |
| Ruokavirasto | "The materials on the page may be used and linked to, but the source of the information must be mentioned. The use of the materials for commercial purposes must always be agreed upon separately with the Finnish Food Authority." | **Restricted.** Needs agreement before commercial use. |
| Natural Earth | Public domain. | Allowed. |
| OpenFreeMap (basemap) | Public instance: free, no registration or API key, no limits on map views or requests. Attribution is required: OpenFreeMap, OpenMapTiles and OpenStreetMap contributors (shown on the map and under Sources). No service guarantee. OpenStreetMap data is under the Open Database Licence. | Allowed ("Yes" on openfreemap.org). If the service is down, the map shows the points on a plain background. |

## Decisions before this goes to main

1. Reuse terms: write to WOAH and FAO about monetised use and scheduled reads, and to Ruokavirasto for
   commercial use, or drop Finland from the public files until agreed.
2. Where the pipeline runs: a weekly scheduled run on a machine gov.ie accepts would also fix the DAFM
   fallback. The editorial hold for UK pig-disease records stays on unless changed in `clean.py`.
3. Public repository: `cache/` is ignored because it holds outbreak points. Keep it that way.

## Known limits

- WAHIS outbreaks are counted by start date from each event's latest report, so recent weeks rise as
  countries report. Events reported only in six-monthly reports are not covered.
- ADIS history starts with the first stored week (15 to 21 October 2026).
- The GOV.UK bluetongue county tables are season totals, so the map shows them only in the week they
  were published.
- `same_as` lists up to 20 ids per row; the linked rows also point back.
- WAHIS can report a cluster of outbreaks as one record (its `clusterCount`). The pipeline counts that
  record as one outbreak at its start date. EMPRES-i may list the detections in a cluster one by one,
  with their own dates, and these do not match the WAHIS record. In this run that is why the HPAI table
  shows 326 reports in wild birds in Australia (311 from EMPRES-i), while the WOAH chart shows 15.
- The map needs WebGL. Without it, the page says so and the table under the map still works.
- Five region centres happen to lie within about 1 km of a reported outbreak. They are the fixed
  Natural Earth label points used for every record in that region, not outbreak locations.
