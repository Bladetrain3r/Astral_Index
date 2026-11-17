"""The three checks for one tile. Pure functions over rows; no network, no clock."""
import math
from datetime import datetime

MAS = 3.6e6            # degrees to milliarcseconds
AB_ZP_UJY = 23.9       # AB magnitude of a 1 microjansky source (definition of the AB system)


def f(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def year(ts):
    d = datetime.fromisoformat(ts.replace("Z", ""))
    start = datetime(d.year, 1, 1)
    return d.year + (d - start).total_seconds() / (datetime(d.year + 1, 1, 1) - start).total_seconds()


def tile_epoch(epoch_rows):
    """The epoch of the tile's catalogue coordinates, and half the span of its observations.

    Euclid documents the coordinate epoch as the tile's reference observation date ("Epoch of source
    coordinates in the DR1 MER catalogue are hidden", Euclid known issues). With several VIS mosaics
    for one tile, the one from the latest release is used.
    """
    row = sorted(epoch_rows, key=lambda r: (r["release_name"], r["reference_observation_date_time"]))[-1]
    first = min(year(r["first_observation_date_time"]) for r in epoch_rows)
    last = max(year(r["last_observation_date_time"]) for r in epoch_rows)
    return year(row["reference_observation_date_time"]), (last - first) / 2, row["release_name"]


def propagate(g, epoch):
    """Gaia position moved linearly by its proper motion to `epoch`. Returns ra, dec, had_pm."""
    ra, dec = float(g["ra"]), float(g["dec"])
    pmra, pmdec = f(g["pmra"]), f(g["pmdec"])
    if pmra is None or pmdec is None:
        return ra, dec, False
    dt = epoch - float(g["ref_epoch"])
    return (ra + pmra * dt / MAS / math.cos(math.radians(dec)), dec + pmdec * dt / MAS, True)


def offset_mas(ra_e, dec_e, ra_g, dec_g):
    """Euclid minus Gaia, tangent-plane approximation, in mas (RA term times cos Dec)."""
    return ((ra_e - ra_g) * math.cos(math.radians(dec_g)) * MAS, (dec_e - dec_g) * MAS)


def median(v):
    s = sorted(v)
    n = len(s)
    return (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2) if n else None


def robust_sigma(v):
    """1.4826 x median absolute deviation: the scatter, ignoring outliers."""
    if len(v) < 2:
        return None
    m = median(v)
    return 1.4826 * median([abs(x - m) for x in v])


def g_bin(g, bins):
    if g is None:
        return None
    for lo, hi in bins:
        if lo <= g < hi:
            return f"{lo:g}-{hi:g}"
    return None


def tier(e, tol):
    """Quality tier of a Euclid source: A (no flags), B (no bad bits), C (not used)."""
    try:
        d, v = int(e["det_quality_flag"] or 0), int(e["flag_vis"] or 0)
    except ValueError:
        return "C"
    if e.get("spurious_flag") not in ("0", "", None):
        return "C"
    if d == 0 and v == 0:
        return "A"
    return "B" if (d | v) & tol["bad_flag_bits"] == 0 else "C"


def usable(e, tol):
    return tier(e, tol) in ("A", "B")


def star_like(p):
    """Gaia gives it a proper motion and Euclid does not call it extended.

    Gaia sources without a proper motion that Euclid sees as extended are mostly compact galaxies;
    they are counted as their own class and kept out of the brightness statistics for stars.
    """
    plp = f(p["e"]["point_like_prob"])
    return p["had_pm"] and not (plp is not None and plp < 0.5)


def slope(xs, ys):
    """Least-squares slope of y on x about the medians, ignoring points beyond 5 sigma in y."""
    if len(xs) < 20:
        return None
    mx, my, s = median(xs), median(ys), robust_sigma(ys)
    k = [(x - mx, y - my) for x, y in zip(xs, ys) if s and abs(y - my) < 5 * s]
    den = sum(a * a for a, _ in k)
    return sum(a * b for a, b in k) / den if den else None


# ---------------------------------------------------------------- C1 match audit

def our_match(euclid, gaia, epoch, radius_arcsec):
    """For each Gaia source, the nearest Euclid source within the radius (grid search)."""
    cell = radius_arcsec / 3600.0
    grid = {}
    for i, e in enumerate(euclid):
        ra, dec = float(e["right_ascension"]), float(e["declination"])
        grid.setdefault((int(math.floor(dec / cell)),
                         int(math.floor(ra * math.cos(math.radians(dec)) / cell))), []).append(i)
    out = {}
    for g in gaia:
        ra, dec, _ = propagate(g, epoch)
        cd = math.cos(math.radians(dec))
        ky, kx = int(math.floor(dec / cell)), int(math.floor(ra * cd / cell))
        best = None
        for dy in (-1, 0, 1):
            for dx in (-2, -1, 0, 1, 2):     # cos(dec) differs slightly per source: look wider in RA
                for i in grid.get((ky + dy, kx + dx), ()):
                    e = euclid[i]
                    x, y = offset_mas(float(e["right_ascension"]), float(e["declination"]), ra, dec)
                    d = math.hypot(x, y) / 1000.0
                    if d <= radius_arcsec and (best is None or d < best[1]):
                        best = (i, d)
        if best:
            out[g["source_id"]] = (euclid[best[0]]["object_id"], best[1])
    return out


def match_audit(euclid, gaia, epoch, box, tol):
    ra0, ra1, d0, d1 = box
    m = tol["edge_margin_arcsec"] / 3600.0
    mra = m / math.cos(math.radians((d0 + d1) / 2))
    def inside(ra, dec):
        return ra0 + mra <= ra <= ra1 - mra and d0 + m <= dec <= d1 - m
    ours = our_match(euclid, gaia, epoch, tol["match_radius_arcsec"])
    gaia_ids = {g["source_id"] for g in gaia}
    theirs = {}                                   # gaia source_id -> [euclid object_id, ...]
    for e in euclid:
        if e["gaia_id"]:
            theirs.setdefault(e["gaia_id"], []).append(e["object_id"])
    cats = {"agree": [], "differ": [], "only_euclid": [], "only_ours": [], "duplicate_vis_nir": [],
            "duplicate_other": [], "gaia_unmatched": [], "euclid_names_unknown_gaia": []}
    vis = {e["object_id"]: e.get("vis_det", "1") for e in euclid}
    for gid, objs in theirs.items():
        if len(objs) > 1:
            # usual case: one detection on the VIS image plus one on the near-infrared stack
            n_vis = sum(1 for o in objs if vis[o] == "1")
            kind = "duplicate_vis_nir" if n_vis == 1 else "duplicate_other"
            cats[kind].append((gid, objs))
        if gid not in gaia_ids:
            cats["euclid_names_unknown_gaia"].append((gid, objs))
    for g in gaia:
        gid = g["source_id"]
        ra, dec, _ = propagate(g, epoch)
        if not inside(ra, dec):
            continue                              # edge: the neighbour tile may hold the match
        t, o = theirs.get(gid), ours.get(gid)
        if t and o:
            cats["agree" if o[0] in t else "differ"].append((gid, t, o[0]))
        elif t:
            cats["only_euclid"].append((gid, t))
        elif o:
            cats["only_ours"].append((gid, o[0], round(o[1], 4)))
        else:
            cats["gaia_unmatched"].append((gid, f(g["phot_g_mean_mag"])))
    return cats


# ---------------------------------------------------------------- C2 position residual

def pairs(euclid, gaia, epoch):
    """Euclid's own matches (VIS detections) joined to Gaia rows, with the residual after proper motion."""
    gi = {g["source_id"]: g for g in gaia}
    out = []
    for e in euclid:
        g = gi.get(e["gaia_id"]) if e["gaia_id"] else None
        if g is None or e.get("vis_det", "1") != "1":
            continue                 # near-infrared-only detections have no VIS position or flux
        ra, dec, had_pm = propagate(g, epoch)
        dx, dy = offset_mas(float(e["right_ascension"]), float(e["declination"]), ra, dec)
        rx, ry = offset_mas(float(e["right_ascension"]), float(e["declination"]),
                            float(g["ra"]), float(g["dec"]))
        dt = epoch - float(g["ref_epoch"])
        # Gaia's own uncertainty at the tile epoch: position error plus proper-motion error times years
        gsx = math.hypot(f(g["ra_error"]) or 0.0, (f(g["pmra_error"]) or 0.0) * dt)
        gsy = math.hypot(f(g["dec_error"]) or 0.0, (f(g["pmdec_error"]) or 0.0) * dt)
        out.append({"e": e, "g": g, "dx": dx, "dy": dy, "raw_dx": rx, "raw_dy": ry, "gsx": gsx, "gsy": gsy,
                    "had_pm": had_pm, "G": f(g["phot_g_mean_mag"])})
    return out


def position_check(prs, tol):
    use = [p for p in prs if p["had_pm"] and usable(p["e"], tol)]
    if not use:
        return {"n_used": 0}, []
    mx, my = median([p["dx"] for p in use]), median([p["dy"] for p in use])
    bins = {}
    for p in use:
        b = g_bin(p["G"], tol["g_bins"])
        if b:
            bins.setdefault(b, []).append(p)
    stats = {}
    for b, ps in bins.items():
        sx, sy = robust_sigma([p["dx"] for p in ps]), robust_sigma([p["dy"] for p in ps])
        gx, gy = median([p["gsx"] ** 2 for p in ps]), median([p["gsy"] ** 2 for p in ps])
        fl = tol["euclid_floor_min_mas"]
        stats[b] = {"n": len(ps), "sigma_ra_mas": sx, "sigma_dec_mas": sy,
                    "raw_sigma_ra_mas": robust_sigma([p["raw_dx"] for p in ps]),
                    "raw_sigma_dec_mas": robust_sigma([p["raw_dy"] for p in ps]),
                    "gaia_sigma_ra_mas": math.sqrt(gx), "gaia_sigma_dec_mas": math.sqrt(gy),
                    # what is left once Gaia's stated uncertainty is taken out: Euclid's share
                    "euclid_sigma_ra_mas": math.sqrt(max((sx or 0) ** 2 - gx, fl ** 2)),
                    "euclid_sigma_dec_mas": math.sqrt(max((sy or 0) ** 2 - gy, fl ** 2))}
    outliers = []
    for p in use:
        s = stats.get(g_bin(p["G"], tol["g_bins"]))
        if not s or s["n"] < tol["min_bin_count"]:
            continue
        # each star is judged against Euclid's share for its brightness plus its own Gaia uncertainty
        z = math.hypot((p["dx"] - mx) / math.hypot(s["euclid_sigma_ra_mas"], p["gsx"]),
                       (p["dy"] - my) / math.hypot(s["euclid_sigma_dec_mas"], p["gsy"]))
        p["pos_z"] = z
        if z > tol["position_outlier_sigma"]:
            outliers.append(p)
    by_tier = {}
    for t in ("A", "B"):
        ps = [p for p in use if tier(p["e"], tol) == t]
        by_tier[t] = {"n": len(ps), "sigma_ra_mas": robust_sigma([p["dx"] for p in ps]),
                      "sigma_dec_mas": robust_sigma([p["dy"] for p in ps])}
    # If the catalogue epoch we assumed is right, the residual does not depend on proper motion.
    # The slope of residual against proper motion is the epoch error in years.
    ep = {"ra_year": slope([f(p["g"]["pmra"]) for p in use], [p["dx"] for p in use]),
          "dec_year": slope([f(p["g"]["pmdec"]) for p in use], [p["dy"] for p in use])}
    return {"n_used": len(use), "median_ra_mas": mx, "median_dec_mas": my, "by_tier": by_tier,
            "implied_epoch_offset": ep, "by_g_bin": dict(sorted(stats.items()))}, outliers


# ---------------------------------------------------------------- C3 brightness (colour_fit tier)

def vis_mag(e, col="flux_vis_psf"):
    """AB magnitude from a flux in microjansky (zero point 23.9, Euclid MER photometry cookbook)."""
    fl = f(e.get(col))
    return AB_ZP_UJY - 2.5 * math.log10(fl) if fl and fl > 0 else None


def _solve(a, b):
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(m[r][i]))
        m[i], m[p] = m[p], m[i]
        for r in range(n):
            if r != i:
                k = m[r][i] / m[i][i]
                m[r] = [x - k * y for x, y in zip(m[r], m[i])]
    return [m[i][n] / m[i][i] for i in range(n)]


def polyfit(xs, ys, deg):
    a = [[sum(x ** (i + j) for x in xs) for j in range(deg + 1)] for i in range(deg + 1)]
    b = [sum(y * x ** i for x, y in zip(xs, ys)) for i in range(deg + 1)]
    return _solve(a, b)


def polyval(c, x):
    return sum(ci * x ** i for i, ci in enumerate(c))


def _colour_fit(prs, tol, col):
    """Fit (VIS - G) against (BP - RP) on usable stars for one Euclid flux column."""
    cf = tol["colour_fit"]
    pts = []
    for p in prs:
        g, bp, rp, v = p["G"], f(p["g"]["phot_bp_mean_mag"]), f(p["g"]["phot_rp_mean_mag"]), vis_mag(p["e"], col)
        if None in (g, bp, rp, v) or not usable(p["e"], tol) or not star_like(p):
            continue
        if cf["bp_rp_min"] <= bp - rp <= cf["bp_rp_max"]:
            pts.append((p, bp - rp, v - g))
    fit_set = [t for t in pts if cf["g_min"] <= t[0]["G"] < cf["g_max"]]
    if len(fit_set) < cf["min_stars"]:
        return None, pts, len(fit_set), 0, None
    use = fit_set
    for _ in range(cf["iterations"]):
        c = polyfit([t[1] for t in use], [t[2] for t in use], cf["degree"])
        res = [t[2] - polyval(c, t[1]) for t in fit_set]
        sig = robust_sigma(res)
        use = [t for t, r in zip(fit_set, res) if abs(r) <= cf["clip_sigma"] * sig]
    return c, pts, len(fit_set), len(use), sig


def brightness_check(prs, tol):
    """Tier `colour_fit`: the residual about a fitted colour relation is the product.

    The relation absorbs any constant offset (aperture losses included), so this tier tests
    star-to-star consistency, not the absolute zero point.
    """
    col = tol["brightness_flux"]
    c, pts, n_fit, n_used, sig = _colour_fit(prs, tol, col)
    also = {}
    for other in tol.get("brightness_flux_also", []):
        oc, _, on, _, osig = _colour_fit(prs, tol, other)
        also[other] = {"n_fit": on, "fit_sigma_mag": osig,
                       "offset_at_bp_rp_1_mag": polyval(oc, 1.0) if oc else None}
    if c is None:
        return {"fitted": False, "flux_column": col, "n_fit": n_fit, "other_flux_columns": also}, []
    bins, outliers = {}, []
    for p, colour, vmg in pts:
        p["bp_rp"], p["vis_resid"] = colour, vmg - polyval(c, colour)
        b = g_bin(p["G"], tol["g_bins"])
        if b:
            bins.setdefault(b, []).append(p)
    stats = {}
    for b, ps in bins.items():
        s = robust_sigma([p["vis_resid"] for p in ps])
        stats[b] = {"n": len(ps), "median_mag": median([p["vis_resid"] for p in ps]), "sigma_mag": s}
        if len(ps) < tol["min_bin_count"] or not s:
            continue
        for p in ps:
            p["vis_z"] = (p["vis_resid"] - stats[b]["median_mag"]) / s
            if abs(p["vis_z"]) > tol["brightness_outlier_sigma"]:
                outliers.append(p)
    return {"fitted": True, "flux_column": col, "n_fit": n_fit, "n_used": n_used, "coefficients": c,
            "offset_at_bp_rp_1_mag": polyval(c, 1.0), "fit_sigma_mag": sig,
            "other_flux_columns": also, "by_g_bin": dict(sorted(stats.items()))}, outliers
