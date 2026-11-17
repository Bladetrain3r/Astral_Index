# Gates

*The build order. A gate passes when its evidence exists in the repo and its test is green. `SPEC.md` is
the what; this is the order. Status as of 2026-11-17.*

| Gate | Passes when | Evidence | Status |
|---|---|---|---|
| **G1 Sources** | Flag meanings, magnitude zero point, saturation, tile geometry, access limits and licence text are read from the official docs and recorded with quotes | `SOURCES.md` Part D | passed; open items listed there |
| **G2 One tile** | C1 to C3 (`colour_fit` tier) run on tile 102018694 and the committed results rebuild byte-for-byte from the committed snapshots, offline | `fixtures/pilot/`, `data/tiles/102018694/`, `tests/test_checks.py` | passed |
| **G2b Spectrum tier** | Decide, with counts, whether the `xp_synth` tier is worth building: how many stars have a Gaia spectrum and a usable Euclid VIS flux | `LOG.md` R2 | blocked: Gaia spectrum service down on 2026-11-17 |
| **G3 Hundred tiles** | 100 tiles spread over the footprint (by Galactic latitude and by observation date); tolerances frozen; a global colour relation fitted; 50 outliers looked at by eye and the look recorded | `data/tiles/*/`, `data/index/tiles.csv`, `snapshots/`, `LOG.md` R2 | passed except the by-eye look: 94 tiles, method v1 frozen, global relation fitted, outliers broken down by context instead (`LOG.md` R3) |
| **G4 Site** | Sky map, tile page and source page live on Pages for the G3 tiles; every figure links to its query and snapshot hash | `site/`, `.github/workflows/pages.yml` | built and browser-tested locally; not deployed. **v1 is done here** |
| **G5 Footprint** | All tiles of the release, run as a resumable background job with a per-run cap | `data/index/tiles.csv` complete | open |
| **G6 First change event** | The watcher sees Gaia DR4 (2 December 2026); the rerun is published beside the DR3 results with a per-tile and per-source diff | `astral/watch.py`, `data/watch/state.json`, `reports/` | watcher built; rerun and diff open |

## Rules that hold at every gate

- Results are a pure function of snapshots and `tolerances.json`. No clock, no network in the checks.
- A snapshot is never edited. A re-fetch for a new release goes in a new directory.
- Tolerances change only with a `LOG.md` entry saying why; after G3 a change is a new method version.
- The site says "disagrees by X". It does not say "error" or "discovery".
- One connection per archive, a pause between queries, bounded retries.

## What needs Ziggy

| When | What |
|---|---|
| G4 | Merge the branch to `main` and turn on GitHub Pages (Settings → Pages → source "GitHub Actions") |
| G3 | Look at the outlier list on the live site and say whether it reads as useful |
| G5 | Per-source tables and bulk snapshots go to Release assets: a session or workflow that may create releases |
| G6 | Say go on the DR4 rerun once the watcher reports the new schema |

No accounts or API keys are needed: both archives are used anonymously.
