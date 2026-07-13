"""scar.py 在整个架构中的位置:[SHTOM-A7/T2] 疤痕敏感化(蓝图 §8)。

```
y=1(真阳): beta_c <- max(beta_lo, beta_c - delta_hit)     # delta_hit=0.01,更敏感
y=0(假阳): beta_c <- min(beta_hi, beta_c + delta_miss)    # delta_miss=0.02,习惯化(升更快:狼来了代价高)
界: beta ∈ [-0.10, +0.15];th_eff 附加安全域断言(th_eff >= 触发阈 * 0.5 恒成立)
```

不衰减、不遗忘(疤痕语义:与 memory 艾宾浩斯刻意不同——疤不是记忆,是组织学
改变);seal/incarnation 随 record 整体清零(重生不带前世疤,`binding_v2.
reset_for_new_incarnation` 已覆盖,本文件不重复实现)。
"""

from __future__ import annotations

from typing import Any

BETA_LO = -0.10
BETA_HI = 0.15
DELTA_HIT = 0.01
DELTA_MISS = 0.02


def update_beta(
    state: dict[str, Any],
    y: int,
    *,
    delta_hit: float = DELTA_HIT,
    delta_miss: float = DELTA_MISS,
    beta_lo: float = BETA_LO,
    beta_hi: float = BETA_HI,
) -> dict[str, Any]:
    """[SHTOM-A7] 单步更新(原地改 `state`,也返回同一对象方便链式调用)。"""
    beta = float(state.get("beta", 0.0))
    if y == 1:
        beta = max(beta_lo, beta - delta_hit)
        state["hits"] = int(state.get("hits", 0)) + 1
    else:
        beta = min(beta_hi, beta + delta_miss)
        state["misses"] = int(state.get("misses", 0)) + 1
    state["beta"] = beta
    return state


def th_eff_for(th_base: float, beta_c: float, *, safety_ratio: float = 0.5) -> float:
    """`th_eff = th_base + beta_c`,附加安全域下限(T2 安全域断言)。"""
    raw = th_base + beta_c
    floor = th_base * safety_ratio
    return max(raw, floor)


def compute_th_eff_table(
    th_base: dict[str, float], sensitization: dict[str, dict[str, Any]]
) -> dict[str, float]:
    """批量算四检测器当前的 `th_eff` 表(orchestrator 消费点)。"""
    out: dict[str, float] = {}
    for ctype, base in th_base.items():
        beta_c = float((sensitization.get(ctype) or {}).get("beta", 0.0))
        out[ctype] = th_eff_for(base, beta_c)
    return out


__all__ = [
    "BETA_LO",
    "BETA_HI",
    "DELTA_HIT",
    "DELTA_MISS",
    "update_beta",
    "th_eff_for",
    "compute_th_eff_table",
]
