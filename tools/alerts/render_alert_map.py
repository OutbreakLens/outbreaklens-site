#!/usr/bin/env python3
"""Render an alert map image for a social post: one point on the same calm basemap as outbreaklens.com/map
(MapLibre GL with OpenFreeMap's Positron style), an OutbreakLens title card, the site's shape-and-colour key,
and the attribution line.

v2 (23 Oct 2026): Positron basemap instead of OpenStreetMap's standard tiles (fewer labels, the site's look,
no tile-policy limits); an optional big --stat line so one number carries the post; shorter text by design.
If the machine cannot run WebGL, it falls back to Leaflet with OpenStreetMap's standard tiles (the v1 look).

Formats (--format): x (1200 x 675, X and Instagram landscape), feed (1080 x 1350, Instagram 4:5),
story (1080 x 1920, Instagram and TikTok stories, with the top and bottom safe zones kept clear).

Usage:
  python3 -I render_alert_map.py --lat 56.736292 --lon 22.684939 --zoom 7 \
      --category bird-flu --host wild --format feed \
      --title "Latvia: bird flu in wild birds" --stat "4 wild ducks" \
      --sub "Saldus region. Reported to WOAH 22 Oct 2026." \
      --source "WOAH WAHIS event 7929, location as reported" --out latvia_7929_feed.png

Shape = the animals affected (circle domestic, triangle wild, square both or not stated).
Colour = the disease, the same palette as outbreaklens.com/map.
Type: Montserrat ExtraBold for the title and the stat, Inter for everything else.
Zoom is capped at 8, as on the site, so a point never reads as an address.
"""
import argparse, os, sys, tempfile, time
from pathlib import Path

CATS = {
    "bird-flu": ("#C0532B", "HPAI"), "bluetongue": ("#0a64b2", "Bluetongue"), "asf": ("#943c82", "African swine fever"),
    "fmd": ("#948904", "Foot-and-mouth disease"), "sheep-goat-pox": ("#028f95", "Sheep and goat pox"),
    "lsd": ("#8976cd", "Lumpy skin disease"), "newcastle-disease": ("#1d7724", "Newcastle disease"), "other": ("#5f6875", "Other exotic disease"),
}
HOST_LABEL = {"wild": "Wild animals", "domestic": "Domestic animals", "mixed": "Domestic and wild"}

# width, height, card font sizes (kicker, title, stat, sub), key font, attribution font, edge padding, top and bottom clear zones
FORMATS = {
    "x": dict(w=1200, h=675, kicker=14, title=36, stat=46, sub=18, key=15, attr=13, pad=28, top=0, bottom=0, cardmax=620),
    "feed": dict(w=1080, h=1350, kicker=18, title=50, stat=72, sub=24, key=20, attr=16, pad=40, top=0, bottom=0, cardmax=1000),
    "story": dict(w=1080, h=1920, kicker=20, title=56, stat=84, sub=27, key=22, attr=17, pad=48, top=230, bottom=260, cardmax=984),
}

BASEMAPS = {
    "positron": dict(
        head='<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/5.24.0/maplibre-gl.css">',
        credit="© OpenFreeMap © OpenMapTiles © OpenStreetMap contributors",
        script="""<script src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/5.24.0/maplibre-gl.js"></script>
<script>
  const c = document.createElement('canvas');
  if (!(c.getContext('webgl2') || c.getContext('webgl'))) { window.__nowebgl = true; }
  else {
    const map = new maplibregl.Map({container: 'map', style: 'https://tiles.openfreemap.org/styles/positron', center: [LON, LAT], zoom: ZOOM,
      interactive: false, attributionControl: false, fadeDuration: 0, canvasContextAttributes: {preserveDrawingBuffer: true}});
    map.jumpTo({center: [LON, LAT], zoom: ZOOM, padding: {top: TOPCLEAR, bottom: BOTTOMCLEAR, left: 0, right: 0}});
    new maplibregl.Marker({element: markerEl(), anchor: 'center'}).setLngLat([LON, LAT]).addTo(map);
    map.on('error', e => { window.__err = String(e && e.error && e.error.message || e); });
    map.once('idle', () => { window.__idle = true; });
  }
</script>"""),
    "osm": dict(
        head='<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">',
        credit="© OpenStreetMap contributors",
        script="""<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const map = L.map('map', {zoomControl:false, attributionControl:false, fadeAnimation:false, zoomAnimation:false});
  map.setView([LAT, LON], ZOOM);
  map.panBy([0, (TOPCLEAR - BOTTOMCLEAR) / -2], {animate:false});
  let loaded = 0, total = 0;
  const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, crossOrigin: true});
  tiles.on('tileloadstart', () => total++); tiles.on('tileload tileerror', () => { loaded++; if (total > 0 && loaded >= total) window.__idle = true; });
  tiles.addTo(map);
  const s = MARK;
  L.marker([LAT, LON], {icon: L.divIcon({className: '', iconSize: [s, s], iconAnchor: [s / 2, s / 2], html: markerEl().outerHTML})}).addTo(map);
</script>"""),
}

HTML = """<!doctype html><html><head><meta charset="utf-8">
__MAPHEAD__
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;width:__W__px;height:__H__px;overflow:hidden;background:#FAF7F1;font-family:Inter,system-ui,sans-serif}
  #map{position:absolute;left:0;top:0;width:__W__px;height:__H__px}
  .maplibregl-ctrl-attrib,.maplibregl-ctrl-logo,.leaflet-control-container{display:none!important}
  .card,.key,.attr,.band,.brand{z-index:1000}
  .band{position:absolute;left:0;right:0;background:#1F3864}
  .band.top{top:0;height:__TOP__px}
  .band.bottom{bottom:0;height:__BOTTOM__px}
  .card{position:absolute;left:__PAD__px;top:calc(__TOP__px + __PAD__px);max-width:__CARDMAX__px;background:rgba(250,247,241,.97);color:#1F3864;
        border-left:8px solid __COLOUR__;padding:calc(__PAD__px * .65) calc(__PAD__px * .85) calc(__PAD__px * .65) calc(__PAD__px * .8);
        box-shadow:0 8px 26px rgba(31,56,100,.18);border-radius:6px}
  .kicker{font:700 __KICKER__px/1 Inter,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#C0532B;margin:0 0 .6em}
  .title{font:800 __TITLE__px/1.1 Montserrat,Inter,sans-serif;margin:0;letter-spacing:-.015em}
  .stat{font:800 __STAT__px/1.05 Montserrat,Inter,sans-serif;margin:.22em 0 0;color:__COLOUR__;letter-spacing:-.02em}
  .sub{font:500 __SUB__px/1.35 Inter,sans-serif;margin:.55em 0 0;color:#2b3f66}
  .key{position:absolute;left:__PAD__px;bottom:calc(__BOTTOM__px + __ATTRH__px + __PAD__px);background:rgba(250,247,241,.97);color:#1F3864;
       padding:.6em .9em;border-radius:6px;font:600 __KEY__px/1 Inter,sans-serif;display:flex;align-items:center;gap:.6em;box-shadow:0 3px 12px rgba(31,56,100,.15)}
  .key svg{width:1.35em;height:1.35em}
  .attr{position:absolute;left:0;right:0;bottom:__BOTTOM__px;min-height:__ATTRH__px;background:rgba(31,56,100,.94);color:#FAF7F1;
        font:400 __ATTR__px/1.35 Inter,sans-serif;padding:.6em __PAD__px;display:flex;justify-content:space-between;gap:1.5em;flex-wrap:wrap;align-items:center;box-sizing:border-box}
  .attr b{font-weight:600}
  .brand{position:absolute;right:__PAD__px;top:calc(__TOP__px + __PAD__px);background:#1F3864;color:#FAF7F1;border-radius:6px;
         padding:.5em .8em;font:800 __KICKER__px/1 Montserrat,Inter,sans-serif;letter-spacing:.02em}
  .brand i{color:#E8875F;font-style:normal}
  .mk{position:relative;width:__MARK__px;height:__MARK__px}
  .mk svg{position:absolute;left:0;top:0;width:100%;height:100%;filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
  .mk .ring{position:absolute;left:50%;top:50%;width:__RING__px;height:__RING__px;margin:calc(__RING__px / -2) 0 0 calc(__RING__px / -2);
            border:3px solid __COLOUR__;border-radius:50%;opacity:.45;box-sizing:border-box}
</style></head><body>
<div id="map"></div>
<div class="band top"></div><div class="band bottom"></div>
<div class="card"><p class="kicker">__KICKER_TEXT__</p><p class="title">__TITLE_TEXT__</p>__STAT_HTML____SUB_HTML__</div>
<div class="brand">Outbreak<i>Lens</i></div>
<div class="key">__KEYSVG__<span>__KEYLABEL__ · __DISEASE__</span></div>
<div class="attr"><span><b>Map</b> __CREDIT__ · <b>Point</b> __SOURCE__</span><span>outbreaklens.com · educational summary of public data, not official advice</span></div>
<script>
  window.__idle = false; window.__err = null; window.__nowebgl = false;
  function markerEl() {
    const host = "__HOST__";
    const shape = host === 'wild' ? '<polygon points="22,4 41,38 3,38"/>' : host === 'domestic' ? '<circle cx="22" cy="22" r="16"/>' : '<rect x="7" y="7" width="30" height="30"/>';
    const el = document.createElement('div'); el.className = 'mk';
    el.innerHTML = '<div class="ring"></div><svg viewBox="0 0 44 44"><g fill="__COLOUR__" stroke="#fff" stroke-width="3" stroke-linejoin="round">' + shape + '</g></svg>';
    return el;
  }
</script>
__MAPSCRIPT__
</body></html>"""

KEY_SHAPES = {
    "wild": '<svg viewBox="0 0 22 22"><polygon points="11,3.4 19.75,18.6 2.25,18.6" fill="__C__"/></svg>',
    "domestic": '<svg viewBox="0 0 22 22"><circle cx="11" cy="11" r="6.5" fill="__C__"/></svg>',
    "mixed": '<svg viewBox="0 0 22 22"><rect x="5.3" y="5.3" width="11.4" height="11.4" fill="__C__"/></svg>',
}

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build_html(a, basemap):
    f = FORMATS[a.format]
    bm = BASEMAPS[basemap]
    colour, disease = CATS[a.category]
    attr_h = round(f["attr"] * 3.2)
    mark = 44 if a.format == "x" else 56
    # Rough height of the card, used to keep the point clear of it.
    card_h = f["kicker"] * 1.6 + f["title"] * 1.1 * 2 + (f["stat"] * 1.3 if a.stat else 0) + (f["sub"] * 1.35 * 1.5 if a.sub else 0) + f["pad"] * 1.3
    top_clear = f["top"] + f["pad"] * 2 + card_h
    bottom_clear = f["bottom"] + attr_h + f["pad"] * 2 + f["key"] * 3
    script = (bm["script"].replace("LAT", repr(a.lat)).replace("LON", repr(a.lon)).replace("ZOOM", str(min(a.zoom, 8)))
              .replace("TOPCLEAR", str(round(top_clear))).replace("BOTTOMCLEAR", str(round(bottom_clear))).replace("MARK", str(mark)))
    reps = {
        "__W__": str(f["w"]), "__H__": str(f["h"]), "__TOP__": str(f["top"]), "__BOTTOM__": str(f["bottom"]), "__PAD__": str(f["pad"]),
        "__CARDMAX__": str(f["cardmax"]), "__KICKER__": str(f["kicker"]), "__TITLE__": str(f["title"]), "__STAT__": str(f["stat"]),
        "__SUB__": str(f["sub"]), "__KEY__": str(f["key"]), "__ATTR__": str(f["attr"]), "__ATTRH__": str(attr_h),
        "__MARK__": str(mark), "__RING__": str(round(mark * 1.9)),
        "__COLOUR__": colour, "__TITLE_TEXT__": esc(a.title), "__KICKER_TEXT__": esc(a.kicker), "__SOURCE__": esc(a.source),
        "__STAT_HTML__": f'<p class="stat">{esc(a.stat)}</p>' if a.stat else "",
        "__SUB_HTML__": f'<p class="sub">{esc(a.sub)}</p>' if a.sub else "",
        "__KEYSVG__": KEY_SHAPES[a.host].replace("__C__", colour), "__KEYLABEL__": HOST_LABEL[a.host], "__DISEASE__": disease,
        "__HOST__": a.host, "__CREDIT__": esc(bm["credit"]), "__MAPHEAD__": bm["head"],
    }
    html = HTML
    # Longest keys first, so __TITLE_TEXT__ is replaced before __TITLE__. The map script goes in last, untouched.
    for k in sorted(reps, key=len, reverse=True):
        html = html.replace(k, reps[k])
    return html.replace("__MAPSCRIPT__", script), f

def render(a, basemap):
    """Returns True when the basemap finished loading and the PNG was written."""
    html, f = build_html(a, basemap)
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as td:
        page_path = Path(td, "alert.html"); page_path.write_text(html, encoding="utf-8")
        with sync_playwright() as p:
            # Software WebGL, so the vector basemap renders on machines without a GPU.
            b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            try:
                ctx = b.new_context(viewport={"width": f["w"], "height": f["h"]}, device_scale_factor=a.scale,
                                    user_agent="OutbreakLens alert renderer/2.0 (hello@outbreaklens.com)")
                pg = ctx.new_page()
                pg.goto(page_path.as_uri(), wait_until="load")
                for _ in range(120):
                    if pg.evaluate("window.__idle === true || window.__nowebgl === true"): break
                    time.sleep(0.25)
                if not pg.evaluate("window.__idle === true"):
                    print(f"{basemap} basemap did not load (webgl off: {pg.evaluate('window.__nowebgl')}, "
                          f"error: {pg.evaluate('window.__err')})", file=sys.stderr)
                    return False
                pg.evaluate("document.fonts.ready"); time.sleep(0.8)
                pg.screenshot(path=a.out, type="png")
            finally:
                b.close()
    print(a.out, os.path.getsize(a.out), "bytes", f["w"] * a.scale, "x", f["h"] * a.scale, "basemap", basemap)
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True); ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--zoom", type=int, default=7)
    ap.add_argument("--category", default="other", choices=sorted(CATS)); ap.add_argument("--host", default="mixed", choices=sorted(HOST_LABEL))
    ap.add_argument("--format", default="x", choices=sorted(FORMATS))
    ap.add_argument("--title", required=True); ap.add_argument("--stat", default="")
    ap.add_argument("--sub", default=""); ap.add_argument("--kicker", default="WAHIS alert")
    ap.add_argument("--source", default="WOAH WAHIS")
    ap.add_argument("--basemap", default="positron", choices=sorted(BASEMAPS))
    ap.add_argument("--out", required=True); ap.add_argument("--scale", type=float, default=2.0)
    a = ap.parse_args()
    if render(a, a.basemap):
        return
    if a.basemap != "osm" and render(a, "osm"):
        return
    raise SystemExit("Could not render the map image.")

if __name__ == "__main__":
    main()
