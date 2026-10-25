"""Core edge/regression tests. Independent benchmark tests live separately."""

from fractions import Fraction
from itertools import product
import json
import math

import numpy as np
import pytest

from crystalbench import (
    ContractError, ExclusionEdge, Site, SourceModel, cell_from_parameters,
    cell_parameters, expand, model_from_dict, quotient_representatives,
    scattering_contract, structure_factors, validate_configuration, write_cif,
)


def source():
    return SourceModel(cell=((3., 0., 0.), (.7, 4., 0.), (.2, .3, 5.)),
                       sites=(Site("A1", "Na", (.13, .27, .39), .5, .01),
                              Site("B1", "Cl", (.62, .11, .83), 1., .02)),
                       nominal_composition={"Na": 1, "Cl": 1}, source_id="synthetic:test")


def test_triclinic_metric_roundtrip():
    cell = cell_from_parameters(4.1, 5.2, 6.3, 77.5, 83.2, 104.7)
    assert cell_parameters(cell) == pytest.approx((4.1, 5.2, 6.3, 77.5, 83.2, 104.7))


def test_near_parallel_admitted_cell_preserves_nonzero_cif_angle(tmp_path):
    cell = ((1., 0., 0.), (1., 1e-10, 0.), (0., 0., 1.))
    s = SourceModel(cell, (Site("Na1", "Na", (0., 0., 0.), 1.),))
    params = cell_parameters(s.cell)
    assert params[5] == pytest.approx(math.degrees(math.atan2(1e-10, 1.)), rel=1e-14)
    assert params[5] > 0
    restored = np.asarray(cell_from_parameters(*params))
    assert np.linalg.det(restored) == pytest.approx(1e-10, rel=1e-13)
    text = write_cif(s, tmp_path/"near_parallel.cif").read_text()
    gamma = float(next(line.split()[1] for line in text.splitlines() if line.startswith("_cell_angle_gamma ")))
    assert gamma > 0


@pytest.mark.parametrize("h", [
    ((2, 0, 0), (0, 3, 0), (0, 0, 1)),
    ((2, 1, 0), (0, 2, 0), (0, 0, 1)),
    ((1, 2, 0), (0, 1, 1), (1, 0, 2)),
    ((0, 1, 0), (-1, 0, 0), (0, 0, 3)),
    ((1, 2, 0), (0, 1, 0), (0, 0, 1)),
])
def test_general_transform_repeat_amplitudes(h):
    original = source()
    extended = expand(original, h)
    n = round(np.linalg.det(h))
    assert len(extended.translations) == n
    assert len(extended.sites) == n * len(original.sites)
    assert extended.volume == pytest.approx(n*original.volume)
    assert extended.source_composition == {"Na": .5, "Cl": 1.}
    assert extended.composition == {"Na": .5*n, "Cl": float(n)}
    parent_h = np.array(list(product(range(-2, 3), repeat=3)))
    child_h = parent_h @ np.asarray(h).T
    # Isotropic damping exercises physical reciprocal-metric consistency.
    f = {"Na": 3 + .2j, "Cl": 4 - .5j}
    fp = structure_factors(original, parent_h, f, adp_mode="isotropic")
    fc = structure_factors(extended, child_h, f, adp_mode="isotropic")
    assert np.max(np.abs(fc-n*fp)) < 1e-11
    assert model_from_dict(json.loads(json.dumps(extended.to_dict()))).to_dict() == extended.to_dict()


def test_unimodular_shear_preserves_full_basis():
    h = ((1, 3, -2), (0, 1, 1), (0, 0, 1))
    assert quotient_representatives(h) == ((0, 0, 0),)
    x = expand(source(), h)
    assert len(x.sites) == 2
    assert x.composition == source().composition


def test_periodic_exclusion_crosses_boundary():
    s = SourceModel(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                    (Site("Na1", "Na", (0, 0, 0), .5),))
    h = ((4, 0, 0), (0, 1, 0), (0, 0, 1))
    edge = ExclusionEdge(0, 0, (1, 0, 0), "synthetic nearest-neighbour rule")
    good = [[1], [0], [1], [0]]
    result = validate_configuration(s, h, good, exact_counts={"Na": 2}, exclusions=[edge])
    assert result["translated_edges_checked"] == 4
    assert expand(s, h, occupancies=good, exact_counts={"Na": 2}, exclusions=[edge]).composition == {"Na": 2.}
    # Only the boundary 3->0 is occupied on both ends in this pair.
    with pytest.raises(ContractError, match="periodic exclusion"):
        expand(s, h, occupancies=[[1], [0], [0], [1]], exclusions=[edge])


def test_sheared_periodic_exclusion_exact_wrapping():
    s = SourceModel(((1, 0, 0), (.8, .6, 0), (0, 0, 1)),
                    (Site("Na1", "Na", (0, 0, 0), .5),))
    h = ((2, 1, 0), (0, 1, 0), (0, 0, 1))
    assert quotient_representatives(h) == ((0, 0, 0), (1, 0, 0))
    edge = ExclusionEdge(0, 0, (1, 1, 0), "explicit parent translation witness")
    expand(s, h, occupancies=[[1], [0]], exclusions=[edge])
    with pytest.raises(ContractError, match="periodic exclusion"):
        expand(s, h, occupancies=[[1], [1]], exclusions=[edge])


def test_supercell_self_image_exclusion_rejects_occupation():
    s = SourceModel(((1, 0, 0), (0, 1, 0), (0, 0, 1)), (Site("Na1", "Na", (0, 0, 0), .5),))
    edge = ExclusionEdge(0, 0, (2, 0, 0), "declared exclusion against a supercell image")
    with pytest.raises(ContractError, match="periodic exclusion"):
        expand(s, ((2, 0, 0), (0, 1, 0), (0, 0, 1)), occupancies=[[1], [0]], exclusions=[edge])


def test_known_two_site_extinction_and_complex_factors():
    s = SourceModel(((3, 0, 0), (0, 3, 0), (0, 0, 3)),
                    (Site("Na1", "Na", (0, 0, 0), 1), Site("Na2", "Na", (.5, 0, 0), 1)),
                    model_kind="configuration")
    result = structure_factors(s, [[0, 0, 0], [1, 0, 0], [2, 0, 0]], {"Na": 2+1j}, adp_mode="none")
    assert result == pytest.approx([4+2j, 0j, 4+2j], abs=2e-15)
    assert "zero-ADP control" in scattering_contract(adp_mode="none")["adp_assumption"]


def test_integer_bragg_phases_ignore_exact_large_integer_site_translations():
    base = SourceModel(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                       (Site("Na1", "Na", (0, 0, 0), 1), Site("Na2", "Na", (.5, 0, 0), 1)))
    moved = SourceModel(base.cell, (base.sites[0], Site("Na2", "Na", (1e12+.5, -1e12, 0), 1)))
    h = [[1, 0, 0], [-1, 2, 0], [2, 0, 0]]
    expected = structure_factors(base, h, {"Na": 1}, adp_mode="none")
    actual = structure_factors(moved, h, {"Na": 1}, adp_mode="none")
    assert actual == pytest.approx(expected, abs=1e-15)
    assert abs(actual[0])**2 < 1e-25
    assert moved.sites[1].frac == (1e12+.5, -1e12, 0)  # Literal source retained.


def test_large_source_offset_supercell_repeat_retains_parity():
    s = SourceModel(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                    (Site("Na1", "Na", (1e12+.5, 0, 0), 1),))
    child = expand(s, ((3, 0, 0), (0, 1, 0), (0, 0, 1)))
    fp = structure_factors(s, [[1, 0, 0]], {"Na": 1}, adp_mode="none")
    fc = structure_factors(child, [[3, 0, 0]], {"Na": 1}, adp_mode="none")
    assert fc == pytest.approx(3*fp, abs=1e-14)


def test_large_source_offsets_preserve_nondiagonal_tile_registration():
    s = SourceModel(((2, 0, 0), (.3, 3, 0), (.1, .2, 4)),
                    (Site("Na1", "Na", (1e12+.5, -1e12+.25, 1e12+.125), .5),
                     Site("Cl1", "Cl", (.25, .5, .75), .5)))
    h = ((3, 1, 0), (0, 2, 1), (0, 0, 1))
    bits = [[1, 0], [0, 1], [1, 1], [0, 0], [0, 1], [1, 0]]
    child = expand(s, h, occupancies=bits, exact_counts={"Na": 3, "Cl": 3})
    # Independently written exact inverse for this fixed triangular transform.
    inverse = ((Fraction(1, 3), Fraction(-1, 6), Fraction(1, 6)),
               (Fraction(0), Fraction(1, 2), Fraction(-1, 2)),
               (Fraction(0), Fraction(0), Fraction(1)))
    for index, site in enumerate(child.sites):
        tile, parent = divmod(index, len(s.sites))
        coordinates = [Fraction(s.sites[parent].frac[k]) + child.translations[tile][k] for k in range(3)]
        expected = [float(sum(coordinates[k]*inverse[k][j] for k in range(3)) % 1) for j in range(3)]
        assert site.frac == pytest.approx(expected, abs=2e-15)
        assert child.source_indices[index] == parent
        assert child.tile_indices[index] == tile
        assert site.occupancy == bits[tile][parent]
    assert child.source.sites[0].frac == s.sites[0].frac
    assert model_from_dict(child.to_dict()).to_dict() == child.to_dict()


def test_noninteger_query_keeps_finite_motif_coordinates():
    a = SourceModel(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                    (Site("Na1", "Na", (0, 0, 0), 1), Site("Na2", "Na", (.5, 0, 0), 1)))
    b = SourceModel(a.cell, (a.sites[0], Site("Na2", "Na", (1.5, 0, 0), 1)))
    # Mixed integer/noninteger rows exercise both paths in one invocation.
    h = [[1, 0, 0], [.25, 0, 0]]
    fa = structure_factors(a, h, {"Na": 1}, adp_mode="none")
    fb = structure_factors(b, h, {"Na": 1}, adp_mode="none")
    assert fa[0] == pytest.approx(fb[0], abs=1e-15)
    assert abs(fa[1])**2 == pytest.approx(2+math.sqrt(2))
    assert abs(fb[1])**2 == pytest.approx(2-math.sqrt(2))


def test_isotropic_damping_analytic_single_site():
    s = SourceModel(((2, 0, 0), (0, 3, 0), (0, 0, 4)), (Site("Na1", "Na", (0, 0, 0), .5, .02),))
    h = np.array([[1, 2, 3]])
    expected = 3*.5*math.exp(-2*math.pi**2*.02*((1/2)**2+(2/3)**2+(3/4)**2))
    assert structure_factors(s, h, {"Na": 3}, adp_mode="isotropic")[0] == pytest.approx(expected)


def test_cif_retains_empty_sites_and_unknown_u(tmp_path):
    s = SourceModel(((2, 0, 0), (0, 3, 0), (0, 0, 4)),
                    (Site("Na1", "Na", (.1, .2, .3), 0), Site("Cl1", "Cl", (.4, .5, .6), 1, .01)))
    p = write_cif(s, tmp_path/"test.cif")
    text = p.read_text()
    assert "Na1 Na 0.1 0.2 0.3 0 ?" in text
    assert "_space_group_IT_number 1" in text
    assert "0.01" in text


def test_source_json_preserves_unknowns_and_nominal_distinction():
    s = source()
    d = s.to_dict()
    assert d["source_weighted_composition"] != d["nominal_composition"]
    assert s.formula_units is None and s.composition_per_formula_unit is None
    assert model_from_dict(json.loads(json.dumps(d))).to_dict() == d


def test_constant_count_not_inferred_from_marginals():
    with pytest.raises(ContractError, match="average"):
        expand(source(), ((2, 0, 0), (0, 1, 0), (0, 0, 1)), exact_counts={"Na": 1})


def test_distinct_occupation_pair_changes_satellites():
    s = SourceModel(((3, 0, 0), (0, 3, 0), (0, 0, 3)), (Site("Na1", "Na", (0, 0, 0), .5),))
    h = ((4, 0, 0), (0, 1, 0), (0, 0, 1))
    a = expand(s, h, occupancies=[[1], [1], [0], [0]], exact_counts={"Na": 2})
    b = expand(s, h, occupancies=[[1], [0], [1], [0]], exact_counts={"Na": 2})
    fa = structure_factors(a, [[1, 0, 0]], {"Na": 1}, adp_mode="none")
    fb = structure_factors(b, [[1, 0, 0]], {"Na": 1}, adp_mode="none")
    assert abs(fa[0])**2 == pytest.approx(2)
    assert abs(fb[0])**2 < 1e-28
    assert a.composition == b.composition
