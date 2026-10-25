# Amendment 02 — retained first run and numerical-range correction

2026-10-25. Run001 passed its finite registered controls, including the external CIF. Subsequent independent review found that the broader API admitted very large unwrapped fractional coordinates whose phase evaluation lost precision. A related expansion calculation also lost precision when multiplying a large integer coordinate by a floating-point inverse.

The original core, protocol and runner are retained in `results/run001/frozen-source.zip`, with hashes in `FREEZE.json`. The passing finite results are preserved; they do not certify the API outside the tested domain.

Version 0.1.1 corrects integer Bragg phase evaluation without altering stored source literals, separates integer/fractional coordinate parts for stable periodic expansion, and makes noninteger finite-motif semantics and numerical phase guards explicit. Added regression tests exercise the reported edge cases. No physical source coordinate, occupancy, factor table, ADP assumption or fit parameter is adjusted.

Because the core changes after external evaluation, **VT07 is now a development/revalidation case for the revised implementation**. Do not describe the revised result as a blind or held-out validation. A different, untouched material is needed for that next claim. The source had already been inspected for admission even before run001, so neither run was a blinded discovery experiment.

The rerun retains the original numeric criteria. Its reporting marks the two determinant-one satellite checks NOT_APPLICABLE (no extra satellites) rather than counting them as substantive passes. A direct literal-multiplicity composition check is added to make the existing composition requirement explicit in the external receipt. No acceptance tolerance is loosened.

Full-profile parity, experimental structure recovery, physical ordering selection, speed advantage and isotropic-ADP transfer remain outside this benchmark's accepted claims.
