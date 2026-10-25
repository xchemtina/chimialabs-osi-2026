# Crystal representation benchmark — protocol v1

Registered locally before benchmark execution on 2026-10-25. This version tests a finite set of mathematical controls and one external geometry transfer. It does not test measured structural recovery, chemical stability, thermodynamic ordering, native powder-profile parity or backend speed.

## Frozen question

Can a generic occupational representation preserve composition, explicit periodic constraints and complete declared reciprocal-space predictions, then express an independently sourced layered-titanate CIF without a material-specific core change?

The external CIF has already been inspected for admission, so this is a prospective frozen-code transfer test, **not a blind material discovery experiment**. If core code changes after its hash is frozen and the external test begins, preserve the failed run and classify the material as development data. Do not retrospectively call a repaired run held out.

## Conventions and limits

Cell vectors are rows in angstrom. `cart = frac @ cell`, `cell_super = H @ cell`, `frac_super = (frac_parent + t) @ inv(H)`, and `h_super = h_parent @ H.T`. H is an integer 3×3 matrix with positive determinant, subject to declared resource caps. Implementation admission is broader than the finite independently tested set.

The synthetic transform suite is fixed to identity; diag(2,3,1); [[2,1,0],[0,2,0],[0,0,1]]; [[1,1,0],[0,1,1],[0,0,1]]; [[0,1,0],[-2,0,0],[0,0,1]]; and [[2,-1,1],[0,1,0],[0,0,2]]. Use an oblique parent cell [[4,0,0],[1,5,0],[0.5,0.25,6]], with three generic sites at rational fractional positions and complex caller-supplied amplitudes. Parent Miller grid is all integers in [-3,3]^3; supercell cancellation grid is [-4,4]^3. Both include the zero vector as an algebraic control, not an experimentally observable Bragg peak.

Reference cosets are computed independently by enumerating t in {0,...,det(H)-1}³ and rational fractional residues. The reference must not call the core's quotient enumerator. Reference amplitudes use scalar complex exponentials independently of the vectorized core. Exact arithmetic checks the integer/rational fixture identities.

## Required gates

1. Determinant, coset cardinality, composition and periodic mapping. Check F_super(g @ H.T) = det(H) F_parent(g). Check zero-modulation extra satellites cancel. The known amplitude factor det(H), or intensity factor det(H)^2, is an explicit identity, never a fitted repair.
2. Origin translation changes amplitude by exp(2*pi*i*h·delta) and preserves intensity. A declared finite site-period representation must round-trip fractional positions, species, occupancies and labels through P1 CIF, using an independent parser.
3. A twelve-cell ring with four occupied sites: A={0,1,2,3} and B={0,2,4,6} have the same per-parent-site mean but distinguishable discrete intensities. C={0,1,4,6} and D={0,1,3,7} are a candidate non-identifiable pair. Independently enumerate all 495 four-of-twelve patterns, calculate integer cyclic autocorrelations and dihedral equivalence classes, and verify that C/D have identical autocorrelations but different dihedral orbits. Compare direct-sum intensities for the twelve discrete modes. This is periodic discrete homometry, not a claim about continuous-q finite clusters or real powder experiments.
4. Supplied exclusion edges include their parent-cell translation witness. In a twelve-cell ring, edge (site 0, site 0, [1,0,0]) admits alternating occupations and rejects occupation at cells {0,11}. Test an internal adjacent pair as well. No nearest-neighbour discovery or chemical exclusion cutoff is inferred.
5. Reject invalid cells, nonfinite values, noninteger transforms, out-of-range occupations and incompatible exact-count constraints. Average occupancies do not define a joint probability law. Configuration means and ensemble mean intensities remain distinct.

## Numerical acceptance fixed before results

Use float64 eps. For N explicit terms, M=sum(abs(occupancy*f)), H1=sum(abs(h_super)), and kappa=cond2(H), set K=128*N+64*(1+2*pi*H1)*(1+kappa), gamma=K*eps/(1-K*eps), and tau_F=gamma*max(1,M). For a difference of two independently rounded calculations add their amplitude budgets. Mark numerically unassessed if K*eps >= 1e-6. This is a conservative operation/phase budget, not a rigorous libm certificate.

Use absolute tolerances near cancellations. For intensities tau_I=2*abs(F_reference)*tau_F+tau_F². Never clip small intensities to obtain a pass. New CIF output must retain at least 12 decimals. Allow only actual serialization quantization: coordinate bounds u=0.5*10^-p per printed field, delta_phase <= 2*pi*sum(abs(h_a)*u_a), and amplitude budget sum(|f|*|delta_occ| + |occ*f|*delta_phase + |f|*|delta_occ|*delta_phase). Source printing error is common to both computations and is not physical uncertainty.

## External geometry transfer: VT07

Source DOI 10.6084/m9.figshare.12446306.v1, CC BY 4.0. Use the A21am 300 K CIF whose SHA256 is 093c4d1121c232bc9bdda7340738138b0622c0c6804fa3ad28facde29fe324f4. Preserve literal occupancies, including mixed Ca/Sr; do not normalize to nominal composition. Expand its explicit symmetry with an independent crystallographic library. The CIF has no ADPs: use an explicitly labelled zero-ADP derivative, neutral-atom IT92 X-ray factors, no anomalous terms, and s²=|h @ inv(cell).T|²/4. Library version and full original source file are retained.

Compare the source model against generic P1 and supercell representations using identity, diag(2,1,1), and [[2,1,0],[0,1,0],[0,0,1]]. Compare complete integer grids [-6,6]^3 for the source and declared corresponding supercell grids. No scale/background fitting, optimization or intensity normalization. Also compare against the crystallographic library's independent structure-factor calculation where available; disclose shared form-factor tables.

The published TOPAS input is a different P21nm multiphase model and references an absent XYE filename. Its ADPs and response parameters cannot silently be attached to this CIF. Full-profile parity and observed structural inference remain NOT ASSESSED. The bundled XYE is shown only as a source-data view, never as an observed-versus-calculated fit.

## Freeze, reproducibility and presentation

Write protocol and core SHA256 manifests before external calculation. Retain failing attempts and amendments. Save numerical arrays, environment, commands, source hashes and results. Use the user's local Rust Powder Plot application for plotted diffraction data; display transformations are labelled and never substitute for numerical analysis. Keep the original array and an export/capture receipt.

Publish only generic code, synthetic fixtures, explicitly licensed external material and their results. No private structures or legacy private implementation are in this package. Runtime and general scientific advantage are exploratory until a separate performance protocol is registered.
