"""hysteresis/signals.py 在整个架构中的位置。

outcome 代理信号:从时延/长度/沉默三个粗代理算出 r ∈ [-1,1]。N9 铁律:
只碰时间戳与长度,零原文——本文件从头到尾没有出现过 draft/text 字样,
运行时断言见 tests/arbiter/test_hysteresis.py 的字段白名单检查。

诚实条款(arbiter_BLUEPRINT §5.1 附注):r 是**代理信号**,测的是"介入后
你的回应形态",不是你的真实感受;它可能错,所以步长小、有共识门、有
硬界(updater.py)——错也错不远,这一条与 shadow 的"模拟不是读心"同宗。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

_RING_CAP = 32


@dataclass(frozen=True)
class PendingOutcome:
    """介入(σ>=1)发生后登记的待结算账;binding 内至多 1 条(不应期保证
    介入稀疏,新介入顶替未决旧账并按沉默结算,arbiter_BLUEPRINT §5.1)。
    """

    sid: str
    turn_id: str
    kind: str  # "SWALLOW" | "REPLACE" | "TRIM_hold" | "TRIM_express"
    ts_i: float


def kind_for_intervention(action: str, verdict_kind: str) -> str | None:
    """把 (action, verdict.kind) 归一到 §5.4 符号映射表用的 kind 桶。

    PASS 不归因(非介入);仅 SWALLOW/REPLACE/TRIM 三类且 TRIM 按
    action 细分为 hold/express 两支(其余 action 的 TRIM 目前不产生,
    但为前向兼容归入 None,不参与 sign_map)。
    """
    if verdict_kind == "SWALLOW":
        return "SWALLOW"
    if verdict_kind == "REPLACE":
        return "REPLACE"
    if verdict_kind == "TRIM":
        if action == "hold":
            return "TRIM_hold"
        if action == "express":
            return "TRIM_express"
        return None
    return None


def _clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


def med_mad(values: Sequence[float]) -> tuple[float, float]:
    """中位数与绝对中位差(MAD),空序列返回 (0.0, 0.0)。"""
    if not values:
        return 0.0, 0.0
    s = sorted(values)
    n = len(s)
    med = s[n // 2] if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    dev = sorted(abs(v - med) for v in s)
    mad = dev[n // 2] if n % 2 == 1 else (dev[n // 2 - 1] + dev[n // 2]) / 2.0
    return med, mad


def compute_r(
    *,
    delta_t: float,
    length: int,
    gaps: Sequence[float],
    lens: Sequence[float],
    silent: bool,
) -> float:
    """§5.1 公式:回得快且长 = 正反馈;沉默 = 温和负反馈(-0.5)。"""
    if silent:
        return -0.5
    eps = 1e-6
    med_g, mad_g = med_mad(gaps)
    med_l, mad_l = med_mad(lens)
    latency_u = _clip((delta_t - med_g) / (mad_g + eps), -3.0, 3.0) / 3.0
    length_u = _clip((length - med_l) / (mad_l + eps), -3.0, 3.0) / 3.0
    r = _clip(0.5 * length_u - 0.5 * latency_u, -1.0, 1.0)
    return r


@dataclass
class SessionSignalState:
    """per-session 的环形缓冲 + 待决账(binding 内持久化块的运行态镜像)。

    只存秒数与字符数(N9 的结构性满足);cap=32,超出丢最旧。
    """

    gaps: list = field(default_factory=list)
    lens: list = field(default_factory=list)
    pending: PendingOutcome | None = None

    def push_gap(self, seconds: float) -> None:
        self.gaps.append(seconds)
        if len(self.gaps) > _RING_CAP:
            self.gaps.pop(0)

    def push_len(self, chars: int) -> None:
        self.lens.append(float(chars))
        if len(self.lens) > _RING_CAP:
            self.lens.pop(0)
