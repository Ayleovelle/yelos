"""policies/duel.py 在整个架构中的位置。

DuelPolicy:理论出身 = 影子评审/分歧采样。并跑 (TablePolicy, SmoothPolicy),
分歧时按 A1 取 σ 较小者(保守者)。

纯函数纪律的落地方式:``decide()`` 本身零 IO——分歧的"脱敏样本落盘"
副作用被拆到 ``evaluate()``(同样是纯函数,只是多返回一份
``DuelResult``);IO 由调用方(pipeline / accounting.duel_corpus,W-6
接线)在拿到 ``DuelResult`` 后自行决定是否落盘。这样 ``PolicyProtocol``
"decide 纯函数,零 IO 零时钟"的契约不被 DuelPolicy 破坏。
"""

from __future__ import annotations

from dataclasses import dataclass

from ...core.arbiter import Verdict
from ..inputs import PolicyInput
from ..lattice import min_sigma_verdict
from .base import register
from .smooth import SMOOTH_POLICY
from .table import TABLE_POLICY


@dataclass(frozen=True)
class DuelResult:
    verdict_a: Verdict  # TablePolicy
    verdict_b: Verdict  # SmoothPolicy
    chosen: Verdict
    diverged: bool


class DuelPolicy:
    policy_id = "duel"

    def evaluate(self, pin: PolicyInput) -> DuelResult:
        va = TABLE_POLICY.decide(pin)
        vb = SMOOTH_POLICY.decide(pin)
        diverged = va.kind != vb.kind
        chosen = min_sigma_verdict(va, vb) if diverged else va
        return DuelResult(verdict_a=va, verdict_b=vb, chosen=chosen, diverged=diverged)

    def decide(self, pin: PolicyInput) -> Verdict:
        return self.evaluate(pin).chosen


DUEL_POLICY = register(DuelPolicy())
