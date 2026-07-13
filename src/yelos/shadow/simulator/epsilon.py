"""epsilon.py 在整个架构中的位置:SHTOM-A5 扰动来源公理的**唯一实现地**
(蓝图 §4.2)。ε_t 不是配置常数,是观测量的确定性函数——本文件是全包唯一
允许写这条公式的地方,其余文件一律调用 `compute_epsilon`,不得另行拼算。

```
ε_t = clip( λ · σ_t , ε_lo , ε_hi )
σ_t = w_obs · σ_obs(t) + w_base · σ_family(t)
σ_obs(t)    = 三通道(pressure/warmth/damage)观测值滚动标准差的均值(EWMA 方差开方)
σ_family(t) = 三通道基线族离散度(day/week/month 极差归一)的 max
```

λ/ε_lo/ε_hi/w_obs/w_base 是"登记进 evolution genome 的白名单参数"(蓝图
§4.2);genome 注册表接线是 W5 任务,本波先把它们落成模块常量 + 函数关键字
参数,预留 override 位。

扰动方向由哈希族确定性生成,键型 `shadow_eps:{sid}:{day_key}:{k}`——**本键
型应登记进 `yelos.primal.determinism.KEY_REGISTRY`**;本任务"只建新文件"的
施工纪律下不编辑 `primal/determinism.py`,故该登记动作记入模块交付说明,
留作后续跨模块 PR(与 A5 测试的可回放性不冲突:键格式已在此固定注释,任何
人补登记时逐字照抄即可,不影响本模块行为)。哈希函数本身直接复用
`primal.determinism.h_byte`(primal 是全平台哈希唯一落点,cross-import 允许,
仅登记动作留待后续)。
"""

from __future__ import annotations

from yelos.primal.determinism import h_byte

# --- A5 白名单参数(genome-mutable 候选,W5 前先做模块常量)------------------

DEFAULT_LAMBDA = 0.5
DEFAULT_EPS_LO = 0.02
DEFAULT_EPS_HI = 0.25
DEFAULT_W_OBS = 0.6
DEFAULT_W_BASE = 0.4

_ENGINE_CHANNELS = ("pressure", "warmth", "damage")


def compute_sigma_obs(ewma_vars: dict[str, float]) -> float:
    """三通道 EWMA 方差开方后取均值(观测滚动标准差的聚合)。"""
    vals = [
        max(0.0, float(ewma_vars.get(ch, 0.0) or 0.0)) ** 0.5 for ch in _ENGINE_CHANNELS
    ]
    return sum(vals) / len(vals) if vals else 0.0


def compute_sigma_family(dispersions: dict[str, float]) -> float:
    """三通道基线族离散度取 max(§5"为什么是 max"同款保守聚合:任一通道乱,
    就该把不确定度算高,不能被稳定通道平均掉)。
    """
    vals = [
        float(dispersions.get(ch, 0.0) or 0.0)
        for ch in _ENGINE_CHANNELS
        if ch in dispersions
    ]
    return max(vals) if vals else 0.0


def compute_epsilon(
    sigma_obs: float,
    sigma_family: float,
    *,
    lam: float = DEFAULT_LAMBDA,
    eps_lo: float = DEFAULT_EPS_LO,
    eps_hi: float = DEFAULT_EPS_HI,
    w_obs: float = DEFAULT_W_OBS,
    w_base: float = DEFAULT_W_BASE,
    epsilon_override: float | None = None,
) -> float:
    """[SHTOM-A5] ε_t 唯一公式。

    `epsilon_override` **仅供测试**注入固定 ε(蓝图 §4.2:"测试专用入口…
    不给部署者旋钮")——生产组合根(`shadow/__init__.py::build_shadow_system`)
    不会读取任何配置键来填这个参数,只有测试直接调用本函数时才会传入。
    """
    if epsilon_override is not None:
        return max(eps_lo, min(eps_hi, epsilon_override))
    sigma_t = w_obs * sigma_obs + w_base * sigma_family
    return max(eps_lo, min(eps_hi, lam * sigma_t))


def perturb_direction(sid: str, day_key: str, k: int) -> int:
    """[SHTOM-A5] 扰动方向:哈希族确定性生成,同键同向,全程可回放。

    键型 `shadow_eps:{sid}:{day_key}:{k}`(见本文件模块 docstring 的登记
    说明)。返回 `+1` 或 `-1`。
    """
    key = f"shadow_eps:{sid}:{day_key}:{k}"
    return 1 if h_byte(key) % 2 == 0 else -1


__all__ = [
    "DEFAULT_LAMBDA",
    "DEFAULT_EPS_LO",
    "DEFAULT_EPS_HI",
    "DEFAULT_W_OBS",
    "DEFAULT_W_BASE",
    "compute_sigma_obs",
    "compute_sigma_family",
    "compute_epsilon",
    "perturb_direction",
]
