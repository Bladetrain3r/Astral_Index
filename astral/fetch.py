"""Fetch what one Euclid tile needs: Euclid candidates, the tile's observation dates, Gaia box."""
import math
from . import tap

EUCLID_COLS = ("object_id, right_ascension, declination, flux_vis_psf, fluxerr_vis_psf, "
               "point_like_prob, point_like_flag, flag_vis, det_quality_flag, spurious_flag, "
               "blended_prob, deblended_flag, binary_flag, variable_flag, vis_det, "
               "gaia_id, gaia_match_quality, tile_index")
GAIA_COLS = ("source_id, ra, dec, ref_epoch, pmra, pmdec, ra_error, dec_error, pmra_error, "
             "pmdec_error, parallax, phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag, ruwe, "
             "astrometric_params_solved, has_xp_continuous, phot_variable_flag")
GAIA_ROW_LIMIT = 50000   # the archive's declared hard limit for one query


def euclid_tile(tile, tol, snap, offline=False):
    q = (f"SELECT {EUCLID_COLS} FROM dr1.mer_catalogue_wide_survey WHERE tile_index={int(tile)} "
         f"AND (gaia_id IS NOT NULL OR flux_vis_psf > {tol['candidate_flux_vis_ujy']})")
    return tap.query("euclid", q, snap, f"euclid_tile_{tile}", offline)


def euclid_epoch(tile, snap, offline=False):
    q = ("SELECT tile_index, release_name, first_observation_date_time, last_observation_date_time, "
         "reference_observation_date_time FROM dr1.mosaic_product "
         f"WHERE tile_index={int(tile)} AND instrument_name='VIS'")
    return tap.query("euclid", q, snap, f"euclid_epoch_{tile}", offline)


def bounds(rows):
    ra = [float(r["right_ascension"]) for r in rows]
    de = [float(r["declination"]) for r in rows]
    if max(ra) - min(ra) > 180:
        raise ValueError("tile crosses RA=0; not handled yet")
    return min(ra), max(ra), min(de), max(de)


def gaia_box(tile, box, tol, snap, offline=False, _part=""):
    """All Gaia DR3 sources in the box (plus a margin). Splits the box if the row limit is hit."""
    ra0, ra1, d0, d1 = box
    m = tol["gaia_box_margin_arcsec"] / 3600.0 if not _part else 0.0
    mra = m / max(0.01, math.cos(math.radians((d0 + d1) / 2)))
    ra0, ra1, d0, d1 = ra0 - mra, ra1 + mra, d0 - m, d1 + m
    q = (f"SELECT {GAIA_COLS} FROM gaiadr3.gaia_source WHERE ra >= {ra0!r} AND ra < {ra1!r} "
         f"AND dec >= {d0!r} AND dec < {d1!r}")
    rows = tap.query("gaia", q, snap, f"gaia_box_{tile}{_part}", offline)
    if len(rows) < GAIA_ROW_LIMIT:
        return rows
    mid = (d0 + d1) / 2          # truncated: split in Dec and fetch both halves
    return (gaia_box(tile, (ra0, ra1, d0, mid), tol, snap, offline, _part + "a") +
            gaia_box(tile, (ra0, ra1, mid, d1), tol, snap, offline, _part + "b"))


def tile(tile_index, tol, snap, offline=False):
    e = euclid_tile(tile_index, tol, snap, offline)
    ep = euclid_epoch(tile_index, snap, offline)
    if not e:
        raise ValueError(f"tile {tile_index}: no Euclid rows")
    box = bounds(e)
    g = gaia_box(tile_index, box, tol, snap, offline)
    return e, ep, g, box
