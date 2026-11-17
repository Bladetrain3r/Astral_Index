"""Run many tiles, politely and resumably, and write the per-tile index.

    python -m astral.batch --sample 100 [--max 200] [--snap DIR] [--out DIR] [--offline]

A tile whose summary already exists is skipped unless --redo. A tile that fails is recorded in
`data/index/failed.csv` with the reason and the run moves on (a tile with an image but no catalogue
rows lands there too); five archive failures in a row stop the run.
"""
import argparse, csv, json, os, sys
from . import run, tiles, tap

HERE = run.HERE
PILOT = 102018694
COLS = ["tile_index", "release_name", "ra", "dec", "gal_lat", "reference_date", "epoch_year",
        "gaia_in_box", "pairs", "not_star_like", "usable", "agree", "differ", "only_euclid", "only_ours",
        "duplicate_vis_nir", "duplicate_other", "gaia_unmatched", "median_ra_mas", "median_dec_mas",
        "sigma_ra_mas", "sigma_dec_mas", "epoch_offset_ra_year", "epoch_offset_dec_year",
        "brightness_fitted", "brightness_sigma_mag", "brightness_offset_mag", "psf_sigma_mag",
        "outliers_position", "outliers_brightness"]


def index_row(t, s):
    c, a, p, b = s["counts"], s["c1_match_audit"], s["c2_position"], s["c3_brightness_colour_fit"]
    tiers = p.get("by_tier", {})
    n = sum(v["n"] for v in tiers.values()) or 1
    def pooled(key):      # tier-weighted scatter over usable stars
        vals = [(v["n"], v[key]) for v in tiers.values() if v.get(key)]
        return (sum(w * x * x for w, x in vals) / sum(w for w, _ in vals)) ** 0.5 if vals else None
    eo = p.get("implied_epoch_offset", {})
    return [t["tile_index"], t["release_name"], round(t["ra"], 5), round(t["dec"], 5), round(t["gal_lat"], 2),
            t["reference_date"], s["epoch_year"], c["gaia_in_box"], c["pairs"], c["pairs_not_star_like"], p.get("n_used", 0),
            a["agree"], a["differ"], a["only_euclid"], a["only_ours"], a["duplicate_vis_nir"],
            a["duplicate_other"], a["gaia_unmatched"], p.get("median_ra_mas"), p.get("median_dec_mas"),
            pooled("sigma_ra_mas"), pooled("sigma_dec_mas"), eo.get("ra_year"), eo.get("dec_year"),
            int(b["fitted"]), b.get("fit_sigma_mag"), b.get("offset_at_bp_rp_1_mag"),
            b["other_flux_columns"].get("flux_vis_psf", {}).get("fit_sigma_mag"),
            s["outliers"]["position"], s["outliers"]["brightness"]]


def write_index(todo, out, index_dir):
    os.makedirs(index_dir, exist_ok=True)
    rows = []
    for t in todo:
        p = os.path.join(out, t["tile_index"], "summary.json")
        if os.path.exists(p):
            with open(p) as fh:
                rows.append(index_row(t, json.load(fh)))
    with open(os.path.join(index_dir, "tiles.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLS)
        for r in rows:
            w.writerow(["" if x is None else (round(x, 4) if isinstance(x, float) else x) for x in r])
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=100)
    ap.add_argument("--max", type=int, default=10 ** 9, help="most tiles to fetch in this run")
    ap.add_argument("--snap", default=os.path.join(HERE, "snapshots"))
    ap.add_argument("--out", default=os.path.join(HERE, "data", "tiles"))
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    index_dir = os.path.join(HERE, "data", "index")
    todo = tiles.sample(tiles.all_tiles(os.path.join(a.snap, "index"), a.offline), a.sample, always=[PILOT])
    failed, streak, done = [], 0, 0
    for t in todo:
        k = t["tile_index"]
        if os.path.exists(os.path.join(a.out, k, "summary.json")) and not a.redo:
            continue
        if done >= a.max:
            break
        snap = os.path.join(HERE, "fixtures", "pilot") if int(k) == PILOT else os.path.join(a.snap, "tiles", k)
        try:
            s = run.run_tile(k, snap, a.out, a.offline)
            streak, done = 0, done + 1
            print(k, "ok", s["c2_position"].get("n_used"), "usable", flush=True)
        except (tap.TapError, ValueError, KeyError, ZeroDivisionError) as e:
            failed.append((k, type(e).__name__, str(e)[:200].replace("\n", " ")))
            if isinstance(e, tap.TapError):       # an empty tile is a fact about the tile, not an outage
                streak += 1
            print(k, "FAILED", failed[-1][1:], flush=True)
            if streak >= 5:
                print("five failures in a row: stopping", flush=True)
                break
    os.makedirs(index_dir, exist_ok=True)
    with open(os.path.join(index_dir, "failed.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["tile_index", "error", "detail"])
        w.writerows(failed)
    n = write_index(todo, a.out, index_dir)
    print(f"index: {n} of {len(todo)} tiles; {len(failed)} failed this run", flush=True)
    return 1 if streak >= 5 else 0


if __name__ == "__main__":
    sys.exit(main())
