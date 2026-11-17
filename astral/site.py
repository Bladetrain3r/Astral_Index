"""Assemble the static site: pages from `site/`, data from `data/`, provenance from the manifests.

    python -m astral.site [--out _site] [--snap snapshots]
"""
import argparse, csv, json, os, shutil, subprocess
from . import run

HERE = run.HERE
PILOT = "102018694"


def manifest(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [json.loads(l) for l in fh if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "_site"))
    ap.add_argument("--snap", default=os.path.join(HERE, "snapshots"))
    a = ap.parse_args()
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    shutil.copytree(os.path.join(HERE, "site"), a.out)
    with open(os.path.join(HERE, "data", "index", "tiles.csv")) as fh:
        tiles = [r["tile_index"] for r in csv.DictReader(fh)]
    os.makedirs(os.path.join(a.out, "data", "index"))
    shutil.copy(os.path.join(HERE, "data", "index", "tiles.csv"), os.path.join(a.out, "data", "index"))
    by_tail, n_src = {}, 0
    for t in tiles:
        src = os.path.join(HERE, "data", "tiles", t)
        dst = os.path.join(a.out, "data", "tiles", t)
        shutil.copytree(src, dst)
        snap = os.path.join(HERE, "fixtures", "pilot") if t == PILOT else os.path.join(a.snap, "tiles", t)
        keep = ("archive", "url", "query", "fetched_utc", "rows", "sha256", "file")
        with open(os.path.join(dst, "provenance.json"), "w") as fh:
            json.dump([{k: r[k] for k in keep} for r in manifest(os.path.join(snap, "MANIFEST.jsonl"))], fh)
        with open(os.path.join(src, "sources.csv")) as fh:
            for r in csv.DictReader(fh):
                by_tail.setdefault(r["gaia_source_id"][-2:], {})[r["gaia_source_id"]] = t
                n_src += 1
    with open(os.path.join(a.out, "data", "index", "sources.json"), "w") as fh:
        json.dump(by_tail, fh, separators=(",", ":"))
    idx = manifest(os.path.join(a.snap, "index", "MANIFEST.jsonl"))
    try:
        commit = subprocess.run(["git", "-C", HERE, "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True).stdout.strip()
    except OSError:
        commit = ""
    tiles_in_release = None
    if idx:
        from . import tiles as tl
        tiles_in_release = len(tl.all_tiles(os.path.join(a.snap, "index"), offline=True))
    with open(os.path.join(a.out, "data", "index", "build.json"), "w") as fh:
        json.dump({"commit": commit, "tiles": len(tiles), "sources": n_src,
                   "tiles_in_release": tiles_in_release}, fh)
    print(f"site: {len(tiles)} tiles, {n_src} sources -> {a.out}")


if __name__ == "__main__":
    main()
