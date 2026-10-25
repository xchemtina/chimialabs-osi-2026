# VT07 public source fixture

Unmodified `source.cif` comes from Fernando Pomiro's deposit, **Cif_files_and_exp_data.zip** (2020), DOI [10.6084/m9.figshare.12446306.v1](https://doi.org/10.6084/m9.figshare.12446306.v1), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The depositor's exact metadata citation and terms are retained in `DEPOSIT.json`. `SOURCE_FILES.json` identifies archive members and byte hashes.

The CIF describes A21am at folder-labelled 300 K. It supplies nine asymmetric site/species records, eight symmetry operations and no ADPs. Full symmetry expansion produces 60 species/site records, including coincident Ca/Sr alternatives; occupancy-weighted composition is Ca8.332 Sr3.668 Ti8 O28 (48 atoms per supplied cell). Dividing by four to express a Ti2O7 reference gives Ca2.083 Sr0.917 Ti2 O7, distinct from nominal Ca2.15 Sr0.85 Ti2 O7. No occupancy normalization was applied.

Benchmark calculations deliberately neglect ADPs, use neutral IT92 X-ray factors and omit anomalous scattering. Generated JSON/P1 CIF files are explicitly derived models. Missing ADPs remain unknown in the exported source contract.

The supplied TOPAS input describes a different P21nm multiphase model and references a filename not present in the deposit. Its ADPs and response cannot be silently assigned to this CIF. No published-profile reproduction or measured structural inference is claimed.

To retrieve the observations and published input from an already downloaded pinned archive:

```sh
python scripts/admit_vt07.py /path/to/Cif_files_and_exp_data.zip /path/to/new-intake
```

Publisher download: <https://ndownloader.figshare.com/files/22972034> (109,011,284 bytes). The script verifies the archive SHA256 before extracting only the three pinned members. The small CIF is included so the numerical benchmark does not require the full download.
