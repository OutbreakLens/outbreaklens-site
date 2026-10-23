# Alert map renderer

`render_alert_map.py` draws a map image for an OutbreakLens alert post: one point on an
OpenStreetMap basemap, a title card, the site's shape-and-colour key (circle domestic, triangle
wild, square both or not stated, colour by disease) and the attribution line.

Formats (`--format`): `x` 1200 x 675 (X, and Instagram landscape), `feed` 1080 x 1350 (Instagram
4:5, the most screen space in the feed), `story` 1080 x 1920 (Instagram and TikTok stories, with the
top and bottom safe zones kept clear). Type: Montserrat ExtraBold titles, Inter for everything else,
the house pairing for every image, short and episode from 23 October 2026.

It needs Python 3 with Playwright and Chromium (`pip install playwright && playwright install chromium`).
It loads Leaflet from unpkg and tiles from tile.openstreetmap.org, so it needs the network.

```
python3 tools/alerts/render_alert_map.py --lat 56.736292 --lon 22.684939 --zoom 7 \
  --category bird-flu --host wild --format feed \
  --title "Latvia: HPAI (bird flu) in wild birds" \
  --sub "Remte parish, Saldus. Four wild ducks found by active surveillance. Reported to WOAH 22 Oct 2026." \
  --source "WOAH WAHIS event 7929, location as reported" --out latvia_7929.png
```

Categories: bird-flu, bluetongue, asf, fmd, sheep-goat-pox, lsd, newcastle-disease, other.
Hosts: wild, domestic, mixed. Zoom 6 shows a country and its neighbours, 7 a region, 8 a county.

Points are plotted as the source reports them. WAHIS gives outbreak coordinates at the
resolution the reporting country chose. Never plot a premises the source has not published.

The OSM tile policy asks for low volume and a named User-Agent, and for the copyright line to
appear on the image. The script does both. A few images a day is fine. Bulk rendering is not.
