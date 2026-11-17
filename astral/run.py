"""Run the checks for one tile and write its results.

    python -m astral.run TILE [--snap DIR] [--out DIR] [--offline]

Results are a pure function of the snapshots and tolerances.json: run it twice, get the same bytes.
"""
import argparse, csv, json, os
from . import fetch, checks

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def r(x, n=3):
    return round(x, n) if isinstance(x, float) else x


def rounded(o, n=4):
    if isinstance(o, dict):
        return {k: rounded(v, n) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [rounded(v, n) for v in o]
    return r(o, n)


def run_tile(tile, snap, out, offline=False, tol_path=None):
    with open(tol_path or os.path.join(HERE, "tolerances.json")) as fh:
        tol = json.load(fh)
    euclid, epoch_rows, gaia, box = fetch.tile(tile, tol, snap, offline)
    epoch, half_span, releases = checks.tile_epoch(epoch_rows)

    audit = checks.match_audit(euclid, gaia, epoch, box, tol)
    prs = checks.pairs(euclid, gaia, epoch)
    pos, pos_out = checks.position_check(prs, half_span, tol)
    bri, bri_out = checks.brightness_check(prs, tol)

    summary = {
        "tile_index": int(tile),
        "catalogues": {"gaia": "gaiadr3.gaia_source", "euclid": "dr1.mer_catalogue_wide_survey",
                       "euclid_releases": releases},
        "box_deg": {"ra_min": box[0], "ra_max": box[1], "dec_min": box[2], "dec_max": box[3]},
        "epoch_year": epoch, "epoch_half_span_year": half_span,
        "counts": {"euclid_candidates": len(euclid), "gaia_in_box": len(gaia),
                   "euclid_with_gaia_id": sum(1 for e in euclid if e["gaia_id"]),
                   "pairs": len(prs),
                   "pairs_clean": sum(1 for p in prs if checks.is_clean(p["e"], tol)),
                   "pairs_with_gaia_spectrum": sum(1 for p in prs if p["g"]["has_xp_continuous"] == "true"),
                   "pairs_clean_with_gaia_spectrum": sum(
                       1 for p in prs if p["g"]["has_xp_continuous"] == "true" and checks.is_clean(p["e"], tol))},
        "c1_match_audit": {k: len(v) for k, v in audit.items()},
        "c2_position": pos,
        "c3_brightness_colour_fit": bri,
        "outliers": {"position": len(pos_out), "brightness": len(bri_out)},
        "tolerances": {k: v for k, v in tol.items() if not k.startswith("_")},
    }
    d = os.path.join(out, str(tile))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "summary.json"), "w") as fh:
        json.dump(rounded(summary), fh, indent=1, sort_keys=True)
        fh.write("\n")

    cols = ["gaia_source_id", "euclid_object_id", "g_mag", "bp_rp", "ra_euclid", "dec_euclid",
            "d_ra_mas", "d_dec_mas", "raw_d_ra_mas", "raw_d_dec_mas", "pos_z", "vis_mag",
            "vis_resid_mag", "vis_z", "clean", "point_like_prob", "flag_vis", "det_quality_flag",
            "gaia_match_quality", "pmra", "pmdec", "ruwe", "gaia_variable", "has_gaia_spectrum"]
    def row(p):
        e, g = p["e"], p["g"]
        v = checks.vis_mag(e)
        return [g["source_id"], e["object_id"], r(p["G"]), r(p.get("bp_rp")), e["right_ascension"],
                e["declination"], r(p["dx"], 2), r(p["dy"], 2), r(p["raw_dx"], 2), r(p["raw_dy"], 2),
                r(p.get("pos_z"), 2), r(v), r(p.get("vis_resid")), r(p.get("vis_z"), 2),
                int(checks.is_clean(e, tol)), e["point_like_prob"], e["flag_vis"], e["det_quality_flag"],
                e["gaia_match_quality"], g["pmra"], g["pmdec"], g["ruwe"], g["phot_variable_flag"],
                g["has_xp_continuous"]]
    def write(name, ps):
        with open(os.path.join(d, name), "w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(cols)
            for p in sorted(ps, key=lambda p: int(p["g"]["source_id"])):
                w.writerow(["" if x is None else x for x in row(p)])
    write("sources.csv", prs)
    seen, both = set(), []
    for p in pos_out + bri_out:
        if id(p) not in seen:
            seen.add(id(p)); both.append(p)
    write("outliers.csv", both)
    with open(os.path.join(d, "match_audit.json"), "w") as fh:
        json.dump({k: sorted(v, key=str) for k, v in audit.items() if k != "agree"}, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tile")
    ap.add_argument("--snap", default=os.path.join(HERE, "snapshots"))
    ap.add_argument("--out", default=os.path.join(HERE, "data", "tiles"))
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    s = run_tile(a.tile, a.snap, a.out, a.offline)
    print(json.dumps(rounded({k: s[k] for k in ("counts", "c1_match_audit", "c2_position",
                                                "c3_brightness_colour_fit", "outliers")}), indent=1))
