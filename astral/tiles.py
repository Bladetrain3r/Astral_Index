"""The list of Euclid tiles, and a deterministic spread-out sample of them."""
import math
from . import tap

QUERY = ("SELECT tile_index, release_name, processing_mode, ra, dec, first_observation_date_time, "
         "last_observation_date_time, reference_observation_date_time FROM dr1.mosaic_product "
         "WHERE instrument_name='VIS'")


def galactic_lat(ra, dec):
    """Galactic latitude in degrees (J2000 pole at RA 192.85948, Dec 27.12825)."""
    a, d = math.radians(ra), math.radians(dec)
    ap, dp = math.radians(192.85948), math.radians(27.12825)
    return math.degrees(math.asin(math.sin(d) * math.sin(dp) + math.cos(d) * math.cos(dp) * math.cos(a - ap)))


def all_tiles(snap, offline=False):
    """One row per tile: the VIS mosaic of the latest release, wide processing only."""
    rows = tap.query("euclid", QUERY, snap, "euclid_tile_index", offline)
    best = {}
    for r in rows:
        if r["processing_mode"] != "WIDE":
            continue
        k = r["tile_index"]
        if k not in best or (r["release_name"], r["reference_observation_date_time"]) > (
                best[k]["release_name"], best[k]["reference_observation_date_time"]):
            best[k] = r
    out = []
    for k in sorted(best, key=int):
        r = best[k]
        out.append({"tile_index": k, "release_name": r["release_name"], "ra": float(r["ra"]),
                    "dec": float(r["dec"]), "gal_lat": galactic_lat(float(r["ra"]), float(r["dec"])),
                    "reference_date": r["reference_observation_date_time"][:10]})
    return out


def sample(tiles, n, always=()):
    """Every k-th tile in tile-index order (which runs across the sky), plus any listed in `always`."""
    step = len(tiles) / n
    picked = {tiles[int(i * step)]["tile_index"] for i in range(n)} | set(map(str, always))
    return [t for t in tiles if t["tile_index"] in picked]
