"""在整个架构中的位置:P 低时她说得更磕绊(蓝图 §7)。

band → 变换族决策表全确定;变体选择键 = h_byte(key) % len(admissible)。
severity 单调(A6):B4=0 <= B3 <= B2 <= B1 <= B0。

**已知简化(交审须知)**:蓝图 §7.1 的 B3 档"仅 intensity>=2 的句"才给
省略变体——但 plan() 签名(蓝图 §7.2)本身不带 intensity 入参,无处收纳
该条件而不破签名;本实现对全部 B3 句一视同仁提供省略变体,不按
intensity 差异化。此简化不影响 A6 severity 单调性质与幂等守卫,只是
B3 档变体池比蓝图文字描述略宽,已如实记录、留待红队核可否放行。
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import determinism
from . import marks

SEVERITY: dict[str, int] = {"B4": 0, "B3": 1, "B2": 2, "B1": 3, "B0": 4}


@dataclass(frozen=True)
class ProsodyPlan:
    text: str
    tags: tuple[str, ...]


def _variants_for(band: str, canonical: str) -> tuple[tuple[str, str], ...]:
    if band == "B4":
        return (marks.identity(canonical),)
    if band == "B3":
        return (marks.identity(canonical), marks.append_ellipsis(canonical))
    if band == "B2":
        return (
            marks.identity(canonical),
            marks.insert_breath(canonical),
            marks.append_ellipsis(canonical),
        )
    if band == "B1":
        return (
            marks.insert_breath(canonical),
            marks.stutter_first(canonical),
            marks.half_stop(canonical),
        )
    # B0
    return (marks.half_stop(canonical), marks.identity(canonical))


def plan(
    canonical: str, band: str, occasion: str, *, key: str, hint: str = ""
) -> ProsodyPlan:  # noqa: ARG001
    """occasion 目前不参与分支(变换族只按 band 分派),保留入参位以对齐

    蓝图 §7.2 签名与未来按场合定制变换族的扩展点。
    """
    if SEVERITY.get(band, 0) == 0 or marks.is_idempotent_skip(canonical, hint):
        return ProsodyPlan(text=canonical, tags=())
    variants = _variants_for(band, canonical)
    if not variants:
        return ProsodyPlan(text=canonical, tags=())
    idx = determinism.h_byte(key) % len(variants)
    text, tag = variants[idx]
    return ProsodyPlan(text=text, tags=(tag,) if tag else ())


def prosody_key(sid: str, day_key: str, occasion: str, canonical: str) -> str:
    """§10 registry 的 prosody 键格式:{sid}|{day_key}|pros|{occ}|{digest8}。"""
    digest = determinism.text_digest(canonical)
    return f"{sid}|{day_key}|pros|{occasion}|{digest}"


__all__ = ["ProsodyPlan", "SEVERITY", "plan", "prosody_key"]
