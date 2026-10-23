# outbreaklens-site

Source for outbreaklens.com: the static site generator (`build_site.py`), brand assets and the built site in `website/`.

Pushes to `main` deploy `website/` to the Cloudflare Pages project `outbreaklens` through the GitHub Actions workflow in `.github/workflows/deploy.yml`, once the `CLOUDFLARE_API_TOKEN` secret is set in the repository settings.

OutbreakLens is an educational summary of public data, made in a personal capacity. It is not veterinary, trade or official advice, and it is not affiliated with or endorsed by any government body.

## Building the site

`python3 -I build_site.py --prelaunch` regenerates `website/` from the templates in the script, `hero_dots.json` and `brand/final/`. Commit the result and push: the workflow deploys it.

## Live data: map, Numbers and open data

`pipeline/` reads official animal-disease data (WOAH WAHIS, EU ADIS, FAO EMPRES-i, GOV.UK, DAFM, Ruokavirasto) and writes open files to `pipeline/data/`. Run `python3 pipeline/run.py`, then build the site: `build_site.py` copies the files to `website/assets/data/` and builds `map.html`, `analytics.html` (Numbers) and `data.html`. See `pipeline/README.md` and `pipeline/notes.md`.

The map uses MapLibre GL JS (from cdnjs, pinned with SRI) and OpenFreeMap's Positron style, which is built on OpenStreetMap data. It needs no key or registration. Keep the credit to OpenFreeMap, OpenMapTiles and OpenStreetMap contributors visible: MapLibre shows it on the map and the Sources block repeats it. Map, Numbers and Downloads sit under Data in the navigation and share a sub-navigation. The country tables on the Numbers page come from `pipeline/data/tables.json`.

The home page leads with the same map and "Reports by country" table as `map.html`: one shared block in `build_site.py`, so the two cannot drift apart. Below them sit the latest episode and newsletter issue, a link to the shorts and one line on sources. Episodes are listed in `EPISODES` in `build_site.py`. The newest also fills the Weekly page, with its chapters. Without `pipeline/data` the build reuses the files already in `website/assets/data`.

