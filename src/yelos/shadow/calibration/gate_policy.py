"""gate_policy.py 在整个架构中的位置:[SHTOM-T3] 校准 → 闸档位(蓝图 §7.3)。

四档:`observe`(校准史不足,n<12,全放行只记账)/ `normal`(B<=0.20,全放行)/
`tight`(0.20<B<=0.30,strength 需额外 margin 才放行,q 上限 0.7)/
`silent`(B>0.30,inject 仍放行——她仍被扰动;concern 原语与 guidance hint
被拦)。档位迁移带迟滞:**升档(收紧)需连续 2 次窗评**同一候选档才生效,
**降档(放松)即时生效**(防 B 在档边抖动,且"宁可慢一点收紧、快一点放松"
与产品克制方向同向)。
"""

from __future__ import annotations

from typing import Any

_SEVERITY = {"normal": 0, "tight": 1, "silent": 2}

DEFAULT_MIN_N = 12
DEFAULT_NORMAL_MAX = 0.20
DEFAULT_TIGHT_MAX = 0.30

_GATE_EFFECTS: dict[str, dict[str, Any]] = {
    "observe": {"allow_enqueue": True, "q_cap": 1.0, "strength_margin": 0.0},
    "normal": {"allow_enqueue": True, "q_cap": 1.0, "strength_margin": 0.0},
    "tight": {"allow_enqueue": True, "q_cap": 0.7, "strength_margin": 0.1},
    "silent": {"allow_enqueue": False, "q_cap": 1.0, "strength_margin": 0.0},
}


def tier_for_brier(
    brier: float | None,
    n: int,
    *,
    min_n: int = DEFAULT_MIN_N,
    normal_max: float = DEFAULT_NORMAL_MAX,
    tight_max: float = DEFAULT_TIGHT_MAX,
) -> str:
    """[SHTOM-T3] Brier → 候选档位(未经迟滞前的原始阶梯判定)。"""
    if n < min_n or brier is None:
        return "observe"
    if brier <= normal_max:
        return "normal"
    if brier <= tight_max:
        return "tight"
    return "silent"


def tier_with_hysteresis(calib_state: dict[str, Any], candidate: str) -> str:
    """档位迁移迟滞:收紧需连续 2 次同候选,放松/冷启动即时。原地更新
    `calib_state["pending_tier"]`/`["pending_streak"]`,返回本次实际生效档位。
    """
    prev = calib_state.get("tier", "observe")
    if candidate == "observe" or prev == "observe":
        calib_state["pending_tier"] = None
        calib_state["pending_streak"] = 0
        return candidate
    if _SEVERITY[candidate] <= _SEVERITY[prev]:
        calib_state["pending_tier"] = None
        calib_state["pending_streak"] = 0
        return candidate
    # 收紧候选:须连续 2 次窗评同一候选才真正生效。
    if calib_state.get("pending_tier") == candidate:
        streak = int(calib_state.get("pending_streak", 0)) + 1
    else:
        streak = 1
    calib_state["pending_tier"] = candidate
    calib_state["pending_streak"] = streak
    if streak >= 2:
        calib_state["pending_tier"] = None
        calib_state["pending_streak"] = 0
        return candidate
    return prev


def gate_effects(tier: str) -> dict[str, Any]:
    """该档位的出口效果:`allow_enqueue`(concern 原语能否入队)/`q_cap`(预测
    确定度上限)/`strength_margin`(strength 需要的额外余量才放行)。
    """
    return _GATE_EFFECTS.get(tier, _GATE_EFFECTS["observe"])


def passes_strength_margin(tier: str, strength: float) -> bool:
    return strength >= gate_effects(tier)["strength_margin"]


__all__ = [
    "DEFAULT_MIN_N",
    "DEFAULT_NORMAL_MAX",
    "DEFAULT_TIGHT_MAX",
    "tier_for_brier",
    "tier_with_hysteresis",
    "gate_effects",
    "passes_strength_margin",
]
