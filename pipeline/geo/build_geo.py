#!/usr/bin/env python3
"""
build_geo.py: build the small gazetteer files the pipeline uses to place records on the map.

    python -I geo/build_geo.py

It downloads Natural Earth (public domain) country and first-level boundaries once into
cache/geo/, then writes three small CSV files next to this script:

  countries.csv    one row per country: ISO codes, names and a label point
  admin1.csv       one row per Natural Earth first-level unit: names and a label point
  local_areas.csv  counties and council areas as GOV.UK and DAFM publish them, each
                   mapped to one or more Natural Earth units, with a centre point

Centres are rounded to 0.01 degrees. They mark an area, never a premises.
"""
import csv, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "cache", "geo")
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
FILES = {"admin1": "ne_10m_admin_1_states_provinces.geojson", "admin0": "ne_50m_admin_0_countries.geojson"}
UA = "OutbreakLensPipeline/2.0 (+https://outbreaklens.com)"


def fetch(name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        print("downloading", name)
        req = urllib.request.Request(NE + name, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
            f.write(r.read())
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def r2(v):
    return "" if v is None else "%.2f" % float(v)


# Extra country names the sources use. Keys are lower case.
COUNTRY_ALIASES = {
    "GBR": ["united kingdom", "uk", "great britain", "the united kingdom of great britain and northern ireland",
            "united kingdom of great britain and northern ireland"],
    "USA": ["united states of america", "united states", "usa", "us"],
    "RUS": ["russia", "russian federation"],
    "KOR": ["korea (rep. of)", "republic of korea", "south korea", "korea, republic of"],
    "PRK": ["korea (dem. people's rep.)", "democratic people's republic of korea", "north korea"],
    "CHN": ["china (people's rep. of)", "china", "people's republic of china"],
    "TWN": ["chinese taipei", "taiwan (province of china)", "taiwan", "china, taiwan province of"],
    "NOR": ["norway", "svalbard and jan mayen islands", "svalbard and jan mayen", "svalbard"],
    "IRN": ["iran", "iran (islamic republic of)"],
    "SYR": ["syria", "syrian arab republic"],
    "VNM": ["vietnam", "viet nam"],
    "LAO": ["laos", "lao people's democratic republic", "lao people's dem. rep."],
    "BOL": ["bolivia", "bolivia (plurinational state of)"],
    "VEN": ["venezuela", "venezuela (bolivarian republic of)"],
    "TZA": ["tanzania", "united republic of tanzania"],
    "COD": ["congo (dem. rep. of the)", "democratic republic of the congo", "dem. rep. congo"],
    "COG": ["congo (rep. of the)", "congo", "republic of the congo"],
    "CIV": ["cote d'ivoire", "côte d'ivoire", "ivory coast"],
    "MDA": ["moldova", "republic of moldova"],
    "MKD": ["north macedonia", "macedonia", "north macedonia (republic of)"],
    "BIH": ["bosnia and herzegovina", "bosnia and herz."],
    "CZE": ["czech republic", "czechia"],
    "SVK": ["slovakia", "slovak republic"],
    "TUR": ["turkey", "türkiye", "turkiye"],
    "NLD": ["netherlands", "the netherlands", "netherlands (kingdom of the)"],
    "SWZ": ["eswatini", "swaziland"],
    "CPV": ["cabo verde", "cape verde"],
    "PSE": ["palestine", "palestinian autonomous territories", "state of palestine"],
    "XKX": ["kosovo"],
    "HKG": ["hong kong", "hong kong sar", "china (hong kong sar)"],
    "BRN": ["brunei", "brunei darussalam"],
    "FSM": ["micronesia (federated states of)", "micronesia"],
    "DOM": ["dominican (rep.)", "dominican republic"],
    "CAF": ["central african (rep.)", "central african republic"],
    "ESP": ["spain", "melilla", "ceuta"],
}
# Natural Earth uses its own codes for a few places. Map them to ISO codes.
NE_FIX = {"KOS": "XKX", "SDS": "SSD", "SAH": "ESH", "PSX": "PSE", "CYN": "CYP", "SOL": "SOM", "KAS": "IND"}
# Display names in the short form GOV.UK uses. Everything else takes Natural Earth's long name.
DISPLAY = {"CZE": "Czechia", "TUR": "Türkiye", "KOR": "South Korea", "PRK": "North Korea", "RUS": "Russia",
           "LAO": "Laos", "SYR": "Syria", "VNM": "Vietnam", "MDA": "Moldova", "IRN": "Iran", "TZA": "Tanzania",
           "BOL": "Bolivia", "VEN": "Venezuela", "TWN": "Taiwan", "CIV": "Côte d'Ivoire", "CHN": "China",
           "COD": "Democratic Republic of the Congo", "COG": "Congo", "SWZ": "Eswatini", "MKD": "North Macedonia",
           "GBR": "United Kingdom", "USA": "United States", "BRN": "Brunei", "CPV": "Cape Verde",
           "FSM": "Micronesia", "GMB": "The Gambia", "BHS": "The Bahamas", "HKG": "Hong Kong", "MAC": "Macao",
           "XKX": "Kosovo", "NLD": "Netherlands", "BIH": "Bosnia and Herzegovina"}


def build_countries(admin0):
    rows = {}
    for feat in admin0["features"]:
        p = feat["properties"]
        iso3 = p.get("ISO_A3_EH") or p.get("ISO_A3")
        if not iso3 or iso3 == "-99":
            iso3 = NE_FIX.get(p.get("ADM0_A3"), p.get("ADM0_A3"))
        iso2 = p.get("ISO_A2_EH") or p.get("ISO_A2") or ""
        if iso2 == "-99":
            iso2 = ""
        names = {p.get("NAME"), p.get("NAME_LONG"), p.get("ADMIN"), p.get("FORMAL_EN"), p.get("NAME_EN"),
                 p.get("NAME_SORT"), p.get("BRK_NAME"), p.get("SOVEREIGNT") if p.get("TYPE") == "Sovereign country" else None}
        names |= set(COUNTRY_ALIASES.get(iso3, []))
        names = sorted({n.strip().lower() for n in names if n})
        if iso3 in rows:   # keep the main unit (largest population) as the label point
            if (p.get("POP_EST") or 0) <= rows[iso3]["_pop"]:
                rows[iso3]["aliases"] = "|".join(sorted(set(rows[iso3]["aliases"].split("|")) | set(names)))
                continue
        rows[iso3] = {"iso3": iso3, "iso2": iso2, "name": DISPLAY.get(iso3) or p.get("NAME_LONG") or p.get("NAME"),
                      "aliases": "|".join(names), "lat": r2(p.get("LABEL_Y")), "lon": r2(p.get("LABEL_X")),
                      "_pop": p.get("POP_EST") or 0}
    # Kosovo and a few others carry no ISO code in Natural Earth; make sure the fixes are present.
    out = sorted(rows.values(), key=lambda r: r["iso3"])
    with open(os.path.join(HERE, "countries.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["iso3", "iso2", "name", "aliases", "lat", "lon"], extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    print("countries.csv:", len(out))


def build_admin1(admin1):
    out = []
    for feat in admin1["features"]:
        p = feat["properties"]
        iso3 = NE_FIX.get(p.get("adm0_a3"), p.get("adm0_a3"))
        names = {p.get("name"), p.get("name_en"), p.get("name_local"), p.get("gn_name"), p.get("woe_name"),
                 p.get("gns_name")}
        for alt in (p.get("name_alt") or "").split("|"):
            names.add(alt)
        names = sorted({n.strip() for n in names if n and n.strip()})
        out.append({"adm1_code": p.get("adm1_code"), "iso3": iso3, "unit": p.get("geonunit") or "",
                    "name": p.get("name") or p.get("name_en") or "", "names": "|".join(names),
                    "type": p.get("type_en") or "", "lat": r2(p.get("latitude")), "lon": r2(p.get("longitude"))})
    with open(os.path.join(HERE, "admin1.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["adm1_code", "iso3", "unit", "name", "names", "type", "lat", "lon"])
        w.writeheader()
        w.writerows(out)
    print("admin1.csv:", len(out))


# Counties and council areas as GOV.UK, DAFM and Ruokavirasto publish them, mapped to Natural Earth
# first-level units. Natural Earth splits England into unitary authorities and metropolitan boroughs,
# so a ceremonial county is the union of its parts. Columns: iso3, published name, admin1 for the
# record (UK nation, or the Finnish region), Natural Earth unit names joined with |.
LONDON = ("Barking and Dagenham|Barnet|Bexley|Brent|Bromley|Camden|City|Croydon|Ealing|Enfield|Greenwich|Hackney|"
          "Hammersmith and Fulham|Haringey|Harrow|Havering|Hillingdon|Hounslow|Islington|Kensington and Chelsea|"
          "Kingston upon Thames|Lambeth|Lewisham|Merton|Newham|Redbridge|Richmond upon Thames|Southwark|Sutton|"
          "Tower Hamlets|Waltham Forest|Wandsworth|Westminster")
LOCAL = [
    # England: ceremonial counties
    ("GBR", "Bedfordshire", "England", "Bedford|Central Bedfordshire|Luton"),
    ("GBR", "Berkshire", "England", "Bracknell Forest|Reading|Royal Borough of Windsor and Maidenhead|Slough|West Berkshire|Wokingham"),
    ("GBR", "Bristol", "England", "Bristol"),
    ("GBR", "City of Bristol", "England", "Bristol"),
    ("GBR", "Buckinghamshire", "England", "Buckinghamshire"),
    ("GBR", "Cambridgeshire", "England", "Cambridgeshire|Peterborough"),
    ("GBR", "Cheshire", "England", "Cheshire East|Cheshire West and Chester"),
    ("GBR", "Cheshire East", "England", "Cheshire East"),
    ("GBR", "Cheshire West and Chester", "England", "Cheshire West and Chester"),
    ("GBR", "Cornwall", "England", "Cornwall"),
    ("GBR", "Isles of Scilly", "England", "Isles of Scilly"),
    ("GBR", "Cumbria", "England", "Cumbria"),
    ("GBR", "Cumberland", "England", "Cumbria"),
    ("GBR", "Westmorland and Furness", "England", "Cumbria"),
    ("GBR", "Derbyshire", "England", "Derbyshire|Derby"),
    ("GBR", "Devon", "England", "Devon"),
    ("GBR", "Plymouth", "England", "Plymouth"),
    ("GBR", "Torbay", "England", "Torbay"),
    ("GBR", "Dorset", "England", "Dorset|Bournemouth|Poole"),
    ("GBR", "Bournemouth, Christchurch and Poole", "England", "Bournemouth|Poole"),
    ("GBR", "Durham", "England", "Durham"),
    ("GBR", "County Durham", "England", "Durham"),
    ("GBR", "Darlington", "England", "Darlington"),
    ("GBR", "Hartlepool", "England", "Hartlepool"),
    ("GBR", "East Riding of Yorkshire", "England", "East Riding of Yorkshire"),
    ("GBR", "East Sussex", "England", "East Sussex|Brighton and Hove"),
    ("GBR", "Essex", "England", "Essex|Southend-on-Sea|Thurrock"),
    ("GBR", "Gloucestershire", "England", "Gloucestershire|South Gloucestershire"),
    ("GBR", "South Gloucestershire", "England", "South Gloucestershire"),
    ("GBR", "Greater London", "England", LONDON),
    ("GBR", "London", "England", LONDON),
    ("GBR", "Greater Manchester", "England", "Bolton|Bury|Manchester|Oldham|Rochdale|Salford|Stockport|Tameside|Trafford|Wigan"),
    ("GBR", "Tameside", "England", "Tameside"),
    ("GBR", "Hampshire", "England", "Hampshire|Portsmouth|Southampton"),
    ("GBR", "Herefordshire", "England", "Herefordshire"),
    ("GBR", "Hertfordshire", "England", "Hertfordshire"),
    ("GBR", "Isle of Wight", "England", "Isle of Wight"),
    ("GBR", "Kent", "England", "Kent|Medway"),
    ("GBR", "Lancashire", "England", "Lancashire|Blackburn with Darwen|Blackpool"),
    ("GBR", "Leicestershire", "England", "Leicestershire|Leicester"),
    ("GBR", "Lincolnshire", "England", "Lincolnshire|North Lincolnshire|North East Lincolnshire"),
    ("GBR", "Merseyside", "England", "Liverpool|Knowsley|Sefton|Merseyside"),
    ("GBR", "Norfolk", "England", "Norfolk"),
    ("GBR", "North Yorkshire", "England", "North Yorkshire|York"),
    ("GBR", "Northamptonshire", "England", "Northamptonshire"),
    ("GBR", "North Northamptonshire", "England", "Northamptonshire"),
    ("GBR", "West Northamptonshire", "England", "Northamptonshire"),
    ("GBR", "Northumberland", "England", "Northumberland"),
    ("GBR", "Nottinghamshire", "England", "Nottinghamshire|Nottingham"),
    ("GBR", "Oxfordshire", "England", "Oxfordshire"),
    ("GBR", "Rutland", "England", "Rutland"),
    ("GBR", "Shropshire", "England", "Shropshire|Telford and Wrekin"),
    ("GBR", "Somerset", "England", "Somerset|Bath and North East Somerset|North Somerset"),
    ("GBR", "North Somerset", "England", "North Somerset"),
    ("GBR", "South Yorkshire", "England", "Barnsley|Doncaster|Rotherham|Sheffield"),
    ("GBR", "Staffordshire", "England", "Staffordshire|Stoke-on-Trent"),
    ("GBR", "Suffolk", "England", "Suffolk"),
    ("GBR", "Surrey", "England", "Surrey"),
    ("GBR", "Tyne and Wear", "England", "Gateshead|Newcastle upon Tyne|North Tyneside|South Tyneside|Sunderland"),
    ("GBR", "Warwickshire", "England", "Warwickshire"),
    ("GBR", "West Midlands", "England", "Birmingham|Coventry|Dudley|Sandwell|Solihull|Walsall|Wolverhampton"),
    ("GBR", "West Midlands (Solihull)", "England", "Solihull"),
    ("GBR", "Solihull", "England", "Solihull"),
    ("GBR", "West Sussex", "England", "West Sussex"),
    ("GBR", "West Yorkshire", "England", "Bradford|Calderdale|Kirklees|Leeds|Wakefield"),
    ("GBR", "Wiltshire", "England", "Wiltshire|Swindon"),
    ("GBR", "Worcestershire", "England", "Worcestershire"),
    # Wales: local authorities (GOV.UK adds the Welsh name in brackets; the parser strips it)
    ("GBR", "Isle of Anglesey", "Wales", "Anglesey"),
    ("GBR", "Anglesey", "Wales", "Anglesey"),
    ("GBR", "Blaenau Gwent", "Wales", "Blaenau Gwent"),
    ("GBR", "Bridgend", "Wales", "Bridgend"),
    ("GBR", "Caerphilly", "Wales", "Caerphilly"),
    ("GBR", "Cardiff", "Wales", "Cardiff"),
    ("GBR", "Carmarthenshire", "Wales", "Carmarthenshire"),
    ("GBR", "Ceredigion", "Wales", "Ceredigion"),
    ("GBR", "Conwy", "Wales", "Conwy"),
    ("GBR", "Denbighshire", "Wales", "Denbighshire"),
    ("GBR", "Flintshire", "Wales", "Flintshire"),
    ("GBR", "Gwynedd", "Wales", "Gwynedd"),
    ("GBR", "Merthyr Tydfil", "Wales", "Merthyr Tydfil"),
    ("GBR", "Monmouthshire", "Wales", "Monmouthshire"),
    ("GBR", "Neath Port Talbot", "Wales", "Neath Port Talbot"),
    ("GBR", "Newport", "Wales", "Newport"),
    ("GBR", "Pembrokeshire", "Wales", "Pembrokeshire"),
    ("GBR", "Powys", "Wales", "Powys"),
    ("GBR", "Rhondda Cynon Taf", "Wales", "Rhondda, Cynon, Taff"),
    ("GBR", "Swansea", "Wales", "Swansea"),
    ("GBR", "Torfaen", "Wales", "Torfaen"),
    ("GBR", "Vale of Glamorgan", "Wales", "Vale of Glamorgan"),
    ("GBR", "Wrexham", "Wales", "Wrexham"),
    # Scotland: council areas
    ("GBR", "Aberdeen City", "Scotland", "Aberdeen"),
    ("GBR", "Aberdeenshire", "Scotland", "Aberdeenshire"),
    ("GBR", "Angus", "Scotland", "Angus"),
    ("GBR", "Argyll and Bute", "Scotland", "Argyll and Bute"),
    ("GBR", "Clackmannanshire", "Scotland", "Clackmannanshire"),
    ("GBR", "Dumfries and Galloway", "Scotland", "Dumfries and Galloway"),
    ("GBR", "Dundee City", "Scotland", "Dundee"),
    ("GBR", "East Ayrshire", "Scotland", "East Ayrshire"),
    ("GBR", "East Dunbartonshire", "Scotland", "East Dunbartonshire"),
    ("GBR", "East Lothian", "Scotland", "East Lothian"),
    ("GBR", "East Renfrewshire", "Scotland", "East Renfrewshire"),
    ("GBR", "City of Edinburgh", "Scotland", "Edinburgh"),
    ("GBR", "Edinburgh", "Scotland", "Edinburgh"),
    ("GBR", "Na h-Eileanan Siar", "Scotland", "Eilean Siar"),
    ("GBR", "Western Isles", "Scotland", "Eilean Siar"),
    ("GBR", "Isle of Lewis", "Scotland", "Eilean Siar"),
    ("GBR", "Falkirk", "Scotland", "Falkirk"),
    ("GBR", "Fife", "Scotland", "Fife"),
    ("GBR", "Glasgow City", "Scotland", "Glasgow"),
    ("GBR", "Highland", "Scotland", "Highland"),
    ("GBR", "Inverclyde", "Scotland", "Inverclyde"),
    ("GBR", "Midlothian", "Scotland", "Midlothian"),
    ("GBR", "Moray", "Scotland", "Moray"),
    ("GBR", "North Ayrshire", "Scotland", "North Ayshire"),
    ("GBR", "North Lanarkshire", "Scotland", "North Lanarkshire"),
    ("GBR", "Orkney", "Scotland", "Orkney"),
    ("GBR", "Orkney Islands", "Scotland", "Orkney"),
    ("GBR", "Perth and Kinross", "Scotland", "Perthshire and Kinross"),
    ("GBR", "Renfrewshire", "Scotland", "Renfrewshire"),
    ("GBR", "Scottish Borders", "Scotland", "Scottish Borders"),
    ("GBR", "Shetland", "Scotland", "Shetland Islands"),
    ("GBR", "Shetland Islands", "Scotland", "Shetland Islands"),
    ("GBR", "South Ayrshire", "Scotland", "South Ayrshire"),
    ("GBR", "South Lanarkshire", "Scotland", "South Lanarkshire"),
    ("GBR", "Stirling", "Scotland", "Stirling"),
    ("GBR", "West Dunbartonshire", "Scotland", "West Dunbartonshire"),
    ("GBR", "West Lothian", "Scotland", "West Lothian"),
    # Ireland: counties as DAFM publishes them
    ("IRL", "Carlow", "", "Carlow"), ("IRL", "Cavan", "", "Cavan"), ("IRL", "Clare", "", "Clare"),
    ("IRL", "Cork", "", "Cork"), ("IRL", "Donegal", "", "Donegal"),
    ("IRL", "Dublin", "", "Dublin|Fingal|South Dublin|Dún Laoghaire–Rathdown"),
    ("IRL", "Galway", "", "Galway"), ("IRL", "Kerry", "", "Kerry"), ("IRL", "Kildare", "", "Kildare"),
    ("IRL", "Kilkenny", "", "Kilkenny"), ("IRL", "Laois", "", "Laoighis"), ("IRL", "Leitrim", "", "Leitrim"),
    ("IRL", "Limerick", "", "Limerick"), ("IRL", "Longford", "", "Longford"), ("IRL", "Louth", "", "Louth"),
    ("IRL", "Mayo", "", "Mayo"), ("IRL", "Meath", "", "Meath"), ("IRL", "Monaghan", "", "Monaghan"),
    ("IRL", "Offaly", "", "Offaly"), ("IRL", "Roscommon", "", "Roscommon"), ("IRL", "Sligo", "", "Sligo"),
    ("IRL", "Tipperary", "", "North Tipperary|South Tipperary"), ("IRL", "Waterford", "", "Waterford"),
    ("IRL", "Westmeath", "", "Westmeath"), ("IRL", "Wexford", "", "Wexford"), ("IRL", "Wicklow", "", "Wicklow"),
    # Finland: municipalities near the 2026 ASF area, placed at their region (maakunta)
    ("FIN", "Virolahti", "Kymenlaakso", "Kymenlaakso"), ("FIN", "Miehikkälä", "Kymenlaakso", "Kymenlaakso"),
    ("FIN", "Hamina", "Kymenlaakso", "Kymenlaakso"), ("FIN", "Kotka", "Kymenlaakso", "Kymenlaakso"),
    ("FIN", "Pyhtää", "Kymenlaakso", "Kymenlaakso"), ("FIN", "Kouvola", "Kymenlaakso", "Kymenlaakso"),
    ("FIN", "Lappeenranta", "South Karelia", "South Karelia"), ("FIN", "Luumäki", "South Karelia", "South Karelia"),
    ("FIN", "Imatra", "South Karelia", "South Karelia"), ("FIN", "Lemi", "South Karelia", "South Karelia"),
    ("FIN", "Taipalsaari", "South Karelia", "South Karelia"), ("FIN", "Savitaipale", "South Karelia", "South Karelia"),
    ("FIN", "Ruokolahti", "South Karelia", "South Karelia"), ("FIN", "Rautjärvi", "South Karelia", "South Karelia"),
    ("FIN", "Parikkala", "South Karelia", "South Karelia"), ("FIN", "Loviisa", "Uusimaa", "Uusimaa"),
    ("FIN", "Porvoo", "Uusimaa", "Uusimaa"),
]


def build_local(admin1):
    from shapely.geometry import shape
    from shapely.ops import unary_union
    by_name = {}
    for feat in admin1["features"]:
        p = feat["properties"]
        key = (NE_FIX.get(p.get("adm0_a3"), p.get("adm0_a3")), p.get("name"))
        by_name.setdefault(key, []).append(feat)
    out, missing = [], []
    nations = [("GBR", n, n, "*" + n) for n in ("England", "Scotland", "Wales", "Northern Ireland")]
    for iso3, published, nation, units in nations + LOCAL:
        feats = []
        if units.startswith("*"):   # a whole UK nation: every Natural Earth unit in it
            feats = [f for f in admin1["features"] if f["properties"].get("geonunit") == units[1:]
                     and f["properties"].get("adm0_a3") == "GBR"]
            units = "all %d units in %s" % (len(feats), units[1:])
        for u in ([] if feats else units.split("|")):
            got = by_name.get((iso3, u))
            if not got:
                missing.append((iso3, published, u))
            feats += got or []
        if not feats:
            continue
        if len(feats) == 1:
            p = feats[0]["properties"]
            lat, lon, method = p.get("latitude"), p.get("longitude"), "Natural Earth label point"
        else:
            geom = unary_union([shape(f["geometry"]).buffer(0) for f in feats])
            pt = geom.centroid if geom.contains(geom.centroid) else geom.representative_point()
            lat, lon, method = pt.y, pt.x, "centre of the union of %d Natural Earth units" % len(feats)
        out.append({"iso3": iso3, "name": published, "admin1": nation, "units": units,
                    "lat": r2(lat), "lon": r2(lon), "method": method})
    with open(os.path.join(HERE, "local_areas.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["iso3", "name", "admin1", "units", "lat", "lon", "method"])
        w.writeheader()
        w.writerows(out)
    print("local_areas.csv:", len(out), "missing units:", missing)
    return missing


if __name__ == "__main__":
    a0 = fetch(FILES["admin0"])
    a1 = fetch(FILES["admin1"])
    build_countries(a0)
    build_admin1(a1)
    miss = build_local(a1)
    sys.exit(1 if miss else 0)
