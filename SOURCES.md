# Sources

*Checked from the build environment on 2026-11-17. "Confirmed" means read from a live response or an official
page that day. Anything else is marked "not confirmed". The pilot tile's raw responses are kept in
`fixtures/pilot/` with URL, query, time and SHA-256. Parts A and B record the first probe; where Part D
(the documentation) or `LOG.md` (the pilot run) say something different, they are the later reading.*

## Summary

| Source | Role in v1 | Access | Licence | Status |
|---|---|---|---|---|
| Gaia DR3 (ESA Gaia Archive) | Reference positions, proper motions, G/BP/RP, spectra flag | TAP, anonymous | CC BY-NC 3.0 IGO | Confirmed, queried |
| Euclid DR1 (ESA Euclid Science Archive) | Star positions, VIS flux, Euclid's own Gaia match, tile dates | TAP, anonymous | CC BY-NC 3.0 IGO | Confirmed, queried |
| GaiaXPy 2.1.5 | Predicted VIS brightness from Gaia spectra | Python package | BSD-3-Clause | `Euclid_VIS` filter listed; not run |
| Aladin Lite | Sky viewer on the site | JS from npm CDN | LGPL-3.0-or-later | npm copy reachable; CDS host not |
| CDS XMatch / VizieR TAP | Independent match oracle (optional) | HTTP | not read | **Unreachable from here** |

## What the checks changed (read first)

1. **Euclid already ships a Gaia match.** `gaia_id` and `gaia_match_quality` are columns of the star
   catalogue. So the match is something to audit, not something to build from nothing (SPEC check C1).
2. **Both datasets are non-commercial.** See Licences. This rules out funding links unless ESA authorises.
3. **No per-source position error and no per-source date in the Euclid catalogue.** Dates come per tile from
   `dr1.mosaic_product`. Position uncertainty has to be measured from the scatter.
4. **The Gaia-spectrum brightness check has a narrow but usable window.** In the pilot tile Gaia spectra
   stop at G ≈ 17 to 18. Only 264 of 1,647 Gaia-matched sources have both Euclid flags zero, and none of
   those is brighter than G = 18. Once the flag bits were read (Part D), 238 stars with a Gaia spectrum turn
   out to carry only harmless bits (blended, bright-star mask) and no saturation bit.
5. **Proper-motion propagation visibly works.** Five pilot stars: raw Euclid−Gaia offsets of 30 to 160 mas
   shrink to 5 to 15 mas for the four unflagged ones (40 mas for the bright G = 14.6 star). Five stars is a
   smoke test, not a result.
6. **Gaia DR4 is dated 2 December 2026, about 12:00 CET.** No `gaiadr4` schema in the archive yet.
7. **Release naming differs.** The web pages say "DR1-Foundation"; the archive's `dr1.data_release` table
   lists `DR1_R1` and `DR1_R2`. Which label maps to Foundation is not confirmed.
8. **The Euclid archive's ADQL rejects `CASE WHEN`.** Use `GROUP BY` on the flag columns instead.

## Hosts unreachable from this environment

`cdsxmatch.cds.unistra.fr` (connection reset), `cdsxmatch.u-strasbg.fr` (503), `tapvizier.cds.unistra.fr`
(no response), `aladin.cds.unistra.fr/AladinLite/api/v3/...` (404 on the paths tried). None was worked around.
v1 does not depend on any of them.

---

# Part A: Gaia DR3

- TAP base: `https://gea.esac.esa.int/tap-server/tap` (`/sync`, `/async`, `/tables`, `/capabilities`,
  `/availability`). Availability: "service is accepting queries".
- Limits declared in `/capabilities`: output 50,000 rows (default and hard), execution 3,600 s, job
  retention 129,600 s, upload 100,000,000 bytes. Whether anonymous async jobs get a higher row limit, and
  whether anonymous upload works, are not confirmed.
- No numeric request-rate limit was found on the pages read. Not confirmed either way.
- Schemas present: `gaiadr1`, `gaiadr2`, `gaiaedr3`, `gaiadr3`, `gaiafpr`, `external`. No `gaiadr4`.

Tables and columns used:

| Table | Columns | Note |
|---|---|---|
| `gaiadr3.gaia_source` | `source_id, ra, dec, ref_epoch, pmra, pmdec, ra_error, dec_error, pmra_error, pmdec_error, parallax, phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag, ruwe, has_xp_continuous` | `ref_epoch` is 2016.0 |
| `gaiadr3.synthetic_photometry_gspc` | Johnson, SDSS and other standard bands | No Euclid band; not used |

Gaia spectra themselves are not a TAP table; they come through the archive's DataLink service or GaiaXPy.
The exact call and its limits are not confirmed.

Test queries run (all HTTP 200, about 1 to 2 s, sync):

- Five rows by `source_id IN (...)`.
- Cone of radius 0.25° at (80.1, −51.2), counts by magnitude and `has_xp_continuous`:

| G bin | with spectrum | without |
|---|---|---|
| 8 to 14 | 69 | 0 |
| 15 | 70 | 1 |
| 16 | 109 | 2 |
| 17 | 72 | 49 |
| 18 | 0 | 185 |
| 19 | 1 | 265 |
| 20 | 0 | 383 |
| 21+ | 0 | 62 |

Release dates (page `https://www.cosmos.esa.int/web/gaia/release`): DR4 "based on 66 months of data",
2 December 2026. DR4 overview: `https://www.cosmos.esa.int/web/gaia/data-release-4`.

# Part B: Euclid DR1

- TAP base: `https://eas.esac.esa.int/tap-server/tap`. Availability true.
- Limits declared: execution 3,600 s, retention 259,200 s, upload 100,000,000 bytes. No output row limit is
  declared. No request-rate limit found. Not confirmed either way.
- Schemas: `dr1`, `q1`, `ivoa`. Release table `dr1.data_release` lists `DR1_R1`, `DR1_R2` (purpose
  `DATA_RELEASE`) plus three on-the-fly sets. Release dates in that table are empty.
- Release page: `https://www.cosmos.esa.int/web/euclid/data-release-dr1`. DR1-Foundation 12 November 2026;
  DR1 16 June 2027. Known issues, contents and data model are linked from it; none read yet (G1).
- Also listed by ESA: Euclid Data Space, `euclid.dataspace.esa.int`. Not checked.

Tables and columns used:

| Table | Columns | Note |
|---|---|---|
| `dr1.mer_catalogue_wide_survey` (478 columns) | `object_id, right_ascension, declination, flux_vis_psf, fluxerr_vis_psf` (µJy), `point_like_prob, point_like_flag, flag_vis, det_quality_flag, spurious_flag, blended_prob, gaia_id, gaia_match_quality, tile_index` | Positions are SExtractor barycentres. `right_ascension_psf_fitting` was empty in the rows sampled |
| `dr1.mosaic_product` | `tile_index, release_name, instrument_name, first_observation_date_time, last_observation_date_time, reference_observation_date_time` | The only observation dates found for catalogue sources |

Not yet read from the documentation (G1): the bit meanings of `flag_vis` and `det_quality_flag`; the scale
and direction of `gaia_match_quality`; which Gaia release `gaia_id` refers to; the VIS saturation limit; the
zero point for turning µJy into a magnitude.

Test queries run (all HTTP 200, under 2 s, sync):

- Pilot tile `102018694`: 121,655 sources, 1,647 with `gaia_id`; RA 79.775 to 80.587, Dec −51.256 to −50.747.
- Its VIS mosaic (`DR1_R2`): first observation 2024-02-28, last 2024-09-03, reference 2024-02-28.
- Gaia-matched sources by flags: `flag_vis=0, det_quality_flag=0` 264; the other 1,383 carry some flag.
- Distinct VIS tiles in `DR1_R2`: 9,376.

Pilot residuals (Euclid − Gaia, mas; RA term multiplied by cos Dec; propagated over 8.16 years):

| Gaia `source_id` | G | Raw RA, Dec | After proper motion |
|---|---|---|---|
| 4772491621214894464 | 18.24 | 9.8, 30.5 | −6.4, 6.6 |
| 4772502788129216640 | 18.90 | 5.4, −27.5 | 5.3, 3.1 |
| 4772495817398990976 | 19.96 | −31.8, 15.9 | −0.1, 12.6 |
| 4772491213192634752 | 20.65 | 40.5, 30.0 | −14.5, 3.7 |
| 4772514680895370240 | 14.61 | 50.6, 153.0 | −6.2, 39.6 |

The last row is bright enough to be saturated in VIS; that is an inference, not something read.

# Part D: What the documentation says (G1, read 2026-11-17)

DPDD = `https://euclid.esac.esa.int/dr/dr1/dpdd`; EDS = `https://euclid.dataspace.esa.int/public-eds-help`
(the help pages behind the JavaScript portal); expsup = `https://euclid.esac.esa.int/dr/dr1/expsup`.

| Topic | What was read | Where |
|---|---|---|
| `det_quality_flag` bits | "1 Source contaminated by close neighbors or has bad pixels; 2 Source blended with another one; 4 Source saturated; 8 Source close to a border; 128 Source within the VIS bright star mask; 256 Source within the NIR bright star mask; 512 Source within an extended object area; 1024 Source skipped by the deblending algorithm" | DPDD `/merdpd/merphotometrycookbook.html` |
| `flag_vis` bits | "only use bits from 1 to 4", same meanings for 1, 2, 4, 8 | same |
| Magnitudes | "ZP = 23.9 in all bands: m_AB = -2.5 × log10(flux_µJy) + 23.9" | same |
| `gaia_id` | "Please interpret the description as 'The associated Gaia DR3 source id'" | EDS `/Ambiguous_Gaia_identifier_in_MER_catalogue_for_DR1.html` |
| Coordinate frame and epoch | "ICRS reference system and the Gaia-CRF3 reference frame. The epoch of the coordinates is not explicitly declared… can be found in the <ReferenceObservationDateTime> tag"; it "varies from tile to tile" | EDS `/Epoch_of_source_coordinates_in_the_DR1_MER_catalogue_are_hidden.html` |
| PSF flux of stars | "the PSF-fitting code was applying the source positional registration correction… in the wrong (opposite) direction… only really affected the measurements of point-like sources" | expsup `/Ch15.S3.SS2.html` |
| Star selection | "heavily biased towards a high purity, and thus has a low completeness"; `POINT_LIKE_FLAG` is `POINT_LIKE_PROB > 0.96 AND DET_QUALITY_FLAG = 0`; bright stars: "select very bright (even saturated) sources at VIS AB magnitudes < 17" | DPDD `/merdpd/mermorphologycookbook.html` |
| Empty values | Stored as NaN; the archive sorts NaN above every number | EDS `/Empty_values_in_catalogues_are_mistakenly_treated_as__NaN_.html` |
| Tiles | "approximately 32' × 32'"; the catalogue "contains only sources within the MER tile core area"; cross-tile duplicates about 1 in 10⁵ | EDS `/Catalogues.html`, DPDD `mer_finalcatalog.html`, expsup `/Ch15.S3.SS7.html` |
| Gaia anonymous limits | Sync time-out 60 s; 50,000 rows per query; results kept 24 h; queue limits are "for the total pool of anonymous users" | `https://www.cosmos.esa.int/web/gaia-users/archive/collaborate` |
| Euclid limits | None documented beyond the capabilities document; anonymous jobs deleted after 3 days | EDS release notes |
| Purpose of the services | "intended for scientific research and educational use and are not designed to support operational dependencies" | ESA terms |

Not found in the documentation read: what `gaia_match_quality` measures and in which direction; the match
radius Euclid used; a stated VIS astrometric accuracy; the VIS saturation magnitude; which of `DR1_R1` and
`DR1_R2` is "DR1-Foundation"; any request-rate etiquette for either archive. Several explanatory-supplement
chapters only point to the DR1 papers, which were not read.

Effects on the build:

- Coordinates are taken at the tile's `reference_observation_date_time`, not the middle of its observations.
- Quality tiers use the flag bits: A (both flags zero), B (no contaminated, saturated or border bit), C (rest).
- Brightness uses the aperture flux `flux_vis_2fwhm_aper`; the PSF flux is reported beside it because of the
  known PSF issue.
- The archive query bounds `flux_vis_psf` above to drop NaN rows (30,000 of 32,000 candidates in the pilot).
- `CASE WHEN` and exponent literals such as `1e12` are rejected by the Euclid ADQL parser.

# Part C: Tools

- **GaiaXPy** 2.1.5 on PyPI, BSD-3-Clause. Its list of built-in filter systems includes `Euclid_VIS`, and
  also `HST_ACSWFC`, `HST_WFC3UVIS` and `JWST_NIRCAM`, which matter for v2. Not installed or run here.
- **Aladin Lite**: npm package `aladin-lite`, latest 3.9.3-beta, LGPL-3.0-or-later, served by
  `cdn.jsdelivr.net`. Loading it from a CDN keeps it separate from the MIT code. Pin a non-beta version at G4.
- **astroquery** is on PyPI and has Gaia and Euclid modules; plain HTTP to the TAP endpoints was enough for
  every check above, so it is optional.

# Licences

- **Gaia** (`https://www.cosmos.esa.int/web/gaia-users/license`): "Gaia data are distributed under the
  CC BY-NC 3.0 IGO license." DR3 acknowledgement
  (`https://gea.esac.esa.int/archive/documentation/GDR3/Miscellaneous/sec_credit_and_citation_instructions/`):
  "This work has made use of data from the European Space Agency (ESA) mission Gaia
  (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC,
  https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has been provided by national
  institutions, in particular the institutions participating in the Gaia Multilateral Agreement."
- **Euclid DR1** (`https://www.cosmos.esa.int/web/euclid/dr1-data-credits`): "Euclid DR1 data is licensed
  with the CC BY-NC 3.0 IGO licence", free for non-commercial use "provided that credit is given to 'ESA
  Euclid/Euclid Consortium/NASA/DR1-2026'". Publications cite DOI `https://doi.org/10.57780/esa-d079c51`;
  other uses carry "Data from ESA Euclid/Euclid Consortium/NASA/DR1-2026."
- **ESA archive terms** (`https://www.cosmos.esa.int/web/esdc/terms-and-conditions`): "Prior to any
  commercial use ... including any use or application that directly or indirectly generates a financial
  gain, a detailed request for authorisation/licence shall be made" to `data.licences@esa.int`. Also: the
  user "shall not use Data or Data Products to state or imply the endorsement by ESA". Nothing on automated
  access or on redistributing derived products beyond the licence itself.

Consequence: derived tables we publish are adaptations of CC BY-NC data. They carry CC BY-NC 3.0 IGO, both credit
lines, and a statement that they are modified. The repo's MIT licence covers code only.
