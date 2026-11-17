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
    """Mid-point of the VIS observations of the tile, and half their span, in years."""
    first = min(year(r["first_observation_date_time"]) for r in epoch_rows)
    last = max(year(r["last_observation_date_time"]) for r in epoch_rows)
    return (first + last) / 2, (last - first) / 2, sorted({r["release_name"] for r in epoch_rows})


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


def is_clean(e, tol):
    c = tol["clean"]
    plp = f(e["point_like_prob"])
    return (plp is not None and plp >= c["point_like_prob_min"]
            and e["flag_vis"] == str(c["flag_vis"])
            and e["det_quality_flag"] == str(c["det_quality_flag"])
            and e["spurious_flag"] in (str(c["spurious_flag"]), ""))


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
    cats = {"agree": [], "differ": [], "only_euclid": [], "only_ours": [], "duplicate_claim": [],
            "gaia_unmatched": [], "euclid_names_unknown_gaia": []}
    for gid, objs in theirs.items():
        if len(objs) > 1:
            cats["duplicate_claim"].append((gid, objs))
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
    """Euclid's own matches joined to Gaia rows, with the residual after proper motion."""
    gi = {g["source_id"]: g for g in gaia}
    out = []
    for e in euclid:
        g = gi.get(e["gaia_id"]) if e["gaia_id"] else None
        if g is None:
            continue
        ra, dec, had_pm = propagate(g, epoch)
        dx, dy = offset_mas(float(e["right_ascension"]), float(e["declination"]), ra, dec)
        rx, ry = offset_mas(float(e["right_ascension"]), float(e["declination"]),
                            float(g["ra"]), float(g["dec"]))
        out.append({"e": e, "g": g, "dx": dx, "dy": dy, "raw_dx": rx, "raw_dy": ry,
                    "had_pm": had_pm, "G": f(g["phot_g_mean_mag"])})
    return out


def position_check(prs, half_span, tol):
    clean = [p for p in prs if p["had_pm"] and is_clean(p["e"], tol)]
    if not clean:
        return {"n_clean": 0}, []
    mx, my = median([p["dx"] for p in clean]), median([p["dy"] for p in clean])
    bins = {}
    for p in clean:
        b = g_bin(p["G"], tol["g_bins"])
        if b:
            bins.setdefault(b, []).append(p)
    stats = {}
    for b, ps in bins.items():
        stats[b] = {"n": len(ps),
                    "sigma_ra_mas": robust_sigma([p["dx"] for p in ps]),
                    "sigma_dec_mas": robust_sigma([p["dy"] for p in ps]),
                    "raw_sigma_ra_mas": robust_sigma([p["raw_dx"] for p in ps]),
                    "raw_sigma_dec_mas": robust_sigma([p["raw_dy"] for p in ps])}
    outliers = []
    for p in clean:
        s = stats.get(g_bin(p["G"], tol["g_bins"]))
        if not s or s["n"] < tol["min_bin_count"] or not s["sigma_ra_mas"] or not s["sigma_dec_mas"]:
            continue
        # a high proper-motion star moves during the tile's observing span: allow for it
        pm = math.hypot(f(p["g"]["pmra"]), f(p["g"]["pmdec"]))
        ex = pm * half_span
        z = math.hypot((p["dx"] - mx) / math.hypot(s["sigma_ra_mas"], ex),
                       (p["dy"] - my) / math.hypot(s["sigma_dec_mas"], ex))
        p["pos_z"] = z
        if z > tol["position_outlier_sigma"]:
            outliers.append(p)
    return {"n_clean": len(clean), "median_ra_mas": mx, "median_dec_mas": my,
            "by_g_bin": dict(sorted(stats.items()))}, outliers


# ---------------------------------------------------------------- C3 brightness (colour_fit tier)

def vis_mag(e):
    fl = f(e["flux_vis_psf"])
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


def brightness_check(prs, tol):
    """Fit (VIS - G) against (BP - RP) on clean stars; the residual is the product."""
    cf = tol["colour_fit"]
    pts = []
    for p in prs:
        g, bp, rp, v = p["G"], f(p["g"]["phot_bp_mean_mag"]), f(p["g"]["phot_rp_mean_mag"]), vis_mag(p["e"])
        if None in (g, bp, rp, v) or not is_clean(p["e"], tol):
            continue
        p["bp_rp"], p["vis_minus_g"] = bp - rp, v - g
        pts.append(p)
    fit_set = [p for p in pts if cf["g_min"] <= p["G"] < cf["g_max"]
               and cf["bp_rp_min"] <= p["bp_rp"] <= cf["bp_rp_max"]]
    if len(fit_set) < cf["min_stars"]:
        return {"n_fit": len(fit_set), "fitted": False}, []
    use = fit_set
    for _ in range(cf["iterations"]):
        c = polyfit([p["bp_rp"] for p in use], [p["vis_minus_g"] for p in use], cf["degree"])
        res = [p["vis_minus_g"] - polyval(c, p["bp_rp"]) for p in fit_set]
        fit_sigma = robust_sigma(res)
        use = [p for p, r in zip(fit_set, res) if abs(r) <= cf["clip_sigma"] * fit_sigma]
    bins, outliers = {}, []
    for p in pts:
        if cf["bp_rp_min"] <= p["bp_rp"] <= cf["bp_rp_max"]:
            p["vis_resid"] = p["vis_minus_g"] - polyval(c, p["bp_rp"])
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
    return {"fitted": True, "n_fit": len(fit_set), "n_used": len(use), "coefficients": c,
            "fit_sigma_mag": fit_sigma, "by_g_bin": dict(sorted(stats.items()))}, outliers
