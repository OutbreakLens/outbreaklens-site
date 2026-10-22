# outbreaklens-site

Source for outbreaklens.com: the static site generator (`build_site.py`), brand assets and the built site in `website/`.

Pushes to `main` deploy `website/` to the Cloudflare Pages project `outbreaklens` through the GitHub Actions workflow in `.github/workflows/deploy.yml`, once the `CLOUDFLARE_API_TOKEN` secret is set in the repository settings.

OutbreakLens is an educational summary of public data, made in a personal capacity. It is not veterinary, trade or official advice, and it is not affiliated with or endorsed by any government body.
