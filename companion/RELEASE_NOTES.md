# Public companion release — 11 November 2026

This release selects the source, static viewer, public PbSO4 fixture, signed
historical artifacts and test evidence from the 22 October companion. The
original archive SHA-256 is
`0e2ad779a343ef8702e3e1bd5e29e529ff93af138de6a12f431c1786a8209a6f`.
The published OSI methods entry remains a distinct earlier artifact.

## Changes for release

- Removed links to omitted slides, narration and PDFs; no research assets added.
- Replaced the viewer's relative “Today” with the actual 22 October integration
  date and identified the deterministic, model-free Rust replay.
- Clarified static receipt display, keyboard controls and narrow-screen layout.
- Pinned Rust 1.89.0; documented macOS/Linux and initial dependency fetching.
- Allowed an explicitly supplied Cargo target directory in the wrapper scripts.
- Added Apache-2.0 scope for new material while retaining separate third-party
  terms, attribution and source pins.
- Added a portfolio and a static site built from the same companion bytes.

Scientific fixtures, numerical results, the compiled fixture commitment,
vendored crate source and original signed artifacts are unchanged. The
historical tests/ and run/ receipts remain dated evidence; fresh release checks
are recorded separately in `validation/release-checks.json`.

## Cycle-count clarification

The immutable fixture provenance says “using three cycles per stage”. Three
were configured, while the final native listing reports four. The signed
result already discloses this discrepancy. This release does not claim an
actual three-cycle execution and does not alter the frozen provenance to make
its hash change disappear.

## Scope

The browser shows saved verification evidence; run the CLI to recompute it.
The recorded poor residual is intentional evidence of a limitation. Neither
a signature nor a passing source check makes the scientific model correct.
