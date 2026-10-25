"""Fail-closed input and lineage checks."""
from dataclasses import replace
import copy

import numpy as np
import pytest

from crystalbench import ContractError, ExclusionEdge, Site, SourceModel, cell_from_parameters, expand, model_from_dict, structure_factors


def model():
    return SourceModel(((1, 0, 0), (0, 1, 0), (0, 0, 1)), (Site("Na1", "Na", (0, 0, 0), .5),))


@pytest.mark.parametrize("occupancy", [-.1, 1.01, float("nan"), float("inf"), True])
def test_invalid_occupancy(occupancy):
    with pytest.raises(ContractError):
        Site("Na1", "Na", (0, 0, 0), occupancy)


@pytest.mark.parametrize("h", [
    [[1.1, 0, 0], [0, 1, 0], [0, 0, 1]],
    [[0, 0, 0], [0, 1, 0], [0, 0, 1]],
    [[-1, 0, 0], [0, 1, 0], [0, 0, 1]],
    [[float("nan"), 0, 0], [0, 1, 0], [0, 0, 1]],
    [[True, 0, 0], [0, 1, 0], [0, 0, 1]],
    [[4097, 0, 0], [0, 1, 0], [0, 0, 1]],
    [[1, 10**8, 0], [0, 1, 0], [0, 0, 1]],
])
def test_invalid_transform(h):
    with pytest.raises(ContractError):
        expand(model(), h)


@pytest.mark.parametrize("cell", [
    ((0, 0, 0), (0, 1, 0), (0, 0, 1)),
    ((-1, 0, 0), (0, 1, 0), (0, 0, 1)),
    ((float("nan"), 0, 0), (0, 1, 0), (0, 0, 1)),
])
def test_invalid_cells(cell):
    with pytest.raises(ContractError):
        replace(model(), cell=cell)


def test_unknown_units_and_fractional_config_rejected():
    with pytest.raises(ContractError):
        replace(model(), length_unit="unknown")
    with pytest.raises(ContractError):
        replace(model(), model_kind="configuration")
    with pytest.raises(ContractError):
        cell_from_parameters(1, 1, 1, 10, 10, 170)


def test_missing_u_never_silently_zero():
    with pytest.raises(ContractError, match="unknown is not zero"):
        structure_factors(model(), [[1, 0, 0]], {"Na": 1}, adp_mode="isotropic")
    with pytest.raises(TypeError):
        structure_factors(model(), [[1, 0, 0]], {"Na": 1})


def test_bad_factors():
    for f in [{}, {"Na": float("nan")}, {"Na": [1, 2]}, [[1, 2]]]:
        with pytest.raises(ContractError):
            structure_factors(model(), [[1, 0, 0]], f, adp_mode="none")


def test_finite_inputs_that_overflow_are_rejected():
    s = SourceModel(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                    (Site("Na1", "Na", (0, 0, 0), 1), Site("Na2", "Na", (0, 0, 0), 1)))
    with pytest.raises(ContractError, match="floating-point"):
        structure_factors(s, [[1, 0, 0]], {"Na": 1e308}, adp_mode="none")


def test_large_noninteger_finite_motif_phase_is_rejected():
    s = replace(model(), sites=(Site("Na1", "Na", (1e12+.5, 0, 0), 1),))
    with pytest.raises(ContractError, match="1e6-cycle"):
        structure_factors(s, [[.25, 0, 0]], {"Na": 1}, adp_mode="none")


def test_large_cancelling_phase_terms_are_rejected_before_dot_product():
    s = replace(model(), sites=(Site("Na1", "Na", (.5, .5, 0), 1),))
    with pytest.raises(ContractError, match="1e6-cycle"):
        structure_factors(s, [[1e8, -1e8, 0]], {"Na": 1}, adp_mode="none")


def test_incompatible_counts_and_nonbinary_decorations():
    h = ((2, 0, 0), (0, 1, 0), (0, 0, 1))
    for bits, counts in [([[1], [0]], {"Na": 2}), ([[.5], [.5]], None), ([[1]], None),
                         ([[1], [0]], {"Cl": 0}), ([[1], [0]], {"Na": 1.2})]:
        with pytest.raises(ContractError):
            expand(model(), h, occupancies=bits, exact_counts=counts)


def test_average_exclusions_not_treated_as_joint_law():
    with pytest.raises(ContractError, match="joint law"):
        expand(model(), np.eye(3, dtype=int), exclusions=[ExclusionEdge(0, 0, (1, 0, 0), "assumption")])


def test_bad_exclusion_witness():
    with pytest.raises(ContractError):
        ExclusionEdge(0, 0, (0, 0, 0), "same site")
    with pytest.raises(ContractError):
        ExclusionEdge(0, 0, (.5, 0, 0), "fractional translation")
    with pytest.raises(ContractError):
        ExclusionEdge(0, 0, (1, 0, 0), "")
    with pytest.raises(ContractError, match="outside"):
        expand(model(), np.eye(3, dtype=int), occupancies=[[0]], exclusions=[ExclusionEdge(0, 1, (0, 0, 0), "invalid index")])


def test_serialized_mapping_tamper_detected():
    x = expand(model(), ((2, 1, 0), (0, 1, 0), (0, 0, 1)))
    for field, bad in [("source_indices", [0, 1]), ("constructed_composition", {"Na": 2.}),
                       ("model_kind", "configuration")]:
        data = copy.deepcopy(x.to_dict())
        data[field] = bad
        with pytest.raises(ContractError):
            model_from_dict(data)
    with pytest.raises(ContractError):
        replace(x, source_indices=(0, 1))


def test_source_dictionary_does_not_repair_composition():
    data = model().to_dict()
    data["source_weighted_composition"] = {"Na": 1}
    with pytest.raises(ContractError):
        model_from_dict(data)
