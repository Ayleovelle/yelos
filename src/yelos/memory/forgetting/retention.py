"""retention.py 在架构中的位置。

艾宾浩斯保持函数两族(MEM-A1)+ 复述增益(MEM-A2)+ 有界性(MEM-T1)。
唯一动力学核心:R(dt, S) 对 dt 严格单调不增,R(0,S)=1;rehearse() 只在
命中访问时调用(MEM-A2),S 单调不减且封顶 S_CAP(MEM-T1)。

零 time.time()/random——dt/S 全部由调用方(recall/l3)传入。
"""

from __future__ import annotations

import math
from typing import Protocol

TAU = 86400.0  # 时间尺度:1 日
BETA = 0.8  # PowRetention 重尾指数
S_CAP = 64.0  # 复述增益上限(MEM-T1)


class RetentionFamily(Protocol):
    name: str

    def R(self, dt: float, S: float) -> float: ...


class ExpRetention:
    """指数遗忘:R = exp(-dt/(S*TAU))。默认族(参数最少,S 语义直白,M9)。"""

    name = "exp"

    def R(self, dt: float, S: float) -> float:
        dt = max(0.0, dt)
        s = max(S, 1e-9)
        return math.exp(-dt / (s * TAU))


class PowRetention:
    """幂律遗忘(Wixted):R = (1+dt/(S*TAU))**(-BETA)。旧忆更难死透,重尾。"""

    name = "pow"

    def R(self, dt: float, S: float) -> float:
        dt = max(0.0, dt)
        s = max(S, 1e-9)
        return (1.0 + dt / (s * TAU)) ** (-BETA)


_FAMILIES: dict[str, RetentionFamily] = {
    "exp": ExpRetention(),
    "pow": PowRetention(),
}


def get_family(name: str) -> RetentionFamily:
    """按配置键取族;未知名回退 exp(保守默认,不 raise)。"""
    return _FAMILIES.get(name, _FAMILIES["exp"])


def rehearse(S: float, R_now: float, g: float = 0.6, s_cap: float = S_CAP) -> float:
    """复述增益(MEM-A2):S' = min(S*(1+g*(1-R_now)), S_CAP)。

    只在被想起(recall 命中进入 top-k)时调用;越是快忘时被想起,巩固越强。
    单调不减:g*(1-R_now) >= 0 恒成立(R_now ∈ (0,1])。
    """
    g = max(0.0, g)
    gain = 1.0 + g * (1.0 - max(0.0, min(1.0, R_now)))
    return min(S * gain, s_cap)
