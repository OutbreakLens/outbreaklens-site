#!/usr/bin/env python3
"""
build_site.py: generate the OutbreakLens static website.

Static HTML and CSS, no build step, drops straight into Cloudflare Pages.
Pulls the latest map, report and cleaned data from the pipeline outputs so the
site refreshes itself each week.

    python build_site.py              # uses pipeline/outputs next to this script if present
    python build_site.py --prelaunch  # holding site with no report data

With live data (pipeline/data) the home page leads with the live map and its
table, the same block as map.html. Without it, the home-page hero is a
dot-matrix world map written as inline SVG. Land comes from Natural Earth (public domain). The computed dots are cached in
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
# latest newsletter issue: web address, label and title (the web version went live on 23 October 2026)
NEWSLETTER_LATEST = ("https://outbreaklens.beehiiv.com/p/bird-flu-is-back-and-bluetongue-passes-3-400-cases",
                     "Issue 1, Friday 23 October 2026", "Bird flu is back, and bluetongue passes 3,400 cases")
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
# Map, Numbers and Downloads sit under Data. Those three pages share this sub-navigation at the top.
DATA_NAV = [("map.html", "Map"), ("analytics.html", "Numbers"), ("data.html", "Downloads")]
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

# ---------- OutbreakWeekly episodes: one entry per episode, newest first ----------
# The newest is the latest episode on the Weekly page, with its chapters, and in the "This week" band on the home
# page. Its thumbnail comes from content/episodes/<slug>/thumb.png next to this script, resized once to
# thumb-640.jpg beside it. Without that folder the copy already published in website/assets/episodes is kept.
EPISODES = [
    {
        "number": 1, "slug": "ep01", "youtube_id": "yQPZnu7jQN8",
        "title": "OutbreakWeekly: bird flu is back, bluetongue passes 3,400 cases, and the watch list (22 Oct 2026)",
        "as_at": "22 October 2026", "as_at_short": "22 Oct 2026", "length": "About 6 minutes",
        "summary": ("Bird flu is back in Great Britain with two cases and two viruses. Bluetongue has reached 3,441 "
                    "cases, with the whole of England, Wales and Scotland in a restricted zone, and 48 herds in Ireland. "
                    "The watch list: foot-and-mouth in Cyprus and Lesvos, sheep and goat pox in south-east Europe, and "
                    "African swine fever in Finland."),
        "chapters": [("0:00", "Title"), ("0:16", "Headline numbers"), ("0:41", "Bird flu, Great Britain"),
                     ("1:12", "Risk and rules"), ("1:43", "Bird flu, Europe"), ("2:07", "Bluetongue, the numbers"),
                     ("2:38", "Zones and moves"), ("3:05", "Reading the numbers"), ("3:31", "Ireland"),
                     ("3:49", "The watch list"), ("4:35", "What it means for keepers"), ("5:06", "Sources")],
        "newsletter": NEWSLETTER_LATEST,
    },
]
EPISODES_DIR = os.path.join(ROOT, "content", "episodes")

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
--font:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
--font-head:"Montserrat","Inter",system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
--gutter:16px;--wrap:1180px;--radius:10px}
@media(min-width:768px){:root{--gutter:24px}}
@media(min-width:1024px){:root{--gutter:32px}}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--font);font-weight:400;font-size:17px;line-height:1.65;
overflow-wrap:break-word;-webkit-font-smoothing:antialiased}
svg,iframe,img{max-width:100%}
h1,h2,h3{font-family:var(--font-head);font-weight:700;color:var(--navy);line-height:1.2;letter-spacing:-.015em;margin:0 0 .5em;text-wrap:balance}
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
font-family:var(--font-head);font-weight:800;font-size:1.1875rem;letter-spacing:-.01em;line-height:1}
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
@media(min-width:768px){.bar{min-height:68px}}
@media(min-width:768px){.nav-desktop{display:flex;align-items:center;gap:2px}.nav-mobile{display:none}}
@media(min-width:768px) and (max-width:899px){.nav-desktop a{padding:10px 9px}.nav-desktop a.nav-cta{margin-left:6px;padding:10px 14px}}
/* sub-navigation for the data pages */
.subnav{background:var(--navy-deep);border-bottom:1px solid rgba(250,247,241,.08)}
.subnav ul{display:flex;gap:0 26px;list-style:none;margin:0;padding:0}
.subnav a{display:inline-flex;align-items:center;min-height:46px;padding-top:3px;border-bottom:3px solid transparent;
color:var(--on-dark2);text-decoration:none;font-size:.9375rem;font-weight:600}
.subnav a:hover{color:#fff}
.subnav a[aria-current="page"]{color:#fff;border-bottom-color:var(--accent)}

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
.hero h1{color:#fff;font-size:clamp(1.875rem,1.3rem + 2.4vw,2.75rem);font-weight:800;line-height:1.14;letter-spacing:-.02em;margin:0 0 18px}
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
.section-head h2{font-size:clamp(1.5rem,1.2rem + 1.2vw,2rem);margin:0 0 10px}
.section-head p{margin:0;color:var(--ink2);font-size:1.0625rem}
.head-row{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px 32px;margin:0 0 32px}
.head-row .section-head{margin:0}
.more{font-weight:600}

/* status strip (pre-launch) */
.status{background:var(--card);border-bottom:1px solid var(--line);padding:28px 0}
.status-inner{display:grid;gap:16px}
.status-mark{width:40px;height:40px}
.status h2{font-size:1.25rem;margin:0 0 4px}
.status p{margin:0;color:var(--ink2);max-width:40em}
@media(min-width:960px){.status{padding:32px 0}.status-inner{grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:28px}}

/* what we do */
.pillars{display:grid;gap:32px}
@media(min-width:768px){.pillars{grid-template-columns:repeat(3,minmax(0,1fr));gap:28px}}
@media(min-width:1100px){.pillars{gap:48px}}
.pillar{border-top:1px solid var(--line);padding-top:24px}
.icon{width:44px;height:44px;color:var(--navy);display:block;margin:0 0 16px}
.pillar h3{font-size:1.25rem;margin:0 0 8px}
.pillar p{margin:0;color:var(--ink2)}

/* who it is for */
.split{display:grid}
@media(min-width:1100px){.split{grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:72px;align-items:start}}
.audience{list-style:none;margin:0;padding:0;display:grid}
@media(min-width:640px){.audience{grid-template-columns:repeat(2,minmax(0,1fr));column-gap:32px}}
.audience li{border-top:1px solid var(--line);padding:20px 0 22px}
.audience h3{font-size:1.125rem;margin:0 0 6px}
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
.cta-band h2{color:#fff;font-size:clamp(1.5rem,1.2rem + 1.4vw,2.25rem);max-width:15em;margin:0 0 12px}
.cta-band p{color:var(--on-dark2);max-width:32em;margin:0 0 28px;font-size:1.0625rem}
.rings{position:absolute;pointer-events:none;width:380px;height:380px;right:-300px;top:-40px;opacity:.6}
@media(min-width:768px){.cta-band{padding:88px 0}.rings{width:520px;height:520px;right:-110px;top:50%;transform:translateY(-50%);opacity:1}}

/* inner page head */
.page-head{position:relative;overflow:hidden;background:var(--navy);color:var(--on-dark);padding:44px 0 48px}
.page-head .wrap{position:relative}
.page-head h1{color:#fff;font-size:clamp(1.75rem,1.3rem + 2vw,2.75rem);font-weight:800;line-height:1.12;letter-spacing:-.02em;max-width:17em;margin:0 0 14px}
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
.card h2{font-size:1.25rem;margin:0 0 8px}
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
.prose h1{font-size:clamp(1.75rem,1.3rem + 1.8vw,2.375rem)}
.prose h2{font-size:1.375rem;margin:1.8em 0 .5em}
.prose h2:first-child{margin-top:0}
.prose h3{font-size:1.125rem;margin:1.5em 0 .4em}
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
.promise-box h2{font-size:1.375rem;margin:0 0 8px}
@media(min-width:1024px){.about{grid-template-columns:minmax(0,1fr) 380px;gap:72px;align-items:start}
.promise-box{position:sticky;top:96px}}

/* subscribe */
.section.pull{padding-top:0}
.signup{position:relative;max-width:640px;margin-top:-56px;background:var(--card);border:1px solid var(--line);
border-top:4px solid var(--accent);border-radius:var(--radius);padding:28px 20px 24px;box-shadow:0 24px 48px -28px rgba(20,30,50,.45)}
.signup h2{font-size:1.375rem;margin:0 0 4px}
.signup .embed{min-height:120px;margin:12px 0 8px}
.signup .note{margin:0}
.follow{margin-top:48px}
.follow h2{font-size:1.125rem;margin:0 0 14px}
@media(min-width:768px){.signup{margin-top:-76px;padding:36px 40px 32px}}
.signup .support{margin-top:10px}
.latest{margin-top:40px}
.latest h2{font-size:1.125rem;margin:0 0 6px}
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
.short-card h3{font-size:1.125rem;margin:0;color:var(--navy)}
.short-card p{margin:0;color:var(--ink2);font-size:.9375rem;line-height:1.55}
.short-card .meta{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font-size:.8125rem;color:var(--muted)}
.short-card .go{margin-top:auto;padding-top:4px;font-weight:600;color:var(--navy);text-decoration:underline;text-underline-offset:.2em}
.short-card:hover .go{color:var(--accent-dark)}
@media(min-width:640px){.short-card{grid-template-columns:160px minmax(0,1fr)}
.short-text{padding:22px 24px 24px;gap:10px}.short-card h3{font-size:1.1875rem}}

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
.keynums b{font-family:var(--font-head);font-weight:700;font-size:1.25rem;line-height:1.25;color:var(--navy)}
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
.report-card h2{font-size:1.375rem;margin:0}
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
.stat b{display:block;font-family:var(--font-head);font-weight:700;font-size:clamp(1.75rem,1.4rem + 1.4vw,2.5rem);color:var(--navy);line-height:1.1;margin:0 0 6px}
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
.site-footer h2{font-size:.9375rem;font-weight:700;letter-spacing:0;color:#fff;margin:0 0 12px}
.foot-grid{display:grid;gap:32px}
@media(min-width:768px){.foot-grid{grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr);gap:40px}}
.foot-brand p{max-width:28em}
.foot-links{list-style:none;margin:0;padding:0}
.foot-links li{margin:0 0 8px}
.plat{display:inline-flex;align-items:center;gap:10px;min-height:28px}
.plat img,.plat svg{width:20px;height:20px;flex:none}
.disclaimer{margin:40px 0 0;padding-top:20px;border-top:1px solid rgba(250,247,241,.14);font-size:.8125rem;line-height:1.55;color:var(--on-dark3);max-width:62em}
.copyright{margin:10px 0 0;font-size:.8125rem;color:var(--on-dark3)}

/* live data pages: map, numbers, data */
.section.tight{padding:28px 0 56px}
@media(min-width:768px){.section.tight{padding:40px 0 72px}}
.section.tight + .section.tight{padding-top:0}
.lede-row{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline;margin:0 0 20px;font-size:.875rem;font-weight:400;color:var(--muted)}
.filters{display:grid;gap:18px;margin:0 0 18px}
.chips{border:0;margin:0;padding:0;min-width:0}
.chips legend,.field-label{display:block;font-size:.875rem;font-weight:600;color:var(--ink2);margin:0 0 8px;padding:0}
.chip-row{display:flex;flex-wrap:wrap;gap:8px}
.chip{position:relative;display:inline-flex}
.chip input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer}
.chip span{display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:8px 14px;border:1px solid #d9d2c5;
border-radius:999px;background:var(--card);font-size:.875rem;font-weight:600;color:var(--navy);line-height:1.2}
.chip input:hover + span{border-color:var(--navy2)}
.chip input:checked + span{background:var(--navy);border-color:var(--navy);color:#fff}
.chip input:focus-visible + span{outline:3px solid var(--accent);outline-offset:2px}
.cat-dot{width:10px;height:10px;border-radius:50%;background:var(--c);flex:none;box-shadow:0 0 0 2px #fff}
@media(max-width:639px){.chip-row{gap:6px}.chip span{min-height:36px;padding:6px 10px;gap:6px;font-size:.8125rem}}
.time-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.time-row .slider{grid-column:1/-1}
@media(min-width:900px){.time-row{grid-template-columns:11rem 11rem minmax(0,1fr);align-items:start;gap:20px}.time-row .slider{grid-column:auto}}
.field{display:grid;gap:6px;min-width:0}
.field select{font:inherit;font-size:.9375rem;font-weight:400;color:var(--ink);width:100%;min-height:44px;padding:8px 36px 8px 12px;
border:1px solid #cfc8bb;border-radius:6px;cursor:pointer;-webkit-appearance:none;-moz-appearance:none;appearance:none;
background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'%3E%3Cpath d='M1 1.5l5 5 5-5' fill='none' stroke='%231F3864' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") no-repeat right 13px center/12px 8px}
.field select:hover{border-color:var(--navy2)}
.field select::-ms-expand{display:none}
.slider input[type=range]{-webkit-appearance:none;-moz-appearance:none;appearance:none;display:block;width:100%;height:36px;margin:0;
padding:0;background:transparent;cursor:pointer}
.slider input[type=range]:focus{outline:none}
.slider input[type=range]::-webkit-slider-runnable-track{height:3px;border:0;border-radius:2px;background:var(--navy)}
.slider input[type=range]::-moz-range-track{height:3px;border:0;border-radius:2px;background:var(--navy)}
.slider input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;box-sizing:border-box;width:14px;height:22px;
margin-top:-9.5px;border:1px solid var(--navy);border-radius:2px;background:linear-gradient(#eef0f2,#c3c8ce);
box-shadow:0 1px 2px rgba(21,36,63,.28)}
.slider input[type=range]::-moz-range-thumb{box-sizing:border-box;width:14px;height:22px;border:1px solid var(--navy);border-radius:2px;
background:linear-gradient(#eef0f2,#c3c8ce);box-shadow:0 1px 2px rgba(21,36,63,.28)}
.slider input[type=range]:hover::-webkit-slider-thumb{background:linear-gradient(#e4e7ea,#b1b7bf)}
.slider input[type=range]:hover::-moz-range-thumb{background:linear-gradient(#e4e7ea,#b1b7bf)}
.slider input[type=range]:focus-visible::-webkit-slider-thumb{box-shadow:0 0 0 2px #fff,0 0 0 5px var(--accent)}
.slider input[type=range]:focus-visible::-moz-range-thumb{box-shadow:0 0 0 2px #fff,0 0 0 5px var(--accent)}
.slider output{display:block;font-size:.875rem;font-weight:400;color:var(--ink2)}
.map-summary{margin:0 0 10px;font-size:.9375rem;font-weight:400;color:var(--ink2)}
.map-shell{position:relative;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:#f2f3f0}
#map{height:64vh;min-height:360px;max-height:620px}
@media(min-width:768px){#map{height:580px}}
.map-shell noscript p,.map-shell .map-off{margin:0;padding:24px}
.map-shell .maplibregl-map{font-family:var(--font)}
.map-shell .maplibregl-ctrl-attrib{font-size:11px;font-weight:400}
.map-shell .maplibregl-ctrl-attrib a{color:var(--ink2)}
.map-shell .maplibregl-popup-content{padding:14px 16px 12px;border-radius:8px;box-shadow:0 4px 18px rgba(21,36,63,.22);
font-size:.875rem;line-height:1.5;font-weight:400;color:var(--ink)}
.map-shell .maplibregl-popup-close-button{width:32px;height:32px;font-size:20px;line-height:1;color:var(--ink2);border-radius:0 8px 0 6px}
.map-shell .maplibregl-popup-close-button:hover{background:#f1efe9}
.map-shell .maplibregl-popup-close-button:focus-visible{outline:3px solid var(--accent);outline-offset:-3px}
.pop .pop-title{display:flex;align-items:center;gap:8px;margin:0 26px 2px 0;font-size:1rem;font-weight:600;line-height:1.3;color:var(--navy)}
.pop .pop-title svg{flex:none;width:18px;height:18px}
.pop .pop-place{margin:0;color:var(--ink2)}
.pop .pop-pop{margin:0 0 8px;color:var(--ink2)}
.pop .pop-num{margin:0}
.pop .pop-n{display:block;font-family:var(--font-head);font-size:1.375rem;font-weight:700;line-height:1.1;color:var(--navy);margin:0 0 2px}
.pop .pop-meta{margin:8px 0 0;font-size:.8125rem;line-height:1.45;color:var(--muted)}
.pop .pop-links{margin:10px 0 0;padding:8px 0 0;border-top:1px solid var(--line);font-size:.8125rem}
.pop a{color:var(--navy)}
.pop-count{margin:0 26px 10px 0;font-size:.8125rem;font-weight:600;color:var(--muted)}
.pop-list{max-height:min(320px,46vh);overflow:auto;margin:0 -16px;padding:0 16px}
.pop-list .pop + .pop{margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
.pop-list .pop .pop-title{margin-right:0}
.legend{display:grid;gap:12px 20px;margin:16px 0 0;font-size:.875rem;font-weight:400;color:var(--ink2)}
.legend-title{margin:0 0 6px;font-size:.8125rem;font-weight:600;color:var(--muted)}
@media(min-width:768px){.legend{grid-template-columns:max-content minmax(0,1fr);gap:8px 24px;align-items:baseline}
.legend > div{display:contents}.legend-title{margin:0}}
.legend ul{display:flex;flex-wrap:wrap;gap:6px 18px;list-style:none;margin:0;padding:0}
.legend li{display:inline-flex;align-items:center;gap:7px}
.legend svg{width:18px;height:18px;flex:none}
.sw{width:18px;height:8px;border-radius:4px;background:var(--c);flex:none}
.key-cluster{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:var(--navy);
color:#fff;font:600 10px/1 var(--font);box-shadow:0 0 0 2px #fff}
.below-map{display:grid;gap:4px;margin:18px 0 0;max-width:52rem}
.map-after .tbl-block{margin-top:18px}
@media(min-width:1100px){.map-after{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:48px;align-items:start}
.map-after .below-map{margin-top:28px}.map-after .tbl-block{margin-top:28px}}
.below-map p{margin:0 0 6px}
.updated{font-size:.875rem;font-weight:400;color:var(--ink2)}
.src-block{max-width:52rem;margin:40px 0 0;padding-top:24px;border-top:1px solid var(--line)}
.src-block h2{font-size:1.25rem;margin:0 0 12px}
.src-items{list-style:none;margin:0 0 14px;padding:0;font-size:.9375rem;font-weight:400}
.src-items li{padding:10px 0;border-bottom:1px solid var(--line)}
.src-items li:first-child{border-top:1px solid var(--line)}
.src-items b{font-weight:600;color:var(--navy)}
.src-items span{display:block;color:var(--muted);font-size:.8125rem;margin-top:2px}
.fine{font-size:.8125rem;line-height:1.55;font-weight:400;color:var(--muted);margin:0 0 8px}
.tiles{display:grid;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;margin:0 0 28px}
@media(min-width:640px){.tiles{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1024px){.tiles{grid-template-columns:repeat(3,minmax(0,1fr))}}
.tile{background:var(--card);padding:20px 20px 18px;display:flex;flex-direction:column;gap:6px;min-width:0}
.tile b{display:block;font-family:var(--font-head);font-weight:700;font-size:clamp(2rem,1.7rem + 1.2vw,2.625rem);line-height:1.05;color:var(--navy)}
.tile .t-label{color:var(--ink);font-weight:400;line-height:1.45}
.tile .t-src{margin-top:auto;padding-top:6px;font-size:.8125rem;color:var(--muted);font-weight:400;line-height:1.45}
.facts{margin:0;border-top:1px solid var(--line)}
.facts div{display:grid;gap:2px 20px;padding:12px 0;border-bottom:1px solid var(--line)}
@media(min-width:768px){.facts div{grid-template-columns:15rem minmax(0,1fr)}}
.facts dt{font-weight:600;color:var(--navy);font-size:.9375rem}
.facts dd{margin:0;color:var(--ink2);font-weight:400;font-size:.9375rem}
.chart-card{position:relative;display:flex;flex-direction:column;min-width:0;background:var(--card);border:1px solid var(--line);
border-radius:var(--radius);padding:20px 18px 16px}
.chart-card[hidden]{display:none}
.chart-card h3{display:flex;align-items:center;gap:10px;font-size:1.0625rem;margin:0 0 4px}
.chart-sub{margin:0 0 12px;font-size:.875rem;line-height:1.45;color:var(--ink2);font-weight:400}
.chart{display:block;width:100%;max-width:520px;height:auto;overflow:visible}
.chart:focus-visible{outline:3px solid var(--accent);outline-offset:4px;border-radius:4px}
.chart .grid{stroke:#ece7de;stroke-width:1}
.chart .base{stroke:#c9c2b5;stroke-width:1}
.chart text{font-family:var(--font)}
.chart .tick,.chart .xl{font-size:11px;font-weight:400;fill:#6b7280;font-variant-numeric:tabular-nums}
.chart .bar{fill:#6b7280}
.chart .bar.now{fill:var(--c,var(--accent))}
.chart .bar.on{fill:#454c58}
.chart .bar.now.on{fill:var(--c,var(--accent));stroke:var(--ink);stroke-width:1.2}
.chart .val{font-size:12px;font-weight:600;fill:var(--ink)}
.chart .hit{fill:transparent}
.chart-top,.chart-src{margin:8px 0 0;font-size:.8125rem;line-height:1.45;font-weight:400;color:var(--ink2)}
.chart-src{color:var(--muted)}
.chart-card details{margin-top:8px;font-size:.875rem}
.chart-card summary,.dict summary{cursor:pointer;font-weight:600;color:var(--navy);min-height:36px;display:flex;align-items:center;
gap:10px;list-style:none}
.chart-card summary::-webkit-details-marker,.dict summary::-webkit-details-marker{display:none}
.chart-card summary::after,.dict summary::after{content:"";width:7px;height:7px;border-right:2px solid currentColor;
border-bottom:2px solid currentColor;transform:translateY(-2px) rotate(45deg)}
.chart-card details[open] > summary::after,.dict[open] > summary::after{transform:translateY(2px) rotate(-135deg)}
.mini-table{width:100%;border-collapse:collapse;font-size:.8125rem;margin:4px 0 0;font-variant-numeric:tabular-nums}
.mini-table th,.mini-table td{padding:5px 6px;border-bottom:1px solid var(--line);text-align:right;font-weight:400}
.mini-table th{font-weight:600;color:var(--ink2)}
.mini-table th:first-child,.mini-table td:first-child{text-align:left}
.chart-tip{position:absolute;z-index:5;pointer-events:none;background:var(--navy-ink);color:#fff;font-size:.8125rem;line-height:1.35;
padding:6px 10px;border-radius:6px;white-space:nowrap;transform:translate(-50%,calc(-100% - 8px));opacity:0;transition:opacity .1s}
.chart-tip.show{opacity:1}
.chart-tip strong{display:block;font-size:1rem;font-weight:600}
.dl-cats{display:flex;flex-wrap:wrap;gap:4px 14px}
.tbl-block{margin:28px 0 0;min-width:0;max-width:60rem}
#tbl-csv-block{margin:44px 0 48px}
.tbl-title{margin:0 0 10px;font-family:var(--font-head);font-size:1rem;font-weight:700;line-height:1.35;letter-spacing:-.005em;color:var(--navy)}
.tbl-wrap{max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}
.tbl-wrap:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.tbl{width:100%;border-collapse:collapse;border-spacing:0;font-size:.875rem;font-weight:400;line-height:1.4;color:var(--ink)}
.tbl th,.tbl td{padding:11px 16px;border:0;border-bottom:1px solid var(--line);text-align:left;vertical-align:baseline;white-space:nowrap}
.tbl thead th{background:#eeebe4;border-bottom:0;color:var(--ink2);font-size:.8125rem;font-weight:600;vertical-align:bottom}
.tbl.wrap-head thead th,.tbl thead .grp-row th{white-space:normal}
.tbl thead .grp-row th{background:transparent;padding:0 16px 6px;color:var(--muted);font-size:.75rem}
.tbl thead .grp-row th[colspan]{border-bottom:1px solid #d9d3c7}
.tbl tbody th{font-weight:400}
.tbl tbody tr:nth-child(even) > *{background:rgba(31,56,100,.035)}
.tbl .num{text-align:right;font-variant-numeric:tabular-nums}
.tbl .grp{padding-left:30px}
.tbl tfoot th,.tbl tfoot td{border-bottom:0;border-top:1px solid #cfc8bb;font-weight:600}
.tbl .dash{color:var(--muted)}
.tbl td.wrap{white-space:normal;min-width:13rem}
.tbl th button{display:inline-flex;align-items:center;gap:6px;margin:0;padding:0;border:0;background:none;font:inherit;color:inherit;
line-height:inherit;text-align:inherit;cursor:pointer}
.tbl th.num button{flex-direction:row-reverse}
.tbl th button::after{content:"";flex:none;width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;
border-top:5px solid currentColor;opacity:0}
.tbl th button:hover::after{opacity:.35}
.tbl th[aria-sort="descending"] button::after{opacity:.85}
.tbl th[aria-sort="ascending"] button::after{opacity:.85;border-top:0;border-bottom:5px solid currentColor}
.tbl th button:focus-visible{outline:3px solid var(--accent);outline-offset:3px;border-radius:2px}
.cat-block .tbl th,.cat-block .tbl td{padding:10px 12px}
.cat-block .tbl .grp{padding-left:22px}
@media(max-width:639px){.tbl th,.tbl td{padding:10px 12px}.tbl .grp{padding-left:20px}}
.tbl-more{display:inline-flex;align-items:center;min-height:40px;margin:6px 0 0;padding:0;border:0;background:none;cursor:pointer;
font:inherit;font-size:.875rem;font-weight:600;color:var(--navy);text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:.2em}
.tbl-more:hover{color:var(--accent-dark)}
.tbl-more[hidden]{display:none}
.tbl-cap{max-width:46rem;margin:8px 0 0;font-size:.8125rem;line-height:1.55;font-weight:400;color:var(--muted)}
.tbl-links{margin:8px 0 0;font-size:.875rem;font-weight:400}
.cat-blocks{display:grid;gap:48px;margin:18px 0 20px}
@media(min-width:1100px){.cat-blocks{grid-template-columns:repeat(2,minmax(0,1fr));gap:56px 36px;align-items:start}}
.cat-block{min-width:0}
.cat-block[hidden]{display:none}
.dict{margin:0 0 32px}
.dict .data-table td:first-child{white-space:nowrap;font-weight:600}
.status-live{color:var(--green);font-weight:600}
.status-fallback{color:#8a5a00;font-weight:600}
.status-failed{color:#b42318;font-weight:600}

/* home, v7: a short hero, the live map, this week and one line on sources */
.page-head.home-hero{padding:22px 0 24px}
.home-hero h1{font-size:clamp(1.5rem,1.15rem + 1.5vw,2.25rem);max-width:none;margin:0 0 8px}
.home-hero .lead{font-size:1rem;line-height:1.55;max-width:none}
.hero-row{display:flex;flex-wrap:wrap;align-items:center;gap:14px 28px;margin:16px 0 0}
.hero-meta{display:flex;flex-wrap:wrap;gap:2px 16px;margin:0;font-size:.875rem;line-height:1.5;color:var(--on-dark2)}
.hero-meta a{color:#fff;text-decoration-color:rgba(250,247,241,.5)}
.hero-meta a:hover{color:var(--accent-soft)}
@media(min-width:768px){.page-head.home-hero{padding:30px 0 32px}.home-hero .lead{font-size:1.0625rem}}
.section.tight.home-map{padding:20px 0 40px}
@media(min-width:768px){.section.tight.home-map{padding:28px 0 56px}}
.week-band{padding:36px 0 32px}
@media(min-width:768px){.week-band{padding:44px 0 40px}}
.week-band .head-row{align-items:baseline;margin:0 0 18px}
.week-band h2{font-size:clamp(1.375rem,1.2rem + .8vw,1.75rem);margin:0}
.week-cards{display:grid;gap:14px}
@media(min-width:960px){.week-cards{grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}}
.week-card{display:grid;grid-template-columns:120px minmax(0,1fr);gap:14px;align-items:start;padding:12px;background:var(--card);
border:1px solid var(--line);border-radius:var(--radius);color:var(--ink);text-decoration:none}
.week-card:hover{border-color:var(--navy2);color:var(--ink)}
.week-media{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;border-radius:6px;background:var(--navy-ink)}
.nl-media{display:flex;align-items:center;justify-content:center;
background:var(--navy) radial-gradient(80% 120% at 70% 20%,#27467d 0,rgba(31,56,100,0) 70%)}
.nl-media .brand-mark{width:44%;height:auto;max-width:72px}
.week-text{display:flex;flex-direction:column;gap:6px;min-width:0}
.week-card .meta{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;font-size:.8125rem;line-height:1.4;color:var(--muted)}
.week-card h3{font-size:1rem;line-height:1.3;margin:0;color:var(--navy)}
.week-card .go{font-size:.9375rem;font-weight:600;color:var(--navy);text-decoration:underline;text-underline-offset:.2em}
.week-card:hover .go{color:var(--accent-dark)}
@media(min-width:640px){.week-card{grid-template-columns:208px minmax(0,1fr);gap:20px;padding:14px}.week-card h3{font-size:1.0625rem}}
.week-more{margin:18px 0 0;font-weight:600}
.src-line{padding:22px 0}
.src-line p{margin:0;font-size:.9375rem;color:var(--ink2)}

/* weekly: the latest episode, with the video, the chapters and the newsletter */
.episode{display:grid;gap:24px;grid-template-areas:"media" "body" "chapters"}
.episode-media{grid-area:media;min-width:0}.episode-body{grid-area:body;min-width:0}.episode-chapters{grid-area:chapters;min-width:0}
@media(min-width:1024px){.episode{grid-template-columns:minmax(0,7fr) minmax(0,5fr);grid-template-areas:"media body" "chapters body";
column-gap:48px;row-gap:28px;align-items:start}}
.episode-frame{position:relative;width:100%;aspect-ratio:16/9;background:var(--navy-ink);border-radius:var(--radius);overflow:hidden;
box-shadow:0 24px 48px -28px rgba(20,30,50,.5)}
.episode-frame iframe{position:absolute;top:0;left:0;width:100%;height:100%;border:0}
.episode-media .note{margin:10px 0 0}
.episode-body .meta{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin:0 0 10px;font-size:.875rem;color:var(--muted)}
.episode-body h2{font-size:clamp(1.25rem,1.1rem + .7vw,1.625rem);line-height:1.25;margin:0 0 12px}
.episode-body p{color:var(--ink2)}
.episode-body .actions-row{margin:20px 0 14px}
.chapters-title{font-size:1.0625rem;margin:0 0 8px}
.chapters{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}
@media(min-width:640px){.chapters{columns:2;column-gap:32px}}
.chapters li{break-inside:avoid;border-bottom:1px solid var(--line)}
.chapters a{display:flex;gap:14px;padding:8px 0;color:var(--ink);text-decoration:none;font-size:.9375rem}
.chapters a:hover{color:var(--accent-dark)}
.chapters a:hover span:nth-child(2){text-decoration:underline}
.chapters .t{flex:none;min-width:2.75rem;font-weight:600;color:var(--navy);font-variant-numeric:tabular-nums}
.earlier{margin-top:48px}

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


def page(title, active, body, desc="Accessible weekly animal-disease intelligence.", path=None, index=True, ld=None, head=""):
    """path is the file the page is written to (defaults to active). index=False keeps a page out of
    search results and the sitemap. ld is an extra JSON-LD object for this page. head is extra markup
    for <head>, such as the map's stylesheets."""
    path = path or active
    def cur(h):
        return ' aria-current="page"' if h == active else ""
    desk = "".join('<a href="%s"%s>%s</a>' % (h, cur(h), t) for h, t in NAV if h not in ("index.html", "subscribe.html"))
    desk += '<a class="nav-cta" href="subscribe.html"%s>Subscribe</a>' % cur("subscribe.html")
    mob = "".join('<a href="%s"%s>%s</a>' % (h, cur(h), t) for h, t in NAV)
    explore = "".join('<li><a href="%s">%s</a></li>' % (h, t) for h, t in
                      [("weekly.html", "Weekly reports"), ("watch.html", "Short videos"), ("map.html", "Map"),
                       ("analytics.html", "Numbers"), ("data.html", "Open data"), ("sources.html", "Sources"),
                       ("about.html", "About")])
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Montserrat:wght@700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/styles.css?v={CSS_VER}">{head}
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
    published = os.path.join(ASSETS, "shorts", slug + ".jpg")
    if not os.path.exists(web):
        # No content/ folder here (it is not in the repository): keep the cover already published in website/.
        return "assets/shorts/%s.jpg" % slug if os.path.exists(published) else ""
    shutil.copy(web, published)
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


# ---------- episodes: thumbnails, the "This week" band and the latest episode ----------
os.makedirs(os.path.join(ASSETS, "episodes"), exist_ok=True)


def episode_thumb(slug):
    """Web-size thumbnail (640 x 360 JPEG), made once from content/episodes/<slug>/thumb.png and cached beside it as
    thumb-640.jpg. Returns the published thumbnail's site path, or "" when there is none."""
    folder = os.path.join(EPISODES_DIR, slug)
    web, src = os.path.join(folder, "thumb-640.jpg"), os.path.join(folder, "thumb.png")
    if not os.path.exists(web) and os.path.exists(src):
        try:
            from PIL import Image
            with Image.open(src) as im:
                small = im.convert("RGB").resize((640, round(im.height * 640 / im.width)), Image.LANCZOS)
            small.save(web, "JPEG", quality=82, optimize=True, progressive=True)
            print("thumbnail: made %s (%d KB)" % (web, os.path.getsize(web) // 1024))
        except Exception as e:   # Pillow missing or the file unreadable: keep the published thumbnail
            print("thumbnail: could not make", web, "-", e)
    published = os.path.join(ASSETS, "episodes", slug + ".jpg")
    if os.path.exists(web):
        shutil.copy(web, published)
    return "assets/episodes/%s.jpg" % slug if os.path.exists(published) else ""


for e in EPISODES:
    e["url"] = "https://youtu.be/" + e["youtube_id"]
    # YouTube's standard thumbnail only when the site has none of its own
    e["thumb"] = episode_thumb(e["slug"]) or "https://i.ytimg.com/vi/%s/hqdefault.jpg" % e["youtube_id"]


def week_band():
    """Home page: the latest episode and the latest newsletter issue, one card each, then a line to the shorts."""
    cards = []
    if EPISODES:
        e = EPISODES[0]
        cards.append('<a class="week-card" href="%s" target="_blank" rel="noopener"><img class="week-media" src="%s" '
                     'width="640" height="360" alt="" loading="lazy" decoding="async"><div class="week-text"><span class="meta">'
                     '<span class="tag">Episode %d</span>%s, figures as at %s</span><h3>%s</h3><span class="go">Watch on YouTube'
                     '</span></div><span class="vh"> (opens in a new tab)</span></a>'
                     % (e["url"], e["thumb"], e["number"], e["length"], e["as_at_short"], escape(e["title"])))
    url, label, title = NEWSLETTER_LATEST
    cards.append('<a class="week-card" href="%s" target="_blank" rel="noopener"><span class="week-media nl-media" aria-hidden="true">'
                 '%s</span><div class="week-text"><span class="meta"><span class="tag">Newsletter</span>%s</span><h3>%s</h3>'
                 '<span class="go">Read the issue</span></div><span class="vh"> (opens in a new tab)</span></a>'
                 % (url, BRAND_MARK, escape(label), escape(title)))
    return f"""
<section class="week-band band-white" aria-labelledby="week-title"><div class="wrap">
<div class="head-row"><h2 id="week-title">This week</h2><a class="more" href="weekly.html">All episodes</a></div>
<div class="week-cards">{"".join(cards)}</div>
<p class="week-more"><a href="watch.html">Watch the shorts</a></p>
</div></section>"""


def episode_block(e):
    """The Weekly page's latest episode: the video (from YouTube in privacy-enhanced mode), what it covers, the
    newsletter issue and the chapters. Each chapter opens the video on YouTube at that point."""
    vid, title, n = e["youtube_id"], escape(e["title"]), e["number"]
    nl_url = e["newsletter"][0]
    chapters = "".join('<li><a href="%s?t=%d" target="_blank" rel="noopener"><span class="t">%s</span><span>%s</span>'
                       '<span class="vh"> (opens in a new tab)</span></a></li>'
                       % (e["url"], int(t.split(":")[0]) * 60 + int(t.split(":")[1]), t, escape(c)) for t, c in e["chapters"])
    return f"""
<article class="episode" aria-labelledby="ep{n}-title">
<div class="episode-media"><div class="episode-frame"><iframe src="https://www.youtube-nocookie.com/embed/{vid}?rel=0" title="Video: {title}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div>
<p class="note">{e["length"]}. Plays from YouTube in privacy-enhanced mode.</p></div>
<div class="episode-body">
<p class="meta"><span class="tag">Latest</span>Episode {n}, figures as at {e["as_at"]}</p>
<h2 id="ep{n}-title">{title}</h2>
<p>{escape(e["summary"])}</p>
<div class="actions-row">{ext(e["url"], "Watch on YouTube", "btn btn-primary btn-sm")}{ext(nl_url, "Read the newsletter", "btn btn-outline btn-sm")}</div>
<p class="note">The video description on YouTube lists the source for every figure.</p>
</div>
<div class="episode-chapters"><h3 class="chapters-title">Chapters</h3><ol class="chapters">{chapters}</ol></div>
</article>"""

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

if PRELAUNCH and EPISODES:
    now = week_band()
elif PRELAUNCH:
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
# The home page is written after the live data pages (see HOME, v7 below). With live data it leads with the map.
# Without live data this v6 page is used.
HOME_DESC = ("Weekly animal-disease intelligence. Official surveillance data turned into clear maps, key numbers and a "
             "short, sourced briefing.")

# ---------- WEEKLY ----------
# The pipeline report card (full mode only): HPAI figures from pipeline/outputs
report_card = "" if PRELAUNCH else f"""
<section class="section"><div class="wrap">
<a class="report-card" href="weekly-latest.html">
<span class="meta">Week {week} <span class="tag">Latest</span><span class="tag">HPAI</span></span>
<h2>HPAI situation report, week {week}</h2>
<p>{ev} new events across {co} countries ({wow_s} week on week). Map, key numbers and a 60-second brief.</p>
<span class="go">Read the report</span></a>
<p class="note archive-note">Earlier reports appear here automatically as the pipeline runs each week.</p>
</div></section>"""
if EPISODES:
    earlier = "".join('<li>%s<span>, Episode %d, figures as at %s</span></li>' % (ext(e["url"], escape(e["title"])), e["number"], e["as_at"])
                      for e in EPISODES[1:])
    weekly = page_head("Weekly reports", "A running archive of the weekly situation report. The newest is at the top.",
                       "OutbreakWeekly") + f"""
<section class="section"><div class="wrap">{episode_block(EPISODES[0])}
{('<div class="prose earlier"><h2>Earlier episodes</h2><ul class="src-list">%s</ul></div>' % earlier) if earlier else ""}
</div></section>""" + report_card
elif PRELAUNCH:
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
                       "OutbreakWeekly") + report_card
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
latest_title = f"Week {week}"
if PRELAUNCH and EPISODES:   # no pipeline report yet: this page shows the latest episode, as on the Weekly page
    latest_title = "Episode %d" % EPISODES[0]["number"]
    latest = (f'\n<nav class="crumbs on-dark" aria-label="Breadcrumb"><div class="wrap"><a href="weekly.html">Weekly reports</a>'
              f'<span aria-hidden="true"> / </span><span aria-current="page">{latest_title}</span></div></nav>'
              f'\n<section class="section"><div class="wrap">{episode_block(EPISODES[0])}\n</div></section>')
elif PRELAUNCH:
    latest = page_head("No report yet",
        'The first OutbreakWeekly report is coming soon. <a href="weekly.html">Back to weekly reports</a>.')
# before launch this page repeats the Weekly page (or is a placeholder), so it stays out of search and the sitemap
write("weekly-latest.html", page(latest_title, "weekly.html", latest, path="weekly-latest.html", index=not PRELAUNCH))

# Map behaviour: MapLibre GL with the OpenFreeMap Positron basemap, filters by disease and week range, a time
# slider, clustered symbols (shape for the animals affected, colour for the disease), pop-ups and the table
# under the map. Pop-up and table text comes from the data, so it is set with textContent, never as HTML.
MAP_JS = r"""(function () {
  "use strict";
  var cfgEl = document.getElementById("map-config"), mapEl = document.getElementById("map");
  var summary = document.getElementById("map-summary");
  if (!cfgEl || !mapEl) return;
  var cfg = JSON.parse(cfgEl.textContent), weeks = cfg.weeks, last = weeks.length - 1;
  var state = { cat: "all", from: 0, to: last };
  var fromSel = document.getElementById("from-week"), toSel = document.getElementById("to-week");
  var slider = document.getElementById("week-slider"), out = document.getElementById("week-out");
  var table = document.getElementById("map-table"), tTitle = document.getElementById("map-table-title");
  var tNote = document.getElementById("map-table-note");
  var SHAPES = { domestic: "circle", wild: "triangle" }, NS = "http://www.w3.org/2000/svg";
  var feats = [], byId = {}, map = null, ready = false, popup = null, mapNote = "";

  function shapeOf(p) { return SHAPES[p.pop] || "square"; }
  function catOf(p) { return cfg.cats[p.cat] ? p.cat : "other"; }
  function total(w) {
    var t = 0;
    for (var i = state.from; i <= state.to; i++) t += w[weeks[i][0]] || 0;
    return t;
  }
  function fmt(n) { return n.toLocaleString("en-GB"); }
  function cap(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
  function span() {   // "weeks starting 3 Aug to 19 Oct 2026"
    var a = weeks[state.from][1], b = weeks[state.to][1];
    if (state.from === state.to) return "week starting " + b;
    if (a.slice(-4) === b.slice(-4)) a = a.slice(0, -5);
    return "weeks starting " + a + " to " + b;
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function link(text, href) {
    if (!/^https?:\/\//.test(href || "")) return el("span", null, text);
    var a = el("a", null, text);
    a.href = href; a.target = "_blank"; a.rel = "noopener";
    return a;
  }
  function glyph(shape, colour) {   // the map symbol, for the pop-up title
    var svg = document.createElementNS(NS, "svg"), s;
    svg.setAttribute("viewBox", "0 0 22 22");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    if (shape === "circle") {
      s = document.createElementNS(NS, "circle");
      s.setAttribute("cx", "11"); s.setAttribute("cy", "11"); s.setAttribute("r", "6.5");
    } else if (shape === "triangle") {
      s = document.createElementNS(NS, "polygon");
      s.setAttribute("points", "11,3.4 19.75,18.6 2.25,18.6");
    } else {
      s = document.createElementNS(NS, "rect");
      s.setAttribute("x", "5.3"); s.setAttribute("y", "5.3"); s.setAttribute("width", "11.4"); s.setAttribute("height", "11.4");
    }
    s.setAttribute("fill", colour);
    svg.appendChild(s);
    return svg;
  }

  // ---------- pop-ups ----------
  function record(f) {
    var p = f.properties, n = total(p.weeks), box = el("div", "pop");
    var unit = n === 1 ? p.unit : (cfg.units[p.unit] || p.unit);
    var t = el("p", "pop-title");
    t.appendChild(glyph(shapeOf(p), cfg.cats[catOf(p)].colour));
    t.appendChild(document.createTextNode(p.title));
    box.appendChild(t);
    box.appendChild(el("p", "pop-place", p.place));
    box.appendChild(el("p", "pop-pop", cfg.pop[p.pop] || cfg.pop[""]));
    var num = el("p", "pop-num");
    num.appendChild(el("span", "pop-n", fmt(n)));
    num.appendChild(document.createTextNode(" " + unit + (/season/.test(unit) ? "" : " in the weeks shown")));
    box.appendChild(num);
    if (p.note) box.appendChild(el("p", "pop-meta", p.note));
    var links = el("p", "pop-links");
    links.appendChild(link("Source: " + p.src, p.url));
    (p.also || []).forEach(function (x) {
      links.appendChild(document.createTextNode(" · "));
      links.appendChild(link("Also: " + x[0], x[1]));
    });
    box.appendChild(links);
    return box;
  }
  function openPopup(at, list) {
    if (!list.length) return;
    var node;
    if (list.length === 1) {
      node = record(list[0]);
    } else {
      node = el("div");
      node.appendChild(el("p", "pop-count", list.length + " records here"));
      var wrap = el("div", "pop-list");
      list.sort(function (a, b) { return total(b.properties.weeks) - total(a.properties.weeks); })
        .forEach(function (f) { wrap.appendChild(record(f)); });
      node.appendChild(wrap);
    }
    if (popup) popup.remove();
    var pp = new maplibregl.Popup({ maxWidth: "300px", offset: 12, focusAfterOpen: true });
    pp.setLngLat(at).setDOMContent(node).addTo(map);
    pp.on("close", function () { if (popup === pp) popup = null; });
    popup = pp;
  }

  // ---------- the table under the map ----------
  function renderTable(list) {
    if (!table) return;
    var all = state.cat === "all", rows = {}, keys = [], split = 0;
    list.forEach(function (f) {
      var p = f.properties, n = total(p.weeks), k = (p.iso3 || p.cc) + "|" + (all ? catOf(p) : "");
      var r = rows[k];
      if (!r) { r = rows[k] = { cc: p.cc, cat: catOf(p), wild: 0, dom: 0, all: 0 }; keys.push(k); }
      if (p.pop === "wild") r.wild += n; else if (p.pop === "domestic") r.dom += n; else split += n;
      r.all += n;
    });
    var data = keys.map(function (k) { return rows[k]; }).sort(function (a, b) {
      return b.all - a.all || a.cc.localeCompare(b.cc, "en-GB");
    });
    var cols = [["Country", "text"]];
    if (all) cols.push(["Disease", "text"]);
    cols.push(["Wild", "num"], ["Domestic", "num"], ["Total", "num"]);
    var head = el("tr");
    cols.forEach(function (c, i) {
      var th = el("th", c[1] === "num" ? "num" : null), b = el("button", null, c[0]);
      th.scope = "col";
      th.setAttribute("data-col", String(i));
      th.setAttribute("data-sort", c[1]);
      th.setAttribute("aria-sort", c[0] === "Total" ? "descending" : "none");
      b.type = "button";
      th.appendChild(b);
      head.appendChild(th);
    });
    table.tHead.textContent = "";
    table.tHead.appendChild(head);
    var body = table.tBodies[0];
    body.textContent = "";
    data.forEach(function (r) {
      var tr = el("tr"), th = el("th", null, r.cc);
      th.scope = "row";
      tr.appendChild(th);
      if (all) tr.appendChild(el("td", null, cfg.cats[r.cat].short));
      [r.wild, r.dom, r.all].forEach(function (v) {
        var td = el("td", "num", fmt(v));
        td.setAttribute("data-v", String(v));
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    if (!data.length) {
      var tr = el("tr"), td = el("td", "dash", "No reports in these weeks.");
      td.colSpan = cols.length;
      tr.appendChild(td);
      body.appendChild(tr);
    }
    table.setAttribute("data-noun", all ? "rows" : "countries");
    table.setAttribute("data-open", "0");
    tTitle.textContent = all ? cap("reports by country, " + span())
      : cfg.cats[state.cat].short + ": reports by country, " + span();
    tNote.textContent = cfg.tableNote + (split ? " Total also includes " + fmt(split) +
      " that cover both wild and domestic animals, or do not say which." : "");
    if (window.OLTables) window.OLTables.setup(table);
  }

  // ---------- the map ----------
  function current() {
    var show = [];
    feats.forEach(function (f) {
      var p = f.properties;
      if (state.cat !== "all" && p.cat !== state.cat) return;
      if (total(p.weeks) > 0) show.push(f);
    });
    return show;
  }
  function lite(list) {   // the map only needs the place, the id and the symbol
    return { type: "FeatureCollection", features: list.map(function (f) {
      return { type: "Feature", geometry: f.geometry,
        properties: { id: f.properties.id, sym: shapeOf(f.properties) + "-" + catOf(f.properties) } };
    }) };
  }
  function webgl() {
    try {
      var c = document.createElement("canvas");
      return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
    } catch (e) { return false; }
  }
  function off(msg) {
    ready = false;
    mapEl.textContent = "";
    mapEl.appendChild(el("p", "map-off", msg ||
      "This map needs WebGL, which this browser does not offer. The table below and the open data hold the same records."));
    mapEl.style.height = "auto";
    mapEl.style.minHeight = "0";
  }
  function tidy(style) {   // credit line, English place names and quieter labels, so the data stands out
    if (style.sources && style.sources.openmaptiles) style.sources.openmaptiles.attribution = cfg.attribution;
    var name = ["coalesce", ["get", "name_en"], ["get", "name:latin"], ["get", "name"]];
    (style.layers || []).forEach(function (l) {
      var lo = l.layout;
      if (lo && lo["text-field"] && JSON.stringify(lo["text-field"]).indexOf("name:nonlatin") >= 0) lo["text-field"] = name;
      if (/^label_/.test(l.id) && l.paint) l.paint["text-color"] = /country/.test(l.id) ? "#4f545b" : "#676c73";
    });
    return style;
  }
  function plain() {
    return { version: 8, glyphs: cfg.glyphs, sources: {},
      layers: [{ id: "background", type: "background", paint: { "background-color": "#f2f3f0" } }] };
  }
  function icon(shape, colour) {   // drawn at twice the size, with a white ring and a faint dark edge
    var r = 2, S = 22, c = document.createElement("canvas"), g;
    c.width = c.height = S * r;
    g = c.getContext("2d");
    g.scale(r, r);
    g.lineJoin = "round";
    g.beginPath();
    if (shape === "circle") g.arc(11, 11, 6.5, 0, 2 * Math.PI);
    else if (shape === "triangle") { g.moveTo(11, 3.4); g.lineTo(19.75, 18.6); g.lineTo(2.25, 18.6); g.closePath(); }
    else g.rect(5.3, 5.3, 11.4, 11.4);
    g.lineWidth = 3.8; g.strokeStyle = "rgba(28,27,25,.38)"; g.stroke();
    g.lineWidth = 2.4; g.strokeStyle = "#fff"; g.stroke();
    g.fillStyle = colour; g.fill();
    return g.getImageData(0, 0, S * r, S * r);
  }
  function layers() {
    Object.keys(cfg.cats).forEach(function (k) {
      ["circle", "triangle", "square"].forEach(function (sh) {
        if (!map.hasImage(sh + "-" + k)) map.addImage(sh + "-" + k, icon(sh, cfg.cats[k].colour), { pixelRatio: 2 });
      });
    });
    map.addSource("reports", { type: "geojson", data: lite(current()), cluster: true,
      clusterRadius: 36, clusterMaxZoom: cfg.maxZoom });
    map.addLayer({ id: "clusters", type: "circle", source: "reports", filter: ["has", "point_count"],
      paint: { "circle-color": "#1F3864", "circle-stroke-width": 3, "circle-stroke-color": "rgba(250,247,241,0.92)",
        "circle-radius": ["step", ["get", "point_count"], 14, 10, 17, 50, 20, 200, 23] } });
    map.addLayer({ id: "cluster-count", type: "symbol", source: "reports", filter: ["has", "point_count"],
      layout: { "text-field": ["get", "point_count_abbreviated"], "text-font": ["Noto Sans Bold"], "text-size": 12,
        "text-allow-overlap": true, "text-ignore-placement": true },
      paint: { "text-color": "#ffffff" } });
    map.addLayer({ id: "points", type: "symbol", source: "reports", filter: ["!", ["has", "point_count"]],
      layout: { "icon-image": ["get", "sym"], "icon-allow-overlap": true, "icon-ignore-placement": true } });
    map.on("click", "clusters", function (e) {
      var f = e.features[0], src = map.getSource("reports"), id = f.properties.cluster_id, at = f.geometry.coordinates;
      src.getClusterExpansionZoom(id).then(function (z) {
        if (z <= map.getMaxZoom()) { map.easeTo({ center: at, zoom: z }); return null; }
        return src.getClusterLeaves(id, 200, 0).then(function (leaves) {   // same place: list them instead
          openPopup(at, leaves.map(function (l) { return byId[l.properties.id]; }).filter(Boolean));
        });
      }).catch(function () {});
    });
    map.on("click", "points", function (e) {
      var seen = {}, list = [];
      e.features.forEach(function (x) {
        var f = byId[x.properties.id];
        if (f && !seen[f.properties.id]) { seen[f.properties.id] = 1; list.push(f); }
      });
      if (list.length) openPopup(list[0].geometry.coordinates, list);
    });
    ["clusters", "points"].forEach(function (id) {
      map.on("mouseenter", id, function () { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", id, function () { map.getCanvas().style.cursor = ""; });
    });
    ready = true;
  }
  function start(style) {
    var small = window.matchMedia("(max-width: 639px)").matches;
    try {
      map = new maplibregl.Map({ container: mapEl, style: style, center: small ? [12, 46] : [14, 47], zoom: small ? 0.9 : 2,
        minZoom: 0.6, maxZoom: cfg.maxZoom, cooperativeGestures: true, dragRotate: false, pitchWithRotate: false,
        touchPitch: false, maxPitch: 0 });
    } catch (e) { off(); return; }
    mapEl.outbreakLensMap = map;   // handy for testing and for embedding scripts
    map.touchZoomRotate.disableRotation();
    map.keyboard.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", layers);
  }

  function render() {
    var list = current();
    if (ready) map.getSource("reports").setData(lite(list));
    if (popup) popup.remove();
    var what = state.cat === "all" ? "any of the eight diseases" : cfg.cats[state.cat].phrase;
    summary.textContent = (list.length
      ? fmt(list.length) + (list.length === 1 ? " place" : " places") + " with reports of " + what + " in these weeks."
      : "No reports of " + what + " in these weeks.") + mapNote;
    renderTable(list);
  }
  function sync() {
    fromSel.value = String(state.from);
    toSel.value = String(state.to);
    slider.value = String(state.to);
    out.textContent = cap(span());
    slider.setAttribute("aria-valuetext", cap(span()));
  }
  Array.prototype.forEach.call(document.querySelectorAll('input[name="map-cat"]'), function (r) {
    r.addEventListener("change", function () { state.cat = r.value; render(); });
  });
  fromSel.addEventListener("change", function () {
    state.from = +fromSel.value; if (state.to < state.from) state.to = state.from; sync(); render();
  });
  toSel.addEventListener("change", function () {
    state.to = +toSel.value; if (state.from > state.to) state.from = state.to; sync(); render();
  });
  slider.addEventListener("input", function () {
    state.to = +slider.value; if (state.from > state.to) state.from = state.to; sync(); render();
  });

  if (!window.maplibregl || !webgl()) {
    off();
  } else {
    fetch(cfg.style).then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(function (st) { start(tidy(st)); })
      .catch(function () {
        mapNote = " The basemap did not load, so the points sit on a plain background.";
        start(plain());
      });
  }
  fetch(cfg.data, { credentials: "same-origin" })
    .then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
    .then(function (gj) {
      feats = gj.features;
      feats.forEach(function (f) { byId[f.properties.id] = f; });
      sync();
      render();
    })
    .catch(function () { summary.textContent = "The map data did not load. The same records are in the open data."; });
})();
"""

# Numbers behaviour: the disease filter and a tooltip on each chart (pointer, or arrow keys once focused).
NUMBERS_JS = r"""(function () {
  "use strict";
  var blocks = Array.prototype.slice.call(document.querySelectorAll(".cat-block"));
  var cards = Array.prototype.slice.call(document.querySelectorAll(".chart-card"));
  Array.prototype.forEach.call(document.querySelectorAll('input[name="num-cat"]'), function (r) {
    r.addEventListener("change", function () {
      blocks.forEach(function (b) { b.hidden = r.value !== "all" && b.getAttribute("data-cat") !== r.value; });
    });
  });
  cards.forEach(function (card) {
    var svg = card.querySelector("svg.chart");
    if (!svg) return;
    var hits = svg.querySelectorAll(".hit"), cur = -1;
    var tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.setAttribute("aria-hidden", "true");
    card.appendChild(tip);
    function bar(i) { return svg.querySelector('.bar[data-i="' + i + '"]'); }
    function show(i) {
      if (cur >= 0 && bar(cur)) bar(cur).classList.remove("on");
      cur = i;
      var h = hits[i], b = bar(i);
      if (!h) return;
      if (b) b.classList.add("on");
      tip.textContent = "";
      var s = document.createElement("strong");
      s.textContent = h.getAttribute("data-v");
      tip.appendChild(s);
      tip.appendChild(document.createTextNode(h.getAttribute("data-l")));
      var cr = card.getBoundingClientRect(), hr = h.getBoundingClientRect(), sr = svg.getBoundingClientRect();
      var topY = (b ? b.getBoundingClientRect().top : sr.top + sr.height * 0.79) - cr.top;
      var x = hr.left + hr.width / 2 - cr.left;
      tip.style.left = Math.min(Math.max(x, 90), cr.width - 90) + "px";
      tip.style.top = Math.max(topY, sr.top - cr.top + 24) + "px";
      tip.classList.add("show");
    }
    function hide() {
      tip.classList.remove("show");
      if (cur >= 0 && bar(cur)) bar(cur).classList.remove("on");
      cur = -1;
    }
    Array.prototype.forEach.call(hits, function (h, i) {
      h.addEventListener("pointerenter", function (e) { if (e.pointerType === "mouse") show(i); });
      h.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") hide(); });
      h.addEventListener("click", function () { if (cur === i) hide(); else show(i); });
    });
    svg.addEventListener("focus", function () { show(hits.length - 1); });
    svg.addEventListener("blur", hide);
    svg.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        var i = cur < 0 ? hits.length - 1 : cur + (e.key === "ArrowRight" ? 1 : -1);
        show(Math.max(0, Math.min(hits.length - 1, i)));
      } else if (e.key === "Escape") {
        hide();
      }
    });
  });
})();
"""

# Tables: sortable columns (header buttons with aria-sort) and the first ten rows with a "Show all" button.
# Without JavaScript every row shows. Inlined on each page that has tables.
TABLES_JS = r"""(function () {
  "use strict";
  function key(td, num) {
    var v = td ? td.getAttribute("data-v") : null;
    if (num) return v == null ? -1 : +v;
    return v != null ? v : (td ? td.textContent : "");
  }
  function limit(table) {
    var top = +table.getAttribute("data-top") || 10, rows = table.tBodies[0].rows, n = rows.length;
    var open = table.getAttribute("data-open") === "1", btn = table.olMore;
    for (var i = 0; i < n; i++) rows[i].hidden = !open && i >= top;
    if (!btn) {
      btn = table.olMore = document.createElement("button");
      btn.type = "button";
      btn.className = "tbl-more";
      btn.addEventListener("click", function () {
        table.setAttribute("data-open", table.getAttribute("data-open") === "1" ? "0" : "1");
        limit(table);
      });
      (table.closest(".tbl-wrap") || table).insertAdjacentElement("afterend", btn);
    }
    btn.hidden = n <= top;
    btn.textContent = open ? "Show the first " + top : "Show all " + n + " " + (table.getAttribute("data-noun") || "rows");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  function sort(table, th) {
    var col = +th.getAttribute("data-col"), num = th.getAttribute("data-sort") === "num", was = th.getAttribute("aria-sort");
    var dir = was === "descending" ? "ascending" : was === "ascending" ? "descending" : (num ? "descending" : "ascending");
    Array.prototype.forEach.call(table.querySelectorAll("thead th[data-sort]"), function (h) { h.setAttribute("aria-sort", "none"); });
    th.setAttribute("aria-sort", dir);
    var body = table.tBodies[0], rows = Array.prototype.slice.call(body.rows);
    rows.sort(function (a, b) {
      var x = key(a.cells[col], num), y = key(b.cells[col], num);
      var r = num ? x - y : String(x).localeCompare(String(y), "en-GB");
      if (dir === "descending") r = -r;
      return r || a.cells[0].textContent.localeCompare(b.cells[0].textContent, "en-GB");
    });
    rows.forEach(function (r) { body.appendChild(r); });
    limit(table);
  }
  function setup(table) {
    if (!table.olBound) {
      table.olBound = true;
      table.addEventListener("click", function (e) {
        var b = e.target.closest ? e.target.closest("thead th[data-sort] button") : null;
        if (b) sort(table, b.parentNode);
      });
    }
    limit(table);
  }
  window.OLTables = { setup: setup };
  Array.prototype.forEach.call(document.querySelectorAll("table.tbl"), setup);
})();
"""


# ---------- LIVE DATA: map, numbers and open data, built from pipeline/data ----------
# The pipeline (pipeline/run.py) writes events.csv, one CSV per disease, aggregates.json, latest.json,
# map.geojson, tables.json and dictionary.csv to pipeline/data. They are copied to website/assets/data and
# drive map.html, analytics.html ("Numbers") and data.html. These pages are built with or without --prelaunch.
LIVE_DIR = os.path.join(ROOT, "pipeline", "data")
LIVE_DATA_URL = "assets/data/"
# One colour per disease, for the map symbols, chips, key, charts and tables. Terracotta (the brand accent) is
# HPAI. The others are muted and distinct, checked for contrast against the grey basemap. Colour is never the
# only cue: map symbols also differ by shape, and the key, pop-ups and tables name the disease.
# Each entry: colour, short name, phrase for running text. "HPAI (bird flu)" is the category label, used for the
# chips and the first mention on a page. Later mentions use "HPAI".
CAT_STYLE = {"bird-flu": ("#C0532B", "HPAI", "HPAI"),
             "bluetongue": ("#0a64b2", "Bluetongue", "bluetongue"),
             "asf": ("#943c82", "African swine fever", "African swine fever"),
             "fmd": ("#948904", "Foot-and-mouth disease", "foot-and-mouth disease"),
             "sheep-goat-pox": ("#028f95", "Sheep and goat pox", "sheep and goat pox"),
             "lsd": ("#8976cd", "Lumpy skin disease", "lumpy skin disease"),
             "newcastle-disease": ("#1d7724", "Newcastle disease", "Newcastle disease"),
             "other": ("#5f6875", "Other exotic diseases", "other exotic diseases")}
# Basemap: MapLibre GL JS with OpenFreeMap's Positron style. OpenStreetMap data, no key, no registration and
# no request limits. Its credit must stay visible. Zoom stops at 8 (the scale of the old map), so a region centre
# never reads as an address.
MAPLIBRE_CSS = ('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/5.24.0/maplibre-gl.css" '
                'integrity="sha512-KIMsMWIdnoG9OwZa+oaIafmbDonqck1UCmq+/zcUi2aaZ97N9QE6TqpTM+n36EO40HGh64hU/375zxtjx7WTyQ==" '
                'crossorigin="anonymous" referrerpolicy="no-referrer">')
MAPLIBRE_JS = ('<script defer src="https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/5.24.0/maplibre-gl.js" '
               'integrity="sha512-rOFgoUgWaVi69JW1dzBu6PWF9xKW9rxYfY5u2SexFABHhWk0qUWkJoWNz4UuZRMvSXsNZG66+tU5B+HlwWF5kA==" '
               'crossorigin="anonymous" referrerpolicy="no-referrer"></script>')
MAP_HEAD = '<link rel="preconnect" href="https://tiles.openfreemap.org" crossorigin>' + MAPLIBRE_CSS
MAP_STYLE = "https://tiles.openfreemap.org/styles/positron"
MAP_GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf"
MAP_MAX_ZOOM = 8
MAP_CREDIT = ('<a href="https://openfreemap.org" target="_blank" rel="noopener">&copy; OpenFreeMap</a> '
              '<a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a>, data '
              '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">&copy; OpenStreetMap contributors</a>')
POP_WORDS = {"domestic": "Domestic animals", "wild": "Wild animals", "mixed": "Domestic and wild animals",
             "": "Animals not stated by the source"}
COUNTED = ("Counts are outbreaks, cases or events, as each source counts them. "
           "Records found in more than one source are counted once.")
SRC_ORDER = ["WOAH WAHIS", "EU ADIS", "FAO EMPRES-i", "GOV.UK", "DAFM", "Ruokavirasto"]
LICENCE_SHORT = [("WOAH WAHIS", "WAHIS terms"), ("EU ADIS", "CC BY 4.0"), ("FAO EMPRES-i", "CC BY 4.0"),
                 ("GOV.UK (Defra and APHA)", "OGL v3.0"), ("DAFM (gov.ie)", "gov.ie terms"),
                 ("Ruokavirasto (Finnish Food Authority)", "Ruokavirasto terms")]
WOAH_DISCLAIMER = ("The World Organisation for Animal Health (WOAH) bears no responsibility for the integrity or accuracy "
                   "of the data contained herein, in particular due, but not limited to, any deletion, manipulation, or "
                   "reformatting of data that may have occurred beyond its control.")
SOURCE_TERMS = [
    ("WOAH WAHIS", "https://wahis.woah.org/",
     "Immediate notifications and follow-up reports: one row per event, with outbreaks counted by their start date.",
     "The WAHIS Terms of Use and Conditions allow &ldquo;viewing, downloading, storing, reproducing, adapting, "
     "translating&rdquo; the data, with WOAH named as the source and the WOAH disclaimer below. OutbreakLens has "
     "reformatted the data: one row per event, a disease category, and places shown at region level."),
    ("EU ADIS", "https://webgate.ec.europa.eu/tracesnt/adis/public/notification/outbreaks-weekly-report",
     "The weekly outbreak report: outbreaks by country, disease and species. Each week is stored, because the report is replaced.",
     "&copy; European Union. Reuse is allowed with credit and an indication of changes (CC BY 4.0, Commission "
     "Decision 2011/833/EU)."),
    ("FAO EMPRES-i", "https://data.apps.fao.org/catalog/dataset/4849cca2-a2bf-4f1a-8348-ea01a692ff30",
     "Latest reported events from FAO&rsquo;s public data catalogue. Most come from WOAH and are matched to the WAHIS rows.",
     "CC BY 4.0, as listed for &lsquo;EMPRES-i: Global Animal Disease Events Dashboard&rsquo; in the FAO data catalogue."),
    ("GOV.UK, Bluetongue: latest situation", "https://www.gov.uk/guidance/bluetongue-latest-situation",
     "Cases (premises) by nation and county, and the daily update notes.",
     "Contains public sector information licensed under the Open Government Licence v3.0."),
    ("GOV.UK, Bird flu (avian influenza): latest situation in England",
     "https://www.gov.uk/guidance/bird-flu-avian-influenza-latest-situation-in-england",
     "Confirmed cases this season, risk levels, and whether the page says a prevention zone or housing order is in force.",
     "Contains public sector information licensed under the Open Government Licence v3.0."),
    ("DAFM, Bluetongue virus (gov.ie)",
     "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/publications/bluetongue-virus/",
     "Herd cases by county in Ireland.",
     "Contains Irish Public Sector Information. Check gov.ie for the re-use terms."),
    ("Ruokavirasto, ASF cases in Finland",
     "https://www.ruokavirasto.fi/en/animals/animal-health-and-diseases/animal-diseases/pigs/african-swine-fever-asf/asf-in-finland-2026/asf-cases-in-finland/",
     "Wild boar cases by date and municipality.",
     "Ruokavirasto&rsquo;s terms: the material may be used with the source named. Commercial use must be agreed "
     "separately with the Finnish Food Authority."),
]


def _fmt_day(iso, short=False):
    """2026-10-21 -> 21 October 2026, or 21 Oct 2026 when short."""
    if not iso:
        return ""
    d = dt.date.fromisoformat(iso[:10])
    return "%d %s %d" % (d.day, d.strftime("%b" if short else "%B"), d.year)


def _fmt_range(a, b):
    """2026-10-15, 2026-10-21 -> 15 to 21 Oct 2026."""
    x, z = dt.date.fromisoformat(a[:10]), dt.date.fromisoformat(b[:10])
    if (x.year, x.month) == (z.year, z.month):
        return "%d to %d %s %d" % (x.day, z.day, z.strftime("%b"), z.year)
    if x.year == z.year:
        return "%d %s to %d %s %d" % (x.day, x.strftime("%b"), z.day, z.strftime("%b"), z.year)
    return "%s to %s" % (_fmt_day(a, True), _fmt_day(b, True))


def _weeks_span(starts):
    """['2026-08-03', ..., '2026-10-19'] -> weeks starting 3 Aug to 19 Oct 2026."""
    a, b = _fmt_day(starts[0], True), _fmt_day(starts[-1], True)
    if a[-4:] == b[-4:]:
        a = a[:-5]
    return "weeks starting %s to %s" % (a, b)


def _cap(t):
    return t[:1].upper() + t[1:]


def _and(items):
    items = list(items)
    return " and ".join([", ".join(items[:-1]), items[-1]]) if len(items) > 1 else "".join(items)


def _fmt_stamp(ts):
    """An ISO timestamp in UTC -> '22 October 2026 at 9:53pm UK time'."""
    try:
        from zoneinfo import ZoneInfo
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/London"))
        return "%s at %s UK time" % (_fmt_day(t.date().isoformat()), t.strftime("%I:%M%p").lstrip("0").lower())
    except Exception:
        return ts


def _size(path):
    b = os.path.getsize(path)
    return "%.1f MB" % (b / 1e6) if b >= 1e6 else "%d KB" % max(1, round(b / 1e3))


def _load_live():
    need = ("events.csv", "latest.json", "aggregates.json", "map.geojson", "dictionary.csv")
    out_dir = os.path.join(ASSETS, "data")
    src_dir = LIVE_DIR
    if not all(os.path.exists(os.path.join(LIVE_DIR, f)) for f in need):
        # No pipeline run beside this script: rebuild from the files already published, if they are all there.
        if not all(os.path.exists(os.path.join(out_dir, f)) for f in need):
            print("live data: none in %s, so the map, numbers and data pages use their placeholders" % LIVE_DIR)
            return None
        src_dir = out_dir
        print("live data: none in %s, so the files already in %s are used" % (LIVE_DIR, out_dir))
    import csv as _csv

    def load(name):
        path = os.path.join(src_dir, name)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    latest, agg, mapdata, tables = load("latest.json"), load("aggregates.json"), load("map.geojson"), load("tables.json")
    with open(os.path.join(src_dir, "dictionary.csv"), encoding="utf-8", newline="") as f:
        dictionary = list(_csv.DictReader(f))
    files = {}
    os.makedirs(out_dir, exist_ok=True)
    for old in ("basemap.geojson",):   # left over from the old Natural Earth basemap
        if os.path.exists(os.path.join(out_dir, old)):
            os.remove(os.path.join(out_dir, old))
    cats = list(agg["categories"].keys())
    for name in (["events.csv"] + ["%s.csv" % c for c in cats] +
                 ["dictionary.csv", "aggregates.json", "latest.json", "map.geojson", "tables.json"]):
        src = os.path.join(src_dir, name)
        if not os.path.exists(src):
            continue
        if src_dir != out_dir:
            shutil.copy(src, os.path.join(out_dir, name))
        rows = cols = None
        sources = set()
        if name.endswith(".csv"):
            with open(src, encoding="utf-8", newline="") as f:
                rd = _csv.reader(f)
                header = next(rd, [])
                si = header.index("source") if "source" in header else None
                rows = 0
                for r in rd:
                    rows += 1
                    if si is not None and si < len(r):
                        sources.add(r[si])
            cols = len(header)
        files[name] = {"rows": rows, "cols": cols, "size": _size(src), "sources": sorted(sources)}
    heads = {h["id"]: h for h in latest.get("headlines", [])}
    print("live data: %d files %s %s" % (len(files), "copied to" if src_dir != out_dir else "read from", out_dir))
    return {"latest": latest, "agg": agg, "dictionary": dictionary, "files": files, "heads": heads, "cats": cats,
            "map": mapdata, "tables": tables}


LIVE = _load_live()


def subnav(current):
    """Map, Numbers and Downloads: the pages under Data in the main navigation."""
    items = "".join('<li><a href="%s"%s>%s</a></li>' % (h, ' aria-current="page"' if h == current else "", t)
                    for h, t in DATA_NAV)
    return '<nav class="subnav" aria-label="Data"><div class="wrap"><ul>%s</ul></div></nav>' % items


def _chips(name, cats_meta):
    opts = ['<label class="chip"><input type="radio" name="%s" value="all" checked><span>All diseases</span></label>' % name]
    for slug in cats_meta:
        colour = CAT_STYLE.get(slug, CAT_STYLE["other"])[0]
        opts.append('<label class="chip"><input type="radio" name="%s" value="%s"><span><i class="cat-dot" style="--c:%s"></i>%s</span></label>'
                    % (name, slug, colour, escape(cats_meta[slug]["label"])))
    return '<fieldset class="chips"><legend>Disease</legend><div class="chip-row">%s</div></fieldset>' % "".join(opts)


def _ext(url, text):
    return ext(escape(url), text)


def _sources_block(latest, extra="", title="Sources"):
    """Every source with the date it was last updated, plus the WOAH disclaimer the WAHIS terms require."""
    status = {s["name"]: s for s in latest.get("sources", [])}
    names = {"WOAH WAHIS": "WOAH WAHIS", "EU ADIS": "EU ADIS", "FAO EMPRES-i": "FAO EMPRES-i",
             "GOV.UK, Bluetongue: latest situation": "GOV.UK (Defra and APHA)",
             "GOV.UK, Bird flu (avian influenza): latest situation in England": "GOV.UK (Defra and APHA)",
             "DAFM, Bluetongue virus (gov.ie)": "DAFM (gov.ie)",
             "Ruokavirasto, ASF cases in Finland": "Ruokavirasto (Finnish Food Authority)"}
    keyed = {"GOV.UK, Bluetongue: latest situation": "govuk_bluetongue",
             "GOV.UK, Bird flu (avian influenza): latest situation in England": "govuk_birdflu"}
    by_key = {s["key"]: s for s in latest.get("sources", [])}
    items = []
    for name, url, what, terms in SOURCE_TERMS:
        s = by_key.get(keyed[name]) if name in keyed else status.get(names[name])
        when = ""
        if s:
            upd = (s.get("source_updated") or "")[:10]
            when = ("updated %s" % _fmt_day(upd)) if upd else ("read %s" % _fmt_day(s["fetched_at"][:10]))
            if s.get("status") == "fallback":
                when += ", from a saved copy"
            elif s.get("status") == "failed":
                when = "not available in this run"
        items.append('<li><b>%s</b>%s<span>%s</span></li>' % (_ext(url, name), (", " + when) if when else "", terms))
    return ('<div class="src-block"><h2>%s</h2><ul class="src-items">%s</ul>'
            '<p class="fine">%s</p><p class="fine">Records are placed using Natural Earth boundaries (public domain).%s</p></div>'
            % (title, "".join(items), escape(WOAH_DISCLAIMER), extra))


def _nice_top(v):
    if v <= 1:
        return 1
    if v <= 2:
        return 2
    import math
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 4, 6, 8, 10):   # halves are whole numbers, so the middle gridline is a clean value
        if m * mag >= v:
            return int(m * mag)
    return int(10 * mag)


def chart_svg(label, values, week_starts, unit_one, unit_many):
    """A 12-week column chart as inline SVG: muted columns, this week (still in progress) in the disease's
    colour, hairline grid, a value on the peak and on this week. Every value is also in the table under the chart."""
    W, H, L_, R_, T_, B_ = 360, 146, 30, 6, 18, 116
    n = len(values)
    slot = (W - L_ - R_) / n
    bw = min(16.0, slot - 6)
    top = _nice_top(max(values) if values else 0)
    ticks = [0, top // 2, top] if top >= 4 else [0, top]
    y = lambda v: B_ - (B_ - T_) * v / top
    cx = lambda i: L_ + i * slot + slot / 2
    p = []
    for t in ticks[1:]:
        p.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (L_, W - R_, y(t), y(t)))
    for t in ticks:
        p.append('<text class="tick" x="%d" y="%.1f" text-anchor="end">%s</text>' % (L_ - 6, y(t) + 3.5, "{:,}".format(t)))
    peak = max(range(n), key=lambda i: (values[i], -i)) if any(values) else None
    for i, v in enumerate(values):
        if v <= 0:
            continue
        x = cx(i) - bw / 2
        h = max(B_ - y(v), 1.5)
        r = min(4.0, h, bw / 2)
        yt = B_ - h
        d = ("M%.1f %.1fV%.1fQ%.1f %.1f %.1f %.1fH%.1fQ%.1f %.1f %.1f %.1fV%.1fZ"
             % (x, B_, yt + r, x, yt, x + r, yt, x + bw - r, x + bw, yt, x + bw, yt + r, B_))
        p.append('<path class="bar%s" data-i="%d" d="%s"/>' % (" now" if i == n - 1 else "", i, d))
    p.append('<line class="base" x1="%d" x2="%d" y1="%d" y2="%d"/>' % (L_, W - R_, B_, B_))
    for i in (0, 4, 8):
        if i < n - 1:
            d = dt.date.fromisoformat(week_starts[i])
            p.append('<text class="xl" x="%.1f" y="%d" text-anchor="middle">%d %s</text>' % (cx(i), B_ + 16, d.day, d.strftime("%b")))
    p.append('<text class="xl" x="%d" y="%d" text-anchor="end">This week</text>' % (W - R_, B_ + 16))
    now_v = values[-1]
    # the label runs left over the two previous columns, so it sits above the tallest of the last three
    now_y = max(min(y(v) for v in values[-3:]) if any(values[-3:]) else B_, T_ - 4)
    p.append('<text class="val" x="%.1f" y="%.1f" text-anchor="end">%s so far</text>' % (cx(n - 1) + bw / 2, now_y - 5, "{:,}".format(now_v)))
    if peak is not None and peak != n - 1:
        clash = abs(cx(peak) - cx(n - 1)) < 64 and abs(y(values[peak]) - now_y) < 16
        if not clash:
            p.append('<text class="val" x="%.1f" y="%.1f" text-anchor="middle">%s</text>' % (cx(peak), y(values[peak]) - 5, "{:,}".format(values[peak])))
    for i, v in enumerate(values):
        when = ("this week, from %s" % _fmt_day(week_starts[i], True)) if i == n - 1 else ("week starting %s" % _fmt_day(week_starts[i], True))
        p.append('<rect class="hit" x="%.1f" y="%d" width="%.1f" height="%d" data-i="%d" data-v="%s" data-l="%s, %s"/>'
                 % (L_ + i * slot, T_ - 10, slot, B_ - T_ + 10, i, "{:,}".format(v) + (" so far" if i == n - 1 else ""),
                    unit_one if v == 1 else unit_many, when))
    if peak is not None:
        summary = "Highest: %s in the week starting %s. This week so far: %s." % (
            "{:,}".format(values[peak]), _fmt_day(week_starts[peak]), "{:,}".format(now_v))
    else:
        summary = "None in these 12 weeks."
    aria = "%s, %s by week for 12 weeks. %s Use the arrow keys to read each week." % (label, unit_many, summary)
    return ('<svg class="chart" viewBox="0 0 %d %d" role="img" tabindex="0" aria-label="%s" focusable="true">%s</svg>'
            % (W, H, escape(aria), "".join(p)))


SERIES_TEXT = {
    "wahis-outbreaks": ("Outbreaks by the week they started, worldwide, from reports to WOAH.", "outbreak", "outbreaks"),
    "govuk-bt-cases": ("Cases (premises) by the week they were confirmed, Great Britain.", "case (premises)", "cases (premises)"),
}


def _chart_card(slug, c, weeks, week_starts):
    colour, short = CAT_STYLE.get(slug, CAT_STYLE["other"])[:2]
    sub, one, many = SERIES_TEXT.get(c["series_id"], (c.get("metric", ""), "record", "records"))
    vals = [int(v) for v in c["total"]]
    svg = chart_svg(short, vals, week_starts, one, many)
    if c["series_id"] == "govuk-bt-cases":
        areas = c.get("by_area") or {}
        top = ", ".join("%s %s" % (k, "{:,}".format(sum(v))) for k, v in areas.items() if sum(v))
        top_line = '<p class="chart-top">Over these 12 weeks: %s.</p>' % top if top else ""
        src = ('Source: %s, updated %s. Weekly counts come from the page&rsquo;s daily update notes and may differ '
               'slightly from its totals.' % (_ext(c["source_url"], "GOV.UK, Bluetongue: latest situation"),
                                               _fmt_day(c["source_updated"][:10], True)))
        cols = [k for k, v in areas.items() if sum(v)]
    else:
        tops = c.get("top_countries") or []
        top_line = ('<p class="chart-top">Most in these 12 weeks: %s.</p>'
                    % ", ".join("%s %s" % (escape(t["name"]), "{:,}".format(t["count"])) for t in tops[:3])) if tops else ""
        src = 'Source: %s, read %s. Recent weeks fill in as countries report.' % (
            _ext(c["source_url"], "WOAH WAHIS"), _fmt_day(c["fetched_at"][:10], True))
        cols = []
    head = '<tr><th scope="col">Week starting</th><th scope="col">%s</th>%s</tr>' % (
        escape(many[0].upper() + many[1:]), "".join('<th scope="col">%s</th>' % escape(k) for k in cols))
    body_rows = []
    for i, ws in enumerate(week_starts):
        extra = "".join("<td>%s</td>" % "{:,}".format(c["by_area"][k][i]) for k in cols)
        body_rows.append("<tr><td>%s%s</td><td>%s</td>%s</tr>" % (
            _fmt_day(ws, True), " (this week so far)" if i == len(week_starts) - 1 else "", "{:,}".format(vals[i]), extra))
    table = ('<details><summary>Show the numbers</summary><table class="mini-table"><caption class="vh">%s, %s by week'
             '</caption><thead>%s</thead><tbody>%s</tbody></table></details>' % (escape(short), many, head, "".join(body_rows)))
    return ('<article class="chart-card" data-cat="%s" id="chart-%s" style="--c:%s"><h3 id="chart-%s-h"><i class="cat-dot"></i>%s</h3>'
            '<p class="chart-sub">%s</p>%s%s<p class="chart-src">%s</p>%s</article>'
            % (slug, slug, colour, slug, escape(short), sub, svg, top_line, src, table))


# ---------- tables in the style of the IZSAM ASF bulletin ----------
def _th(label, col, kind="num", sort="none", cls=""):
    """A sortable column header. kind is num or text. sort is the starting aria-sort value."""
    c = " ".join(x for x in ("num" if kind == "num" else "", cls) if x)
    return ('<th scope="col"%s data-col="%d" data-sort="%s" aria-sort="%s"><button type="button">%s</button></th>'
            % (' class="%s"' % c if c else "", col, kind, sort, label))


def _td(v, cls=""):
    """A number cell, right-aligned, with its value for sorting. None shows a dash."""
    c = "num" + (" " + cls if cls else "")
    if v is None:
        return '<td class="%s dash" data-v="-1">&ndash;</td>' % c
    return '<td class="%s" data-v="%d">%s</td>' % (c, v, "{:,}".format(v))


def _tbl(tid, title, head, body, cap, noun="countries", foot="", level="h4", top=10, cls=""):
    """One-line title, then the table in its own scrolling box, then a caption with the source and date.
    The script shows the first ten rows and a "Show all" button. Without it every row shows."""
    return ('<div class="tbl-block" id="%s-block"><%s class="tbl-title" id="%s-title">%s</%s>'
            '<div class="tbl-wrap" role="region" tabindex="0" aria-labelledby="%s-title">'
            '<table class="tbl%s" id="%s" data-top="%d" data-noun="%s" aria-labelledby="%s-title">'
            '<thead>%s</thead><tbody>%s</tbody>%s</table></div><p class="tbl-cap">%s</p></div>'
            % (tid, level, tid, title, level, tid, " " + cls if cls else "", tid, top, noun, tid, head, body,
               ("<tfoot>%s</tfoot>" % foot) if foot else "", cap))


def _row(name, cells):
    return '<tr><th scope="row">%s</th>%s</tr>' % (escape(name), "".join(cells))


def _srcs(names):
    return _and(x for x in SRC_ORDER if x in names)


def _country_table(slug, bc, span, read):
    """Country, wild and domestic counts over the 12 weeks (Total when some records are not split)."""
    rows = bc.get("rows") or []
    short = CAT_STYLE.get(slug, CAT_STYLE["other"])[1]
    hpai = slug == "bird-flu"
    wild, dom = ("Wild birds", "Poultry") if hpai else ("Wild", "Domestic")
    need_total = any(r["other"] or r.get("mammals") for r in rows)
    head = "<tr>%s%s%s%s</tr>" % (_th("Country", 0, "text"), _th(wild, 1), _th(dom, 2),
                                  _th("Total", 3, sort="descending") if need_total else "")
    body = "".join(_row(r["country"], [_td(r["wild"]), _td(r["domestic"])] + ([_td(r["total"])] if need_total else []))
                   for r in rows)
    notes = ["Poultry includes other kept birds."] if hpai else []
    parts = []
    if bc.get("mammals_total"):
        parts.append("%s in mammals" % "{:,}".format(bc["mammals_total"]))
    if bc.get("other_total"):
        parts.append("%s that cover both wild and %s animals, or do not say which"
                     % ("{:,}".format(bc["other_total"]), "kept" if hpai else "domestic"))
    if parts:
        notes.append("Total also includes %s." % _and(parts))
    cap = "%s %s Sources: %s, read %s." % (COUNTED, " ".join(notes), _srcs(bc.get("sources", [])), read)
    if not rows:
        body = '<tr><td colspan="%d" class="dash">No reports in these weeks.</td></tr>' % (4 if need_total else 3)
    return _tbl("tbl-" + slug, '<span class="vh">%s: </span>By country, %s' % (escape(short), span), head, body, cap)


def _asf_table(bc, wk, span, read):
    """ASF: wild boar and domestic pigs in the latest ADIS week and over the 12 weeks."""
    twelve = {r["iso3"]: r for r in bc.get("rows") or []}
    week = {r["iso3"]: r for r in (wk or {}).get("rows") or []}
    zero = {"wild": 0, "domestic": 0, "other": 0, "total": 0}
    order = sorted(set(twelve) | set(week), key=lambda k: (-twelve.get(k, zero)["total"], -week.get(k, zero)["total"],
                                                           (twelve.get(k) or week.get(k))["country"]))
    need_total = any(r["other"] for r in twelve.values())
    period = (wk or {}).get("period") or []
    wlab = ("ADIS week, %s" % _fmt_range(period[0], period[1])) if len(period) == 2 and period[0] else "Latest ADIS week"
    head = ('<tr class="grp-row"><td></td><th scope="colgroup" colspan="2" class="grp">%s</th>'
            '<th scope="colgroup" colspan="%d" class="grp">%s</th></tr>' % (wlab, 3 if need_total else 2, _cap(span)))
    head += "<tr>%s%s%s%s%s%s</tr>" % (_th("Country", 0, "text"), _th("Wild boar", 1, cls="grp"), _th("Domestic pigs", 2),
                                       _th("Wild boar", 3, cls="grp"), _th("Domestic pigs", 4),
                                       _th("Total", 5, sort="descending") if need_total else "")
    body = []
    for k in order:
        w, t = week.get(k), twelve.get(k, zero)
        name = (twelve.get(k) or week.get(k))["country"]
        cells = [_td(w["wild"] if w else None, "grp"), _td(w["domestic"] if w else None),
                 _td(t["wild"], "grp"), _td(t["domestic"])] + ([_td(t["total"])] if need_total else [])
        body.append(_row(name, cells))
    notes = []
    if wk:
        notes.append("Latest week: the EU ADIS weekly report, read %s. A dash means that report lists no ASF "
                     "outbreaks for the country, or the country does not report to ADIS." % _fmt_day(wk["source_updated"][:10] or "", True)
                     if wk.get("source_updated") else "Latest week: the EU ADIS weekly report.")
    if bc.get("other_total"):
        notes.append("Total also includes %s that cover both wild boar and domestic pigs, or do not say which."
                     % "{:,}".format(bc["other_total"]))
    cap = "%s %s Sources for the 12 weeks: %s, read %s." % (COUNTED, " ".join(notes), _srcs(bc.get("sources", [])), read)
    return _tbl("tbl-asf", '<span class="vh">African swine fever: </span>By country, latest week and last 12 weeks',
                head, "".join(body), cap, cls="wrap-head")


def _bt_tables(heads, T):
    """Bluetongue: cases by nation from GOV.UK, and herd cases by county in Ireland from DAFM."""
    out = []
    h = heads.get("govuk-bt-total")
    if h and h.get("by_area"):
        areas = sorted(h["by_area"].items(), key=lambda kv: (-kv[1], kv[0]))
        head = "<tr>%s%s</tr>" % (_th("Nation", 0, "text"), _th("Cases", 1, sort="descending"))
        body = "".join(_row(k, [_td(v)]) for k, v in areas)
        foot = _row("United Kingdom", [_td(h["value"])])
        cap = ("Source: %s, counts to %s, updated %s. A case is a premises where bluetongue was confirmed."
               % (_ext(h["source_url"], "GOV.UK, Bluetongue: latest situation"), _fmt_day(h["counts_to"], True),
                  _fmt_day(h["as_of"], True)))
        out.append(_tbl("tbl-bt-gb", "Bluetongue cases by nation, %s season" % escape(h.get("season") or "this"),
                        head, body, cap, noun="nations", foot=foot))
    ie = (T or {}).get("bluetongue_ie")
    if ie and ie.get("rows"):
        rows = ie["rows"]
        head = "<tr>%s%s%s%s</tr>" % (_th("County", 0, "text"), _th("Cattle herds", 1), _th("Sheep flocks", 2),
                                      _th("Total", 3, sort="descending"))
        body = "".join(_row(r["county"], [_td(r.get("cattle")), _td(r.get("sheep")), _td(r["total"])]) for r in rows)
        tot = lambda k: sum((r.get(k) or 0) for r in rows)
        hh = heads.get("ie-bt-herds")
        if hh and hh.get("value") != tot("total"):
            print("tables: Ireland county rows add up to %d, the page total is %s" % (tot("total"), hh.get("value")))
        foot = _row("Ireland", [_td(tot("cattle")), _td(tot("sheep")), _td(tot("total"))])
        saved = " Read from a saved copy of the page, because gov.ie could not be read in this run." if ie.get("status") == "fallback" else ""
        cap = "Source: %s, as at %s.%s" % (_ext(ie["source_url"], "DAFM, Bluetongue virus (gov.ie)"),
                                           _fmt_day(ie.get("as_at") or "", True), saved)
        out.append(_tbl("tbl-bt-ie", "Bluetongue herd cases in Ireland by county, as at %s" % _fmt_day(ie.get("as_at") or "", True),
                        head, body, cap, noun="counties", foot=foot))
    return "".join(out)


def _cat_block(slug, c, weeks, starts, T, heads):
    """One disease on the Numbers page: its chart, then its table (or tables) beneath."""
    tables = ""
    if T:
        bc = (T.get("by_category") or {}).get(slug) or {}
        span, read = _weeks_span(T["window"]["week_starts"]), _fmt_day(T["generated_at"][:10], True)
        if slug == "bluetongue":
            tables = _bt_tables(heads, T)
        elif slug == "asf":
            tables = _asf_table(bc, T.get("asf_adis_week"), span, read)
        else:
            tables = _country_table(slug, bc, span, read)
    return ('<section class="cat-block" data-cat="%s" aria-labelledby="chart-%s-h">%s%s</section>'
            % (slug, slug, _chart_card(slug, c, weeks, starts), tables))


def _map_table(features, weeks):
    """The table under the map as first served: all diseases, all 12 weeks. The map script redraws it."""
    rows, split = {}, 0
    for f in features:
        p = f["properties"]
        n = sum(p["weeks"].get(w, 0) for w in weeks)
        if not n:
            continue
        cat = p["cat"] if p["cat"] in CAT_STYLE else "other"
        r = rows.setdefault((p.get("iso3") or p["cc"], cat), {"cc": p["cc"], "cat": cat, "wild": 0, "dom": 0, "all": 0})
        if p.get("pop") == "wild":
            r["wild"] += n
        elif p.get("pop") == "domestic":
            r["dom"] += n
        else:
            split += n
        r["all"] += n
    data = sorted(rows.values(), key=lambda r: (-r["all"], r["cc"]))
    head = "<tr>%s%s%s%s%s</tr>" % (_th("Country", 0, "text"), _th("Disease", 1, "text"), _th("Wild", 2),
                                    _th("Domestic", 3), _th("Total", 4, sort="descending"))
    body = "".join('<tr><th scope="row">%s</th><td>%s</td>%s%s%s</tr>' % (
        escape(r["cc"]), escape(CAT_STYLE[r["cat"]][1]), _td(r["wild"]), _td(r["dom"]), _td(r["all"])) for r in data)
    note = COUNTED + ((" Total also includes %s that cover both wild and domestic animals, or do not say which."
                       % "{:,}".format(split)) if split else "")
    return head, body, note


def _shape_svg(shape, colour="#4b5260"):
    if shape == "circle":
        el = '<circle cx="11" cy="11" r="6.5"/>'
    elif shape == "triangle":
        el = '<polygon points="11,3.4 19.75,18.6 2.25,18.6"/>'
    else:
        el = '<rect x="5.3" y="5.3" width="11.4" height="11.4"/>'
    return '<svg viewBox="0 0 22 22" aria-hidden="true" focusable="false"><g fill="%s">%s</g></svg>' % (colour, el)


def _tiles(heads, latest):
    def tile(value, label, src_html):
        return '<div class="tile"><b>%s</b><span class="t-label">%s</span><span class="t-src">%s</span></div>' % (value, label, src_html)
    out = []
    h = heads.get("govuk-bt-total")
    if h:
        areas = ", ".join("%s %s" % (k, "{:,}".format(v)) for k, v in (h.get("by_area") or {}).items())
        out.append(tile("{:,}".format(h["value"]), "bluetongue cases (premises) confirmed in the UK this season. %s." % areas,
                        "%s, counts to %s" % (_ext(h["source_url"], "GOV.UK"), _fmt_day(h["counts_to"], True))))
    h = heads.get("govuk-ai-season")
    if h:
        strains = sorted((k.replace(" cases", ""), v) for k, v in (h.get("by_strain") or {}).items() if v)
        out.append(tile("{:,}".format(h["value"]), "HPAI (bird flu) cases confirmed in the UK this season%s. Latest confirmed %s."
                        % ((": " + _and("%s %s" % ("{:,}".format(v), k) for k, v in strains)) if strains else "",
                           _fmt_day(h.get("latest_case", ""))),
                        "%s, updated %s" % (_ext(h["source_url"], "GOV.UK"), _fmt_day(h["as_of"], True))))
    h = heads.get("adis-week")
    if h:
        start, end = h["detail"].split(",")[0].split(" to ")
        cats = h.get("by_category") or {}
        biggest = max(cats.items(), key=lambda kv: kv[1]) if cats else None
        ncountries = re.search(r"(\d+) countries", h["detail"])
        lab = ("outbreaks in the EU&rsquo;s weekly ADIS report, %s%s." % (
            _fmt_range(start.strip(), end.strip()),
            (", in %s countries" % ncountries.group(1)) if ncountries else ""))
        if biggest:
            lab += " %s were %s." % ("{:,}".format(biggest[1]), CAT_STYLE.get(biggest[0], CAT_STYLE["other"])[2])
        out.append(tile("{:,}".format(h["value"]), lab, "%s, %s" % (_ext(h["source_url"], "European Commission, ADIS"), _fmt_day(h["as_of"], True))))
    h = heads.get("wahis-recent")
    if h:
        out.append(tile("{:,}".format(h["value"]), "disease events in %d countries with a new report to WOAH in the last 7 days. %s."
                        % (h.get("countries", 0), h.get("detail", "").capitalize()),
                        "%s, read %s" % (_ext(h["source_url"], "WOAH WAHIS"), _fmt_day(h["fetched_at"][:10], True))))
    h = heads.get("fi-asf-wild-boar")
    if h:
        out.append(tile("{:,}".format(h["value"]), "wild boar found with African swine fever in Finland this year, in %d cases. "
                        "Latest confirmed %s in %s." % (h.get("cases", 0), _fmt_day(h.get("latest_date", "")), escape(h.get("latest_municipality", ""))),
                        "%s, updated %s" % (_ext(h["source_url"], "Ruokavirasto"), _fmt_day(h["as_of"], True))))
    h = heads.get("ie-bt-herds")
    if h:
        saved = " Read from a saved copy of the page." if h.get("status") == "fallback" else ""
        out.append(tile("{:,}".format(h["value"]), "bluetongue herd cases in Ireland (%s), as at %s." % (h.get("detail", ""), _fmt_day(h.get("counts_to", ""))),
                        "%s, updated %s.%s" % (_ext(h["source_url"], "DAFM"), _fmt_day(h["as_of"], True), saved)))
    return '<div class="tiles">%s</div>' % "".join(out)


def _facts(heads):
    rows = []
    h = heads.get("govuk-ai-risk")
    if h:
        if h.get("poultry_poor_level") and h.get("poultry_poor_uncertainty") == h.get("poultry_stringent_uncertainty"):
            poultry = "%s where biosecurity is poor and %s where it is stringent, both with %s uncertainty" % (
                h["poultry_poor_level"], h["poultry_stringent_level"], h["poultry_poor_uncertainty"])
        else:
            poultry = "%s where biosecurity is poor, %s where it is stringent" % (
                h["poultry_poor_biosecurity"], h["poultry_stringent_biosecurity"])
        rows.append(("HPAI risk, Great Britain", "Wild birds: %s. Poultry: %s. %s, updated %s."
                     % (h["wild_birds"], poultry, _ext(h["source_url"], "GOV.UK"), _fmt_day(h["as_of"], True))))
        rows.append(("Prevention zone or housing order, England", "%s %s, updated %s."
                     % (escape(h["aipz_or_housing"]), _ext(h["source_url"], "GOV.UK"), _fmt_day(h["as_of"], True))))
    h = heads.get("govuk-bt-risk")
    inv = heads.get("govuk-bt-investigation")
    if h:
        rows.append(("Bluetongue risk and zones",
                     "Risk of incursion: %s. %s%s %s, updated %s."
                     % (h["detail"].rstrip(".").replace(". ", ", ").lower(), h.get("zone", ""),
                        (" %s potential cases under investigation in Great Britain." % "{:,}".format(inv["value"])) if inv else "",
                        _ext(h["source_url"], "GOV.UK"), _fmt_day(h["as_of"], True))))
    return '<dl class="facts">%s</dl>' % "".join("<div><dt>%s</dt><dd>%s</dd></div>" % r for r in rows)


TABLES_TAG = "<script>%s</script>" % TABLES_JS.strip()

if LIVE:
    _latest, _agg = LIVE["latest"], LIVE["agg"]
    _weeks = _agg["window"]["weeks"]
    _starts = _agg["window"]["week_starts"]
    _cats = _agg["categories"]
    _read = _fmt_stamp(_latest["generated_at"])
    _first, _last = _fmt_day(_starts[0], True), _fmt_day(_starts[-1], True)
    _span = _weeks_span(_starts)

    # ---------- MAP ----------
    cfg = {"data": LIVE_DATA_URL + "map.geojson", "style": MAP_STYLE, "glyphs": MAP_GLYPHS, "attribution": MAP_CREDIT,
           "maxZoom": MAP_MAX_ZOOM, "weeks": [[w, _fmt_day(s, True)] for w, s in zip(_weeks, _starts)],
           "cats": {k: {"colour": v[0], "short": v[1], "phrase": v[2]} for k, v in CAT_STYLE.items()},
           "units": {"outbreak": "outbreaks", "event": "events", "case": "cases",
                     "case (premises) this season": "cases (premises) this season",
                     "herd case this season": "herd cases this season"},
           "pop": POP_WORDS, "tableNote": COUNTED}
    cfg_json = json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/")
    week_opts = "".join('<option value="%d">%s</option>' % (i, _fmt_day(s, True)) for i, s in enumerate(_starts))
    week_opts_to = week_opts.replace('<option value="%d">' % (len(_starts) - 1), '<option value="%d" selected>' % (len(_starts) - 1))
    shapes = "".join("<li>%s%s</li>" % (_shape_svg(sh), t) for sh, t in
                     (("circle", "Domestic animals"), ("triangle", "Wild animals"), ("square", "Both, or not stated")))
    colours = "".join('<li><i class="sw" style="--c:%s"></i>%s</li>' % (v[0], escape(v[1])) for k, v in CAT_STYLE.items() if k in _cats)
    legend = ('<div class="legend" role="group" aria-label="Key">'
              '<div><p class="legend-title">Shape: the animals affected</p><ul>%s</ul></div>'
              '<div><p class="legend-title">Colour: the disease</p><ul>%s</ul></div>'
              '<div><p class="legend-title">Groups</p><ul><li><span class="key-cluster">12</span>Places close together. '
              'Zoom in or select to see them.</li></ul></div></div>' % (shapes, colours))
    m_head, m_body, m_note = _map_table((LIVE["map"] or {}).get("features", []), _weeks)
    map_table = ('<div class="tbl-block" id="by-country"><h2 class="tbl-title" id="map-table-title">%s</h2>'
                 '<div class="tbl-wrap" role="region" tabindex="0" aria-labelledby="map-table-title">'
                 '<table class="tbl" id="map-table" data-top="10" data-noun="rows" aria-labelledby="map-table-title">'
                 '<thead>%s</thead><tbody>%s</tbody></table></div>'
                 '<p class="tbl-cap" id="map-table-note">%s</p>'
                 '<p class="tbl-links"><a href="data.html">Download the data</a></p></div>'
                 % (_cap("reports by country, " + _span), m_head, m_body, m_note))
    map_credit = (" The basemap is %s, under the Open Database Licence." % MAP_CREDIT)
    # The map with its filters, key, notes and table, then its scripts. map.html and the home page both use
    # these two pieces, so the two maps cannot drift apart.
    map_widget = f"""
<form class="filters" id="map-filters" onsubmit="return false">
{_chips("map-cat", _cats)}
<div class="time-row">
<div class="field"><label class="field-label" for="from-week">From week starting</label><select id="from-week">{week_opts}</select></div>
<div class="field"><label class="field-label" for="to-week">To week starting</label><select id="to-week">{week_opts_to}</select></div>
<div class="field slider"><label class="field-label" for="week-slider">Show weeks up to</label>
<input type="range" id="week-slider" min="0" max="{len(_starts) - 1}" value="{len(_starts) - 1}" step="1">
<output id="week-out" for="week-slider">{_cap(_span)}</output></div>
</div>
</form>
<p class="map-summary" id="map-summary" aria-live="polite">Loading the map data.</p>
<div class="map-shell"><div id="map" role="region" aria-label="Map of official animal-disease reports"></div>
<noscript><p>The map needs JavaScript. The table below and the <a href="data.html">open data</a> hold the same records.</p></noscript></div>
{legend}
<div class="map-after">
<div class="below-map">
<p><strong>Points sit at the centre of a country, region or county. They never show a farm or other premises.</strong></p>
<p class="note">Where a national source publishes the figures (GOV.UK, DAFM in Ireland, Ruokavirasto in Finland), the map shows them and links the matching WOAH and EU records in the pop-up, so nothing is counted twice. Season totals appear in the week they were published. Counts change with the weeks you choose.</p>
</div>
{map_table}
</div>"""
    map_scripts = f"""<script type="application/json" id="map-config">{cfg_json}</script>
{TABLES_TAG}
{MAPLIBRE_JS}<script defer src="assets/map.js?v={hashlib.sha256(MAP_JS.encode()).hexdigest()[:8]}"></script>"""
    map_body = subnav("map.html") + page_head("Map of official reports",
        "Outbreaks and cases reported by WOAH, the EU, FAO and national governments in the last 12 weeks. "
        "Every point sits at the centre of a country, region or county.", "Live data") + f"""
<section class="section tight"><div class="wrap">
<p class="lede-row"><span>Data read {_read}</span><a href="data.html">Download the data</a><a href="analytics.html">See the numbers</a></p>{map_widget}
{_sources_block(_latest, map_credit)}
<div class="actions"><a class="btn btn-primary" href="data.html">Download the data</a><a class="btn btn-outline" href="analytics.html">See the numbers</a></div>
</div></section>
{map_scripts}"""
    write("map.html", page("Map", "data.html", map_body,
          "A map of official animal-disease reports from WOAH, the EU, FAO and national governments, at country, region or county level.",
          path="map.html", head=MAP_HEAD))
    write(os.path.join("assets", "map.js"), MAP_JS)

    # ---------- NUMBERS ----------
    _T = LIVE.get("tables")
    blocks = "".join(_cat_block(slug, _cats[slug], _weeks, _starts, _T, LIVE["heads"]) for slug in _cats)
    num_body = subnav("analytics.html") + page_head("The numbers",
        "Headline figures and 12 weeks of counts for each disease, from official sources. Every figure shows its source and date.",
        "Live data") + f"""
<section class="section tight"><div class="wrap">
<p class="lede-row"><span>Data read {_read}</span><a href="map.html">See the map</a><a href="data.html">Download the data</a></p>
<h2 class="vh">Headline figures</h2>
{_tiles(LIVE["heads"], _latest)}
<h2 class="vh">Risk levels and controls</h2>
{_facts(LIVE["heads"])}
</div></section>
<section class="section tight" aria-labelledby="weekly-title"><div class="wrap">
<div class="section-head"><h2 id="weekly-title">Week by week</h2>
<p>The last 12 weeks for each disease, with a table by country under each chart. This week is shown in the disease&rsquo;s colour and is not finished yet.</p></div>
<form class="filters" onsubmit="return false">{_chips("num-cat", _cats)}</form>
<div class="cat-blocks">{blocks}</div>
<p class="note">Each chart keeps its source&rsquo;s own counting rules, so the charts cannot be added together. The weekly counts by country are in <a href="{LIVE_DATA_URL}aggregates.json">aggregates.json</a>, and the country tables are in <a href="{LIVE_DATA_URL}tables.json">tables.json</a>.</p>
{_sources_block(_latest)}
</div></section>
{TABLES_TAG}
<script defer src="assets/numbers.js?v={hashlib.sha256(NUMBERS_JS.encode()).hexdigest()[:8]}"></script>"""
    write("analytics.html", page("Numbers", "data.html", num_body,
          "Headline animal-disease figures and 12 weeks of counts for each disease, each with its official source and date.",
          path="analytics.html"))
    write(os.path.join("assets", "numbers.js"), NUMBERS_JS)


# ---------- HOME, v7 (23 Oct 2026) ----------
# With live data the home page leads with the map: a short hero, then the map and its table exactly as on map.html
# (the same markup and script), this week's episode and newsletter, a line to the shorts and one line on sources.
# The shorts stay on the Watch page. Without live data the v6 home page above is used.
if LIVE:
    hero_extra = ('<div class="hero-row">%s<p class="hero-meta"><span>Data read %s</span>'
                  '<a href="analytics.html">See the numbers</a><a href="data.html">Download the data</a></p></div>' % (email_btn, _read))
    home = page_head("Making the world&#39;s <span class=\"nw\">animal-disease</span> data make sense.",
                     "Each week we turn official surveillance data into clear maps, key numbers and a short, sourced briefing.",
                     extra=hero_extra, cls="home-hero") + f"""
<section class="section tight home-map" aria-labelledby="home-map-title"><div class="wrap">
<h2 class="vh" id="home-map-title">Map of official reports</h2>{map_widget}
</div></section>
{week_band()}
<div class="src-line"><div class="wrap"><p>Every figure comes from a named public source. <a href="sources.html">Sources and reuse terms</a>.</p></div></div>
{map_scripts}"""
    write("index.html", page("Home", "index.html", home, HOME_DESC, head=MAP_HEAD))
else:
    write("index.html", page("Home", "index.html", home, HOME_DESC))


# ---------- DATA ----------
licence = ('<p class="note">Licence: free to reuse with attribution to OutbreakLens and to the original data providers. '
           'Derived from publicly available sources. Always check the primary source&#39;s own terms.</p>')
if LIVE:
    _files, _dict = LIVE["files"], LIVE["dictionary"]
    _status = {s["key"]: s for s in LIVE["latest"].get("sources", [])}

    def _dl(name, label=None):
        f = _files.get(name)
        if not f:
            return ""
        kind = {"csv": "CSV", "json": "JSON", "geojson": "GeoJSON"}.get(name.rsplit(".", 1)[1], name.rsplit(".", 1)[1])
        # one wrapping span, so the phone layout (label | value grid) keeps the size next to the link
        return '<span><a href="%s%s" download>%s</a> <span class="nw">(%s, %s)</span></span>' % (
            LIVE_DATA_URL, name, escape(label or name), kind, f["size"])

    def _rows(name):
        r = (_files.get(name) or {}).get("rows")
        return "{:,} rows".format(r) if r is not None else ""

    def _licences(sources):
        out = []
        for name, short in LICENCE_SHORT:
            if name in sources and short not in out:
                out.append(short)
        return ", ".join(out) if out else "OutbreakLens, free to reuse"

    by_cat = "".join('<span><a href="%s%s.csv" download>%s</a> <span class="nw">(%s)</span></span>' % (
        LIVE_DATA_URL, slug, escape(LIVE["agg"]["categories"][slug]["label"]),
        "{:,}".format((_files.get("%s.csv" % slug) or {}).get("rows") or 0)) for slug in LIVE["cats"])
    table_rows = [
        ("All records", "Every event, case and published total from the seven sources. One row each, with its source, date and link. %s." % _rows("events.csv"), _dl("events.csv")),
        ("By disease", "The same rows, one file for each of the eight diseases. Rows in brackets.", '<span class="dl-cats">%s</span>' % by_cat),
        ("Weekly counts", "Counts by week, disease and country for the last 12 weeks, kept separate for each source.", _dl("aggregates.json")),
        ("Headline numbers", "The figures on the Numbers page, each with its source and date.", _dl("latest.json")),
        ("Map points", "The places on the map, at the centre of a country, region or county, with counts by week.", _dl("map.geojson")),
        ("Data dictionary", "What each column in the CSV files means.", _dl("dictionary.csv")),
    ]
    rows_html = "".join('<tr><td data-label="Dataset">%s</td><td data-label="What it holds">%s</td><td data-label="Download">%s</td></tr>'
                        % r for r in table_rows)
    _stamp_iso = LIVE["latest"]["generated_at"][:10]
    csv_rows = "".join(
        '<tr><th scope="row"><a href="%s%s" download>%s</a></th>%s%s<td data-v="%s">%s</td><td class="wrap">%s</td></tr>'
        % (LIVE_DATA_URL, n, n, _td(_files[n]["rows"]), _td(_files[n]["cols"]), _stamp_iso, _fmt_day(_stamp_iso, True),
           _licences(_files[n]["sources"]))
        for n in ["events.csv"] + ["%s.csv" % c for c in LIVE["cats"]] + ["dictionary.csv"] if n in _files)
    csv_head = "<tr>%s%s%s%s%s</tr>" % (_th("File", 0, "text"), _th("Rows", 1), _th("Columns", 2),
                                        _th("Last updated", 3, "text"), _th("Licence", 4, "text"))
    csv_table = _tbl("tbl-csv", "CSV files, data read %s" % _fmt_day(_stamp_iso, True), csv_head, csv_rows,
                     "Free to reuse with credit to OutbreakLens and to the sources. The terms named apply to the rows "
                     "from each source. They are set out under Sources below.", noun="files", level="h2")
    dict_rows = "".join('<tr><td data-label="Column"><code>%s</code></td><td data-label="Type">%s</td><td data-label="Meaning">%s</td></tr>'
                        % (escape(d["column"]), escape(d["type"]), escape(d["description"])) for d in _dict)
    status_label = {"live": "Read live", "fallback": "Saved copy", "failed": "Not available", "stub": "Not connected"}
    status_rows = "".join(
        '<tr><td data-label="Source">%s</td><td data-label="This run"><span class="status-%s">%s</span></td>'
        '<td data-label="Rows">%s</td><td data-label="Source updated">%s</td></tr>'
        % (escape(s["name"].replace("GOV.UK (Defra and APHA)", "GOV.UK " + ("bluetongue" if s["key"] == "govuk_bluetongue" else "HPAI"))),
           escape(s["status"]), status_label.get(s["status"], escape(s["status"])), "{:,}".format(s["rows"]),
           _fmt_day((s.get("source_updated") or "")[:10], True) or "not given")
        for s in LIVE["latest"].get("sources", []))
    data = subnav("data.html") + page_head("Open data, free to use",
        "The records behind the map and the numbers. One row per event, case or published total, each with its source, "
        "date and link. Updated each time the pipeline runs.", "Live data") + f"""
<section class="section tight"><div class="wrap">
<p class="lede-row"><span>Data read {_fmt_stamp(LIVE["latest"]["generated_at"])}</span><a href="map.html">See the map</a><a href="analytics.html">See the numbers</a></p>
<table class="data-table"><caption class="vh">Files to download</caption>
<thead><tr><th scope="col">Dataset</th><th scope="col">What it holds</th><th scope="col">Download</th></tr></thead>
<tbody>{rows_html}</tbody></table>
{csv_table}
<div class="narrow">
<h2>Licence</h2>
<p>Free to reuse with attribution to OutbreakLens and to the original providers. Each provider&rsquo;s own terms also apply, and some limit commercial use. They are listed under Sources below.</p>
<p class="note">Suggested credit: &ldquo;OutbreakLens open data, from WOAH WAHIS, EU ADIS, FAO EMPRES-i, GOV.UK, DAFM and Ruokavirasto, read {_fmt_day(LIVE["latest"]["generated_at"][:10])}.&rdquo;</p>
<h2>How it is made</h2>
<ul>
<li>Each source is read as published. Nothing is estimated or filled in.</li>
<li>When two sources describe the same event, both rows are kept and linked in the <code>same_as</code> column, so every figure stays traceable.</li>
<li>Places are given at country, region or county level. Points are the centre of that area and never show a farm or other premises.</li>
<li>Dates use YYYY-MM-DD. Countries use ISO 3166 three-letter codes.</li>
</ul>
</div>
<details class="dict"><summary>Columns in the CSV files ({len(_dict)})</summary>
<table class="data-table"><caption class="vh">Data dictionary</caption>
<thead><tr><th scope="col">Column</th><th scope="col">Type</th><th scope="col">Meaning</th></tr></thead>
<tbody>{dict_rows}</tbody></table></details>
<h2>Sources in this run</h2>
<table class="data-table"><caption class="vh">What each source returned</caption>
<thead><tr><th scope="col">Source</th><th scope="col">This run</th><th scope="col">Rows</th><th scope="col">Source updated</th></tr></thead>
<tbody>{status_rows}</tbody></table>
<p class="note">A saved copy means the source could not be read in this run, so the last good copy was used. Its date is shown.</p>
{_sources_block(LIVE["latest"])}
</div></section>
{TABLES_TAG}"""
elif PRELAUNCH:
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
write("data.html", page("Data", "data.html", data,
      "Open animal-disease data from official sources: one row per event, case or published total, with its source, date and link."
      if LIVE else "Clean, free-to-use animal-disease event data behind every OutbreakLens report."))

# ---------- SOURCES ----------
SRC=[("WOAH WAHIS","Global official disease notifications and dashboards.","https://wahis.woah.org/"),
("EU ADIS","EU outbreak notifications (successor to ADNS), linked to WAHIS.","https://food.ec.europa.eu/animals/animal-diseases/animal-disease-information-system-adis_en"),
("FAO EMPRES-i+","Global disease events, mapping layers and early warning.","https://empres-i.apps.fao.org/"),
("EFSA","Avian influenza and ASF surveillance reports and datasets.","https://www.efsa.europa.eu/en/topics/topic/avian-influenza"),
("SHIC","Global swine disease monitoring reports.","https://www.swinehealth.org/"),
("Defra / APHA","UK outbreak assessments and notifiable-disease updates.","https://www.gov.uk/government/collections/animal-diseases-international-and-uk-monitoring"),
("DAFM, Ireland","Bluetongue herd cases by county in Ireland.","https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/publications/bluetongue-virus/"),
("Ruokavirasto, Finland","African swine fever cases in wild boar in Finland.","https://www.ruokavirasto.fi/en/animals/animal-health-and-diseases/animal-diseases/pigs/african-swine-fever-asf/"),
("ECDC / WHO / OFFLU","Zoonotic and influenza-at-the-interface context.","https://www.offlu.org/")]
def _slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def _domain(u): return re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
cards="".join('<article class="card" id="%s"><h2>%s</h2><p>%s</p><p class="domain">%s</p>%s</article>'
              % (_slug(n), n, d, _domain(u), ext(u, "Visit " + n, "card-link", ICON_EXT)) for n,d,u in SRC)
# With live data the reuse terms for each source follow the cards. The home page links here for them.
terms = ('<div id="terms">%s</div>' % _sources_block(LIVE["latest"], map_credit, "Reuse terms for the open data")) if LIVE else ""
sources = page_head("Authoritative sources",
    "We interpret and signpost. We never replace the authorities below. For official figures, decisions and guidance, always go to the primary source.") + f"""
<section class="section"><div class="wrap"><div class="cards">{cards}</div>{terms}</div></section>"""
write("sources.html", page("Sources", "sources.html", sources,
      "The official animal-health sources OutbreakLens uses and signposts, and the reuse terms for its open data."
      if LIVE else "The official animal-health sources OutbreakLens uses and signposts."))

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
      + "".join("<url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (canonical(p), TODAY.isoformat())
                for p in sorted(INDEXED, key=lambda p: p != "index.html"))   # the home page first
      + "</urlset>\n")
write("robots.txt", "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)

print("built site ->", SITE)
print("pages:", sorted(f for f in os.listdir(SITE) if f.endswith(".html")) + [s["page"] for s in SHORTS])
print("sitemap:", len(INDEXED), "pages")
