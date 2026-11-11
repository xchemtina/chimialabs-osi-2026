# PbSO4 public integration fixture

Unmodified files copied from AdvancedPhotonSource/GSAS-II `tests/testinp` at local upstream revision `b5638d706f1318be273af548f581665e1da912ad` on 2026-09-04. File SHA-256 commitments are in `case.json`; the originating repository LICENSE is included verbatim as `GSAS-II-LICENSE.txt`. No GSAS binaries are redistributed.

This product includes software produced by UChicago Argonne, LLC under Contract No. DE-AC02-06CH11357 with the Department of Energy.

Source: https://github.com/AdvancedPhotonSource/GSAS-II/tree/b5638d706f1318be273af548f581665e1da912ad/tests/testinp

Tutorial: https://advancedphotonsource.github.io/GSAS-II-tutorials/CWCombined/Combined%20refinement.htm

License source: https://github.com/AdvancedPhotonSource/GSAS-II/blob/b5638d706f1318be273af548f581665e1da912ad/LICENSE

The source repository grants use and redistribution subject to its notice and attribution conditions. These fixture copies retain that license; they are not relicensed under the OpenAgents root license. No individual file-specific contrary notice was found.

The tutorial identifies measured room-temperature Cu K-alpha data from a laboratory Bragg-Brentano diffractometer. The XRA header identifies the 1989 measurement; the GSAS format uses centidegrees, which the native importer converts. The instrument file contains Cu K-alpha wavelengths 1.540500 and 1.544300 Angstrom and approximate profile coefficients. We hold instrument coefficients, atomic positions and displacement parameters fixed, refining only scale/background and then cell using three cycles per stage over 16–110 degrees two-theta. This is deliberately narrower than the full combined X-ray/neutron tutorial.

This is a software integration fixture, not independently calibrated validation. The starting CIF is not a truth label. A poor residual remains visible and cannot be corrected by silently changing this frozen protocol. A scientist may request a separately identified successor protocol/result.

GSAS-II citation: Toby, B. H. and Von Dreele, R. B. (2013), Journal of Applied Crystallography 46, 544–549, https://doi.org/10.1107/S0021889813003531.
