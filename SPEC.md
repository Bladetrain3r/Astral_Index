# Astral Index — specification

*Draft 1, 2026-11-17. Written from Ziggy's brief of the same day ("stars first") and the checks recorded in
`SOURCES.md`. This file is the what; `SOURCES.md` is where the data comes from and what was actually read.
Items marked **Ziggy** are his to decide; everything else is the builder's judgment and can change.*

## Purpose

A public, reproducible record of where two star catalogues disagree: Gaia DR3 and Euclid DR1, on the stars both
see. The visible part is a static explorer site. Every number on it can be re-derived from kept query
snapshots by anyone who clones the repo.

Cross-matching catalogues is already solved (CDS XMatch, the archives' own neighbour tables, TOPCAT). This
project publishes the layer after the match: the residuals, the sources that disagree beyond the measured
scatter, and how both change when a catalogue is re-released.

Not a catalogue, not a mirror, and not a discovery claim. An outlier here is a flag for a human to look at.

## Scope of v1

| In | Out (later) |
|---|---|
| Gaia DR3 × Euclid DR1, Euclid Wide Survey footprint | Galaxies, redshifts, Euclid spectra |
| Stars and other point sources that Gaia sees (G ≲ 21) | Hubble and JWST (v2, deep fields) |
| Three checks: match audit, position, VIS brightness | Variability over time, exoplanets (v3) |
| Change tracking across catalogue releases | Euclid Deep fields |

## The three checks

**C1. Match audit.** Euclid's star catalogue already names a Gaia counterpart for each matched source
(`gaia_id`, `gaia_match_quality`). We redo the match independently and compare:

- Our match: Gaia position moved by its proper motion to the Euclid tile's observation date, then nearest
  Euclid source within a radius set at G2.
- Reported: agree; Euclid names a different Gaia source; Euclid names none and we find one; we find none and
  Euclid names one; two Euclid sources claiming one Gaia source; Gaia sources in the tile with no Euclid source.

**C2. Position residual.** Euclid position minus Gaia position propagated to the tile's observation date.

- Per tile: median offset in RA and Dec, and scatter by brightness bin. This is the calibration map.
- Per source: residual divided by the measured scatter for its brightness bin. Large values go on the
  outlier list.
- Two limits, stated on the site. Euclid's astrometry is calibrated on Gaia, so the per-tile offset measures
  calibration, not independent agreement. The Euclid catalogue carries no per-source position error, so
  "beyond the errors" means beyond the scatter we measure, not beyond a published uncertainty.

**C3. Brightness residual (Euclid VIS band).** Two tiers, labelled on every figure:

- `xp_synth`: Gaia's low-resolution spectrum turned into a predicted VIS brightness with GaiaXPy's
  `Euclid_VIS` filter, compared with Euclid's measured `flux_vis_psf`. Only for stars that have a Gaia
  spectrum (roughly G < 17.65). Risk: many of these are flagged or saturated in Euclid; G2 measures how many
  survive.
- `colour_fit`: for fainter stars, a relation from Gaia G and BP−RP to VIS brightness, fitted by us on clean
  stars and published with its coefficients. Lower confidence; the residual scatter is the product.

## Change tracking

Catalogue releases are immutable, so there is no daily series. A scheduled watcher checks, cheaply:

- the release list and table schemas of both archives (new schema, new columns, changed row counts);
- the two "known issues" pages.

On a change it opens a report; a human-approved rerun produces a new set of results beside the old, and the
site shows the diff per tile and per source. Known events: Gaia DR4 on 2 December 2026; full Euclid DR1 on
16 June 2027.

## Unit of work and scale

- The unit is one Euclid tile (about 0.5° × 0.5°). The archive lists 9,376 VIS tiles in release `DR1_R2`.
- Pilot tile 102018694: 121,655 Euclid sources, 1,647 with a Gaia match, observed 2024-02-28 to 2024-09-03.
- Two queries per tile (one per archive). Full footprint is about 19,000 queries; at one query every few
  seconds this is a resumable job of a day or two, run once per release.
- Rough size: 1,647 × 9,376 ≈ 15 million matched rows if the pilot tile is typical (it will not be near the
  Galactic plane). Too big for git.

## What is kept, and where

- In the repo: per-tile aggregates, outlier lists, the fitted relations, tolerances, the query text, and a
  manifest of every raw response (URL, query, UTC time, SHA-256).
- Outside the repo (Release assets): per-source tables and raw snapshots.
- A hash-chained ledger of published results, as in Four Corners.

## The site

Static pages, no server. Three views:

1. **Sky map.** Aladin Lite with survey imagery, tiles coloured by a chosen residual. Click a tile.
2. **Tile page.** Offset, scatter by brightness, match-audit counts, outlier table, the exact queries.
3. **Source page.** Both catalogues' values side by side, the residuals, flags, links out to the Gaia and
   Euclid archives and SIMBAD.

Search by Gaia source ID, Euclid object ID, or coordinates. Downloadable CSV on every table.

## Rules for talking to the archives

- One connection per archive, a pause between queries, bounded retries with backoff, stop on repeated 5xx.
- Never re-fetch what is already in the manifest for the same release.
- Read only public, anonymous endpoints. No scraping of pages that have an API.

## Build order (gates, to be expanded in `GATES.md`)

| Gate | Passes when |
|---|---|
| G1 Sources | Flag meanings, the Euclid magnitude zero point and saturation limit, and rate guidance are read from the docs and recorded |
| G2 One tile | C1 to C3 run end to end on the pilot tile, offline-reproducible from snapshots; survival counts for `xp_synth` known |
| G3 Hundred tiles | 100 tiles spread across the footprint; tolerances frozen; outlier list reviewed by eye |
| G4 Site | The three views live on Pages for the 100 tiles |
| G5 Footprint | All tiles, as a background job |
| G6 First change event | Rerun against Gaia DR4 and publish the diff |

G4 is "done" for v1. G5 and G6 are accretion.

## Decisions for Ziggy

1. **Non-commercial data.** Gaia and Euclid data are both CC BY-NC, and ESA's terms require authorisation
   for any use that "directly or indirectly generates a financial gain". Proposal: code stays MIT; published
   data files carry CC BY-NC and the credit lines; no funding or sponsor links on this repo or site.
2. **Gaia DR4 lands in two weeks.** Proposal: build on DR3 now and treat DR4 as the first change event (G6).
   The alternative is to wait and build on DR4 only, which loses the diff.
3. **Per-source tables as Release assets,** not in git. Needs a session with a token, as in Four Corners.
4. **Outlier wording.** Proposal: the site never says "error" or "discovery", only "disagrees by X".
