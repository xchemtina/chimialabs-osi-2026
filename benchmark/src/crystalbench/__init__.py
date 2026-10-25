"""Small, explicit periodic representation core; no physical model selection."""

from .model import (
    ContractError,
    ExclusionEdge,
    ExpandedModel,
    Site,
    SourceModel,
    cell_from_parameters,
    cell_parameters,
    expand,
    model_from_dict,
    quotient_representatives,
    validate_configuration,
    write_cif,
)
from .scattering import scattering_contract, structure_factors

__all__ = [
    "ContractError", "ExclusionEdge", "ExpandedModel", "Site", "SourceModel",
    "cell_from_parameters", "cell_parameters", "expand", "model_from_dict",
    "quotient_representatives", "validate_configuration", "write_cif",
    "scattering_contract", "structure_factors",
]
