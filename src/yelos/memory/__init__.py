"""memory 包在整个架构中的位置。

YELOS 记忆器官(memory_BLUEPRINT v2):L1 情景流水 / L2 自著语义摘要图
(PPMI+截断 SVD)/ L3 自传体主题生命周期状态机;多因子确定性召回;
五张下游供血契约;隐私公理 MEM-A5 执行。对外唯一符号是 ``MemoryFacade``
与 ``contracts`` 里的数据类型(§3.8,session/server 只准触这两处)。
"""

from __future__ import annotations

from .contracts import (
    AffectStamp,
    BaselineContext,
    ConsolidationReport,
    ContinuityFlags,
    EpisodeEvent,
    EVENT_KINDS,
    JobBudget,
    MemoryConfig,
    RecallHit,
    RecallQuery,
    RecallResult,
    SemanticEntry,
    ThemeDigest,
    TopicEvent,
    TopicNode,
)
from .facade import MemoryFacade

__all__ = [
    "MemoryFacade",
    "AffectStamp",
    "BaselineContext",
    "ConsolidationReport",
    "ContinuityFlags",
    "EpisodeEvent",
    "EVENT_KINDS",
    "JobBudget",
    "MemoryConfig",
    "RecallHit",
    "RecallQuery",
    "RecallResult",
    "SemanticEntry",
    "ThemeDigest",
    "TopicEvent",
    "TopicNode",
]
