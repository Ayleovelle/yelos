"""policies 子包:四套裁决策略 + 注册表(arbiter_BLUEPRINT §3)。"""

from __future__ import annotations

from .base import PolicyProtocol, REGISTRY, register
from .conservative import CONSERVATIVE_POLICY, ConservativePolicy
from .duel import DUEL_POLICY, DuelPolicy, DuelResult
from .smooth import SMOOTH_POLICY, SmoothPolicy
from .table import TABLE_POLICY, TablePolicy

__all__ = [
    "PolicyProtocol",
    "REGISTRY",
    "register",
    "TablePolicy",
    "TABLE_POLICY",
    "SmoothPolicy",
    "SMOOTH_POLICY",
    "ConservativePolicy",
    "CONSERVATIVE_POLICY",
    "DuelPolicy",
    "DUEL_POLICY",
    "DuelResult",
]
