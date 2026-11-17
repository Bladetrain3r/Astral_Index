# Build log

One block per round: what was tried, what came out, what was decided. Newest last.

## R1, 2026-11-17: sources probed, pilot tile end to end (G1 mostly, G2 passed)

**Did.** Probed both TAP services anonymously; read the Euclid DR1 documentation and known issues, the Gaia
quota page and the ESA terms (`SOURCES.md` Part D). Built the stdlib pipeline (`astral/`) and ran it on Euclid
tile 102018694 against Gaia DR3. Snapshots in `fixtures/pilot/`, results in `data/tiles/102018694/`.

**Pilot numbers** (one tile, Galactic latitude about −34°; not yet a result about the survey):

| Check | Outcome |
|---|---|
| Match audit | 1,563 agree, 0 where Euclid and we pick different Gaia sources, 0 only-Euclid, 20 where we find a match Euclid does not name, 77 Gaia sources with no Euclid source within 0.5 arcsec, 66 Gaia sources claimed by two Euclid sources |
| The 66 double claims | All are one VIS detection plus one near-infrared-only detection of the same bright star (median G 15.2, median separation 0.08 arcsec) |
| Position, 1,235 usable stars | Median offset +0.7 mas RA, −0.7 mas Dec. Scatter per axis 5 to 7 mas for G < 19, 11 mas for G 20 to 21.5. Before applying Gaia proper motions the scatter is 25 to 56 mas |
| Epoch audit | Implied epoch error +0.03 yr (RA) and +0.13 yr (Dec) against the documented reference epoch 2024.160. The mid-point of the observations fits slightly worse |
| Brightness, 456 stars in the fit | Scatter about the colour relation 0.028 mag with the 2-FWHM aperture flux, 0.026 with the total flux, 0.047 with the PSF flux |
| Outliers at 5 sigma | 39 position, 79 brightness (104 distinct sources) |

**What the outliers are, as far as the catalogues themselves say.**

- Position: 14 of 39 outliers have Gaia RUWE above 1.4, against 24 of the other 1,196. Gaia already doubts
  the single-star fit for a third of them.
- Brightness: 74 of 79 are brighter in Euclid than the relation predicts. 56 of those 74 have no Gaia proper
  motion and their median Euclid point-like probability is 0.0. My reading, not verified by eye: these are
  mostly compact galaxies that Gaia catalogued, where Euclid's aperture collects more light than Gaia saw.
- The faintest bin (G 20 to 21.5) sits 0.10 mag bright as a whole. Not explained yet; the fit only uses
  G 18 to 20, and Gaia colours are noisy that faint.

**Decided.**

- Coordinate epoch is the tile's reference observation date (documented, and it fits better).
- Quality tiers A and B from the flag bits. Using only stars with no flags at all would leave 197 stars, none
  brighter than G = 18; tier B adds 1,038 with no worse scatter.
- Aperture flux for the colour relation; PSF flux reported beside it. The PSF scatter being 1.7 times larger
  agrees with the known PSF issue in the Euclid notes.
- Near-infrared-only detections are left out of C2 and C3.
- The Euclid candidate query bounds the flux above; 30,000 of 32,000 rows were NaN fluxes. This loses one
  of 21 audit cases (a source with no VIS flux).
- Snapshot hashes cover the stored gzip file, so `sha256sum` checks them.

**Open.** What `gaia_match_quality` measures; which release is "DR1-Foundation"; whether the 77 unmatched
Gaia sources are near bright stars or tile gaps; the faint-bin offset; the `xp_synth` tier (G2b).

## R2, 2026-11-17: a hundred tiles, the site, the watcher (G3 partly, G4 built)

**Did.** Drew every 95th tile from the 9,547 wide tiles the archive lists (101 with the pilot), ran them
(`astral/batch.py`), and kept every raw response under `snapshots/` (29 MB) so CI rebuilds all results
offline. Built the static explorer (`site/`, assembled by `astral/site.py`), the release watcher
(`astral/watch.py`, state in `data/watch/state.json`) and three workflows (tests, Pages, daily watch).

**Sample.** 94 tiles processed; Galactic latitude 20° to 75° either side; coordinate epochs December 2023
to May 2025. 7 sampled tiles have a VIS image in the archive but no rows in `dr1.mer_catalogue_wide_survey`
(`data/index/failed.csv`): all 5 sampled tiles whose only release is `DR1_R1`, and 2 `DR1_R2` tiles near
RA 53, Dec −26 to −30. Why is not established; the two R2 tiles are close to the Fornax deep field. 4 of
the 94 are edge tiles with under 100 usable stars.

**Numbers over the 94 tiles** (108,007 Gaia–Euclid pairs, 83,196 usable stars):

| Check | Outcome |
|---|---|
| Match audit | 108,756 agree; 0 where Euclid and we link different sources; 9 Euclid-only; 1,495 where we find a source Euclid does not link; 9,180 Gaia sources with no Euclid source in 0.5 arcsec; 4,593 VIS-plus-infrared double claims; 7 other double claims |
| Position scatter per axis, per tile | 6.0 to 9.0 mas, median 7.2 |
| Tile median offset | up to 9 mas in either axis; medians −1.9 mas RA, −0.3 mas Dec |
| Implied epoch error | medians −0.06 yr (RA), −0.03 yr (Dec); extremes −0.30 to +0.39 yr |
| Brightness scatter about the colour relation | median 0.030 mag (aperture flux); PSF flux 1.62 times larger in the median tile |
| Outliers at 5 sigma | 3,271 position (3.9% of usable), 2,185 brightness |

**What the first outlier list was made of.** Before the change below there were 6,970 brightness outliers.
About 70% were sources Euclid classes as extended or that Gaia gives no proper motion, and nine in ten
were brighter in Euclid: compact galaxies in the Gaia catalogue, as in the pilot. Of sources off in both
position and brightness, 637 of 1,009 have a poor Gaia single-star fit (RUWE above 1.4).

**Decided.**

- Brightness statistics and outliers are for star-like sources only: Gaia gives a proper motion and Euclid
  does not call it extended. The rest (15,892 pairs) are counted per tile as `not_star_like`.
- Snapshots for these tiles live in git. The full footprint will not (about 2.5 GB at this rate).
- A tile with an image but no catalogue rows is recorded, not treated as an outage.

**Not done, and why.**

- `xp_synth` tier (G2b): GaiaXPy installs in a clean virtual environment and lists `Euclid_VIS`, but the Gaia
  spectrum service (`gea.esac.esa.int/data-server`) answered "Unable to create connection to database" and
  then timed out, three times. About 240 stars per tile would qualify. Retry another day.
- The by-eye look at 50 outliers (part of G3) and freezing the tolerances. A 3.9% position outlier rate at
  "5 sigma" says the tails are heavy, most likely blends admitted by tier B; that needs images to judge.
- A relation fitted over all tiles instead of per tile.
- Pages is not live: the workflow deploys from `main`, and Pages must be switched on in the repo settings.
- Aladin Lite on the tile page loads on a button press; it could not be exercised from the build container.

## R3, 2026-11-17: what the outliers are; method v1 frozen (G3)

**Did.** Measured the position-outlier rate against properties of the star, changed the position test,
fitted one colour relation over all tiles, and compared Euclid's three flux measures between hemispheres.

**Position outliers, before the change** (40 tiles, 35,958 usable stars, 3.9% flagged):

| Property of the star | Share flagged |
|---|---|
| Gaia RUWE above 1.4 | 42.6% (against 2.8% without) |
| Another Gaia source within 3 arcsec | 23.8% (against 3.5%) |
| Another bright Euclid source within 3 arcsec | 12.9% (against 3.7%) |
| Euclid "blended" bit set | 4.6% (against 2.3%) |
| Tier A (no Euclid flags) | 2.1% |

**Change 1: each star is judged against its own Gaia uncertainty.** The old test divided by the scatter of
a one-magnitude bin. Gaia's uncertainty at the tile epoch (position error plus proper-motion error times
about 8 years) grows from 0.3 mas at G < 16 to about 10 mas at G > 20.5, so it varies a lot inside a bin.
Now: expected scatter = Euclid's share for the bin (measured scatter with the median Gaia part removed,
floor 3 mas) plus the star's own Gaia part; bins are half a magnitude. In the pilot tile Euclid's share
comes out between 4 and 8 mas per axis at every brightness.

**After the change** (94 tiles, 82,230 stars with a position test): 2,823 flagged, 3.4%. Tier A 1.4%;
"blended" bit clear 1.6%; RUWE high 35.6%; Gaia neighbour 22.7%. By context: 859 poor Gaia fit, 243 a
neighbour, 49 Gaia variable, 1,668 with nothing in either catalogue to hint why.

The rate is still far above what a Gaussian gives at 5 sigma. I have not established why. Candidates, none
tested: blends below Gaia's resolution; stars whose proper motion over Gaia's 34 months differs from their
motion over 8 years (long-period binaries); Gaia uncertainties that are too small for faint stars; Euclid
centroid errors with long tails. The by-eye look that G3 asked for is not done: the Euclid cutout service
did not answer a guessed request, and each outlier links to ESASky instead.

**Change 2: Euclid's total flux, not the 2-FWHM aperture.** Offset of each flux from Gaia G at BP−RP = 1,
median over tiles:

| Euclid flux | North (23 tiles) | South (66 tiles) | Difference |
|---|---|---|---|
| 2-FWHM aperture | 0.236 | 0.084 | 0.153 mag |
| PSF | −0.016 | −0.032 | 0.016 mag |
| Total (Kron) | −0.116 | −0.115 | −0.001 mag |

The aperture flux differs by 0.15 mag between hemispheres; the total flux does not. My guess, not checked
against the documentation: the aperture size follows the seeing of the ground-based images, which come
from different telescopes north and south. The total flux is also the one the Euclid cookbook calls the
reference measurement.

**Global relation** (`data/index/colour_relation.json`): 33,211 stars in 89 tiles, scatter 0.026 mag.
Tile offsets from it: standard deviation 2.6 mmag, range −5.8 to +8.9 mmag, north and south medians within
1 mmag. Euclid's VIS zero point, seen through Gaia, is uniform to a few thousandths of a magnitude over
this sample. This is relative: the relation is fitted to the same data.

**Brightness outliers after both changes:** 2,924 over 94 tiles.

**Frozen as method v1** (`tolerances.json`): tiers A and B; half-magnitude bins; match radius 0.5 arcsec;
neighbour radius 3 arcsec; 5-sigma cuts; Euclid floor 3 mas; total flux; fit range G 18 to 20.

**Still blocked.** Gaia spectrum service: HTTP 500 again several hours later.
