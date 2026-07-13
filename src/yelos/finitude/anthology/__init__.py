"""anthology/ 在整个架构中的位置:"她的一生"富工件生成器(finitude_BLUEPRINT §6)。"""

from __future__ import annotations

from .assemble import (
    assemble_anthology_v2,
    build_context,
    legacy_assemble,
    write_anthology,
)
from .registry import EXCLUDED, FIELD_REGISTRY, FieldSpec, top_level_covered_keys

__all__ = [
    "FieldSpec",
    "FIELD_REGISTRY",
    "EXCLUDED",
    "top_level_covered_keys",
    "build_context",
    "write_anthology",
    "assemble_anthology_v2",
    "legacy_assemble",
]
