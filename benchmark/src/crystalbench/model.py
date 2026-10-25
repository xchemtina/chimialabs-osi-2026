"""Generic periodic site/occupation representation, written independently.

Conventions: cell vectors are rows in angstrom; cart = frac @ cell.
For integer H, cell_super = H @ cell and frac_super = (frac + t) @ inv(H).
Translation equivalence is t ~ t + z @ H. Exact integer adjugate residues
enumerate this quotient; no component-wise wrapping approximation is used.

This module does not infer chemical exclusions, expand crystallographic space
groups, discover nearest images, infer an ensemble from marginals, or fit data.
Input sites are already the complete source-cell basis, including alternatives.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence
import math
import re

import numpy as np


class ContractError(ValueError):
    """The requested object is outside its declared mathematical contract."""


MAX_DETERMINANT = 4096
MAX_EXPANDED_SITES = 1_000_000
MAX_TRANSFORM_CONDITION = 1e8
SCHEMA = "crystalbench.periodic-model.v1"
_IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+\-]*$")


def _finite(value: Any, name: str) -> float:
    if not isinstance(value, Real) or isinstance(value, bool):
        raise ContractError(f"{name} must be a finite real number")
    out = float(value)
    if not math.isfinite(out):
        raise ContractError(f"{name} must be finite")
    return out


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ContractError(f"{name} must be an integer, not Boolean")
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real) and math.isfinite(float(value)) and float(value).is_integer():
        return int(value)
    raise ContractError(f"{name} must be an integer")


def _triple(values: Sequence[Any], name: str, integer: bool = False) -> tuple:
    try:
        if len(values) != 3:
            raise ContractError(f"{name} must have three entries")
        convert = _integer if integer else _finite
        return tuple(convert(x, name) for x in values)
    except TypeError as exc:
        raise ContractError(f"{name} must have three entries") from exc


def _token(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ContractError(f"{name} must be a nonempty simple CIF-safe token")
    return value


def _composition(values: Mapping[str, Any] | None, name: str) -> Mapping[str, float] | None:
    if values is None:
        return None
    out: dict[str, float] = {}
    for key, value in values.items():
        key = _token(key, f"{name} species")
        value = _finite(value, f"{name}[{key}]")
        if value < 0:
            raise ContractError(f"{name} cannot contain negative counts")
        out[key] = value
    return MappingProxyType(out)


def _cell(cell: Sequence[Sequence[float]]) -> tuple:
    try:
        if len(cell) != 3:
            raise ContractError("cell must be 3 by 3")
        result = tuple(_triple(row, "cell") for row in cell)
    except TypeError as exc:
        raise ContractError("cell must be 3 by 3") from exc
    a = np.asarray(result, dtype=float)
    det = float(np.linalg.det(a))
    if not math.isfinite(det) or det <= 0 or np.linalg.cond(a) > 1e12:
        raise ContractError("cell must be finite, right-handed and nonsingular (condition <= 1e12)")
    return result


@dataclass(frozen=True)
class Site:
    label: str
    species: str
    frac: tuple[float, float, float]
    occupancy: float
    u_iso: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _token(self.label, "site label"))
        object.__setattr__(self, "species", _token(self.species, "species"))
        object.__setattr__(self, "frac", _triple(self.frac, "fractional coordinates"))
        occ = _finite(self.occupancy, "occupancy")
        if not 0 <= occ <= 1:
            raise ContractError("occupancy must lie in [0,1]")
        object.__setattr__(self, "occupancy", occ)
        if self.u_iso is not None:
            u = _finite(self.u_iso, "u_iso")
            if u < 0:
                raise ContractError("negative u_iso is outside this physical input contract")
            object.__setattr__(self, "u_iso", u)

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "species": self.species, "frac": list(self.frac),
                "occupancy": self.occupancy, "u_iso": self.u_iso}


@dataclass(frozen=True)
class SourceModel:
    cell: tuple[tuple[float, float, float], ...]
    sites: tuple[Site, ...]
    model_kind: str = "average"
    nominal_composition: Mapping[str, float] | None = None
    formula_units: int | None = None
    source_id: str = "unspecified"
    length_unit: str = "angstrom"
    coordinate_convention: str = "row_basis"

    def __post_init__(self) -> None:
        if self.length_unit != "angstrom" or self.coordinate_convention != "row_basis":
            raise ContractError("only explicit angstrom row-basis input is supported")
        object.__setattr__(self, "cell", _cell(self.cell))
        sites = tuple(self.sites)
        if not sites or any(not isinstance(s, Site) for s in sites):
            raise ContractError("sites must be a nonempty complete cell basis of Site objects")
        if len({s.label for s in sites}) != len(sites):
            raise ContractError("source-site labels must be unique")
        if self.model_kind not in {"average", "configuration"}:
            raise ContractError("model_kind must be average or configuration")
        if self.model_kind == "configuration" and any(s.occupancy not in (0, 1) for s in sites):
            raise ContractError("a configuration requires binary occupations")
        object.__setattr__(self, "sites", sites)
        object.__setattr__(self, "nominal_composition", _composition(self.nominal_composition, "nominal_composition"))
        if self.formula_units is not None:
            z = _integer(self.formula_units, "formula_units")
            if z <= 0:
                raise ContractError("formula_units must be positive when supplied")
            object.__setattr__(self, "formula_units", z)
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ContractError("source_id must be a nonempty string")

    @property
    def composition(self) -> dict[str, float]:
        """Occupation-weighted count per supplied cell, not nominal formula."""
        result: dict[str, list[float]] = {}
        for s in self.sites:
            result.setdefault(s.species, []).append(s.occupancy)
        return {key: math.fsum(values) for key, values in result.items()}

    @property
    def composition_per_formula_unit(self) -> dict[str, float] | None:
        if self.formula_units is None:
            return None
        return {k: v / self.formula_units for k, v in self.composition.items()}

    @property
    def volume(self) -> float:
        return float(np.linalg.det(np.asarray(self.cell)))

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "object_type": "source", "cell": [list(x) for x in self.cell],
                "length_unit": self.length_unit, "coordinate_convention": self.coordinate_convention,
                "sites": [s.to_dict() for s in self.sites], "model_kind": self.model_kind,
                "nominal_composition": None if self.nominal_composition is None else dict(self.nominal_composition),
                "source_weighted_composition": self.composition,
                "formula_units": self.formula_units, "source_id": self.source_id}


@dataclass(frozen=True)
class ExclusionEdge:
    """Exclude simultaneous i at t and j at t+translation, in parent cells."""
    site_i: int
    site_j: int
    translation: tuple[int, int, int]
    provenance: str

    def __post_init__(self) -> None:
        for key in ("site_i", "site_j"):
            value = _integer(getattr(self, key), key)
            if value < 0:
                raise ContractError("exclusion indices cannot be negative")
            object.__setattr__(self, key, value)
        object.__setattr__(self, "translation", _triple(self.translation, "exclusion translation", integer=True))
        if self.site_i == self.site_j and self.translation == (0, 0, 0):
            raise ContractError("zero-translation exclusion of a site against itself is not an edge")
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ContractError("exclusions require explicit rule/witness provenance")

    def to_dict(self) -> dict[str, Any]:
        return {"site_i": self.site_i, "site_j": self.site_j,
                "translation": list(self.translation), "provenance": self.provenance}


@dataclass(frozen=True)
class ExpandedModel(SourceModel):
    source: SourceModel | None = None
    transform: tuple[tuple[int, int, int], ...] = _IDENTITY
    translations: tuple[tuple[int, int, int], ...] = ()
    source_indices: tuple[int, ...] = ()
    tile_indices: tuple[int, ...] = ()
    exact_counts: Mapping[str, int] | None = None
    exclusions: tuple[ExclusionEdge, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.source, SourceModel):
            raise ContractError("expanded model requires its source model")
        h, determinant, adj = _transform(self.transform)
        expected_tiles = quotient_representatives(h)
        nsource = len(self.source.sites)
        if len(self.sites) != determinant*nsource or len(self.sites) > MAX_EXPANDED_SITES:
            raise ContractError("expanded basis size must equal determinant times source size")
        if tuple(map(tuple, self.translations)) != expected_tiles:
            raise ContractError("expanded translations do not match the exact quotient")
        if tuple(self.source_indices) != tuple(j for _ in expected_tiles for j in range(nsource)):
            raise ContractError("expanded source-index mapping is inconsistent")
        if tuple(self.tile_indices) != tuple(k for k in range(determinant) for _ in range(nsource)):
            raise ContractError("expanded tile-index mapping is inconsistent")
        expected_cell = np.asarray(h) @ np.asarray(self.source.cell)
        if not np.allclose(self.cell, expected_cell, rtol=1e-13, atol=1e-13):
            raise ContractError("expanded cell does not match H @ source.cell")
        if self.source_id != self.source.source_id or self.nominal_composition != self.source.nominal_composition:
            raise ContractError("expanded source identity/nominal formula changed")
        expected_z = None if self.source.formula_units is None else determinant*self.source.formula_units
        if self.formula_units != expected_z:
            raise ContractError("expanded formula-unit normalization is inconsistent")
        for site, j, k in zip(self.sites, self.source_indices, self.tile_indices):
            original = self.source.sites[j]
            expected = _expanded_fraction(original.frac, expected_tiles[k], adj, determinant)
            delta = np.remainder(np.asarray(site.frac)-expected+0.5, 1.)-0.5
            if site.label != f"{original.label}_t{k}" or site.species != original.species or site.u_iso != original.u_iso:
                raise ContractError("expanded source-site identity/ADP changed")
            if np.max(np.abs(delta)) > 5e-12:
                raise ContractError("expanded coordinates do not match source/tile mapping")
            if self.model_kind == "average" and site.occupancy != original.occupancy:
                raise ContractError("an average expansion must preserve source marginals")
        counts = _counts(self.exact_counts, self.source)
        rules = tuple(self.exclusions)
        if self.model_kind == "configuration":
            bits = np.asarray([s.occupancy for s in self.sites]).reshape(determinant, nsource)
            validate_configuration(self.source, h, bits, exact_counts=counts, exclusions=rules)
        elif counts is not None or rules:
            raise ContractError("average expansion cannot certify configuration constraints")
        object.__setattr__(self, "transform", h)
        object.__setattr__(self, "translations", expected_tiles)
        object.__setattr__(self, "source_indices", tuple(self.source_indices))
        object.__setattr__(self, "tile_indices", tuple(self.tile_indices))
        object.__setattr__(self, "exact_counts", counts)
        object.__setattr__(self, "exclusions", rules)

    @property
    def source_composition(self) -> dict[str, float]:
        if self.source is None:
            raise ContractError("expanded model has no source")
        return self.source.composition

    @property
    def constructed_composition(self) -> dict[str, float]:
        return self.composition

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(object_type="expanded", source=None if self.source is None else self.source.to_dict(),
                      transform=[list(x) for x in self.transform],
                      translations=[list(x) for x in self.translations],
                      source_indices=list(self.source_indices), tile_indices=list(self.tile_indices),
                      source_weighted_composition=self.source_composition,
                      constructed_composition=self.composition,
                      exact_counts=None if self.exact_counts is None else dict(self.exact_counts),
                      exclusions=[e.to_dict() for e in self.exclusions])
        return result


def _transform(H: Sequence[Sequence[int]]) -> tuple[tuple, int, tuple]:
    try:
        if len(H) != 3:
            raise ContractError("transform must be 3 by 3")
        h = tuple(_triple(row, "transform", integer=True) for row in H)
    except TypeError as exc:
        raise ContractError("transform must be 3 by 3") from exc
    a, b, c = h[0]; d, e, f = h[1]; g, i, j = h[2]
    adj = ((e*j-f*i, c*i-b*j, b*f-c*e),
           (f*g-d*j, a*j-c*g, c*d-a*f),
           (d*i-e*g, b*g-a*i, a*e-b*d))
    determinant = a * adj[0][0] + b * adj[1][0] + c * adj[2][0]
    if not 1 <= determinant <= MAX_DETERMINANT:
        raise ContractError(f"positive transform determinant must be <= {MAX_DETERMINANT}")
    if max(abs(v) for row in h for v in row) > 10**9:
        raise ContractError("transform entries exceed the declared 1e9 integer bound")
    if np.linalg.cond(np.asarray(h, dtype=float)) > MAX_TRANSFORM_CONDITION:
        raise ContractError(f"transform condition exceeds {MAX_TRANSFORM_CONDITION:g}")
    return h, determinant, adj


def _residue(t: Sequence[int], adj: tuple, determinant: int) -> tuple[int, int, int]:
    return tuple(sum(t[k] * adj[k][j] for k in range(3)) % determinant for j in range(3))


def _expanded_fraction(frac: Sequence[float], translation: Sequence[int],
                       adj: tuple, determinant: int) -> np.ndarray:
    """Apply inverse H without multiplying huge source integer offsets in float.

    Keep the source integer offset in the exact quotient calculation. Simply
    canonicalizing the source before tiling would change configuration registry.
    """
    integer_part = tuple(math.floor(v) for v in frac)
    fractional_part = np.remainder(np.asarray(frac), 1.)
    shifted = tuple(integer_part[k] + translation[k] for k in range(3))
    exact_residue = np.asarray(_residue(shifted, adj, determinant), dtype=float) / determinant
    inverse = np.asarray(adj, dtype=float) / determinant
    return np.remainder(exact_residue + fractional_part @ inverse, 1.)


def quotient_representatives(H: Sequence[Sequence[int]]) -> tuple[tuple[int, int, int], ...]:
    """Exact deterministic representatives of row Z^3 / row Z^3 H.

    Breadth-first generators begin at (0,0,0), then +x,+y,+z. Representative
    choices are not canonical crystallographic coordinates; their equivalence
    classes and cardinality are exact. Floating coordinates are created later.
    """
    _, determinant, adj = _transform(H)
    pending = deque([(0, 0, 0)])
    seen = {(0, 0, 0)}
    representatives = [(0, 0, 0)]
    while pending and len(representatives) < determinant:
        t = pending.popleft()
        for axis in range(3):
            trial = tuple(t[k] + int(k == axis) for k in range(3))
            residue = _residue(trial, adj, determinant)
            if residue not in seen:
                seen.add(residue)
                pending.append(trial)
                representatives.append(trial)
    if len(representatives) != determinant:
        raise RuntimeError("exact quotient enumeration did not reach determinant cardinality")
    return tuple(representatives)


def _counts(counts: Mapping[str, Any] | None, source: SourceModel) -> Mapping[str, int] | None:
    if counts is None:
        return None
    out = {}
    species = {s.species for s in source.sites}
    for name, value in counts.items():
        if name not in species:
            raise ContractError(f"exact-count species {name!r} is absent from source")
        count = _integer(value, f"exact_counts[{name}]")
        if count < 0:
            raise ContractError("exact counts cannot be negative")
        out[name] = count
    return MappingProxyType(out)


def validate_configuration(source: SourceModel, H: Sequence[Sequence[int]],
                           occupancies: Sequence[Sequence[float]], *,
                           exact_counts: Mapping[str, int] | None = None,
                           exclusions: Sequence[ExclusionEdge] = ()) -> dict[str, Any]:
    """Verify one binary decoration. This is not ensemble feasibility or energy."""
    h, determinant, adj = _transform(H)
    tiles = quotient_representatives(h)
    nsites = len(source.sites)
    if determinant * nsites > MAX_EXPANDED_SITES:
        raise ContractError("expanded site count exceeds resource contract")
    bits = np.asarray(occupancies)
    if bits.shape != (determinant, nsites) or not np.all(np.isin(bits, (0, 1))):
        raise ContractError(f"occupancies must be a binary array of shape {(determinant, nsites)}")
    bits = bits.astype(np.int8)
    counts = _counts(exact_counts, source)
    actual = {name: sum(int(bits[:, j].sum()) for j, s in enumerate(source.sites) if s.species == name)
              for name in source.composition}
    if counts is not None:
        for name, target in counts.items():
            if actual[name] != target:
                raise ContractError(f"exact count violated for {name}: {actual[name]} != {target}")
    lookup = {_residue(t, adj, determinant): k for k, t in enumerate(tiles)}
    checked = 0
    for edge in exclusions:
        if not isinstance(edge, ExclusionEdge):
            raise ContractError("exclusions must contain ExclusionEdge objects")
        if max(edge.site_i, edge.site_j) >= nsites:
            raise ContractError("exclusion index is outside the source basis")
        for tile_index, t in enumerate(tiles):
            translated = tuple(t[k] + edge.translation[k] for k in range(3))
            other_tile = lookup[_residue(translated, adj, determinant)]
            checked += 1
            if bits[tile_index, edge.site_i] + bits[other_tile, edge.site_j] > 1:
                raise ContractError(f"periodic exclusion violated: source sites {edge.site_i},{edge.site_j}; "
                                    f"tile {tile_index}->{other_tile}; parent translation {edge.translation}")
    return {"valid": True, "model_kind": "configuration", "composition": actual,
            "translated_edges_checked": checked, "determinant": determinant,
            "scope": "declared binary occupations, exact counts and explicit periodic exclusions only"}


def expand(source: SourceModel, H: Sequence[Sequence[int]], *,
           occupancies: Sequence[Sequence[float]] | None = None,
           exact_counts: Mapping[str, int] | None = None,
           exclusions: Sequence[ExclusionEdge] = ()) -> ExpandedModel:
    """Expand the complete input basis, optionally installing binary occupations.

    All source alternatives, including zero occupations, are retained. Rules do
    not infer source-marginal preservation; a particular decoration may have a
    different composition unless the caller explicitly registers exact counts.
    """
    if not isinstance(source, SourceModel):
        raise ContractError("source must be a SourceModel")
    h, determinant, adj = _transform(H)
    if determinant * len(source.sites) > MAX_EXPANDED_SITES:
        raise ContractError("expanded site count exceeds resource contract")
    translations = quotient_representatives(h)
    rules = tuple(exclusions)
    counts = _counts(exact_counts, source)
    if occupancies is None:
        bits = np.tile([s.occupancy for s in source.sites], (determinant, 1))
        kind = source.model_kind
        if counts is not None and kind != "configuration":
            raise ContractError("exact counts on an average do not define constant-count configurations")
        if kind == "configuration":
            validate_configuration(source, h, bits, exact_counts=counts, exclusions=rules)
        elif rules:
            raise ContractError("exclusions require an explicit configuration; average marginals are not a joint law")
    else:
        validate_configuration(source, h, occupancies, exact_counts=counts, exclusions=rules)
        bits = np.asarray(occupancies, dtype=float)
        kind = "configuration"
    sites = []
    source_indices = []
    tile_indices = []
    for k, translation in enumerate(translations):
        for j, site in enumerate(source.sites):
            frac = _expanded_fraction(site.frac, translation, adj, determinant)
            sites.append(Site(f"{site.label}_t{k}", site.species, tuple(frac), float(bits[k, j]), site.u_iso))
            source_indices.append(j)
            tile_indices.append(k)
    return ExpandedModel(cell=tuple(map(tuple, np.asarray(h) @ np.asarray(source.cell))),
                         sites=tuple(sites), model_kind=kind,
                         nominal_composition=source.nominal_composition,
                         formula_units=None if source.formula_units is None else source.formula_units * determinant,
                         source_id=source.source_id,
                         source=source, transform=h, translations=translations,
                         source_indices=tuple(source_indices), tile_indices=tuple(tile_indices),
                         exact_counts=counts, exclusions=rules)


def model_from_dict(data: Mapping[str, Any]) -> SourceModel:
    """Load canonical JSON; reconstruct expansions rather than trusting mappings."""
    if data.get("schema") != SCHEMA:
        raise ContractError("unrecognized model schema")
    if data.get("object_type") == "expanded":
        source = model_from_dict(data["source"])
        h, determinant, _ = _transform(data["transform"])
        site_data = data["sites"]
        if len(site_data) != determinant * len(source.sites):
            raise ContractError("serialized expanded basis has wrong size")
        occupations = np.array([x["occupancy"] for x in site_data]).reshape(determinant, len(source.sites))
        is_configuration = data["model_kind"] == "configuration"
        result = expand(source, h, occupancies=occupations if is_configuration else None,
                        exact_counts=data.get("exact_counts"),
                        exclusions=[ExclusionEdge(**x) for x in data.get("exclusions", [])])
        if result.to_dict() != dict(data):
            raise ContractError("serialized expansion does not match reconstructed source/mapping")
        return result
    if data.get("object_type") != "source":
        raise ContractError("object_type must be source or expanded")
    result = SourceModel(cell=data["cell"], sites=tuple(Site(**s) for s in data["sites"]),
                         model_kind=data["model_kind"], nominal_composition=data.get("nominal_composition"),
                         formula_units=data.get("formula_units"), source_id=data["source_id"],
                         length_unit=data["length_unit"], coordinate_convention=data["coordinate_convention"])
    if result.to_dict() != dict(data):
        raise ContractError("serialized source fields differ from the canonical contract")
    return result


def cell_from_parameters(a: float, b: float, c: float,
                         alpha: float, beta: float, gamma: float) -> tuple:
    """Conventional right-handed row basis; angles in degrees, lengths angstrom."""
    lengths = [_finite(v, "cell length") for v in (a, b, c)]
    angles = [_finite(v, "cell angle") for v in (alpha, beta, gamma)]
    if min(lengths) <= 0 or any(not 0 < v < 180 for v in angles):
        raise ContractError("cell lengths must be positive and angles strictly between 0 and 180")
    a, b, c = lengths
    ar, br, gr = map(math.radians, angles)
    cx = c * math.cos(br)
    cy = c * (math.cos(ar) - math.cos(br)*math.cos(gr)) / math.sin(gr)
    cz2 = c*c - cx*cx - cy*cy
    if cz2 <= 0:
        raise ContractError("cell parameters do not define positive volume")
    return _cell(((a, 0., 0.), (b*math.cos(gr), b*math.sin(gr), 0.), (cx, cy, math.sqrt(cz2))))


def cell_parameters(cell: Sequence[Sequence[float]]) -> tuple[float, ...]:
    rows = np.asarray(_cell(cell))
    lengths = np.linalg.norm(rows, axis=1)
    def angle(i: int, j: int) -> float:
        # acos(dot/(norms)) rounds near-parallel admitted cells to zero angle.
        # Unit-vector atan2 retains the small perpendicular component instead.
        u, v = rows[i]/lengths[i], rows[j]/lengths[j]
        result = math.degrees(math.atan2(float(np.linalg.norm(np.cross(u, v))), float(np.dot(u, v))))
        if not 0 < result < 180:
            raise ContractError("cell angle is not representable strictly inside (0,180) degrees")
        return result
    return tuple(float(v) for v in lengths) + (angle(1, 2), angle(0, 2), angle(0, 1))


def write_cif(model: SourceModel, path: str | Path) -> Path:
    """Write all sites as P1, including zero occupations and unknown U values.

    CIF records the metric and fractional coordinates, not the arbitrary global
    Cartesian orientation of the input cell. No anisotropic information or
    probability law is inferred. Use model.to_dict() alongside CIF for lineage.
    """
    parameters = cell_parameters(model.cell)
    lines = ["data_crystalbench", "# Generic P1 representation; full lineage is in companion JSON.",
             f"# model_kind: {model.model_kind}", "# cell lengths: angstrom; U_iso: angstrom^2; '?' means unknown."]
    keys = ("length_a", "length_b", "length_c", "angle_alpha", "angle_beta", "angle_gamma")
    lines.extend(f"_cell_{k} {v:.16g}" for k, v in zip(keys, parameters))
    lines += ["_space_group_name_H-M_alt 'P 1'", "_space_group_IT_number 1"]
    if model.formula_units is not None:
        lines.append(f"_cell_formula_units_Z {model.formula_units}")
    lines += ["loop_", "_space_group_symop_id", "_space_group_symop_operation_xyz", "1 'x,y,z'",
              "loop_", "_atom_site_label", "_atom_site_type_symbol", "_atom_site_fract_x",
              "_atom_site_fract_y", "_atom_site_fract_z", "_atom_site_occupancy", "_atom_site_U_iso_or_equiv"]
    for site in model.sites:
        xyz = " ".join(f"{v:.16g}" for v in site.frac)
        u = "?" if site.u_iso is None else f"{site.u_iso:.16g}"
        lines.append(f"{site.label} {site.species} {xyz} {site.occupancy:.16g} {u}")
    out = Path(path)
    out.write_text("\n".join(lines) + "\n")
    return out
