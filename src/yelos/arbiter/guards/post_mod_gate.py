"""guards/post_mod_gate.py 在整个架构中的位置。

唯一的后置降格滤波:调制闸降级 + narrow 收窄,AX:A2 的落点之一
(σ(f(v)) <= σ(v),只降不升)。只用于非 Table 策略(TablePolicy 内核
自含同款语义,跑两遍会漂 reason 字符串,§2.1 管线语义表)。

调制闸公式是 core.arbiter._gate_allows 的差分锁抽出件(同一哈希键型,
N3:hysteresis 不触碰哈希币),额外乘了 gate_scale(γ,仅 SmoothPolicy
经 θ 消费;其余策略 gate_scale 恒 1.0,退化为与冻结内核逐字节等价的
闸公式)。narrow 收窄边界 narrow_p 是幕 V 语义铁域常量(§5.3),不从
θ 来。
"""

from __future__ import annotations

import hashlib

from ...core import sget
from ...core.arbiter import Verdict
from ..inputs import PolicyInput
from ..lattice import sigma_of


def _gate_allows(
    session_id: str, day_key: str, action: str, draft: str, p: float, gate_scale: float
) -> bool:
    draft_h = hashlib.blake2b(draft.encode()).hexdigest()[:8]
    key = f"{session_id}|{day_key}|mod|{action}|{draft_h}"
    b = hashlib.sha256(key.encode()).digest()[0]
    return b / 255 < gate_scale * p / 0.5


def post_mod_gate(verdict: Verdict, pin: PolicyInput) -> Verdict:
    b = pin.base
    p = b.p
    # narrow 收窄:P<=narrow_p 时任何 σ>=1 候选一律折叠为 PASS。
    if p <= pin.params.narrow_p and sigma_of(verdict) >= 1:
        return Verdict("PASS", reason=f"narrow_collapse:{verdict.reason}")
    # SWALLOW 不过调制闸(v0.1 契约:它走阈值下调,§4.4);TRIM/REPLACE 才过闸。
    if verdict.kind in ("TRIM", "REPLACE") and p < 0.5:
        action = (
            str(sget(b.surface, "decision.action", "hold")) if b.surface else "hold"
        )
        if not _gate_allows(
            b.session_id, b.day_key, action, b.draft, p, pin.params.gate_scale
        ):
            return Verdict("PASS", reason=f"mod_gate_downgrade:{verdict.reason}")
    return verdict


post_mod_gate.__name__ = "post_mod_gate"  # type: ignore[attr-defined]
