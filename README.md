# Astral Index

Where two star catalogues disagree. Gaia DR3 and Euclid DR1 both measure the same stars; this project
records, tile by tile, how far their positions and brightnesses differ, which sources disagree by more than
the measured scatter, and how that changes when either catalogue is re-released. Every number rebuilds from
kept query snapshots.

Status (2026-11-17): one pilot tile runs end to end and is reproducible offline (gate G2). Not live.

- `SPEC.md`: what is built and why
- `GATES.md`: the build order and each gate's status
- `SOURCES.md`: the archives, what was read from them, and the licences
- `LOG.md`: the build log
- `astral/`: the code (Python standard library only)
- `fixtures/pilot/`: raw archive responses for the pilot tile, with a hash manifest
- `data/tiles/<tile>/`: results per tile

```bash
python -m unittest discover -s tests
```

```bash
python -m astral.run 102018694 --snap fixtures/pilot --offline
```

Not a catalogue, not a mirror, not a discovery claim.

## Licence and credits

Code: MIT (`LICENSE`). Data files under `fixtures/` and `data/` are derived from Gaia and Euclid data and
are **CC BY-NC 3.0 IGO**: free for non-commercial use with credit. They are modified from the originals, and
neither ESA nor the consortia endorse this project.

- This work has made use of data from the European Space Agency (ESA) mission Gaia
  (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC,
  https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has been provided by national
  institutions, in particular the institutions participating in the Gaia Multilateral Agreement.
- Data from ESA Euclid/Euclid Consortium/NASA/DR1-2026. This work has made use of the Euclid DR1 data from
  the Euclid mission of the European Space Agency (ESA), 2026, https://doi.org/10.57780/esa-d079c51.
