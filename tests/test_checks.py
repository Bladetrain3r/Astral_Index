import json, os, sys, tempfile, unittest, filecmp
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from astral import checks, run, tap

PILOT = "102018694"


def gaia(sid, ra, dec, pmra="", pmdec="", g="19.0"):
    return {"source_id": sid, "ra": repr(ra), "dec": repr(dec), "ref_epoch": "2016.0", "pmra": str(pmra),
            "pmdec": str(pmdec), "phot_g_mean_mag": g}


def euclid(oid, ra, dec, gaia_id=""):
    return {"object_id": oid, "right_ascension": repr(ra), "declination": repr(dec), "gaia_id": gaia_id}


class Maths(unittest.TestCase):
    def test_propagate_moves_by_pm_times_years(self):
        ra, dec, had = checks.propagate(gaia("1", 10.0, 0.0, 100.0, -50.0), 2026.0)
        self.assertTrue(had)
        self.assertAlmostEqual((ra - 10.0) * checks.MAS, 1000.0, places=3)
        self.assertAlmostEqual(dec * checks.MAS, -500.0, places=3)

    def test_propagate_ra_uses_cos_dec(self):
        ra, _, _ = checks.propagate(gaia("1", 10.0, 60.0, 100.0, 0.0), 2026.0)
        self.assertAlmostEqual((ra - 10.0) * checks.MAS, 2000.0, places=1)

    def test_no_proper_motion_is_reported(self):
        self.assertEqual(checks.propagate(gaia("1", 10.0, 5.0), 2026.0), (10.0, 5.0, False))

    def test_offset_round_trips_propagation(self):
        g = gaia("1", 80.0, -51.0, 7.0, 14.0)
        ra, dec, _ = checks.propagate(g, 2024.4)
        dx, dy = checks.offset_mas(ra, dec, 80.0, -51.0)
        self.assertAlmostEqual(dx, 7.0 * 8.4, places=2)
        self.assertAlmostEqual(dy, 14.0 * 8.4, places=2)

    def test_robust_sigma_ignores_an_outlier(self):
        v = [-1.0, -0.5, 0.0, 0.5, 1.0, 1000.0]
        self.assertLess(checks.robust_sigma(v), 2.0)

    def test_polyfit_recovers_a_quadratic(self):
        xs = [i / 10 for i in range(30)]
        c = checks.polyfit(xs, [0.4 - 0.5 * x + 0.1 * x * x for x in xs], 2)
        for got, want in zip(c, (0.4, -0.5, 0.1)):
            self.assertAlmostEqual(got, want, places=6)

    def test_year(self):
        self.assertAlmostEqual(checks.year("2024-07-02T00:00:00"), 2024.5, places=2)


class Audit(unittest.TestCase):
    tol = {"edge_margin_arcsec": 0.0, "match_radius_arcsec": 0.5}
    box = (9.0, 11.0, -1.0, 1.0)

    def test_categories(self):
        a = 1 / 3600.0
        g = [gaia("A", 10.0, 0.0), gaia("B", 10.1, 0.0), gaia("C", 10.2, 0.0), gaia("D", 10.3, 0.0),
             gaia("E", 10.4, 0.0)]
        e = [euclid("a", 10.0 + 0.1 * a, 0.0, "A"),            # agree
             euclid("b1", 10.1 + 0.1 * a, 0.0), euclid("b2", 10.1 + 5 * a, 0.0, "B"),   # differ
             euclid("c", 10.2 + 5 * a, 0.0, "C"),              # only Euclid: too far for us
             euclid("d", 10.3, 0.0),                           # only ours
             euclid("x", 10.9, 0.0, "A")]                      # second claim on A
        r = checks.match_audit(e, g, 2016.0, self.box, self.tol)
        got = {k: len(v) for k, v in r.items()}
        self.assertEqual(got, {"agree": 1, "differ": 1, "only_euclid": 1, "only_ours": 1,
                               "duplicate_vis_nir": 0, "duplicate_other": 1, "gaia_unmatched": 1, "euclid_names_unknown_gaia": 0})

    def test_match_follows_proper_motion(self):
        g = [gaia("A", 10.0, 0.0, 0.0, 1000.0)]               # 1 arcsec per year
        e = [euclid("a", 10.0, 8.0 / 3600.0)]
        self.assertEqual(checks.our_match(e, g, 2016.0, 0.5), {})
        self.assertIn("A", checks.our_match(e, g, 2024.0, 0.5))


class Reproduce(unittest.TestCase):
    """The committed pilot results are exactly what the committed snapshots give, offline."""
    def test_pilot_tile_is_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            run.run_tile(PILOT, os.path.join(HERE, "fixtures", "pilot"), d, offline=True)
            for name in ("summary.json", "sources.csv", "outliers.csv", "match_audit.json"):
                self.assertTrue(filecmp.cmp(os.path.join(d, PILOT, name),
                                            os.path.join(HERE, "data", "tiles", PILOT, name), shallow=False),
                                name + " differs from the committed result")

    def test_tampered_snapshot_is_refused(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(os.path.join(HERE, "fixtures", "pilot"), os.path.join(d, "s"))
            name = [n for n in os.listdir(os.path.join(d, "s")) if n.startswith("euclid_epoch")][0]
            with open(os.path.join(d, "s", name), "ab") as fh:
                fh.write(b"x")
            with self.assertRaises(tap.TapError):
                run.run_tile(PILOT, os.path.join(d, "s"), os.path.join(d, "o"), offline=True)


class Watch(unittest.TestCase):
    def test_new_schema_is_reported_and_outage_is_not(self):
        from astral import watch
        old = {"gaia_schemas": ["gaiadr3"], "euclid_releases": ["DR1_R2 | 2"], "cols": {"count": 1, "sha256": "a"}}
        new = {"gaia_schemas": ["gaiadr3", "gaiadr4"], "euclid_releases": {"unreachable": "URLError"},
               "cols": {"count": 2, "sha256": "b"}}
        lines = watch.diff(old, new)
        self.assertEqual(len(lines), 2)
        self.assertIn("new `gaiadr4`", lines[1])
        self.assertEqual(watch.diff(old, old), [])


if __name__ == "__main__":
    unittest.main()
