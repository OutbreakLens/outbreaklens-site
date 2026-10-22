#!/usr/bin/env python3
"""
run.py: run every adapter, clean and link the rows, and write the public files to data/.

    python3 run.py                    # live run: all sources, last 12 weeks
    python3 run.py --offline          # no network: stored snapshots and saved copies only
    python3 run.py --only wahis,adis  # a subset of adapters, written to cache/partial-run/ (not data/)
    python3 run.py --weeks 8          # a shorter window

Each adapter returns status live, fallback (a stored copy was used), failed or stub. One failing
source never stops the run. data/run_status.json records what happened, and the block between the
run-status markers in notes.md is rewritten.
"""
from __future__ import annotations
import argparse, collections, csv, datetime as dt, json, os, re, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from adapters.common import Context, COLUMNS, now_utc   # noqa: E402
from adapters import wahis, empres_i, adis, govuk_bluetongue, govuk_birdflu, ie_dafm_bluetongue, fi_ruokavirasto_asf  # noqa: E402
import clean, outputs   # noqa: E402

ADAPTERS = [("wahis", wahis), ("govuk_bluetongue", govuk_bluetongue), ("govuk_birdflu", govuk_birdflu),
            ("adis", adis), ("empres_i", empres_i), ("ie_dafm", ie_dafm_bluetongue), ("fi_ruokavirasto", fi_ruokavirasto_asf)]


def main(argv=None):
    ap = argparse.ArgumentParser(description="OutbreakLens live data pipeline")
    ap.add_argument("--offline", action="store_true", help="use stored snapshots and saved copies only")
    ap.add_argument("--only", default="", help="comma-separated adapter names")
    ap.add_argument("--weeks", type=int, default=12)
    ap.add_argument("--outdir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--wahis-max-fetch", type=int, default=450, help="cap on new WAHIS report requests per run")
    args = ap.parse_args(argv)
    if args.only and args.outdir == os.path.join(ROOT, "data"):
        # a partial run must never overwrite the public files with a subset
        args.outdir = os.path.join(ROOT, "cache", "partial-run")
        print("--only: writing to %s, not data/" % args.outdir)
    os.makedirs(args.outdir, exist_ok=True)
    ctx = Context(weeks=args.weeks, offline=args.offline, wahis_max_fetch=args.wahis_max_fetch)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    generated = now_utc()
    print("OutbreakLens pipeline: window %s to %s (%d weeks)%s" % (ctx.window_start, ctx.today, ctx.weeks,
                                                                   ", offline" if ctx.offline else ""))
    results = []
    for key, mod in ADAPTERS:
        if only and key not in only:
            continue
        t = time.time()
        try:
            res = mod.fetch(ctx)
        except Exception as e:   # an adapter bug must not stop the others
            from adapters.common import SourceResult
            res = SourceResult(key, key, "", status="failed", error="adapter error: %r" % e, fetched_at=now_utc())
        print("  %-17s %-8s %5d rows  %4.0fs  %s" % (key, res.status, len(res.rows), time.time() - t, res.error[:90]))
        results.append(res)

    rows = [r for res in results for r in res.rows]
    rows, issues = clean.validate(rows, ctx.today)
    rows, dups = clean.dedupe(rows)
    wres = next((r for r in results if r.key == "wahis"), None)
    rules, edges = clean.link(rows, wres.extras.get("outbreak_points", []) if wres else [])
    rows, held = clean.hold(rows)
    if held:   # editorial rule: never published automatically; kept locally for the editor to review
        hdir = os.path.join(ROOT, "cache", "held")
        os.makedirs(hdir, exist_ok=True)
        with open(os.path.join(hdir, "held-%s.csv" % ctx.today.isoformat()), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, COLUMNS)
            w.writeheader()
            w.writerows(clean.public(r) for r in held)
    counts = outputs.write_tables(args.outdir, rows)
    outputs.write_aggregates(args.outdir, ctx, results, generated)
    outputs.write_latest(args.outdir, ctx, results, rows, generated, counts)
    mapc = outputs.write_map(args.outdir, rows, results, edges)

    status = {"generated_at": generated, "window": [ctx.window_start.isoformat(), ctx.today.isoformat()],
              "sources": [r.summary() for r in results],
              "rows_by_source": dict(collections.Counter(r["source"] for r in rows)),
              "rows_by_category": counts, "rows_total": len(rows), "duplicates_removed": dups,
              "same_as_links": rules, "rows_held_for_review": len(held),
              "validation_issues": [{"event_id": a, "issue": b} for a, b in issues][:200],
              "validation_issue_count": len(issues), "map_features_by_source": dict(mapc)}
    with open(os.path.join(args.outdir, "run_status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1)
    if args.outdir == os.path.join(ROOT, "data"):
        _notes(status)
    print("rows: %d (%s)" % (len(rows), ", ".join("%s %d" % kv for kv in counts.items())))
    print("links: %s; held: %d; validation issues: %d; map features: %d" % (
        rules, len(held), len(issues), sum(mapc.values())))
    return status


def _notes(status):
    """Rewrite the generated block in notes.md with this run's results."""
    path = os.path.join(ROOT, "notes.md")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = ["Last run: %s. Window %s to %s." % (status["generated_at"], *status["window"]), "",
             "| Source | Status | Rows | Updated by source | Note |", "|---|---|---|---|---|"]
    for s in status["sources"]:
        note = (s["error"] or "; ".join(n for n in s["notes"] if n))[:160].replace("|", "/")
        label = {"govuk_bluetongue": "GOV.UK bluetongue", "govuk_birdflu": "GOV.UK bird flu"}.get(s["key"], s["name"])
        lines.append("| %s | %s | %d | %s | %s |" % (label, s["status"], s["rows"], (s["source_updated"] or "")[:10], note))
    lines += ["", "Rows by category: %s." % ", ".join("%s %d" % kv for kv in status["rows_by_category"].items()),
              "Links added (same_as): %s." % (", ".join("%s %d" % kv for kv in status["same_as_links"].items()) or "none"),
              "Rows held for editorial review: %d. Validation issues: %d." % (
                  status["rows_held_for_review"], status["validation_issue_count"])]
    block = "<!-- run-status:start -->\n" + "\n".join(lines) + "\n<!-- run-status:end -->"
    text = re.sub(r"<!-- run-status:start -->.*?<!-- run-status:end -->", lambda m: block, text, flags=re.S)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
