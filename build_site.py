#!/usr/bin/env python3
"""
build_site.py: generate the OutbreakLens static website.

Static HTML and CSS, no build step, drops straight into Cloudflare Pages.
Pulls the latest map, report and cleaned data from the pipeline outputs so the
site refreshes itself each week.

    python build_site.py              # uses pipeline/outputs next to this script if present
    python build_site.py --prelaunch  # holding site with no report data

The home-page hero is a dot-matrix world map written as inline SVG. Land comes
from Natural Earth (public domain). The computed dots are cached in
hero_dots.json next to this script, so the network is needed only once. Delete
that file to recompute it. With no cache and no network the hero falls back to
an abstract ring graphic.

The Watch section has one page per short, built from SHORTS below. Each cover
comes from content/shorts/<slug>/cover.png next to this script and is resized
once (with Pillow) to cover-540.jpg in the same folder. Delete cover-540.jpg to
remake it after a new cover. The build also writes sitemap.xml and robots.txt.
"""
import os, re, json, shutil, sys, hashlib, datetime as dt
from html import escape

# python build_site.py --prelaunch  -> holding site with no report data (used until the first real report)
PRELAUNCH = "--prelaunch" in sys.argv
CONTACT_EMAIL = "hello@outbreaklens.com"
BEEHIIV_EMBED = ('<script async src="https://subscribe-forms.beehiiv.com/v3/loader.js" '
                 'data-beehiiv-form="a3ac8168-313d-47c9-aed9-3ebd85269b2c"></script>')
SOCIAL = [("YouTube", "https://www.youtube.com/@outbreaklens"),
          ("TikTok", "https://www.tiktok.com/@outbreaklens"),
          ("Instagram", "https://www.instagram.com/outbreaklens")]
X_URL = "https://x.com/OutbreakWeekly"   # listed in the footer with the other platforms
SITE_URL = "https://outbreaklens.com"    # live address, used for absolute links (share image, canonical, sitemap)
KOFI_URL = "https://ko-fi.com/outbreaklens"
CF_ANALYTICS_TOKEN = ""   # Cloudflare Web Analytics site token. Empty means no beacon is added.
NEWSLETTER_LATEST = ("https://outbreaklens.beehiiv.com/p/bird-flu-is-back-and-bluetongue-passes-3400-cases",
                     "Issue 1, from Friday 23 October 2026")   # beehiiv publishes it on Friday at 07:00
DISCLAIMER = ("OutbreakLens is an educational summary of public data, made in a personal capacity. "
              "It is not veterinary, trade or official advice, and it is not affiliated with or endorsed by "
              "any government body. Always check the primary source.")

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "website")
ASSETS = os.path.join(SITE, "assets")
PIPE = os.path.join(ROOT, "pipeline", "outputs")
BRAND_DIR = os.path.join(ROOT, "brand", "final")   # optional: final favicons and share image
SHORTS_DIR = os.path.join(ROOT, "content", "shorts")   # cover.png for each short, in a folder named by its slug
NAV = [("index.html","Home"),("weekly.html","Weekly"),("watch.html","Watch"),("data.html","Data"),
       ("sources.html","Sources"),("about.html","About"),("subscribe.html","Subscribe")]
TODAY = dt.date.today()
YEAR = TODAY.year
YOUTUBE = SOCIAL[0][1]

# ---------- shorts: one entry per short, newest first ----------
# Each gets a page at shorts/<slug>.html, a card on the home and Watch pages and a VideoObject.
# Every figure needs a named source and date. Never name or locate a farm or premises.
# Text is plain (it also goes into JSON-LD). "keepers" items may hold links, written as [text](url).
SHORTS = [
    {
        "slug": "02-bluetongue-mapped",
        "title": "Bluetongue in Britain: 3,436 cases mapped",
        "video_title": "Bluetongue in Britain: 3,436 cases mapped, and what the restricted zone means",
        "topic": "Bluetongue",
        "as_at": "21 October 2026", "as_at_short": "21 Oct 2026",
        "uploaded": "2026-10-22", "seconds": 97, "youtube_id": "y2GAfATVBzc",
        "lead": "A 97-second tour of the official case map and zone map, and what the restricted zone means for moving animals.",
        "summary": "3,436 cases since 10 July, a restricted zone across England, Wales and Scotland, and what it means for moving animals.",
        "description": ("Bluetongue in Britain, mapped: 3,436 cases confirmed since 10 July (England 2,890, Wales 492, "
                        "Scotland 54, Northern Ireland 0), the whole of England, Wales and Scotland in a restricted zone, "
                        "and what the zone rules mean for moving animals. Figures as at 21 October 2026."),
        "meta": ("Bluetongue in Britain: 3,436 cases since 10 July, mapped, and what the restricted zone means "
                 "for moving animals. Figures as at 21 October 2026."),
        "copies": [("YouTube", "https://www.youtube.com/shorts/y2GAfATVBzc"),
                   ("TikTok", "https://www.tiktok.com/@outbreaklens/video/7699442004844907798"),
                   ("Instagram", "https://www.instagram.com/reel/Dey0K4BS3ZV/"),
                   ("X", "https://x.com/OutbreakWeekly/status/2113228054772453599")],
        "numbers": [("3,436", "cases confirmed in Great Britain since 10 July 2026. A case is a premises where bluetongue was confirmed."),
                    ("2,890", "in England"), ("492", "in Wales"), ("54", "in Scotland"), ("0", "in Northern Ireland"),
                    ("BTV-3", "where the serotype is known. No BTV-8 this season."),
                    ("3 Oct 2026", "Scotland joined the restricted zone. All of England, Wales and Scotland is now in it."),
                    ("56", "potential cases under investigation in Great Britain")],
        "numbers_note": ("Source: GOV.UK, Bluetongue: latest situation, updated 21 October 2026. Counts run to midnight "
                         "on 20 October. The official case map updates separately."),
        "keepers": ["You can move animals within England without a specific bluetongue licence or a pre-movement test.",
                    "Moves between England and Wales need no vaccination or extra measures.",
                    "In Scotland, check the movement controls and apply for a licence where you need one.",
                    "Midges have been active since 31 March 2026. In many parts of the UK it is still warm enough "
                    "for the virus to develop inside them.",
                    "Watch for fever, a swollen head or muzzle, drooling and nasal discharge. Report suspicion to APHA. "
                    "The phone numbers are on [Bluetongue: how to spot and report it](https://www.gov.uk/guidance/bluetongue).",
                    "Defra has urged keepers to consider vaccination. Read the [official BTV-3 vaccination guidance]"
                    "(https://www.gov.uk/guidance/bluetongue-serotype-3-btv-3-vaccination) and talk to your vet.",
                    "Daily counts show when a case was confirmed, not when the animal was infected.",
                    "Bluetongue does not affect people or food safety."],
        "sources": [("GOV.UK, Bluetongue: latest situation", "updated 21 October 2026",
                     "https://www.gov.uk/guidance/bluetongue-latest-situation"),
                    ("GOV.UK, Bluetongue: how to spot and report it", "updated 21 October 2026",
                     "https://www.gov.uk/guidance/bluetongue"),
                    ("GOV.UK, Bluetongue serotype 3 (BTV-3) vaccination", "updated 15 September 2026",
                     "https://www.gov.uk/guidance/bluetongue-serotype-3-btv-3-vaccination"),
                    ("Defra, Livestock keepers urged to be on high alert and consider vaccination as Bluetongue cases rise",
                     "14 August 2026",
                     "https://www.gov.uk/government/news/livestock-keepers-urged-to-be-on-high-alert-and-consider-vaccination--as-bluetongue-cases-rise"),
                    ("APHA and Defra, bluetongue case map (linked from GOV.UK)", "captured 22 October 2026",
                     "https://experience.arcgis.com/experience/4867f4e1f680415898482df7aabb703d/page/Page/"),
                    ("APHA and Defra, bluetongue zone map (linked from GOV.UK)", "captured 22 October 2026",
                     "https://defra.maps.arcgis.com/apps/webappviewer/index.html?id=514ec88edec74575958d860f0196d2ea")],
        "sources_note": ("Map stills in the video and on the cover. Case map: Contains OS data © Crown Copyright and "
                         "database right 2026. Contains data from OS Zoomstack. Powered by Esri. Its heat map includes "
                         "suspected cases. Zone map: Contains OS data © Crown Copyright and database right 2020."),
    },
    {
        "slug": "01-bird-flu-two-cases",
        "title": "Bird flu is back in Britain: two cases, two viruses",
        "video_title": "Bird flu is back in Britain: two cases, two viruses (October 2026)",
        "topic": "Bird flu",
        "as_at": "21 October 2026", "as_at_short": "21 Oct 2026",
        "uploaded": "2026-10-22", "seconds": 95, "youtube_id": "6aI73EKPq6k",
        "lead": "A 95-second map of the two cases so far this season, the zone rules and the current risk levels.",
        "summary": "H5N5 on the Isle of Lewis and H5N1 near Belford, Northumberland, with the zone rules and the risk levels.",
        "description": ("Bird flu is back in Britain: H5N5 on the Isle of Lewis (2 Oct) and H5N1 in Northumberland (19 Oct), "
                        "mapped against how last season started, and what the zone declaration means inside the 3 km "
                        "and 10 km zones. Figures as at 21 October 2026."),
        "meta": ("Bird flu is back in Britain: H5N5 on the Isle of Lewis and H5N1 in Northumberland, mapped, with the "
                 "zone rules and risk levels. Figures as at 21 October 2026."),
        "copies": [("YouTube", "https://www.youtube.com/shorts/6aI73EKPq6k"),
                   ("TikTok", "https://www.tiktok.com/@outbreaklens/video/7699372317494856982"),
                   ("Instagram", "https://www.instagram.com/reel/DeyWRe6SUCR/"),
                   ("X", "https://x.com/OutbreakWeekly/status/2113157592411181133")],
        "numbers": [("2", "cases confirmed in Great Britain this season, with two different viruses"),
                    ("2 Oct 2026", "H5N5 in a backyard flock at Ness, on the Isle of Lewis. Great Britain lost its "
                                   "bird-flu-free status."),
                    ("19 Oct 2026", "H5N1 in commercial poultry near Belford, Northumberland. The flock is being culled."),
                    ("3 km, 10 km", "the protection zone and the surveillance zone around the Belford case"),
                    ("Medium", "risk for wild birds"),
                    ("Low", "risk for poultry where biosecurity is suboptimal or poor"),
                    ("Very low", "risk for poultry with stringent biosecurity"),
                    ("6 Nov 2025", "last season, every poultry keeper in England had to house their birds from this date")],
        "numbers_note": ("Source: GOV.UK, Bird flu (avian influenza): latest situation in England, updated 21 October "
                         "2026. Both poultry risk levels carry high uncertainty. Last season's housing date: GOV.UK, "
                         "4 November 2025."),
        "keepers": ["Keep your birds away from wild birds and standing water.",
                    "Check them every day. Report anything unusual.",
                    "Keep biosecurity tight. Where it is stringent, GOV.UK rates the risk to poultry very low."],
        "zones": ("Inside the Belford zones",
                  "From the declaration of 19 October 2026. The first rule applies in the 3 km protection zone, "
                  "the rest in both zones.",
                  ["Protection zone: birds must be housed or isolated.",
                   "Most moves of birds, eggs or litter need a licence.",
                   "No fairs, shows or other bird gatherings.",
                   "Record visitors, and cleanse and disinfect vehicles.",
                   "Immediately report more sickness, deaths or fewer eggs."],
                  "Isolation applies only where a veterinary inspector directs it. The declaration has the full rules "
                  "and exceptions. In the video the rings are drawn around Belford village as a guide only."),
        "sources": [("GOV.UK, Bird flu (avian influenza): latest situation in England", "updated 21 October 2026",
                     "https://www.gov.uk/government/news/bird-flu-avian-influenza-latest-situation-in-england"),
                    ("GOV.UK, Bird flu: near Belford, North Northumberland, Northumberland (AIV2026/21)", "19 October 2026",
                     "https://www.gov.uk/animal-disease-cases-england/bird-flu-near-belford-north-northumberland-northumberland-aiv2026-slash-21"),
                    ("Defra, Declaration of a Protection Zone and a Surveillance Zone, near Belford (AIV 2026/21), PDF",
                     "19 October 2026",
                     "https://assets.publishing.service.gov.uk/media/6ad6458da89985bb97026922/Protection-and-Surveillance-Zone-AIV2026-21.pdf"),
                    ("GOV.UK, National Housing Order declared to protect poultry from Avian Influenza", "4 November 2025",
                     "https://www.gov.uk/government/news/national-housing-order-declared-to-protect-poultry-from-avian-influenza"),
                    ("Farmers Weekly, Birds ordered inside in England as avian flu escalates (last season's timeline)",
                     "4 November 2025",
                     "https://www.fwi.co.uk/news/birds-ordered-inside-in-england-as-avian-flu-escalates")],
        "sources_note": "The map in the video uses Natural Earth data (public domain).",
    },
]

# ---------- hero map: dot-matrix world from Natural Earth, cached ----------
HERO_CACHE = os.path.join(ROOT, "hero_dots.json")
NE_URLS = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson",
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson",
)
# Plate carree in degrees: x = lon + 180, y = top - lat. Crops Antarctica and the high Arctic.
GRID = {"version": 1, "step": 2, "top": 80, "bottom": -58}
LENS = (212, 34, 19)                        # lens ring centre x, y and radius (32E, 46N)
SIGNALS = ((24, 51), (104, 14), (37, -1))   # decorative signal dots (lon, lat). Not data.


def _land_polygons(gj):
    polys = []
    for feat in gj.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") == "Polygon":
            polys.append(geom["coordinates"])
        elif geom.get("type") == "MultiPolygon":
            polys.extend(geom["coordinates"])
    return polys


def _land_test(polys):
    """Return on_land(lon, lat). Uses shapely when installed, otherwise plain ray casting."""
    try:
        from shapely.geometry import Point, shape
        from shapely.ops import unary_union
        from shapely.prepared import prep
        land = prep(unary_union([shape({"type": "Polygon", "coordinates": p}).buffer(0) for p in polys]))
        return lambda lon, lat: land.contains(Point(lon, lat))
    except ImportError:
        pass

    def in_ring(ring, x, y):
        inside, j = False, len(ring) - 1
        for i in range(len(ring)):
            xi, yi, xj, yj = ring[i][0], ring[i][1], ring[j][0], ring[j][1]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        return inside

    boxes = []
    for p in polys:
        xs = [c[0] for c in p[0]]
        ys = [c[1] for c in p[0]]
        boxes.append((min(xs), min(ys), max(xs), max(ys), p))

    def on_land(lon, lat):
        for x0, y0, x1, y1, p in boxes:
            if (x0 <= lon <= x1 and y0 <= lat <= y1 and in_ring(p[0], lon, lat)
                    and not any(in_ring(h, lon, lat) for h in p[1:])):
                return True
        return False
    return on_land


def _compute_dots():
    import urllib.request
    step, top, bottom = GRID["step"], GRID["top"], GRID["bottom"]
    for url in NE_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OutbreakLens site build"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                polys = _land_polygons(json.load(resp))
            if not polys:
                continue
            on_land = _land_test(polys)
            rows, y, i = {}, step // 2, 0
            while top - y > bottom:
                first = step // 2 + (step // 2 if i % 2 else 0)   # stagger alternate rows by half a step
                xs = [x for x in range(first, 360, step) if on_land(x - 180, top - y)]
                if xs:
                    rows[str(y)] = xs
                y += step
                i += 1
            return dict(GRID, source=url, rows=rows)
        except Exception as e:   # network, SSL or parse problem: try the next file, then fall back
            print("hero map: could not use", url, "-", e)
    return None


def _hero_dots():
    try:
        with open(HERO_CACHE, encoding="utf-8") as f:
            cached = json.load(f)
        if all(cached.get(k) == v for k, v in GRID.items()) and cached.get("rows"):
            return cached
    except (OSError, ValueError):
        pass
    fresh = _compute_dots()
    if fresh:
        try:
            with open(HERO_CACHE, "w", encoding="utf-8") as f:
                json.dump(fresh, f, separators=(",", ":"))
            print("hero map: cached %d dots in %s" % (sum(len(v) for v in fresh["rows"].values()), HERO_CACHE))
        except OSError as e:
            print("hero map: could not write cache -", e)
    return fresh


def _svg_open(h):
    return ('<svg class="hero-svg" viewBox="0 0 360 %d" preserveAspectRatio="xMidYMid meet" '
            'aria-hidden="true" focusable="false">' % h)


def _circles(points, r):
    return "".join('<circle cx="%d" cy="%d" r="%s"/>' % (x, y, r) for x, y in points)


def _rows(points, r):
    """Circles grouped by map row. Each row is moved into place once, so a circle needs only cx and r.
    This keeps about 3,800 dots under 100 KB."""
    by_row = {}
    for x, y in points:
        by_row.setdefault(y, []).append(x)
    return "".join('<g transform="translate(0 %d)">%s</g>' % (y, "".join('<circle cx="%d" r="%s"/>' % (x, r) for x in xs))
                   for y, xs in sorted(by_row.items()))


def _signals(points):
    pulses = "".join('<circle class="sig-pulse d%d" cx="%d" cy="%d" r="1.6"/>' % (i + 1, x, y)
                     for i, (x, y) in enumerate(points))
    return pulses + '<g fill="#C0532B">' + _circles(points, "1.5") + "</g>"


def fallback_svg():
    """Abstract lens graphic, used only when the land data cannot be loaded."""
    cx, cy = 222, 69
    ring = ('<circle cx="%d" cy="%d" r="%%d" fill="none" stroke="#2E5496" stroke-width="1.2" '
            'vector-effect="non-scaling-stroke"/>' % (cx, cy))
    near = [(x, y) for y in range(9, 132, 4) for x in range(cx - 60, cx + 61, 4)
            if (x - cx) ** 2 + (y - cy) ** 2 <= 30 ** 2]
    return (_svg_open(138) + "".join(ring % r for r in (44, 58, 72))
            + '<g fill="#2E5496">' + _circles(near, ".7") + "</g>"
            + '<circle cx="%d" cy="%d" r="30" fill="none" stroke="#FAF7F1" stroke-opacity=".85" '
              'stroke-width="1.25" vector-effect="non-scaling-stroke"/>' % (cx, cy)
            + _signals([(cx - 10, cy - 7), (cx + 14, cy + 9)]) + "</svg>")


def hero_svg():
    d = _hero_dots()
    if not d:
        return fallback_svg()
    top = d["top"]
    pts = [(int(x), int(y)) for y, xs in d["rows"].items() for x in xs]
    lx, ly, lr = LENS
    sig = []
    for lon, lat in SIGNALS:   # snap each signal onto the nearest land dot
        tx, ty = lon + 180, top - lat
        sig.append(min(pts, key=lambda p: (p[0] - tx) ** 2 + (p[1] - ty) ** 2))
    near, far = [], []
    for p in pts:
        if p not in sig:
            (near if (p[0] - lx) ** 2 + (p[1] - ly) ** 2 <= lr * lr else far).append(p)
    return (_svg_open(top - d["bottom"])
            + '<defs><radialGradient id="lens-glow"><stop offset="0" stop-color="#2E5496" stop-opacity=".75"/>'
              '<stop offset="1" stop-color="#2E5496" stop-opacity="0"/></radialGradient></defs>'
            + '<g fill="#2E5496">' + _rows(far, ".6") + "</g>"
            + '<circle cx="%d" cy="%d" r="%d" fill="url(#lens-glow)"/>' % (lx, ly, lr)
            + '<g fill="#FAF7F1">' + _rows(near, ".66") + "</g>"
            + '<circle cx="%d" cy="%d" r="%d" fill="none" stroke="#FAF7F1" stroke-opacity=".9" '
              'stroke-width="1.25" vector-effect="non-scaling-stroke"/>' % (lx, ly, lr)
            + '<circle cx="%d" cy="%d" r="%d" fill="none" stroke="#FAF7F1" stroke-opacity=".3" '
              'stroke-width="1" stroke-dasharray="2 5" vector-effect="non-scaling-stroke"/>' % (lx, ly, lr + 4)
            + _signals(sig) + "</svg>")


# ---------- small inline graphics ----------
# Final small mark, ring, dot and hen for 24 px use (brand/final/mark-small.svg). Navy on light
# backgrounds, paper on navy. The case dot stays terracotta. No IDs, so it can repeat on a page.
MARK_SMALL = (
    '<path d="M82.3 29.44A39 39 0 1 1 46.92 9.01" fill="none" stroke="{c}" stroke-width="10" stroke-linecap="round"/>'
    '<circle cx="67.5" cy="14.23" r="10.5" fill="#C0532B"/>'
    '<g fill="{c}" transform="translate(15.31 16.04) scale(0.6196)"><path fill-rule="evenodd" d="M13.2 23A4.5 4.5 0 0 1 '
    '20.5 20.5C30 33 44 43 58 40L64.15 28.74A10 10 0 1 1 83.4 30.42C87 38 84 46 80 52A30 30 0 0 1 20 52ZM74.1 25A2.4 2.4 '
    '0 1 0 78.9 25A2.4 2.4 0 1 0 74.1 25Z"/><circle cx="68.5" cy="17.5" r="4.4"/><circle cx="74.5" cy="15" r="4.8"/>'
    '<circle cx="80.6" cy="17.8" r="4.2"/><path d="M82.6 23.6L93 28.4L83.2 33Z"/><rect x="42" y="76" width="6" height="18" '
    'rx="3"/><rect x="55" y="76" width="6" height="18" rx="3"/></g>')


def _mark(cls, on_dark=True):
    return ('<svg class="%s" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" aria-hidden="true" focusable="false">'
            '%s</svg>' % (cls, MARK_SMALL.replace("{c}", "#FAF7F1" if on_dark else "#1F3864")))

# Final brand mark, "Herd in the lens" (brand/final/header-inline.svg). Paper and terracotta for navy
# backgrounds. No IDs, so it can sit in the header and the footer of the same page.
BRAND_MARK = (
    '<svg class="brand-mark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" aria-hidden="true" focusable="false">'
    '<path d="M78.01 20.06A41 41 0 1 1 57.19 8.04" fill="none" stroke="#FAF7F1" stroke-width="6" stroke-linecap="round"/>'
    '<circle cx="68.5" cy="12.49" r="6" fill="#C0532B"/>'
    '<path fill="#FAF7F1" fill-rule="evenodd" d="M73.55 29.53L73.8 28.75L74.13 28.11L74.32 27.84L74.65 27.46L75.34 26.91L75.5 26.75L75.7 26.43L75.82 26.08L75.86 25.78L75.83 25.48L75.75 25.19L75.61 24.92L75.42 24.68L75.19 24.49L74.93 24.34L74.64 24.25L74.42 24.22L74.12 24.23L73.83 24.3L73.55 24.42L72.75 25.04L72.05 25.75L71.52 26.5L71.08 27.31L70.74 28.18L70.45 29.28L70.13 29.1L69.81 28.97L69.37 28.85L68.96 28.78L67.95 28.72L66.87 28.81L65.79 29.03L64.79 29.37L63.95 29.8L63.63 30.02L63.31 30.3L63.08 30.59L62.9 30.92L62.85 31.2L62.88 31.47L63 31.72L63.25 31.99L63.54 32.18L63.91 32.35L64.42 32.49L64.92 32.58L65.46 32.62L66.03 32.62L66.62 32.57L67.22 32.49L67.8 32.36L68.41 32.19L67.78 32.55L66.99 32.94L65.82 33.41L65.21 33.6L64.57 33.75L62.74 33.96L60.77 34.11L57.66 34.23L48.79 34.39L46.55 34.48L44.32 34.61L42.81 34.75L42.51 34.81L42.1 35L41.92 35.15L41.72 35.37L41.6 35.57L41.48 35.85L41.42 36.3L41.49 36.75L41.69 37.16L41.88 37.39L42.12 37.58L42.92 37.97L43.44 38.31L43.81 38.63L44.19 39.06L44.58 39.64L44.9 40.36L45.06 41.02L45.16 41.98L45.25 42.27L45.4 42.53L45.59 42.76L45.83 42.95L46.94 43.5L47.2 43.67L47.48 43.9L47.74 44.2L47.96 44.54L48.09 44.81L48.22 45.19L48.29 45.72L48.26 46.25L48.13 46.77L47.9 47.25L47.58 47.68L47.21 48.01L46.84 48.24L45.95 48.67L45.59 48.96L45.41 49.21L45.28 49.48L45.21 49.78L45.19 50.12L45.28 50.57L45.46 50.91L45.71 51.2L46.03 51.41L46.31 51.53L46.68 51.59L48.2 51.67L48.2 62.5L48.25 62.8L48.38 63.15L48.55 63.4L48.82 63.66L49.15 63.85L49.51 63.95L50.32 63.96L50.69 63.9L51.04 63.74L51.34 63.51L51.6 63.15L51.74 62.8L51.79 62.43L51.79 51.58L52.64 51.56L52.57 51.92L52.55 52.25L52.6 52.64L52.69 52.96L52.82 53.26L53.01 53.58L53.25 53.87L53.51 54.11L53.98 54.43L54.52 54.67L55.1 54.81L55.7 54.85L56.37 54.77L57.01 54.56L57.6 54.22L58.1 53.77L58.45 53.24L58.57 52.96L58.65 52.64L58.7 52.05L58.65 51.73L58.57 51.42L59.98 51.38L59.98 62.43L60.03 62.8L60.16 63.15L60.43 63.51L60.73 63.74L61.07 63.9L61.44 63.96L62.25 63.95L62.62 63.85L62.94 63.66L63.17 63.46L63.38 63.15L63.52 62.8L63.56 62.5L63.57 51.29L65.34 51.25L65.36 62.43L65.42 62.87L65.62 63.28L65.92 63.61L66.31 63.85L66.67 63.95L67.66 63.96L68.04 63.92L68.25 63.85L68.52 63.7L68.7 63.57L68.9 63.34L69.02 63.15L69.13 62.87L69.2 62.43L69.2 50.29L69.94 47.77L70.51 46.01L71.16 44.29L71.75 42.98L72.36 43.32L73.01 43.63L73.69 43.89L74.42 44.08L75.18 44.22L75.97 44.3L76.8 44.3L77.65 44.24L77.93 44.2L78.44 44.03L78.89 43.78L79.26 43.44L79.43 43.25L79.7 42.81L79.89 42.32L80.01 41.79L80.06 41.23L80.03 40.64L79.92 40.05L79.72 39.45L79.44 38.87L78.15 36.73L77.33 35.49L76.54 34.39L75.42 33.01L74.71 32.27L74.36 31.95L73.67 31.42L73.3 31.18L73.41 30.22ZM75.53 35.26L75.46 35.49L75.34 35.71L75.2 35.88L75.02 36.04L74.81 36.15L74.58 36.23L74.34 36.25L74.1 36.23L73.87 36.17L73.66 36.06L73.47 35.91L73.31 35.72L73.19 35.51L73.12 35.28L73.09 35.04L73.11 34.8L73.18 34.57L73.29 34.36L73.44 34.17L73.62 34.01L73.85 33.89L74.08 33.82L74.32 33.8L74.56 33.82L74.79 33.89L75.01 34L75.19 34.16L75.34 34.34L75.46 34.55L75.53 34.78L75.55 35.02Z"/>'
    '<g fill="#FAF7F1" transform="translate(9.64 34.87) scale(0.3866)">'
    '<path fill-rule="evenodd" d="M13.2 23A4.5 4.5 0 0 1 20.5 20.5C30 33 44 43 58 40L64.15 28.74A10 10 0 1 1 83.4 30.42C87 38 84 46 80 52A30 30 0 0 1 20 52ZM74.1 25A2.4 2.4 0 1 0 78.9 25A2.4 2.4 0 1 0 74.1 25Z"/>'
    '<circle cx="68.5" cy="17.5" r="4.4"/><circle cx="74.5" cy="15" r="4.8"/><circle cx="80.6" cy="17.8" r="4.2"/>'
    '<path d="M82.6 23.6L93 28.4L83.2 33Z"/><rect x="42" y="76" width="6" height="18" rx="3"/><rect x="55" y="76" width="6" height="18" rx="3"/>'
    '</g></svg>')
BRAND = '<a class="brand" href="index.html">' + BRAND_MARK + '<span>Outbreak<span class="brand-lens">Lens</span></span></a>'
ICON_MAIL = ('<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect x="2.5" y="4.5" width="15" height="11" rx="1.5" '
             'fill="none" stroke="currentColor" stroke-width="1.5"/><path d="m3 5.5 7 5.5 7-5.5" fill="none" stroke="currentColor" '
             'stroke-width="1.5" stroke-linejoin="round"/></svg>')
RINGS = ('<svg class="rings" viewBox="0 0 400 400" aria-hidden="true" focusable="false">'
         '<circle cx="200" cy="200" r="198" fill="none" stroke="#2E5496" stroke-width="1.2"/>'
         '<circle cx="200" cy="200" r="160" fill="none" stroke="#2E5496" stroke-width="1.2"/>'
         '<circle cx="200" cy="200" r="118" fill="none" stroke="#C0532B" stroke-opacity=".3" stroke-width="18"/></svg>')
ICON_MENU = ('<svg class="i-menu" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M3 5.5h14M3 10h14M3 14.5h14" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
             '<svg class="i-close" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M5 5l10 10M15 5 5 15" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>')
ICON_EXT = ('<svg class="i-ext" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M9 3h4v4M13 3 7.5 8.5M11.5 9.5V13h-8.5V4.5H7" '
            'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')
_ICON = '<svg class="icon" viewBox="0 0 48 48" aria-hidden="true" focusable="false">'
_STROKE = '<g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
ICON_SYNTH = (_ICON + _STROKE + '<circle cx="9" cy="11" r="3"/><circle cx="9" cy="24" r="3"/><circle cx="9" cy="37" r="3"/>'
              '<path d="M12 12.6 27.6 20.8M12 24h15M12 35.4 27.6 27.2"/><circle cx="35" cy="24" r="8"/></g>'
              '<circle cx="35" cy="24" r="3" fill="#C0532B"/></svg>')
ICON_SIGN = (_ICON + _STROKE + '<path d="M24 5v38M17 43h14"/><path d="M34 23H14.5L10 27.5l4.5 4.5H34z"/></g>'
             '<path d="M12 9h21.5l4.5 4.5-4.5 4.5H12z" fill="#C0532B"/></svg>')
ICON_CALM = (_ICON + _STROKE + '<rect x="4" y="16" width="40" height="16" rx="8"/><path d="M18 19.5v9M30 19.5v9"/></g>'
             '<circle cx="24" cy="24" r="3.5" fill="#C0532B"/></svg>')

CSS = """
:root{--navy:#1F3864;--navy2:#2E5496;--navy-deep:#17294B;--navy-ink:#15243F;
--accent:#C0532B;--accent-dark:#A9461F;--accent-soft:#F2B8A0;
--paper:#FAF7F1;--card:#fff;--ink:#1c1b19;--ink2:#3b3934;--muted:#6b7280;--line:#e7e2d8;--green:#2E7D32;
--on-dark:#FAF7F1;--on-dark2:#C9D4E8;--on-dark3:#9fb0cc;
--font:"Open Sans",system-ui,Arial,sans-serif;
--gutter:16px;--wrap:1180px;--radius:10px}
@media(min-width:768px){:root{--gutter:24px}}
@media(min-width:1024px){:root{--gutter:32px}}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--font);font-weight:300;font-size:17px;line-height:1.65;
overflow-wrap:break-word;-webkit-font-smoothing:antialiased}
svg,iframe,img{max-width:100%}
h1,h2,h3{font-family:var(--font);font-weight:300;color:var(--navy);line-height:1.2;letter-spacing:-.01em;margin:0 0 .5em;text-wrap:balance}
h3,.status h2,.card h2,.report-card h2,.promise-box h2,.signup h2,.follow h2{font-weight:400}
strong,b{font-weight:600}
.note,figcaption,.stat span,.source-row span,.domain,.meta,.crumbs,.site-footer,.data-table td{font-weight:400}
p{margin:0 0 1em}
a{color:var(--navy);text-decoration-thickness:1px;text-underline-offset:.2em}
a:hover{color:var(--accent-dark)}
:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
.on-dark :focus-visible{outline-color:var(--accent-soft)}
main:focus{outline:none}
[id]{scroll-margin-top:84px}
.wrap{width:100%;max-width:var(--wrap);margin:0 auto;padding:0 var(--gutter)}
.narrow{max-width:46rem}
.nw{white-space:nowrap}
.vh{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.skip{position:absolute;left:12px;top:-64px;z-index:100;background:var(--paper);color:var(--navy);padding:10px 16px;border-radius:6px;font-weight:600}
.skip:focus{top:12px}

/* header */
.site-header{position:sticky;top:0;z-index:50;background:var(--navy);border-bottom:1px solid rgba(250,247,241,.1)}
.bar{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:60px}
.brand{display:inline-flex;align-items:center;gap:10px;color:#fff;text-decoration:none;
font-weight:600;font-size:1.25rem;letter-spacing:-.015em;line-height:1}
.brand:hover{color:#fff}
.brand-mark{width:32px;height:32px;flex:none}
.brand-lens{color:var(--accent)}
.nav-desktop{display:none}
.nav-desktop a{color:var(--on-dark);text-decoration:none;font-size:.9375rem;font-weight:600;padding:10px 12px;border-radius:6px}
.nav-desktop a:hover{background:rgba(250,247,241,.08);color:#fff}
.nav-desktop a[aria-current="page"]{color:#fff;text-decoration:underline;text-decoration-color:var(--accent);
text-decoration-thickness:2px;text-underline-offset:9px}
.nav-desktop a.nav-cta{margin-left:10px;background:var(--accent);color:#fff;font-weight:600;padding:10px 16px;text-decoration:none}
.nav-desktop a.nav-cta:hover{background:var(--accent-dark)}
.nav-desktop a.nav-cta[aria-current="page"]{box-shadow:0 0 0 2px var(--navy),0 0 0 3.5px var(--accent-soft)}
.nav-mobile summary{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 14px;
border:1px solid rgba(250,247,241,.4);border-radius:6px;color:#fff;font-weight:600;font-size:.9375rem;
cursor:pointer;list-style:none;-webkit-user-select:none;user-select:none}
.nav-mobile summary::-webkit-details-marker{display:none}
.nav-mobile summary::marker{content:""}
.nav-mobile svg{width:18px;height:18px;display:block}
.nav-mobile .i-close,.nav-mobile[open] .i-menu{display:none}
.nav-mobile[open] .i-close{display:block}
.nav-mobile[open] summary{background:rgba(250,247,241,.12)}
.nav-mobile nav{position:absolute;left:0;right:0;top:100%;background:var(--navy-deep);border-bottom:4px solid var(--accent);
padding:6px 0 10px;box-shadow:0 18px 32px rgba(8,16,34,.35)}
.nav-mobile nav a{display:block;padding:13px var(--gutter);color:#fff;text-decoration:none;font-size:1.0625rem;
font-weight:600;border-left:4px solid transparent}
.nav-mobile nav a:hover{background:rgba(250,247,241,.06)}
.nav-mobile nav a[aria-current="page"]{border-left-color:var(--accent);background:rgba(250,247,241,.05)}
@media(min-width:768px){.bar{min-height:68px}.nav-desktop{display:flex;align-items:center;gap:2px}.nav-mobile{display:none}}

/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:12px 22px;
border:1.5px solid transparent;border-radius:6px;font-family:var(--font);font-weight:600;font-size:1rem;line-height:1.2;
text-align:center;text-decoration:none;transition:background-color .15s,border-color .15s,color .15s}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent-dark);color:#fff}
.btn-light{border-color:rgba(250,247,241,.6);color:#fff}
.btn-light:hover{background:rgba(250,247,241,.1);border-color:#fff;color:#fff}
.btn-outline{border-color:var(--navy);color:var(--navy);background:transparent}
.btn-outline:hover{background:var(--navy);color:#fff}
.btn-sm{min-height:44px;padding:10px 16px;font-size:.9375rem}
@media(max-width:399px){.btn-sm{padding:10px 14px}}
.actions{display:flex;flex-direction:column;gap:12px}
.actions-row{display:flex;flex-wrap:wrap;gap:10px}
@media(min-width:480px){.actions{flex-direction:row;flex-wrap:wrap}}

/* hero */
.hero{position:relative;background:var(--navy) radial-gradient(70% 90% at 62% 28%,#27467d 0,rgba(31,56,100,0) 70%);color:var(--on-dark);overflow:hidden}
.hero-map{line-height:0;overflow:hidden}
.hero-svg{display:block;width:172%;max-width:none;height:auto;margin-left:-44%}
.sig-pulse{fill:none;stroke:var(--accent);stroke-width:1.5px;vector-effect:non-scaling-stroke;transform-box:fill-box;
transform-origin:center;opacity:0;animation:sig 3.6s cubic-bezier(.2,.6,.3,1) infinite}
.sig-pulse.d2{animation-delay:1.2s}.sig-pulse.d3{animation-delay:2.4s}
@keyframes sig{0%{transform:scale(1);opacity:.95}100%{transform:scale(4.4);opacity:0}}
.hero-inner{position:relative;padding:0 var(--gutter) 44px}
.hero-panel{position:relative;margin-top:-36px;background:var(--navy-deep);border-top:4px solid var(--accent);
padding:24px 20px 28px;box-shadow:0 22px 44px -18px rgba(6,14,30,.6)}
.kicker{display:flex;align-items:flex-start;gap:10px;margin:0 0 16px;color:var(--accent-soft);font-size:.8125rem;font-weight:600;
letter-spacing:.14em;text-transform:uppercase;line-height:1.4}
.kicker svg{width:20px;height:20px;flex:none;margin-top:-1px}
.hero h1{color:#fff;font-size:clamp(2rem,1.3rem + 3vw,3.25rem);font-weight:300;line-height:1.14;letter-spacing:-.015em;margin:0 0 18px}
.hero .lead{color:var(--on-dark2);font-size:1.0625rem;line-height:1.6;margin:0 0 26px;max-width:32em}
@media(min-width:768px){
.hero-svg{width:122%;margin-left:-14%}
.hero-inner{padding-bottom:64px}
.hero-panel{margin-top:-64px;max-width:640px;padding:32px 36px 36px}
.hero .lead{font-size:1.1875rem}}
@media(min-width:1100px){
.hero{display:grid;align-items:center}
.hero-map,.hero-inner{grid-area:1/1}
.hero-svg{width:100%;max-width:1680px;margin:0 auto}
.hero-inner{width:100%;max-width:var(--wrap);margin:0 auto;padding:72px var(--gutter)}
.hero-panel{margin:0;max-width:520px;padding:40px 40px 44px;background:rgba(23,41,75,.92);
-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px)}}
@media(min-width:1280px){.hero-panel{max-width:560px}}

/* sections */
.section{padding:56px 0}
@media(min-width:768px){.section{padding:80px 0}}
@media(min-width:1100px){.section{padding:96px 0}}
.band-white{background:var(--card);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.section-head{max-width:42rem;margin:0 0 32px}
.section-head h2{font-size:clamp(1.75rem,1.35rem + 1.6vw,2.375rem);margin:0 0 10px}
.section-head p{margin:0;color:var(--ink2);font-size:1.0625rem}
.head-row{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px 32px;margin:0 0 32px}
.head-row .section-head{margin:0}
.more{font-weight:600}

/* status strip (pre-launch) */
.status{background:var(--card);border-bottom:1px solid var(--line);padding:28px 0}
.status-inner{display:grid;gap:16px}
.status-mark{width:40px;height:40px}
.status h2{font-size:1.375rem;margin:0 0 4px}
.status p{margin:0;color:var(--ink2);max-width:40em}
@media(min-width:960px){.status{padding:32px 0}.status-inner{grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:28px}}

/* what we do */
.pillars{display:grid;gap:32px}
@media(min-width:768px){.pillars{grid-template-columns:repeat(3,minmax(0,1fr));gap:28px}}
@media(min-width:1100px){.pillars{gap:48px}}
.pillar{border-top:1px solid var(--line);padding-top:24px}
.icon{width:44px;height:44px;color:var(--navy);display:block;margin:0 0 16px}
.pillar h3{font-size:1.375rem;margin:0 0 8px}
.pillar p{margin:0;color:var(--ink2)}

/* who it is for */
.split{display:grid}
@media(min-width:1100px){.split{grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:72px;align-items:start}}
.audience{list-style:none;margin:0;padding:0;display:grid}
@media(min-width:640px){.audience{grid-template-columns:repeat(2,minmax(0,1fr));column-gap:32px}}
.audience li{border-top:1px solid var(--line);padding:20px 0 22px}
.audience h3{font-size:1.25rem;margin:0 0 6px}
.audience p{margin:0;color:var(--ink2)}

/* official sources row */
.source-row{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
border-top:1px solid var(--line);border-left:1px solid var(--line)}
@media(min-width:768px){.source-row{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:1100px){.source-row{grid-template-columns:repeat(6,minmax(0,1fr))}}
.source-row li{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:20px 16px 18px}
.source-row b{display:block;font-size:1.0625rem;font-weight:600;color:var(--navy);letter-spacing:.01em;line-height:1.25}
.source-row span{display:block;margin-top:6px;font-size:.8125rem;color:var(--muted);line-height:1.4}

/* call to action band */
.cta-band{position:relative;overflow:hidden;background:var(--navy);color:var(--on-dark);padding:64px 0}
.cta-band .wrap{position:relative}
.cta-band h2{color:#fff;font-size:clamp(1.75rem,1.3rem + 1.9vw,2.625rem);max-width:15em;margin:0 0 12px}
.cta-band p{color:var(--on-dark2);max-width:32em;margin:0 0 28px;font-size:1.0625rem}
.rings{position:absolute;pointer-events:none;width:380px;height:380px;right:-300px;top:-40px;opacity:.6}
@media(min-width:768px){.cta-band{padding:88px 0}.rings{width:520px;height:520px;right:-110px;top:50%;transform:translateY(-50%);opacity:1}}

/* inner page head */
.page-head{position:relative;overflow:hidden;background:var(--navy);color:var(--on-dark);padding:44px 0 48px}
.page-head .wrap{position:relative}
.page-head h1{color:#fff;font-size:clamp(2rem,1.45rem + 2.4vw,3.25rem);line-height:1.08;letter-spacing:-.018em;max-width:17em;margin:0 0 14px}
.page-head .lead{color:var(--on-dark2);font-size:clamp(1.0625rem,1rem + .35vw,1.25rem);max-width:38em;margin:0}
.page-head .lead a{color:#fff}
.page-head .actions{margin-top:28px}
.page-head .rings{top:-60px}
.page-head.overlap{padding-bottom:92px}
@media(min-width:768px){.page-head{padding:72px 0 76px}.page-head .rings{right:-90px;width:460px;height:460px;top:50%}
.page-head.overlap{padding-bottom:124px}}
.crumbs{background:var(--navy);color:var(--on-dark2);font-size:.9375rem;padding:14px 0}
.crumbs a{color:#fff}

/* cards */
.cards{display:grid;gap:16px}
@media(min-width:640px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1024px){.cards{grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}}
.card{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:24px}
.card h2{font-size:1.375rem;margin:0 0 8px}
.card p{margin:0 0 16px;color:var(--ink2)}
.card .domain{margin:auto 0 6px;font-size:.8125rem;color:var(--muted)}
.card-link{display:inline-flex;align-items:center;gap:6px;font-weight:600;min-height:32px}
.i-ext{width:14px;height:14px;flex:none}

/* lists */
.checklist{list-style:none;margin:0 0 32px;padding:0}
.checklist li{position:relative;padding:13px 0 13px 34px;border-top:1px solid var(--line)}
.checklist li:last-child{border-bottom:1px solid var(--line)}
.checklist li::before{content:"";position:absolute;left:3px;top:20px;width:14px;height:8px;
border-left:2.5px solid var(--green);border-bottom:2.5px solid var(--green);transform:rotate(-45deg)}
.promise{list-style:none;margin:0 0 24px;padding:0}
.promise li{position:relative;padding:14px 0 14px 36px;border-top:1px solid var(--line)}
.promise li:first-child{border-top:0}
.promise-mark{position:absolute;left:0;top:16px;width:24px;height:24px}

/* prose and about */
.prose{max-width:42rem}
.prose h1{font-size:clamp(1.875rem,1.4rem + 2vw,2.75rem)}
.prose h2{font-size:1.5rem;margin:1.8em 0 .5em}
.prose h2:first-child{margin-top:0}
.prose h3{font-size:1.25rem;margin:1.5em 0 .4em}
.prose ul{padding-left:1.25em;margin:0 0 1em}
.prose li{margin:0 0 .4em}
.prose blockquote{margin:24px 0;padding:14px 20px;border-left:4px solid var(--accent);background:var(--card);color:var(--ink2)}
.prose hr{border:0;border-top:1px solid var(--line);margin:32px 0}
.prose code{font-size:.9em;background:var(--card);border:1px solid var(--line);border-radius:4px;padding:1px 5px}
.prose .actions{margin-top:28px}
.intro{font-size:1.1875rem;line-height:1.55}
.note{font-size:.875rem;color:var(--muted)}
.about{display:grid;gap:40px}
.promise-box{background:var(--card);border:1px solid var(--line);border-top:4px solid var(--navy);border-radius:var(--radius);padding:28px 24px}
.promise-box h2{font-size:1.5rem;margin:0 0 8px}
@media(min-width:1024px){.about{grid-template-columns:minmax(0,1fr) 380px;gap:72px;align-items:start}
.promise-box{position:sticky;top:96px}}

/* subscribe */
.section.pull{padding-top:0}
.signup{position:relative;max-width:640px;margin-top:-56px;background:var(--card);border:1px solid var(--line);
border-top:4px solid var(--accent);border-radius:var(--radius);padding:28px 20px 24px;box-shadow:0 24px 48px -28px rgba(20,30,50,.45)}
.signup h2{font-size:1.5rem;margin:0 0 4px}
.signup .embed{min-height:120px;margin:12px 0 8px}
.signup .note{margin:0}
.follow{margin-top:48px}
.follow h2{font-size:1.25rem;margin:0 0 14px}
@media(min-width:768px){.signup{margin-top:-76px;padding:36px 40px 32px}}
.signup .support{margin-top:10px}
.latest{margin-top:40px}
.latest h2{font-size:1.25rem;font-weight:400;margin:0 0 6px}
.latest p{margin:0}

/* shorts: cards on the home and Watch pages */
.status + .band-white,.band-white + .band-white{border-top:0}
.short-card.no-cover{grid-template-columns:minmax(0,1fr)}
.short-cards{display:grid;gap:16px}
@media(min-width:1024px){.short-cards{grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}}
.short-card{display:grid;grid-template-columns:112px minmax(0,1fr);align-items:stretch;background:var(--card);
border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;color:var(--ink);text-decoration:none}
.short-card:hover{border-color:var(--navy2);color:var(--ink)}
/* the whole 9:16 cover always shows: no side crop, and any spare height below it is navy like the cover's edge */
.short-card img{display:block;width:100%;height:100%;aspect-ratio:9/16;object-fit:contain;object-position:top center;
background:var(--navy-ink)}
@media(max-width:639px){.short-card p{display:none}}
.short-text{display:flex;flex-direction:column;gap:8px;padding:16px 16px 18px;min-width:0}
.short-card h3{font-size:1.1875rem;margin:0;color:var(--navy)}
.short-card p{margin:0;color:var(--ink2);font-size:.9375rem;line-height:1.55}
.short-card .meta{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font-size:.8125rem;color:var(--muted)}
.short-card .go{margin-top:auto;padding-top:4px;font-weight:600;color:var(--navy);text-decoration:underline;text-underline-offset:.2em}
.short-card:hover .go{color:var(--accent-dark)}
@media(min-width:640px){.short-card{grid-template-columns:160px minmax(0,1fr)}
.short-text{padding:22px 24px 24px;gap:10px}.short-card h3{font-size:1.3125rem}}

/* shorts: one page per short */
.short-layout{display:grid;gap:36px}
.short-frame{position:relative;width:100%;max-width:420px;aspect-ratio:9/16;background:var(--navy-ink);
border-radius:var(--radius);overflow:hidden;box-shadow:0 24px 48px -28px rgba(20,30,50,.5)}
.short-frame iframe{position:absolute;top:0;left:0;width:100%;height:100%;border:0}
.short-media .note{margin:10px 0 0;max-width:420px}
@media(min-width:960px){.short-layout{grid-template-columns:360px minmax(0,1fr);gap:56px;align-items:start}
.short-frame{max-width:none}}
@media(min-width:960px) and (min-height:780px){.short-media{position:sticky;top:96px}}
.prose .keynums{list-style:none;margin:0 0 12px;padding:0;border-top:1px solid var(--line)}
.prose .keynums li{display:grid;grid-template-columns:7.25rem minmax(0,1fr);gap:4px 16px;align-items:baseline;
margin:0;padding:11px 0 12px;border-bottom:1px solid var(--line)}
.keynums b{font-weight:300;font-size:1.375rem;line-height:1.25;color:var(--navy)}
.keynums span{color:var(--ink2)}
@media(min-width:640px){.prose .keynums li{grid-template-columns:9rem minmax(0,1fr)}}
.prose .src-list{padding-left:1.4em}
.src-list li{padding-left:.2em}
.src-list span{color:var(--muted);font-weight:400}
.disclaimer-box{margin:28px 0 8px;padding:16px 20px;background:var(--card);border:1px solid var(--line);
border-left:4px solid var(--navy);border-radius:6px;font-size:.9375rem;line-height:1.6;font-weight:400;color:var(--ink2)}
.prose .actions-row{margin:0 0 8px}

/* weekly and data */
.report-card{display:grid;gap:8px;max-width:760px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);
border-radius:var(--radius);padding:24px;color:var(--ink);text-decoration:none}
.report-card:hover{border-color:var(--navy2);border-left-color:var(--accent);color:var(--ink)}
.report-card h2{font-size:1.5rem;margin:0}
.report-card p{margin:0;color:var(--ink2)}
.report-card .meta{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:.875rem;color:var(--muted)}
.report-card .go{font-weight:600;color:var(--navy);text-decoration:underline;text-underline-offset:.2em}
.tag{display:inline-block;font-size:.75rem;font-weight:600;color:var(--navy2);background:#eef2f9;border-radius:999px;padding:2px 10px}
.archive-note{margin:20px 0 0}
.data-table{width:100%;border-collapse:separate;border-spacing:0;background:var(--card);border:1px solid var(--line);
border-radius:var(--radius);overflow:hidden;margin:0 0 20px}
.data-table th{background:var(--navy);color:#fff;text-align:left;font-weight:600;font-size:.875rem;padding:12px 16px}
.data-table td{padding:14px 16px;border-top:1px solid var(--line);vertical-align:top}
@media(max-width:639px){
.data-table,.data-table tbody{display:block}
.data-table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.data-table tr{display:block;padding:14px 16px;border-top:1px solid var(--line)}
.data-table tbody tr:first-child{border-top:0}
.data-table td{display:grid;grid-template-columns:6.5rem minmax(0,1fr);gap:12px;padding:4px 0;border:0}
.data-table td::before{content:attr(data-label);font-size:.8125rem;font-weight:600;color:var(--muted)}}

/* this week (full mode) */
.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line);
border-radius:var(--radius);overflow:hidden;margin:0 0 56px}
@media(min-width:900px){.stats{grid-template-columns:repeat(4,minmax(0,1fr))}}
.stat{background:var(--paper);padding:20px 18px}
.stat b{display:block;font-weight:300;font-size:clamp(2rem,1.5rem + 1.8vw,2.875rem);color:var(--navy);line-height:1.1;margin:0 0 6px}
.stat span{display:block;font-size:.875rem;color:var(--muted);line-height:1.4}
.mapfig{margin:0}
.mapframe{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:var(--card)}
.mapframe iframe{display:block;width:100%;height:420px;border:0}
.mapfig figcaption{margin-top:10px;font-size:.875rem;color:var(--muted)}
@media(min-width:768px){.mapframe iframe{height:540px}}
.report{display:grid;gap:32px}
@media(min-width:1024px){.report{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:48px;align-items:start}
.report .mapframe{position:sticky;top:92px}.report .mapframe iframe{height:600px}}

/* footer */
.site-footer{background:var(--navy-ink);color:var(--on-dark2);padding:56px 0 32px;font-size:.9375rem}
.site-footer a{color:#fff;text-decoration-color:rgba(250,247,241,.45)}
.site-footer a:hover{color:var(--accent-soft)}
.site-footer .brand{margin:0 0 16px;text-decoration:none}
.site-footer h2{font-size:.9375rem;font-weight:600;letter-spacing:0;color:#fff;margin:0 0 12px}
.foot-grid{display:grid;gap:32px}
@media(min-width:768px){.foot-grid{grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr);gap:40px}}
.foot-brand p{max-width:28em}
.foot-links{list-style:none;margin:0;padding:0}
.foot-links li{margin:0 0 8px}
.plat{display:inline-flex;align-items:center;gap:10px;min-height:28px}
.plat img,.plat svg{width:20px;height:20px;flex:none}
.disclaimer{margin:40px 0 0;padding-top:20px;border-top:1px solid rgba(250,247,241,.14);font-size:.8125rem;line-height:1.55;color:var(--on-dark3);max-width:62em}
.copyright{margin:10px 0 0;font-size:.8125rem;color:var(--on-dark3)}

@media(prefers-reduced-motion:reduce){*{transition:none!important}
.sig-pulse{animation:none;opacity:.55;transform:scale(2.2)}}
"""


def ext(url, text, cls="", icon=""):
    """External link: opens in a new tab and says so to screen readers."""
    c = ' class="%s"' % cls if cls else ""
    return ('<a%s href="%s" target="_blank" rel="noopener">%s%s<span class="vh"> (opens in a new tab)</span></a>'
            % (c, url, text, icon))


INDEXED = []   # pages for sitemap.xml, in build order


def canonical(path):
    """The address Cloudflare Pages serves a page at: / for the home page, no .html on the others."""
    if path == "index.html":
        return SITE_URL + "/"
    return SITE_URL + "/" + (path[:-5] if path.endswith(".html") else path)


def _relink(html, prefix):
    """Point relative links at the site root: prefix "../" for a page in a subfolder, "/" for the 404 page,
    which Cloudflare can serve at any depth. Links with a scheme (https:, mailto:), #anchors and / are left alone."""
    return re.sub(r'\b(href|src)="(?![a-zA-Z][a-zA-Z0-9+.-]*:|#|/)', lambda m: m.group(1) + '="' + prefix, html)


def ld_json(extra=None):
    """Structured data for every page: the Organization and the WebSite, plus an optional object such as a VideoObject."""
    org = {"@type": "Organization", "@id": SITE_URL + "/#organization", "name": "OutbreakLens", "url": SITE_URL}
    if LOGO_URL:
        org["logo"] = LOGO_URL
    org["sameAs"] = [u for _, u in SOCIAL] + [X_URL, KOFI_URL]
    site = {"@type": "WebSite", "@id": SITE_URL + "/#website", "name": "OutbreakLens", "url": SITE_URL,
            "inLanguage": "en-GB", "publisher": {"@id": SITE_URL + "/#organization"}}
    data = {"@context": "https://schema.org", "@graph": [org, site] + ([extra] if extra else [])}
    return ('<script type="application/ld+json">%s</script>'
            % json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))


def page(title, active, body, desc="Accessible weekly animal-disease intelligence.", path=None, index=True, ld=None):
    """path is the file the page is written to (defaults to active). index=False keeps a page out of
    search results and the sitemap. ld is an extra JSON-LD object for this page."""
    path = path or active
    def cur(h):
        return ' aria-current="page"' if h == active else ""
    desk = "".join('<a href="%s"%s>%s</a>' % (h, cur(h), t) for h, t in NAV if h not in ("index.html", "subscribe.html"))
    desk += '<a class="nav-cta" href="subscribe.html"%s>Subscribe</a>' % cur("subscribe.html")
    mob = "".join('<a href="%s"%s>%s</a>' % (h, cur(h), t) for h, t in NAV)
    explore = "".join('<li><a href="%s">%s</a></li>' % (h, t) for h, t in
                      [("weekly.html", "Weekly reports"), ("watch.html", "Short videos"), ("data.html", "Open data"),
                       ("sources.html", "Sources"), ("about.html", "About")])
    # platform icons: official monochrome logos from the Simple Icons CDN, never redrawn here.
    # alt is empty because the platform name sits next to each icon as link text.
    follow = '<li><a class="plat" href="subscribe.html">%sNewsletter</a></li>' % ICON_MAIL + "".join(
        '<li><a class="plat" href="%s" target="_blank" rel="noopener"><img src="https://cdn.simpleicons.org/%s/FAF7F1" '
        'width="20" height="20" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">%s'
        '<span class="vh"> (opens in a new tab)</span></a></li>' % (u, n.lower(), n) for n, u in SOCIAL + [("X", X_URL)])
    follow += ('<li><a class="plat" href="%s" target="_blank" rel="noopener"><img src="https://cdn.simpleicons.org/kofi/FAF7F1" '
               'width="20" height="20" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">Support'
               '<span class="vh"> OutbreakLens on Ko-fi (opens in a new tab)</span></a></li>' % KOFI_URL)
    full_title = "OutbreakLens | Weekly animal-disease intelligence" if title == "Home" else f"{title} | OutbreakLens"
    canon = canonical(path)
    if index:
        INDEXED.append(path)
        robots = f'<meta name="robots" content="index,follow"><link rel="canonical" href="{canon}">'
        og_url = f'<meta property="og:url" content="{canon}">'
    else:
        robots, og_url = '<meta name="robots" content="noindex,follow">', ""
    beacon = ("<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
              "data-cf-beacon='{\"token\": \"%s\"}'></script>" % CF_ANALYTICS_TOKEN) if CF_ANALYTICS_TOKEN else ""
    html = f"""<!doctype html><html lang="en-GB"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{full_title}</title><meta name="description" content="{desc}">
{robots}
<meta name="theme-color" content="#1F3864">
<meta property="og:type" content="website"><meta property="og:site_name" content="OutbreakLens">
<meta property="og:title" content="{full_title}"><meta property="og:description" content="{desc}">{og_url}
{SHARE_META}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/styles.css?v={CSS_VER}">
{ICON_LINKS}
{ld_json(ld)}
</head><body>
<a class="skip" href="#main">Skip to main content</a>
<header class="site-header on-dark"><div class="wrap bar">
{BRAND}
<nav class="nav-desktop" aria-label="Main">{desk}</nav>
<details class="nav-mobile"><summary>Menu {ICON_MENU}</summary><nav aria-label="Main">{mob}</nav></details>
</div></header>
<main id="main" tabindex="-1">{body}</main>
<footer class="site-footer on-dark"><div class="wrap">
<div class="foot-grid">
<div class="foot-brand">{BRAND}
<p>Making the world&#39;s animal-disease data make sense. Public surveillance data, turned into clear weekly intelligence.</p>
<p>Contact <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p></div>
<nav aria-label="Footer"><h2>Explore</h2><ul class="foot-links">{explore}</ul></nav>
<div><h2>Follow</h2><ul class="foot-links">{follow}</ul></div>
</div>
<p class="disclaimer">{DISCLAIMER}</p>
<p class="copyright">&copy; {YEAR} OutbreakLens</p>
</div></footer>{beacon}</body></html>"""
    if path == "404.html":
        return _relink(html, "/")
    return _relink(html, "../" * path.count("/")) if "/" in path else html


def page_head(title, lead="", kicker="", extra="", cls=""):
    k = '<p class="kicker">%s%s</p>' % (_mark("kicker-mark"), kicker) if kicker else ""
    l = '<p class="lead">%s</p>' % lead if lead else ""
    return ('<div class="page-head on-dark%s">%s<div class="wrap">%s<h1>%s</h1>%s%s</div></div>'
            % (" " + cls if cls else "", RINGS, k, title, l, extra))

# ---------- tiny markdown -> html ----------
def md2html(md):
    out=[]; inlist=False
    def inline(t):
        t=re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t=re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return t
    for raw in md.splitlines():
        l=raw.rstrip()
        if l.startswith("> "):
            out.append(f"<blockquote>{inline(l[2:])}</blockquote>"); continue
        if re.match(r"^---+$", l): out.append("<hr>"); continue
        if l.startswith("### "): out.append(f"<h3>{inline(l[4:])}</h3>"); continue
        if l.startswith("## "): out.append(f"<h2>{inline(l[3:])}</h2>"); continue
        if l.startswith("# "): out.append(f"<h1>{inline(l[2:])}</h1>"); continue
        if l.startswith("- "):
            if not inlist: out.append("<ul>"); inlist=True
            out.append(f"<li>{inline(l[2:])}</li>"); continue
        if inlist: out.append("</ul>"); inlist=False
        if l.startswith("*") and l.endswith("*") and len(l)>2:
            out.append(f'<p class="note">{inline(l.strip("*"))}</p>'); continue
        if l.strip(): out.append(f"<p>{inline(l)}</p>")
    if inlist: out.append("</ul>")
    return "\n".join(out)

# ---------- load pipeline outputs ----------
os.makedirs(ASSETS, exist_ok=True); os.makedirs(os.path.join(ASSETS,"data"), exist_ok=True)
analysis={}; report_md=""
if os.path.isdir(PIPE) and not PRELAUNCH:
    p=os.path.join(PIPE,"analysis.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f: analysis=json.load(f)
    m=os.path.join(PIPE,"map.html")
    if os.path.exists(m): shutil.copy(m, os.path.join(ASSETS,"map-latest.html"))
    r=os.path.join(PIPE,"weekly_report.md")
    if os.path.exists(r):
        with open(r, encoding="utf-8") as f: report_md=f.read()
    c=os.path.join(PIPE,"cleaned_events.csv")
    if os.path.exists(c): shutil.copy(c, os.path.join(ASSETS,"data","hpai_cleaned_latest.csv"))

def _n(v):   # 2911 -> 2,911 for whole-number counts
    return f"{v:,}" if isinstance(v, int) and not isinstance(v, bool) else v
week=analysis.get("this_week","—")
ev=_n(analysis.get("events_this_week","—"))
co=_n(analysis.get("countries_affected","—"))
wow=analysis.get("wow_pct"); wow_s=(f"{wow:+.1f}%" if isinstance(wow,(int,float)) else "—")
total=_n(analysis.get("total_events_period","—"))


def write(name, html):
    with open(os.path.join(SITE, name), "w", encoding="utf-8") as f:
        f.write(html)

# favicons and share image: copied from brand/final next to this script when it is there
BRAND_FILES = (("favicon.svg", "favicon.svg"), ("favicon.ico", "favicon.ico"), ("favicon-32.png", "favicon-32.png"),
               ("favicon-180.png", "favicon-180.png"), ("social-1200x630.png", "og.png"),
               ("logo-1024-paper.png", "logo-1024.png"))
copied = []
for src, dst in BRAND_FILES:
    if os.path.exists(os.path.join(BRAND_DIR, src)):
        shutil.copy(os.path.join(BRAND_DIR, src), os.path.join(ASSETS, dst))
        copied.append(dst)
print("brand files:", ", ".join(copied) if copied else "none in %s, using the generated favicon" % BRAND_DIR)
if "favicon.svg" not in copied:   # fallback: the generated ring favicon
    write(os.path.join("assets", "favicon.svg"),
     '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1F3864"/><circle cx="16" cy="16" r="6" fill="none" stroke="#C0532B" stroke-width="2.5"/><circle cx="16" cy="16" r="1.6" fill="#fff"/></svg>')
write(os.path.join("assets", "styles.css"), CSS.strip() + "\n")
# the stylesheet link carries a hash of the CSS, so a new deploy never serves a cached old stylesheet
CSS_VER = hashlib.sha256((CSS.strip() + "\n").encode("utf-8")).hexdigest()[:8]
LOGO_URL = SITE_URL + "/assets/logo-1024.png" if "logo-1024.png" in copied else ""   # for the Organization JSON-LD

ICON_LINKS = '<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">'
if "favicon.ico" in copied:
    ICON_LINKS += '<link rel="icon" href="assets/favicon.ico" sizes="any">'
if "favicon-180.png" in copied:
    ICON_LINKS += '<link rel="apple-touch-icon" href="assets/favicon-180.png">'
if "og.png" in copied:   # share scrapers need an absolute image address
    SHARE_META = ('<meta property="og:image" content="%s/assets/og.png"><meta property="og:image:width" content="1200">'
                  '<meta property="og:image:height" content="630"><meta property="og:image:alt" content="OutbreakLens. '
                  'Making the world&#39;s animal-disease data make sense."><meta name="twitter:card" content="summary_large_image">'
                  % SITE_URL)
else:
    SHARE_META = '<meta name="twitter:card" content="summary">'

social_btns = "".join(ext(u, n, "btn btn-outline btn-sm") for n, u in SOCIAL)
email_btn = '<a class="btn btn-primary" href="subscribe.html">Get the weekly email</a>'

# ---------- shorts: covers and cards ----------
os.makedirs(os.path.join(ASSETS, "shorts"), exist_ok=True)
os.makedirs(os.path.join(SITE, "shorts"), exist_ok=True)


def short_cover(slug):
    """Web-size cover (540 px wide JPEG, under 150 KB), made once from content/shorts/<slug>/cover.png and cached
    beside it as cover-540.jpg. Returns the cover's site path, or "" when there is none."""
    folder = os.path.join(SHORTS_DIR, slug)
    web, src = os.path.join(folder, "cover-540.jpg"), os.path.join(folder, "cover.png")
    if not os.path.exists(web) and os.path.exists(src):
        try:
            from PIL import Image
            with Image.open(src) as im:
                small = im.convert("RGB").resize((540, round(im.height * 540 / im.width)), Image.LANCZOS)
            for q in (84, 80, 76, 72, 68, 64, 60):
                small.save(web, "JPEG", quality=q, optimize=True, progressive=True)
                if os.path.getsize(web) < 150_000:
                    break
            print("cover: made %s (%d KB)" % (web, os.path.getsize(web) // 1024))
        except Exception as e:   # Pillow missing or the file unreadable: build without a cover
            print("cover: could not make", web, "-", e)
    if not os.path.exists(web):
        return ""
    shutil.copy(web, os.path.join(ASSETS, "shorts", slug + ".jpg"))
    return "assets/shorts/%s.jpg" % slug


for s in SHORTS:
    s["page"] = "shorts/%s.html" % s["slug"]
    s["cover"] = short_cover(s["slug"])


def short_card(s):
    img = ('<img src="%s" width="540" height="960" alt="" loading="lazy" decoding="async">' % s["cover"]
           if s["cover"] else "")
    return ('<a class="short-card%s" href="%s">%s<div class="short-text"><span class="meta"><span class="tag">%s</span>'
            '%d seconds, as at %s</span><h3>%s</h3><p>%s</p><span class="go">Watch and read</span></div></a>'
            % ("" if img else " no-cover", s["page"], img, s["topic"], s["seconds"], s["as_at_short"],
               escape(s["title"]), escape(s["summary"])))

# ---------- HOME ----------
hero = f"""
<section class="hero on-dark" aria-labelledby="hero-title">
<div class="hero-map">{hero_svg()}</div>
<div class="hero-inner"><div class="hero-panel">
<p class="kicker">{_mark("kicker-mark")}Weekly animal-disease intelligence</p>
<h1 id="hero-title">Making the world&#39;s <span class="nw">animal-disease</span> data make sense.</h1>
<p class="lead">Each week we turn official surveillance data into clear maps, key numbers and a short, sourced briefing.</p>
<div class="actions">{email_btn}{ext(YOUTUBE, "Follow on YouTube" if PRELAUNCH else "Watch on YouTube", "btn btn-light")}</div>
</div></div>
</section>"""

if PRELAUNCH:
    now = f"""
<section class="status" aria-labelledby="status-title"><div class="wrap status-inner">
{_mark("status-mark", on_dark=False)}
<div><h2 id="status-title">First report coming soon</h2>
<p>OutbreakWeekly launches with a map-led situation report on avian influenza, built from the week&#39;s official notifications. Follow the channel to catch the first edition.</p></div>
<div class="actions-row">{social_btns}</div>
</div></section>"""
else:
    now = f"""
<section class="section band-white" aria-labelledby="glance-title"><div class="wrap">
<div class="head-row"><div class="section-head"><h2 id="glance-title">This week at a glance</h2></div>
<a class="more" href="weekly-latest.html">Read the full report</a></div>
<div class="stats">
<div class="stat"><b>{ev}</b><span>HPAI events this week ({week})</span></div>
<div class="stat"><b>{co}</b><span>countries affected</span></div>
<div class="stat"><b>{wow_s}</b><span>week-on-week change</span></div>
<div class="stat"><b>{total}</b><span>events in the trailing record</span></div>
</div>
<div class="head-row"><div class="section-head"><h2>The latest map</h2></div>
<a class="more" href="data.html">Download the data</a></div>
<figure class="mapfig"><div class="mapframe"><iframe src="assets/map-latest.html" title="Interactive map of this week&#39;s reported HPAI events" loading="lazy"></iframe></div>
<figcaption>Reported events by country, with points coloured by host type. Built from public data each week.</figcaption></figure>
</div></section>"""

latest_shorts = f"""
<section class="section band-white" aria-labelledby="shorts-title"><div class="wrap">
<div class="head-row"><div class="section-head"><h2 id="shorts-title">Latest shorts</h2>
<p>Short map videos on the week&#39;s animal-disease news, each with the key numbers and every source.</p></div>
<a class="more" href="watch.html">All shorts</a></div>
<div class="short-cards">{"".join(short_card(s) for s in SHORTS[:2])}</div>
</div></section>"""

home = hero + now + latest_shorts + f"""
<section class="section" aria-labelledby="what-title"><div class="wrap">
<div class="section-head"><h2 id="what-title">What we do</h2></div>
<div class="pillars">
<div class="pillar">{ICON_SYNTH}<h3>We synthesise</h3><p>We read the official portals each week and turn them into plain English, maps and charts.</p></div>
<div class="pillar">{ICON_SIGN}<h3>We signpost</h3><p>Every figure links to a named public source and date. We point you to the authorities, never replace them.</p></div>
<div class="pillar">{ICON_CALM}<h3>We stay calm</h3><p>Context over clickbait. We state uncertainty and correct mistakes promptly.</p></div>
</div></div></section>

<section class="section band-white" aria-labelledby="who-title"><div class="wrap split">
<div class="section-head"><h2 id="who-title">Who it is for</h2><p>Anyone who needs a clear, sourced view of animal disease without reading every portal.</p></div>
<ul class="audience">
<li><h3>Farmers and smallholders</h3><p>What is spreading and where, with links to the official guidance.</p></li>
<li><h3>Vets and students</h3><p>Sourced numbers and maps you can check, cite and teach from.</p></li>
<li><h3>Traders and industry</h3><p>Trends across regions and species, linked to the official notices.</p></li>
<li><h3>Journalists and educators</h3><p>Plain-English context and a named source for every figure.</p></li>
</ul></div></section>

<section class="section" aria-labelledby="src-title"><div class="wrap">
<div class="head-row"><div class="section-head"><h2 id="src-title">Built on official sources</h2>
<p>We use public data from these bodies and link to them in every report. We are not affiliated with any of them.</p></div>
<a class="more" href="sources.html">See all sources</a></div>
<ul class="source-row">
<li><b>WOAH</b><span>World Organisation for Animal Health</span></li>
<li><b>EU ADIS</b><span>EU Animal Disease Information System</span></li>
<li><b>FAO EMPRES-i+</b><span>UN Food and Agriculture Organization</span></li>
<li><b>EFSA</b><span>European Food Safety Authority</span></li>
<li><b>Defra / APHA</b><span>UK Government</span></li>
<li><b>ECDC / WHO / OFFLU</b><span>Zoonotic and influenza context</span></li>
</ul></div></section>

<section class="cta-band on-dark" aria-labelledby="cta-title">{RINGS}<div class="wrap">
<h2 id="cta-title">The week in animal disease, in five minutes.</h2>
<p>One clear email a week with the key numbers, the map and what to watch. Free.</p>
{email_btn}
</div></section>
"""
write("index.html", page("Home", "index.html", home,
      "Weekly animal-disease intelligence. Official surveillance data turned into clear maps, key numbers and a short, sourced briefing."))

# ---------- WEEKLY ----------
if PRELAUNCH:
    weekly = page_head("Weekly reports",
        "The first situation report is in production. Reports will appear here, newest first, with the map and the data behind each one.",
        "OutbreakWeekly") + f"""
<section class="section"><div class="wrap"><div class="narrow">
<h2>What each report will include</h2>
<ul class="checklist">
<li>A map of the week&#39;s official notifications</li>
<li>The key numbers, with the change on last week</li>
<li>A short briefing on what to watch</li>
<li>Links to every source, plus the clean data</li>
</ul>
<div class="actions">{email_btn}{ext(YOUTUBE, "Follow on YouTube", "btn btn-outline")}</div>
</div></div></section>"""
else:
    weekly = page_head("Weekly reports", "A running archive of the weekly situation report. The newest is at the top.",
                       "OutbreakWeekly") + f"""
<section class="section"><div class="wrap">
<a class="report-card" href="weekly-latest.html">
<span class="meta">Week {week} <span class="tag">Latest</span><span class="tag">HPAI</span></span>
<h2>HPAI situation report, week {week}</h2>
<p>{ev} new events across {co} countries ({wow_s} week on week). Map, key numbers and a 60-second brief.</p>
<span class="go">Read the report</span></a>
<p class="note archive-note">Earlier reports appear here automatically as the pipeline runs each week.</p>
</div></section>"""
write("weekly.html", page("Weekly", "weekly.html", weekly, "The OutbreakWeekly situation report archive."))

# ---------- WEEKLY LATEST (rendered report) ----------
report_html=md2html(report_md) if report_md else "<p>Run the pipeline to generate this week&#39;s report.</p>"
latest=f"""
<nav class="crumbs on-dark" aria-label="Breadcrumb"><div class="wrap"><a href="weekly.html">Weekly reports</a>
<span aria-hidden="true"> / </span><span aria-current="page">Week {week}</span></div></nav>
<section class="section"><div class="wrap report">
<article class="prose">{report_html}
<div class="actions"><a class="btn btn-outline" href="weekly.html">All reports</a><a class="btn btn-primary" href="data.html">Download the data</a></div></article>
<div class="mapframe"><iframe src="assets/map-latest.html" title="Map of this week&#39;s reported events" loading="lazy"></iframe></div>
</div></section>"""
if PRELAUNCH:
    latest = page_head("No report yet",
        'The first OutbreakWeekly report is coming soon. <a href="weekly.html">Back to weekly reports</a>.')
# before launch this page is only a "No report yet" placeholder, so it stays out of search and the sitemap
write("weekly-latest.html", page(f"Week {week}", "weekly.html", latest, path="weekly-latest.html", index=not PRELAUNCH))

# ---------- DATA ----------
licence = ('<p class="note">Licence: free to reuse with attribution to OutbreakLens and to the original data providers. '
           'Derived from publicly available sources. Always check the primary source&#39;s own terms.</p>')
if PRELAUNCH:
    data = page_head("Clean data, free to use",
        "Every report will come with a tidy, de-duplicated dataset: one row per reported event, standard columns, "
        "ready for your own analysis. The first dataset is published with the first report.") + f"""
<section class="section"><div class="wrap"><div class="narrow">{licence}
<div class="actions">{email_btn}</div></div></div></section>"""
else:
    data = page_head("Clean data, free to use",
        "The tidy, de-duplicated dataset behind every report. One row per reported event, standard columns, "
        "ready for your own analysis.") + f"""
<section class="section"><div class="wrap">
<table class="data-table"><caption class="vh">Datasets to download</caption>
<thead><tr><th scope="col">Dataset</th><th scope="col">Description</th><th scope="col">Format</th><th scope="col">Download</th></tr></thead>
<tbody>
<tr><td data-label="Dataset">HPAI events, latest</td><td data-label="Description">Cleaned avian influenza events (week {week} snapshot)</td><td data-label="Format">CSV</td><td data-label="Download"><a href="assets/data/hpai_cleaned_latest.csv">Download CSV</a></td></tr>
<tr><td data-label="Dataset">Schema and methods</td><td data-label="Description">How the data is sourced and cleaned, and what each column means</td><td data-label="Format">Page</td><td data-label="Download"><a href="sources.html">Read</a></td></tr>
</tbody></table>
{licence}
</div></section>"""
write("data.html", page("Data", "data.html", data, "Clean, free-to-use animal-disease event data behind every OutbreakLens report."))

# ---------- SOURCES ----------
SRC=[("WOAH WAHIS","Global official disease notifications and dashboards.","https://wahis.woah.org/"),
("EU ADIS","EU outbreak notifications (successor to ADNS), linked to WAHIS.","https://food.ec.europa.eu/animals/animal-diseases/animal-disease-information-system-adis_en"),
("FAO EMPRES-i+","Global disease events, mapping layers and early warning.","https://empres-i.apps.fao.org/"),
("EFSA","Avian influenza and ASF surveillance reports and datasets.","https://www.efsa.europa.eu/en/topics/topic/avian-influenza"),
("SHIC","Global swine disease monitoring reports.","https://www.swinehealth.org/"),
("Defra / APHA","UK outbreak assessments and notifiable-disease updates.","https://www.gov.uk/government/collections/animal-diseases-international-and-uk-monitoring"),
("ECDC / WHO / OFFLU","Zoonotic and influenza-at-the-interface context.","https://www.offlu.org/")]
def _slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def _domain(u): return re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
cards="".join('<article class="card" id="%s"><h2>%s</h2><p>%s</p><p class="domain">%s</p>%s</article>'
              % (_slug(n), n, d, _domain(u), ext(u, "Visit " + n, "card-link", ICON_EXT)) for n,d,u in SRC)
sources = page_head("Authoritative sources",
    "We interpret and signpost. We never replace the authorities below. For official figures, decisions and guidance, always go to the primary source.") + f"""
<section class="section"><div class="wrap"><div class="cards">{cards}</div></div></section>"""
write("sources.html", page("Sources", "sources.html", sources, "The official animal-health sources OutbreakLens uses and signposts."))

# ---------- ABOUT ----------
PROMISE_MARK = _mark("promise-mark", on_dark=False)
about = page_head("An accessible lens on animal disease") + f"""
<section class="section"><div class="wrap about">
<div class="prose">
<p class="intro">Avian influenza, African swine fever and bluetongue are rarely out of the news. The data exists, but it is scattered across technical portals and rarely packaged for people who want to understand what is happening and why it matters.</p>
<h2>What we do</h2>
<p>Each week we read the world&#39;s open animal-health data and turn it into clear maps, short videos and a plain-English briefing. We synthesise, we signpost the authorities behind the numbers, and we stay calm.</p>
<h2>Who writes it</h2>
<p>OutbreakLens is produced by a veterinary epidemiologist in a personal capacity. It uses only publicly available information and is not affiliated with or endorsed by any government body.</p>
</div>
<aside class="promise-box" aria-labelledby="promise-title">
<h2 id="promise-title">Our promise</h2>
<ul class="promise">
<li>{PROMISE_MARK}Every figure is traceable to a named public source and date.</li>
<li>{PROMISE_MARK}Uncertainty is stated. Corrections are issued promptly.</li>
<li>{PROMISE_MARK}Nothing here is veterinary, trade or official advice.</li>
</ul>
{email_btn}
</aside>
</div></section>"""
write("about.html", page("About", "about.html", about, "About OutbreakLens, an accessible lens on animal disease."))

# ---------- SUBSCRIBE ----------
# v6: the pre-launch line "The first edition goes out with the first report." is gone. Issue 1 goes out on
# Friday 23 October 2026, before the first weekly report, and the "Latest issue" link below says so.
sub_lead = "One clear email a week: the key numbers, the map and what to watch. Free."
sub = page_head("The week in animal disease, in five minutes.", sub_lead, cls="overlap") + f"""
<section class="section pull"><div class="wrap">
<div class="signup">
<h2>Get the weekly email</h2>
<div class="embed">{BEEHIIV_EMBED}
<noscript><p>The sign-up form needs JavaScript. You can still follow OutbreakLens on the channels below.</p></noscript></div>
<p class="note">No spam. Unsubscribe at any time.</p>
<p class="note support">OutbreakLens is free. If it saves you time, you can {ext(KOFI_URL, "support it on Ko-fi")}.</p>
</div>
<div class="latest"><h2>Latest issue</h2><p>{ext(NEWSLETTER_LATEST[0], NEWSLETTER_LATEST[1], "card-link", ICON_EXT)}</p></div>
<div class="follow"><h2>Or follow OutbreakLens</h2><div class="actions-row">{social_btns}</div></div>
</div></section>"""
write("subscribe.html", page("Subscribe", "subscribe.html", sub, "Get the OutbreakLens weekly email. Free."))

# ---------- WATCH ----------
watch = page_head("Short videos, mapped and sourced",
    "Map-led videos of about 90 seconds on the week&#39;s animal-disease news. Each one has a page with the key "
    "numbers, what it means for keepers and every source. Newest first.", "OutbreakWeekly shorts") + f"""
<section class="section"><div class="wrap">
<div class="short-cards">{"".join(short_card(s) for s in SHORTS)}</div>
<div class="follow"><h2>Follow for the next one</h2><div class="actions-row">{social_btns}{ext(X_URL, "X", "btn btn-outline btn-sm")}</div></div>
</div></section>"""
write("watch.html", page("Watch", "watch.html", watch,
      "Short map videos on animal disease, each with the key numbers, what it means for keepers and every source."))


def _md_links(t):
    """Plain text with [label](url) links to HTML. The links open in a new tab."""
    out, last = [], 0
    for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", t):
        out.append(escape(t[last:m.start()]) + ext(escape(m.group(2)), escape(m.group(1))))
        last = m.end()
    return "".join(out) + escape(t[last:])


for s in SHORTS:
    vid, title = s["youtube_id"], escape(s["title"])
    nums = "".join("<li><b>%s</b><span>%s</span></li>" % (escape(a), escape(b)) for a, b in s["numbers"])
    keepers = "".join("<li>%s</li>" % _md_links(k) for k in s["keepers"])
    zones = ""
    if s.get("zones"):
        zh, zi, zl, zn = s["zones"]
        zones = ('\n<h3>%s</h3>\n<p>%s</p>\n<ul>%s</ul>\n<p class="note">%s</p>'
                 % (escape(zh), escape(zi), "".join("<li>%s</li>" % escape(z) for z in zl), escape(zn)))
    srcs = "".join("<li>%s<span>, %s</span></li>" % (ext(escape(u), escape(n)), escape(d)) for n, d, u in s["sources"])
    src_note = '\n<p class="note">%s</p>' % escape(s["sources_note"]) if s.get("sources_note") else ""
    copies = "".join(ext(escape(u), n, "btn btn-outline btn-sm") for n, u in s["copies"])
    body = ('\n<nav class="crumbs on-dark" aria-label="Breadcrumb"><div class="wrap"><a href="watch.html">Watch</a>'
            '<span aria-hidden="true"> / </span><span aria-current="page">%s</span></div></nav>' % escape(s["topic"])
            + page_head(title, "Figures as at %s. %s" % (s["as_at"], escape(s["lead"])), "OutbreakWeekly short") + f"""
<section class="section"><div class="wrap short-layout">
<div class="short-media"><div class="short-frame"><iframe src="https://www.youtube-nocookie.com/embed/{vid}?rel=0" title="Video: {title}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div>
<p class="note">{s["seconds"]} seconds, with on-screen captions. Plays from YouTube in privacy-enhanced mode.</p></div>
<article class="prose short-body">
<h2>Key numbers</h2>
<ul class="keynums">{nums}</ul>
<p class="note">{escape(s["numbers_note"])}</p>
<h2>What it means for keepers</h2>
<ul>{keepers}</ul>{zones}
<h2>Sources</h2>
<ol class="src-list">{srcs}</ol>{src_note}
<p class="disclaimer-box">{escape(DISCLAIMER)}</p>
<h2>Watch it elsewhere</h2>
<div class="actions-row">{copies}</div>
<h2>Get the weekly email</h2>
<p>One clear email a week: the key numbers, the map and what to watch. Free. Latest issue: {ext(NEWSLETTER_LATEST[0], NEWSLETTER_LATEST[1])}.</p>
<div class="actions">{email_btn}<a class="btn btn-outline" href="watch.html">All shorts</a></div>
</article>
</div></section>""")
    video = {"@type": "VideoObject", "name": s["video_title"], "description": s["description"],
             "thumbnailUrl": [SITE_URL + "/" + s["cover"] if s["cover"] else "https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid],
             "uploadDate": s["uploaded"], "duration": "PT%dM%dS" % divmod(s["seconds"], 60),
             "embedUrl": "https://www.youtube-nocookie.com/embed/" + vid,
             "contentUrl": "https://www.youtube.com/shorts/" + vid,
             "inLanguage": "en-GB", "publisher": {"@id": SITE_URL + "/#organization"}}
    write(s["page"], page(title, "watch.html", body, escape(s["meta"]), path=s["page"], ld=video))

# Cloudflare niceties
write("_redirects", "/  /index.html  200\n")
write("404.html", page("Not found", "index.html", page_head("Page not found",
    'Try the <a href="index.html">home page</a> or the <a href="weekly.html">weekly reports</a>.'),
    path="404.html", index=False))

# ---------- search: sitemap.xml and robots.txt (written last, after every page) ----------
write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
      + "".join("<url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (canonical(p), TODAY.isoformat()) for p in INDEXED)
      + "</urlset>\n")
write("robots.txt", "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)

print("built site ->", SITE)
print("pages:", sorted(f for f in os.listdir(SITE) if f.endswith(".html")) + [s["page"] for s in SHORTS])
print("sitemap:", len(INDEXED), "pages")
