"""rites/ 在整个架构中的位置:仪式集中(finitude_BLUEPRINT §7)——孵化冻结/跃迁通告/送别摘要。"""

from __future__ import annotations

from .epoch_notice import EpochNoticePayload, build_notice
from .farewell import farewell_summary
from .incarnation import AgingSpec, aging_of, expr_p, stamp_aging, validate_params

__all__ = [
    "AgingSpec",
    "stamp_aging",
    "aging_of",
    "validate_params",
    "expr_p",
    "EpochNoticePayload",
    "build_notice",
    "farewell_summary",
]
