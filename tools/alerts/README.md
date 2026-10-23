# Alert map renderer

`render_alert_map.py` draws a map image for an OutbreakLens alert post: one point on the same calm
basemap as outbreaklens.com/map (MapLibre GL with OpenFreeMap's Positron style), a title card with an
optional big number, the site's shape-and-colour key (circle domestic, triangle wild, square both or
not stated, colour by disease) and the attribution line.

Formats (`--format`): `x` 1200 x 675 (X, and Instagram landscape), `feed` 1080 x 1350 (Instagram
4:5, the most screen space in the feed), `story` 1080 x 1920 (Instagram and TikTok stories, with the
top and bottom safe zones kept clear). Type: Montserrat ExtraBold for the title and the number, Inter
for everything else.

Keep the text short: a title of about six words, one number with its noun (`--stat "4 wild ducks"`,
`--stat "1,166 cases"`, `--stat "16 holdings"`), and a sub line of about eight words. Use the count the
source gives as cases, deaths or holdings, never the number of animals at risk on its own.

It needs Python 3 with Playwright and Chromium (`pip install playwright && playwright install chromium`).
It loads MapLibre from cdnjs and the basemap from tiles.openfreemap.org, so it needs the network. It
renders WebGL in software, so no GPU is needed. If WebGL is unavailable it falls back to Leaflet with
OpenStreetMap's standard tiles (`--basemap osm` forces this).

```
python3 -I tools/alerts/render_alert_map.py --lat 56.736292 --lon 22.684939 --zoom 7 \
  --category bird-flu --host wild --format feed \
  --title "Latvia: bird flu in wild birds" --stat "4 wild ducks" \
  --sub "Saldus region. Reported to WOAH 22 Oct 2026." \
  --source "WOAH WAHIS event 7929, location as reported" --out latvia_7929_feed.png
```

Categories: bird-flu, bluetongue, asf, fmd, sheep-goat-pox, lsd, newcastle-disease, other.
Hosts: wild, domestic, mixed. Zoom 6 shows a country and its neighbours, 7 a region, 8 a county.
Zoom is capped at 8, as on the site, so a point never reads as an address.

Points are plotted as the source reports them. WAHIS gives outbreak coordinates at the
resolution the reporting country chose. Never plot a premises the source has not published.

Credits printed on every image: OpenFreeMap, OpenMapTiles and OpenStreetMap contributors (or
OpenStreetMap contributors alone on the fallback). The fallback follows the OSM tile policy: low
volume, a named User-Agent and the copyright line on the image.
