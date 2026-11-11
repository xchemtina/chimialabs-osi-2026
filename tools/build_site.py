#!/usr/bin/env python3
"""Copy the exact public companion viewer and evidence into the static site."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root / "companion"
target = root / "docs" / "companion"
for directory in ("public", "fixtures/pbso4", "run"):
    src = source / directory
    dst = target / directory
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
for name in ("LICENSE", "NOTICE"):
    shutil.copyfile(root / name, target / name)
(root / "docs" / ".nojekyll").touch()
print("Static viewer and public evidence copied without data transformations.")
