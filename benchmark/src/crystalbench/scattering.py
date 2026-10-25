"""Kinematic complex amplitudes with explicit caller-provided scattering factors."""

from __future__ import annotations

from typing import Any, Mapping, Sequence
import numpy as np

from .model import ContractError, SourceModel

MAX_PHASE_ABSOLUTE_SUM = 1e6


def scattering_contract(*, adp_mode: str) -> dict[str, Any]:
    if adp_mode not in {"none", "isotropic"}:
        raise ContractError("adp_mode must explicitly be none or isotropic")
    return {"observable": "kinematic complex amplitude F(h)",
            "phase_convention": "exp(+2*pi*i*frac.dot(h))",
            "phase_evaluation": {
                "integer_Bragg_rows": "reduce coordinates modulo one; preserve stored source literals",
                "noninteger_rows": "literal-coordinate finite motif; no coordinate reduction",
                "phase_cycles": "reduce modulo one after bounded dot product",
                "maximum_absolute_term_sum_cycles": MAX_PHASE_ABSOLUTE_SUM,
            },
            "reciprocal_units": "cycles per angstrom; h in current-cell reciprocal coordinates",
            "normalization": "none: explicit sum over supplied sites",
            "factor_contract": "caller-supplied complex factors, excluding occupancy and ADP",
            "adp_mode": adp_mode,
            "adp_assumption": "all ADPs deliberately neglected (zero-ADP control)" if adp_mode == "none"
                              else "isotropic exp(-2*pi^2*U_iso*|g|^2); all U_iso known",
            "not_included": ["powder multiplicity", "Lorentz/polarization", "instrument response",
                             "absorption", "phase scale", "ensemble intensity averaging"]}


def structure_factors(model: SourceModel, hkl: Sequence[Sequence[float]],
                      factors: Mapping[str, Any] | Sequence[Any], *, adp_mode: str) -> np.ndarray:
    """Return F, not |F|²; same caller/evaluator can compare representations.

    factors is either species -> complex scalar/length-n_reflections array,
    length-n_sites complex array, or (n_reflections,n_sites) complex array.
    The caller explicitly chooses chemical tables and anomalous conventions.
    Average models calculate mean-density amplitude, not mean intensity.
    Integer Bragg rows evaluate the periodic coordinates modulo one. Noninteger
    rows use the literal finite motif, with a declared phase-accuracy guard.
    """
    scattering_contract(adp_mode=adp_mode)
    h = np.asarray(hkl, dtype=float)
    if h.ndim != 2 or h.shape[1] != 3 or not np.all(np.isfinite(h)):
        raise ContractError("hkl must be a finite (n_reflections,3) array")
    nref, nsites = len(h), len(model.sites)
    if isinstance(factors, Mapping):
        columns = []
        for site in model.sites:
            if site.species not in factors:
                raise ContractError(f"missing explicit factor for species {site.species}")
            value = np.asarray(factors[site.species], dtype=complex)
            if value.ndim == 0:
                columns.append(np.full(nref, value.item(), dtype=complex))
            elif value.shape == (nref,):
                columns.append(value)
            else:
                raise ContractError("species factor must be a scalar or one value per reflection")
        amplitudes = np.stack(columns, axis=1)
    else:
        amplitudes = np.asarray(factors, dtype=complex)
        if amplitudes.shape == (nsites,):
            amplitudes = np.broadcast_to(amplitudes, (nref, nsites))
        elif amplitudes.shape != (nref, nsites):
            raise ContractError("site factors must have shape (n_sites,) or (n_reflections,n_sites)")
    if not np.all(np.isfinite(amplitudes)):
        raise ContractError("all scattering factors must be finite")
    frac = np.asarray([s.frac for s in model.sites])
    occupancy = np.asarray([s.occupancy for s in model.sites])
    try:
        with np.errstate(over="raise", invalid="raise"):
            # Reducing fractional coordinates preserves phases only for integer
            # reciprocal rows. It must not silently change finite-motif queries.
            integer_rows = np.all(h == np.rint(h), axis=1)
            cycles = np.empty((nref, nsites), dtype=float)
            for selected, coordinates in ((integer_rows, np.remainder(frac, 1.)),
                                          (~integer_rows, frac)):
                if not np.any(selected):
                    continue
                rows = h[selected]
                absolute_sum = np.abs(rows) @ np.abs(coordinates).T
                if not np.all(np.isfinite(absolute_sum)) or np.any(absolute_sum > MAX_PHASE_ABSOLUTE_SUM):
                    raise ContractError("phase absolute-term sum exceeds the supported 1e6-cycle numerical bound")
                cycles[selected] = rows @ coordinates.T
            phase = np.exp(2j*np.pi*np.remainder(cycles, 1.))
            terms = amplitudes * occupancy[None, :] * phase
            if adp_mode == "isotropic":
                if any(s.u_iso is None for s in model.sites):
                    raise ContractError("isotropic scattering requires every U_iso; unknown is not zero")
                g = h @ np.linalg.inv(np.asarray(model.cell)).T
                g2 = np.sum(g*g, axis=1)
                u = np.asarray([s.u_iso for s in model.sites])
                terms *= np.exp(-2*np.pi**2 * g2[:, None] * u[None, :])
            result = np.sum(terms, axis=1)
    except FloatingPointError as exc:
        raise ContractError("scattering calculation exceeded finite floating-point range") from exc
    if not np.all(np.isfinite(result)):
        raise ContractError("scattering calculation produced a nonfinite amplitude")
    return result
