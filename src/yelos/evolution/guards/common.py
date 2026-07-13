"""guards/common.py 在整个架构中的位置:GuardVerdict 共享 schema(蓝图 §2.1)。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GuardVerdict:
    """守卫判决,机器可读(explain 纪律与 arbiter 同风格)。"""

    ok: bool
    stage: str  # "static" | "property"
    reasons: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["GuardVerdict"]
