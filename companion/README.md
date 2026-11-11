# ChimiaLabs: replay of a public diffraction result

A small scientific-software companion using licensed public **PbSO4** diffraction data. It carries a recorded result through the real OpenAgents `NodeRuntime` with a deterministic Rust `PxrdReplaySkill`: verify sources, check a signed request/result relationship, reject tampering and avoid duplicating an existing result. **The replay makes no LLM calls and performs no new scientific calculation.**

[Inspect the browser demo](https://xchemtina.github.io/chimialabs-osi-2026/companion/public/) · [Portfolio](../PORTFOLIO.md) · [Release notes](RELEASE_NOTES.md)

## What you can inspect

Open [public/index.html](public/index.html) directly in a browser. It works offline without a server. The page displays saved receipts and all 6,000 recorded profile points; it does not perform cryptographic verification in your browser.

- [Initial runtime receipt](run/report.json) and [historical verification receipt](run/verification.json).
- [Public fixture provenance](fixtures/pbso4/PROVENANCE.md), [sanitized native receipt](fixtures/pbso4/historical-receipt.json) and [native metrics](fixtures/pbso4/native-metrics.json).
- [Adapter source](adapter/src/main.rs), [upstream pins](adapter/vendor/UPSTREAM.json) and [claim boundaries](docs/CLAIMS.json).

The native GSAS-II result dates to **13 September 2026**. The runtime integration, signed lineage, tests and viewer were prepared on **22 October**. This November release packages that separate public-data companion; the OSI entry itself published only a methods description. It contains no private copper research implementation, coordinates, figures or measurements.

## Reproduce the software checks

Requirements: **macOS or Linux**, a shell and **Rust/Cargo 1.89.0**, pinned by `rust-toolchain.toml`. The adapter uses `/dev/urandom`; Windows is not qualified. With rustup, entering this directory selects the pinned toolchain (it may download the toolchain if absent).

Seven OpenAgents crates are included. Cargo registry dependencies are locked but not bundled. A new machine needs network access once to fetch them:

```sh
cd companion
cargo fetch --locked --manifest-path adapter/Cargo.toml
./run_demo.sh
./verify_demo.sh
```

If you downloaded only the companion directory, start inside it and omit `cd companion`. After dependencies are cached, both scripts build/run with `--offline --locked`. They do not require GSAS-II, Python, a wallet, an API key or an AI service. `CARGO_HOME` and `CARGO_TARGET_DIR` may be set to isolated caches/build directories.

The shipped `run/` contains the initial signed artifacts and public demonstration keys. Running again verifies those artifacts and skips the existing child. It writes a new `run/verification.json` and regenerates the viewer data while preserving `run/report.json`. Use a disposable copy to keep the distributed bytes unchanged.

For a fresh local signing demonstration, use a disposable copy, move its `run/` directory to `reference-run/`, and run the same scripts. The private signing keys are ephemeral and not written to disk. This creates a new software receipt over the same recorded scientific result; it does not perform a fresh refinement.

## What passes, and what does not follow

The software checks exact fixture membership and file hashes, regular-file paths, profile/residual consistency, the fitted observation count, signed payloads, parent/child lineage and the recorded local demonstration keys. Five Rust tests exercise the fixture and reject modified sources, a changed manifest, an extra file and a symlink. Runtime negative checks reject altered envelopes, payloads and key substitution. Repeated execution must skip the existing child.

These local signatures establish byte commitments against the included demonstration keys. They do not authenticate an external person, establish instrument calibration, prove physical correctness or constitute independent laboratory validation. A person replacing the entire package and its declared trust roots is outside this demonstration's trust boundary.

## Scientific limits

The export has 6,000 points spanning 10–159.975 degrees two-theta. The fit used 16–110 degrees and 3,761 observations. Native Rwp is **32.476329298163684%** over that fitted window. Its poor residual is retained. The supplied instrument approximation and atomic coordinates were fixed; the starting CIF is not a truth label.

Three cycles per stage were configured; the final native listing reports four. The frozen provenance file's phrase “using three cycles per stage” describes the configuration, not a verified actual cycle count. It remains unchanged to preserve its source commitment. See [release notes](RELEASE_NOTES.md).

This is evidence-processing software, not a new refinement, a good physical fit, copper validation, autonomous discovery, a selected structure or a multi-laboratory federation.

## Attribution and license

New companion materials use Apache-2.0, consistent with the adapter. Reused OpenAgents sources retain their license and NOTICE. The GSAS-II fixture retains its own license and UChicago Argonne acknowledgment; it is not relicensed. See the repository [LICENSE](../LICENSE), [NOTICE](../NOTICE) and [fixture license](fixtures/pbso4/GSAS-II-LICENSE.txt).

This product includes software produced by UChicago Argonne, LLC under Contract No. DE-AC02-06CH11357 with the Department of Energy.
