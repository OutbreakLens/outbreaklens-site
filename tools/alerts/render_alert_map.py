#!/usr/bin/env python3
"""Render an alert map image for a social post: one point on an OpenStreetMap basemap, an
OutbreakLens title card, the site's shape-and-colour key, and the attribution line.

Formats (--format): x (1200 x 675, X and Instagram landscape), feed (1080 x 1350, Instagram 4:5),
story (1080 x 1920, Instagram and TikTok stories, with the top and bottom safe zones kept clear).

Usage:
  python3 render_alert_map.py --lat 56.736292 --lon 22.684939 --zoom 7 \
      --category bird-flu --host wild --format feed \
      --title "Latvia: HPAI (bird flu) in wild birds" \
      --sub "Remte parish, Saldus. 4 wild ducks. Reported to WOAH 22 Oct 2026" \
      --source "WOAH WAHIS event 7929, location as reported" \
      --out latvia_7929_feed.png

Shape = the animals affected (circle domestic, triangle wild, square both or not stated).
Colour = the disease, the same palette as outbreaklens.com/map.
Type: Montserrat ExtraBold for the title, Inter for everything else (the house pairing from 23 Oct 2026).
Basemap: OpenStreetMap standard tiles. Low volume only, with a named User-Agent, and the
copyright line is printed on the image, as the OSM tile policy asks.
"""
import argparse, os, tempfile, time
from pathlib import Path

CATS = {
    "bird-flu": ("#C0532B", "HPAI"), "bluetongue": ("#0a64b2", "Bluetongue"), "asf": ("#943c82", "African swine fever"),
    "fmd": ("#948904", "Foot-and-mouth disease"), "sheep-goat-pox": ("#028f95", "Sheep and goat pox"),
    "lsd": ("#8976cd", "Lumpy skin disease"), "newcastle-disease": ("#1d7724", "Newcastle disease"), "other": ("#5f6875", "Other exotic disease"),
}
HOST_LABEL = {"wild": "Wild animals", "domestic": "Domestic animals", "mixed": "Domestic and wild"}

# width, height, card font sizes (kicker, title, sub), key font, attribution font, edge padding, top and bottom clear zones
FORMATS = {
    "x": dict(w=1200, h=675, kicker=14, title=34, sub=18, key=15, attr=13, pad=28, top=0, bottom=0, cardmax=600),
    "feed": dict(w=1080, h=1350, kicker=18, title=46, sub=24, key=20, attr=16, pad=40, top=0, bottom=0, cardmax=1000),
    "story": dict(w=1080, h=1920, kicker=20, title=52, sub=27, key=22, attr=17, pad=48, top=230, bottom=260, cardmax=984),
}

HTML = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;width:__W__px;height:__H__px;overflow:hidden;background:#FAF7F1;font-family:Inter,system-ui,sans-serif}
  #map{position:absolute;left:0;top:0;width:__W__px;height:__H__px}
  .leaflet-control-container{display:none}
  .card,.key,.attr,.band{z-index:1000}
  .band{position:absolute;left:0;right:0;background:#1F3864}
  .band.top{top:0;height:__TOP__px}
  .band.bottom{bottom:0;height:__BOTTOM__px}
  .card{position:absolute;left:__PAD__px;top:calc(__TOP__px + __PAD__px);max-width:__CARDMAX__px;background:rgba(250,247,241,.96);color:#1F3864;
        border-left:8px solid __COLOUR__;padding:calc(__PAD__px * .65) calc(__PAD__px * .85) calc(__PAD__px * .65) calc(__PAD__px * .8);
        box-shadow:0 8px 26px rgba(31,56,100,.2);border-radius:6px}
  .kicker{font:700 __KICKER__px/1 Inter,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#C0532B;margin:0 0 .6em}
  .title{font:800 __TITLE__px/1.12 Montserrat,Inter,sans-serif;margin:0 0 .3em;letter-spacing:-.015em}
  .sub{font:500 __SUB__px/1.35 Inter,sans-serif;margin:0;color:#2b3f66}
  .key{position:absolute;left:__PAD__px;bottom:calc(__BOTTOM__px + __ATTRH__px + __PAD__px);background:rgba(250,247,241,.96);color:#1F3864;
       padding:.6em .9em;border-radius:6px;font:600 __KEY__px/1 Inter,sans-serif;display:flex;align-items:center;gap:.6em;box-shadow:0 3px 12px rgba(31,56,100,.15)}
  .key svg{width:1.35em;height:1.35em}
  .attr{position:absolute;left:0;right:0;bottom:__BOTTOM__px;min-height:__ATTRH__px;background:rgba(31,56,100,.94);color:#FAF7F1;
        font:400 __ATTR__px/1.35 Inter,sans-serif;padding:.6em __PAD__px;display:flex;justify-content:space-between;gap:1.5em;flex-wrap:wrap;align-items:center}
  .attr b{font-weight:600}
  .mark{filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
  .brand{position:absolute;right:__PAD__px;top:calc(__TOP__px + __PAD__px);z-index:1000;background:#1F3864;color:#FAF7F1;border-radius:6px;
         padding:.5em .8em;font:800 __KICKER__px/1 Montserrat,Inter,sans-serif;letter-spacing:.02em}
  .brand i{color:#E8875F;font-style:normal}
</style></head><body>
<div id="map"></div>
<div class="band top"></div><div class="band bottom"></div>
<div class="card"><p class="kicker">WAHIS alert</p><p class="title">__TITLE_TEXT__</p><p class="sub">__SUB__</p></div>
<div class="brand">Outbreak<i>Lens</i></div>
<div class="key">__KEYSVG__<span>__KEYLABEL__ · __DISEASE__</span></div>
<div class="attr"><span><b>Map</b> © OpenStreetMap contributors · <b>Point</b> __SOURCE__</span><span>outbreaklens.com · educational summary of public data, not official advice</span></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const lat = __LAT__, lon = __LON__, zoom = __ZOOM__, colour = "__COLOUR__", host = "__HOST__";
  const map = L.map('map', {zoomControl:false, attributionControl:false, fadeAnimation:false, zoomAnimation:false});
  map.setView([lat, lon], zoom);
  // Shift the view so the point sits in the clear part of the frame, below the card and above the key.
  const topClear = __TOP__ + __PAD__ * 2 + __TITLE__ * 4, bottomClear = __BOTTOM__ + __ATTRH__ + __PAD__ * 2 + __KEY__ * 3;
  const centreY = (topClear + (__H__ - bottomClear)) / 2;
  map.panBy([0, centreY - __H__ / 2], {animate:false});
  let loaded = 0, total = 0;
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, crossOrigin: true});
  tiles.on('tileloadstart', () => total++); tiles.on('tileload tileerror', () => loaded++);
  tiles.addTo(map);
  const s = __MARK__;
  const shape = host === 'wild' ? '<polygon points="22,4 41,38 3,38"/>' : host === 'domestic' ? '<circle cx="22" cy="22" r="16"/>' : '<rect x="7" y="7" width="30" height="30"/>';
  const icon = L.divIcon({className:'', iconSize:[s,s], iconAnchor:[s/2,s/2],
    html:'<svg class="mark" viewBox="0 0 44 44" width="'+s+'" height="'+s+'"><g fill="'+colour+'" stroke="#fff" stroke-width="3" stroke-linejoin="round">'+shape+'</g></svg>'});
  L.marker([lat, lon], {icon}).addTo(map);
  L.circleMarker([lat, lon], {radius: s * 0.8, color: colour, weight: 3, fill: false, opacity: .45}).addTo(map);
  window.__ready = () => total > 0 && loaded >= total;
</script></body></html>"""

KEY_SHAPES = {
    "wild": '<svg viewBox="0 0 22 22"><polygon points="11,3.4 19.75,18.6 2.25,18.6" fill="__C__"/></svg>',
    "domestic": '<svg viewBox="0 0 22 22"><circle cx="11" cy="11" r="6.5" fill="__C__"/></svg>',
    "mixed": '<svg viewBox="0 0 22 22"><rect x="5.3" y="5.3" width="11.4" height="11.4" fill="__C__"/></svg>',
}

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build_html(a):
    f = FORMATS[a.format]
    colour, disease = CATS[a.category]
    attr_h = round(f["attr"] * 3.2)
    mark = 44 if a.format == "x" else 56
    reps = {
        "__W__": str(f["w"]), "__H__": str(f["h"]), "__TOP__": str(f["top"]), "__BOTTOM__": str(f["bottom"]), "__PAD__": str(f["pad"]),
        "__CARDMAX__": str(f["cardmax"]), "__KICKER__": str(f["kicker"]), "__TITLE__": str(f["title"]), "__SUB__": esc(a.sub),
        "__KEY__": str(f["key"]), "__ATTR__": str(f["attr"]), "__ATTRH__": str(attr_h), "__MARK__": str(mark),
        "__COLOUR__": colour, "__TITLE_TEXT__": esc(a.title), "__SOURCE__": esc(a.source),
        "__KEYSVG__": KEY_SHAPES[a.host].replace("__C__", colour), "__KEYLABEL__": HOST_LABEL[a.host], "__DISEASE__": disease,
        "__LAT__": repr(a.lat), "__LON__": repr(a.lon), "__ZOOM__": str(a.zoom), "__HOST__": a.host,
    }
    html = HTML
    # Longest keys first, so __TITLE_TEXT__ is replaced before __TITLE__.
    for k in sorted(reps, key=len, reverse=True):
        html = html.replace(k, reps[k])
    return html, f

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True); ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--zoom", type=int, default=7)
    ap.add_argument("--category", default="other", choices=sorted(CATS)); ap.add_argument("--host", default="mixed", choices=sorted(HOST_LABEL))
    ap.add_argument("--format", default="x", choices=sorted(FORMATS))
    ap.add_argument("--title", required=True); ap.add_argument("--sub", default=""); ap.add_argument("--source", default="WOAH WAHIS")
    ap.add_argument("--out", required=True); ap.add_argument("--scale", type=float, default=2.0)
    a = ap.parse_args()
    html, f = build_html(a)
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as td:
        page_path = Path(td, "alert.html"); page_path.write_text(html, encoding="utf-8")
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": f["w"], "height": f["h"]}, device_scale_factor=a.scale,
                                user_agent="OutbreakLens alert renderer/1.1 (hello@outbreaklens.com)")
            pg = ctx.new_page()
            pg.goto(page_path.as_uri(), wait_until="load")
            for _ in range(60):
                if pg.evaluate("window.__ready && window.__ready()"): break
                time.sleep(0.25)
            pg.evaluate("document.fonts.ready"); time.sleep(0.8)
            pg.screenshot(path=a.out, type="png")
            b.close()
    print(a.out, os.path.getsize(a.out), "bytes", f["w"] * a.scale, "x", f["h"] * a.scale)

if __name__ == "__main__":
    main()
