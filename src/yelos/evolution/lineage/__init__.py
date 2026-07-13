"""lineage/ 在整个架构中的位置:追加式谱系账本(蓝图 §2)。"""

from __future__ import annotations

from .ledger import (
    ACCEPTED,
    CORRUPTION,
    REJECTED_FITNESS,
    REJECTED_GUARD_PROPERTY,
    REJECTED_GUARD_STATIC,
    ROLLBACK,
    SKIPPED,
    LineageIntegrityError,
    LineageLedger,
)
from .records import ChangeEntry, LineageRecord

__all__ = [
    "LineageLedger",
    "LineageIntegrityError",
    "LineageRecord",
    "ChangeEntry",
    "ACCEPTED",
    "REJECTED_GUARD_STATIC",
    "REJECTED_GUARD_PROPERTY",
    "REJECTED_FITNESS",
    "ROLLBACK",
    "SKIPPED",
    "CORRUPTION",
]
