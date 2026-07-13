"""genome/ 在整个架构中的位置:基因组注册表包(蓝图 §2)。"""

from __future__ import annotations

from .registry import (
    REGISTRY,
    hatch_genome,
    iron_keys,
    mutable_keys,
    spec_for,
    validate_registry,
)
from .spec import GeneSpec, Genome

__all__ = [
    "GeneSpec",
    "Genome",
    "REGISTRY",
    "mutable_keys",
    "iron_keys",
    "spec_for",
    "hatch_genome",
    "validate_registry",
]
