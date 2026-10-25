"""Public synthetic same-count/different-correlation demonstration.

This is an abstract one-dimensional occupation pattern embedded in a cubic
three-dimensional cell. It is not a model of chemical stability or real data.
Run with PYTHONPATH=src python examples/occupation_pair.py.
"""
import json
import numpy as np
from crystalbench import Site, SourceModel, expand, structure_factors, scattering_contract

source = SourceModel(((3., 0., 0.), (0., 3., 0.), (0., 0., 3.)),
                     (Site("Na1", "Na", (0., 0., 0.), .5),),
                     source_id="synthetic:four-cell-occupation-control")
H = ((4, 0, 0), (0, 1, 0), (0, 0, 1))
models = {"paired": expand(source, H, occupancies=[[1], [1], [0], [0]], exact_counts={"Na": 2}),
          "alternating": expand(source, H, occupancies=[[1], [0], [1], [0]], exact_counts={"Na": 2})}
h = np.array([[v, 0, 0] for v in range(-4, 5)])
result = {"source": source.to_dict(), "hkl": h.tolist(), "scattering": scattering_contract(adp_mode="none"),
          "factor_assumption": "unit real scattering factor, not a chemical Na table", "observed_data_used": False}
for name, model in models.items():
    F = structure_factors(model, h, {"Na": 1}, adp_mode="none")
    result[name] = {"composition": model.composition, "intensity": (abs(F)**2).tolist()}
print(json.dumps(result, indent=2))
