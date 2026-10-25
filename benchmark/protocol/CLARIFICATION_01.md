# Pre-execution clarification 01 — 2026-10-25

The core writes CIF numeric tokens with 16 significant digits. Protocol v1's requirement for at least twelve decimals means an absolute fractional-coordinate quantization no larger than 0.5e-12 on canonical coordinates, not mandatory trailing zero characters. Exact tokens such as `0` and `0.5` are valid. CIF round-trip compares the cell metric, because lengths/angles do not preserve arbitrary Cartesian orientation. This interpretation is recorded before benchmark execution; it does not change acceptance tolerances after a result.

The external source has already been inspected for admission. The claim is frozen-code transfer, not blinded discovery. The independent reviewer found a near-parallel-cell angle serialization defect before freeze; it was fixed using atan2(cross norm, dot), with a regression test. No external scattering evaluation preceded the fix.
