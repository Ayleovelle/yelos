"""circadian/phase_learn.py 在整个架构中的位置:用户作息相位在线学习(维一)。

学的只有**一件事**:用户交互时刻(0..1439 分钟)的圆均值 μ 与集中度 κ
(合成向量长,0..1)。**边界(总纲 §2.3 明文,禁 ToM 越界)**:不建模内容、
不建模情绪、不推断状态——输入面只收分钟整数(T-CIR-02 断言签名)。

在线更新用指数加权的圆统计:每次观测把该分钟的单位向量以学习率 η
(随样本数衰减,`η = 1/(n_obs+1)`)融入当前合成向量;`n_obs < 14` 时不
启用相位偏移(冷启动用配置基线相位,offset=0)。纯函数,零 random/
time.time()(AX-7);状态由调用方持久化(binding.intrinsic_field.circadian)。

`PhaseLearner`(本模块的圆统计机制整体)是 [TH-3](昼夜锁相)的实现体:
"平稳作息输入下收敛到真相位邻域"**仍是猜想**(合成数据测试 T-CIR-02
支持,未经证明),实现不得引用 TH-3 为决策依据(律四)。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .forcing import MINUTES_PER_DAY

MIN_OBS_FOR_OFFSET = 14

# 先验基线相位(配置未学习前的默认假设:典型互动集中在晚间 22:00 附近),
# 相位偏移 = 学到的圆均值相对此先验的有符号最短弧距(分钟,-720..720)。
DEFAULT_MU_MIN = 22 * 60


@dataclass(frozen=True)
class PhaseLearnerState:
    mu_min: int = 0
    kappa: float = 0.0
    n_obs: int = 0

    def to_dict(self) -> dict:
        return {"mu_min": self.mu_min, "kappa": self.kappa, "n_obs": self.n_obs}

    @classmethod
    def from_dict(cls, d: dict | None) -> "PhaseLearnerState":
        if not d:
            return cls()
        return cls(
            mu_min=int(d.get("mu_min", 0)) % MINUTES_PER_DAY,
            kappa=max(0.0, min(1.0, float(d.get("kappa", 0.0)))),
            n_obs=max(0, int(d.get("n_obs", 0))),
        )


def _to_vec(mu_min: float, kappa: float) -> tuple[float, float]:
    theta = 2.0 * math.pi * mu_min / MINUTES_PER_DAY
    return kappa * math.cos(theta), kappa * math.sin(theta)


def _from_vec(x: float, y: float) -> tuple[int, float]:
    kappa = math.hypot(x, y)
    if kappa == 0.0:
        return 0, 0.0
    theta = math.atan2(y, x) % (2.0 * math.pi)
    mu_min = int(round(theta * MINUTES_PER_DAY / (2.0 * math.pi))) % MINUTES_PER_DAY
    return mu_min, min(1.0, kappa)


def update(state: PhaseLearnerState, interaction_minute: int) -> PhaseLearnerState:
    """把一次用户交互时刻(分钟整数)融入圆统计。输入面只收 minutes(T-CIR-02)。"""
    minute = int(interaction_minute) % MINUTES_PER_DAY
    cx, cy = _to_vec(state.mu_min, state.kappa)
    theta = 2.0 * math.pi * minute / MINUTES_PER_DAY
    ux, uy = math.cos(theta), math.sin(theta)
    eta = 1.0 / (state.n_obs + 1)
    nx = cx + eta * (ux - cx)
    ny = cy + eta * (uy - cy)
    mu_min, kappa = _from_vec(nx, ny)
    return PhaseLearnerState(mu_min=mu_min, kappa=kappa, n_obs=state.n_obs + 1)


def phase_offset_minutes(state: PhaseLearnerState) -> float:
    """产出:仅作 forcing() 的相位偏移。n_obs 不足冷启动阈值 → 0(不启用)。

    偏移 = 学到的圆均值相对 `DEFAULT_MU_MIN` 先验的有符号最短弧距
    (-720..720 分钟),而非绝对 mu_min——避免把整条 forcing 基线相位
    平移到与默认设计脱节的位置。
    """
    if state.n_obs < MIN_OBS_FOR_OFFSET:
        return 0.0
    delta = (state.mu_min - DEFAULT_MU_MIN) % MINUTES_PER_DAY
    if delta > MINUTES_PER_DAY / 2:
        delta -= MINUTES_PER_DAY
    return float(delta)


__all__ = [
    "MIN_OBS_FOR_OFFSET",
    "DEFAULT_MU_MIN",
    "PhaseLearnerState",
    "update",
    "phase_offset_minutes",
]
