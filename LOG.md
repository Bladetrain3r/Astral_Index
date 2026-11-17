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
