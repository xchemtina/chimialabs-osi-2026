# Periodic representation API contract

This is the implementation contract for `crystalbench` 0.1.1. It describes mathematical operations and input checks, not evidence of experimental structure recovery. Benchmark protocols may admit a smaller domain than the implementation supports. Version 0.1.1 corrects a post-freeze integer-phase range defect; it does not revise the retained v0.1.0 run001 evidence.

## Source model and coordinates

```python
from crystalbench import Site, SourceModel, expand, structure_factors

source = SourceModel(
    cell=((3., 0., 0.), (0., 3., 0.), (0., 0., 3.)),
    sites=(Site("Na1", "Na", (0., 0., 0.), occupancy=0.5, u_iso=None),),
    model_kind="average",
    source_id="synthetic:example",
)
```

`cell` contains lattice vectors as **rows**, in angstrom. Fractional and Cartesian vectors are rows:

- `cart = frac @ cell`
- `cell_super = H @ cell`
- `frac_super = (frac_parent + translation) @ inv(H)`, modulo integer child translations
- `h_super = h_parent @ H.T` for an embedded parent reciprocal vector
- Reciprocal Cartesian vectors are `h @ inv(cell).T`, in cycles per angstrom.

Input `sites` are the complete source-cell basis, including partial/empty alternatives. This core does not expand a crystallographic asymmetric unit. Each site has a unique label, species token, fractional position, occupancy in `[0,1]`, and optional isotropic `u_iso` in angstrom squared. Coordinates need not initially lie inside `[0,1)`. Sites and cell values must be finite; cells must be right-handed, nonsingular, and have 2-norm condition at most `1e12`. Unknown length units or basis conventions are rejected. The caller must retain original source literals, uncertainties, symmetry expansion and provenance separately.

`model_kind="average"` denotes an average-density object. It does not specify an occupation probability law. `model_kind="configuration"` requires every occupation to be exactly zero or one. Negative U is rejected as outside this physical-input contract; its original source value must not be silently repaired upstream.

## Composition semantics

- `nominal_composition`: optional nominal-formula coefficients; never used to repair source values.
- `source.composition`: occupation-weighted species counts per source cell.
- `expanded.source_composition`: the original source-cell counts.
- `expanded.constructed_composition` (also `.composition`): current supercell counts.
- `formula_units`: optional positive integer Z for the actual cell. Expansion multiplies Z by `det(H)`; `.composition_per_formula_unit` is `None` when Z is unknown.

`expand(..., occupancies=None)` repeats source marginals unchanged. Explicit `occupancies` have shape `(det(H), n_source_sites)` and must be binary; they create a configuration. A configuration may change the source populations unless the caller supplies constraints and checks.

Optional `exact_counts={species: integer, ...}` constrain the listed **species totals per supercell**, not every source site's translation mean. They are enforced only for configurations. Unlisted species remain unconstrained by this mapping. Per-source marginal preservation must be checked separately from the tile-by-site array. An integer expected total in an average model is not a constant-count ensemble, so attaching exact configuration counts to an average is rejected.

## Supercell and exclusion domain

`H` is a 3×3 integer matrix with positive determinant. Supported limits are:

- `1 <= det(H) <= 4096`
- maximum absolute entry `1e9`
- 2-norm condition at most `1e8`
- at most `1,000,000` expanded sites

Singular, negative-determinant, fractional and Boolean transforms are rejected. Quotient representatives are computed with exact Python-integer adjugate residues: `translation @ adj(H) mod det(H)`. Breadth-first `+x,+y,+z` generators give a deterministic representative order. This handles non-diagonal/sheared matrices without pretending that independent axis wrapping is sufficient. Floating coordinates are formed only after exact quotient enumeration. Declared bounds are resource/numerical limits, not an empirical validation claim across all admitted matrices.

Expansion is tile-major, then source-site order. `translations`, `source_indices` and `tile_indices` retain the mapping. Labels become `source_label_t<tile_index>`. All sites, including zero-occupation alternatives, are preserved.

Version 0.1.1 separates each source coordinate into its integer floor and fractional remainder during expansion and validation. The integer floor plus tile translation is reduced through the exact adjugate quotient; only the bounded remainder is transformed in floating point. This avoids large-offset loss during division by H while preserving the literal source coordinate and the configuration's tile registration. Merely wrapping the source coordinate before assigning occupations would not preserve that registration.

`ExclusionEdge(site_i, site_j, translation, provenance)` excludes simultaneous occupation of source site `i` in parent cell `t` and site `j` in parent cell `t + translation`. Indices are zero-based; translation is an integer parent-cell row vector. The rule is evaluated for every quotient tile, including boundaries and images coinciding in the finite supercell. Rule provenance is mandatory. These are supplied combinatorial constraints: no distance cutoff, nearest-image choice, chemistry, energy or valence is inferred. Exclusions require explicit configurations; this core is not a marginal-feasibility solver.

## Scattering

```python
F = structure_factors(model, hkl, factors, adp_mode="none")
```

`hkl` is a finite `(n_reflections,3)` array in the current cell's reciprocal coordinates. Periodic Bragg comparisons use integer indices. The return is the unnormalized complex amplitude

`F(h) = sum_j occupancy_j * factor_j(h) * exp(+2*pi*i*frac_j.dot(h)) * DW_j(h)`.

For exactly integer reciprocal rows, phase evaluation reduces the source fractional coordinates modulo one. This preserves the periodic meaning and avoids feeding huge, integer-equivalent source coordinates directly to a trigonometric function; the stored source literals are unchanged. Noninteger rows instead describe the literal finite motif, so their coordinates are **not** reduced modulo one. The two meanings are not interchangeable.

In either branch, the sum of absolute phase-dot-product terms must not exceed `1e6` cycles for any site/reflection. The integer branch evaluates that bound after coordinate reduction; the noninteger branch uses literal coordinates. Larger or nonfinite sums are rejected, including large terms that cancel in the final dot product. Bounded phase cycles are then reduced modulo one before the complex exponential. This is a numerical support guard, not a claim of uniform accuracy across the admitted range; registered validation covers its stated reflection subset. Fractional detail already lost when a source literal is converted to binary floating point cannot be reconstructed by this policy.

`factors` is either a species-to-complex-scalar/length-`n_reflections` mapping, a length-`n_sites` array, or an `(n_reflections,n_sites)` array. Factors exclude occupancy and ADP. The caller explicitly chooses chemical tables, anomalous terms, units and probe conventions; no chemical scattering factors are supplied internally.

The keyword `adp_mode` is mandatory:

- `"none"`: deliberately neglect all ADPs, including unknown values. `scattering_contract(adp_mode="none")` records this as a **zero-ADP control**, not a measurement of U.
- `"isotropic"`: every site must have known U; applies `exp(-2*pi**2*U_iso*|g|**2)`.

There is no fitted scale, normalization, powder multiplicity, Lorentz/polarization, absorption, instrument response or ensemble-intensity averaging. An average model gives mean-density amplitude, not mean intensity. Finite-input overflow and nonfinite outputs are rejected.

## Serialization and CIF scope

`.to_dict()` emits canonical JSON-compatible data with schema `crystalbench.periodic-model.v1`. `model_from_dict()` reconstructs and checks expanded objects against their source rather than trusting stored positions or mapping tables. Unknown or inconsistent canonical records are rejected.

`write_cif(model, path)` writes all sites in P1 with metric, fractional positions, occupancy and isotropic U. Unknown U is `?`, never silently zero. CIF preserves the metric, not an arbitrary global Cartesian orientation; independent reimport comparisons must use metric and periodic fractional positions. The JSON companion retains the source/transform/model semantics that ordinary CIF does not encode. CIF parsing and asymmetric-unit expansion belong to the independently checked admission adapter, outside this core.

The core provides no optimizer, structure selection, energy model, anisotropic ADPs, displacement variables, magnetic scattering, diffuse-scattering law, finite-domain model or experimental inference.
