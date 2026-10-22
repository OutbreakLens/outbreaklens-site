#!/usr/bin/env python3
"""Render a 1200x675 alert map for an X post: one point on an OpenStreetMap basemap,
an OutbreakLens title card, the site's shape-and-colour scheme, and the attribution line.

Usage:
  python3 render_alert_map.py --lat 56.736292 --lon 22.684939 --zoom 7 \
      --category bird-flu --host wild \
      --title "Latvia: HPAI (bird flu) in wild birds" \
      --sub "Remte parish, Saldus. 4 wild ducks. Reported to WOAH 22 Oct 2026" \
      --source "WOAH WAHIS event 7929, location as reported" \
      --out latvia_7929.png

Shape = the animals affected (circle domestic, triangle wild, square both or not stated).
Colour = the disease, the same palette as outbreaklens.com/map.
Basemap: OpenStreetMap standard tiles. Low volume only, with a named User-Agent, and the
copyright line is printed on the image, as the OSM tile policy asks.
"""
import argparse, json, os, sys, tempfile, time
from pathlib import Path

CATS = {
    "bird-flu": ("#C0532B", "HPAI"), "bluetongue": ("#0a64b2", "Bluetongue"), "asf": ("#943c82", "African swine fever"),
    "fmd": ("#948904", "Foot-and-mouth disease"), "sheep-goat-pox": ("#028f95", "Sheep and goat pox"),
    "lsd": ("#8976cd", "Lumpy skin disease"), "newcastle-disease": ("#1d7724", "Newcastle disease"), "other": ("#5f6875", "Other exotic disease"),
}
HOST_LABEL = {"wild": "Wild animals", "domestic": "Domestic animals", "mixed": "Domestic and wild"}

HTML = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;width:1200px;height:675px;overflow:hidden;background:#FAF7F1;font-family:Inter,system-ui,sans-serif}
  #map{position:absolute;inset:0;width:1200px;height:675px}
  .leaflet-control-container{display:none}
  .card,.key,.attr{z-index:1000}
  .card{position:absolute;left:28px;top:28px;max-width:600px;background:rgba(250,247,241,.96);color:#1F3864;
        border-left:6px solid __COLOUR__;padding:18px 24px 18px 22px;box-shadow:0 6px 22px rgba(31,56,100,.18);border-radius:4px}
  .kicker{font:600 14px/1 Inter,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#C0532B;margin:0 0 10px}
  .title{font:700 34px/1.15 Fraunces,Georgia,serif;margin:0 0 8px;letter-spacing:-.01em}
  .sub{font:500 18px/1.35 Inter,sans-serif;margin:0;color:#2b3f66}
  .key{position:absolute;left:28px;bottom:58px;background:rgba(250,247,241,.96);color:#1F3864;padding:9px 14px;border-radius:4px;
       font:500 15px/1 Inter,sans-serif;display:flex;align-items:center;gap:9px;box-shadow:0 3px 12px rgba(31,56,100,.15)}
  .key svg{width:20px;height:20px}
  .attr{position:absolute;left:0;right:0;bottom:0;background:rgba(31,56,100,.92);color:#FAF7F1;font:400 13px/1.3 Inter,sans-serif;
        padding:8px 28px;display:flex;justify-content:space-between;gap:20px}
  .attr b{font-weight:600}
  .mark{filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
  .pulse{position:absolute;border-radius:50%;border:3px solid __COLOUR__;opacity:.55}
</style></head><body>
<div id="map"></div>
<div class="card"><p class="kicker">OutbreakLens · WAHIS alert</p><p class="title">__TITLE__</p><p class="sub">__SUB__</p></div>
<div class="key">__KEYSVG__<span>__KEYLABEL__ · __DISEASE__</span></div>
<div class="attr"><span><b>Map</b> © OpenStreetMap contributors · <b>Point</b> __SOURCE__</span><span>outbreaklens.com · educational summary of public data, not official advice</span></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const lat = __LAT__, lon = __LON__, zoom = __ZOOM__, colour = "__COLOUR__", host = "__HOST__";
  const map = L.map('map', {zoomControl:false, attributionControl:false, fadeAnimation:false, zoomAnimation:false});
  map.setView([lat, lon], zoom);
  let loaded = 0, total = 0;
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, crossOrigin: true});
  tiles.on('tileloadstart', () => total++); tiles.on('tileload tileerror', () => loaded++);
  tiles.addTo(map);
  const shape = host === 'wild' ? '<polygon points="22,4 41,38 3,38"/>' : host === 'domestic' ? '<circle cx="22" cy="22" r="16"/>' : '<rect x="7" y="7" width="30" height="30"/>';
  const icon = L.divIcon({className:'', iconSize:[44,44], iconAnchor:[22,22],
    html:'<svg class="mark" viewBox="0 0 44 44" width="44" height="44"><g fill="'+colour+'" stroke="#fff" stroke-width="3" stroke-linejoin="round">'+shape+'</g></svg>'});
  L.marker([lat, lon], {icon}).addTo(map);
  L.circleMarker([lat, lon], {radius: 34, color: colour, weight: 3, fill: false, opacity: .45}).addTo(map);
  window.__ready = () => total > 0 && loaded >= total;
</script></body></html>"""

KEY_SHAPES = {
    "wild": '<svg viewBox="0 0 22 22"><polygon points="11,3.4 19.75,18.6 2.25,18.6" fill="__C__"/></svg>',
    "domestic": '<svg viewBox="0 0 22 22"><circle cx="11" cy="11" r="6.5" fill="__C__"/></svg>',
    "mixed": '<svg viewBox="0 0 22 22"><rect x="5.3" y="5.3" width="11.4" height="11.4" fill="__C__"/></svg>',
}

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True); ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--zoom", type=int, default=7)
    ap.add_argument("--category", default="other", choices=sorted(CATS)); ap.add_argument("--host", default="mixed", choices=sorted(HOST_LABEL))
    ap.add_argument("--title", required=True); ap.add_argument("--sub", default=""); ap.add_argument("--source", default="WOAH WAHIS")
    ap.add_argument("--out", required=True); ap.add_argument("--scale", type=float, default=2.0)
    a = ap.parse_args()
    colour, disease = CATS[a.category]
    html = (HTML.replace("__COLOUR__", colour).replace("__TITLE__", esc(a.title)).replace("__SUB__", esc(a.sub))
            .replace("__SOURCE__", esc(a.source)).replace("__KEYSVG__", KEY_SHAPES[a.host].replace("__C__", colour))
            .replace("__KEYLABEL__", HOST_LABEL[a.host]).replace("__DISEASE__", disease)
            .replace("__LAT__", repr(a.lat)).replace("__LON__", repr(a.lon)).replace("__ZOOM__", str(a.zoom)).replace("__HOST__", a.host))
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as td:
        page_path = Path(td, "alert.html"); page_path.write_text(html, encoding="utf-8")
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 1200, "height": 675}, device_scale_factor=a.scale,
                                user_agent="OutbreakLens alert renderer/1.0 (hello@outbreaklens.com)")
            pg = ctx.new_page()
            pg.goto(page_path.as_uri(), wait_until="load")
            for _ in range(60):
                if pg.evaluate("window.__ready && window.__ready()"): break
                time.sleep(0.25)
            pg.evaluate("document.fonts.ready"); time.sleep(0.6)
            pg.screenshot(path=a.out, type="png")
            b.close()
    print(a.out, os.path.getsize(a.out), "bytes")

if __name__ == "__main__":
    main()
