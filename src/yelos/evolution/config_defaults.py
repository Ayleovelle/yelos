"""config_defaults.py 在整个架构中的位置:evolution 侧配置键默认值(蓝图 §3.7/T7)。

施工纪律(与 shadow/intrinsic/finitude 波同款):本波**禁止编辑**
``src/yelos/config.py``;真正把 ``evolution_enabled`` /
``evolution_velocity_bound`` / ``evolution_min_days`` /
``evolution_online_weight`` / ``evolution_strategy`` 五个键注册进
``YelosConfig``(config.py 单一入口)是另一任务的编码前置义务。本文件先把
默认值与 ``cfg_get`` 立好——``build_evolution(cfg)`` 用 ``cfg_get`` 双形态
兼容读取:``cfg`` 可以是尚未升级的 ``YelosConfig`` 实例(读不到新键,一律
落默认)、一个已扩展的对象,或一个普通 dict(测试常用)。

默认 ``evolution_enabled=False``——opt-in 门控(T1)在组合根
``build_evolution`` 处短路:关则 ``None``,不留半活对象。
"""

from __future__ import annotations

from typing import Any

DEFAULT_EVOLUTION_ENABLED = False
DEFAULT_EVOLUTION_VELOCITY_BOUND = 0.05
DEFAULT_EVOLUTION_MIN_DAYS = 7
DEFAULT_EVOLUTION_ONLINE_WEIGHT = 0.0
DEFAULT_EVOLUTION_STRATEGY = "pattern_search"

VALID_STRATEGIES = ("pattern_search", "grid_descent", "nelder_mead")


def cfg_get(cfg: Any, key: str, default: Any) -> Any:
    """dict / 对象双形态兼容读取,键缺失一律回落默认(与 shadow 侧同精神)。"""
    if cfg is None:
        return default
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def evolution_enabled(cfg: Any) -> bool:
    return bool(cfg_get(cfg, "evolution_enabled", DEFAULT_EVOLUTION_ENABLED))


def evolution_velocity_bound(cfg: Any) -> float:
    try:
        return float(
            cfg_get(cfg, "evolution_velocity_bound", DEFAULT_EVOLUTION_VELOCITY_BOUND)
        )
    except (TypeError, ValueError):
        return DEFAULT_EVOLUTION_VELOCITY_BOUND


def evolution_min_days(cfg: Any) -> int:
    try:
        return int(cfg_get(cfg, "evolution_min_days", DEFAULT_EVOLUTION_MIN_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_EVOLUTION_MIN_DAYS


def evolution_online_weight(cfg: Any) -> float:
    try:
        return float(
            cfg_get(cfg, "evolution_online_weight", DEFAULT_EVOLUTION_ONLINE_WEIGHT)
        )
    except (TypeError, ValueError):
        return DEFAULT_EVOLUTION_ONLINE_WEIGHT


def evolution_strategy(cfg: Any) -> str:
    value = cfg_get(cfg, "evolution_strategy", DEFAULT_EVOLUTION_STRATEGY)
    return value if value in VALID_STRATEGIES else DEFAULT_EVOLUTION_STRATEGY


def evolution_dir(data_dir: Any) -> "Any":
    """``{data_dir}/evolution`` 派生路径(同 ``ledger_path`` 风格,§3.7)。"""
    from pathlib import Path

    return Path(data_dir) / "evolution"


def evolution_overlay_path(data_dir: Any) -> "Any":
    """``{data_dir}/evolution.overlay.json`` 派生路径(§3.7)。"""
    from pathlib import Path

    return Path(data_dir) / "evolution.overlay.json"


__all__ = [
    "DEFAULT_EVOLUTION_ENABLED",
    "DEFAULT_EVOLUTION_VELOCITY_BOUND",
    "DEFAULT_EVOLUTION_MIN_DAYS",
    "DEFAULT_EVOLUTION_ONLINE_WEIGHT",
    "DEFAULT_EVOLUTION_STRATEGY",
    "VALID_STRATEGIES",
    "cfg_get",
    "evolution_enabled",
    "evolution_velocity_bound",
    "evolution_min_days",
    "evolution_online_weight",
    "evolution_strategy",
    "evolution_dir",
    "evolution_overlay_path",
]
