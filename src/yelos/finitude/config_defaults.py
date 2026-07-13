"""config_defaults.py 在整个架构中的位置:finitude 侧配置键默认值(施工纪律:禁编辑 config.py)。

真正把 `finitude_model` / `finitude_model_params` / `finitude_epoch_track` 注册进
`YelosConfig`(config.py 单一入口)是另一任务的编码前置义务。本文件先把默认值与
`cfg_get` 立好——`cfg_get` 支持 dict / 带同名属性对象 / 尚未升级的 `YelosConfig`
实例三种输入,缺键一律回落默认(与 primal/intrinsic 侧同款纪律)。
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_FINITUDE_MODEL = "linear"
DEFAULT_FINITUDE_MODEL_PARAMS = "{}"  # JSON 字符串(与 primal_routes 同款文件配置形态)
DEFAULT_FINITUDE_EPOCH_TRACK = "fixed"
DEFAULT_ACTIVE_BUDGET_CAP = 3  # rho_budget 的 cap;与 DEFAULT_INTRINSIC_DAILY_CAP 对齐

VALID_MODEL_IDS = ("linear", "weibull", "event", "reserve")
VALID_EPOCH_TRACKS = ("fixed", "order_parameter")


def cfg_get(cfg: Any, key: str, default: Any) -> Any:
    """dict / 对象双形态兼容读取,键缺失一律回落默认。"""
    if cfg is None:
        return default
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def finitude_model_id(cfg: Any) -> str:
    value = cfg_get(cfg, "finitude_model", DEFAULT_FINITUDE_MODEL)
    return value if value in VALID_MODEL_IDS else DEFAULT_FINITUDE_MODEL


def finitude_model_params(cfg: Any) -> dict:
    raw = cfg_get(cfg, "finitude_model_params", DEFAULT_FINITUDE_MODEL_PARAMS)
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def finitude_epoch_track(cfg: Any) -> str:
    value = cfg_get(cfg, "finitude_epoch_track", DEFAULT_FINITUDE_EPOCH_TRACK)
    return value if value in VALID_EPOCH_TRACKS else DEFAULT_FINITUDE_EPOCH_TRACK


def active_budget_cap(cfg: Any) -> int:
    value = cfg_get(cfg, "intrinsic_daily_cap", DEFAULT_ACTIVE_BUDGET_CAP)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_ACTIVE_BUDGET_CAP
    return value if value >= 0 else DEFAULT_ACTIVE_BUDGET_CAP


def finitude_globally_on(cfg: Any) -> bool:
    """镜像 `YelosConfig.finitude_globally_on()`(不要求 cfg 是该类实例)。"""
    enabled = bool(cfg_get(cfg, "finitude_enabled", True))
    lifespan = cfg_get(cfg, "lifespan_active_days", 545)
    try:
        lifespan = int(lifespan)
    except (TypeError, ValueError):
        lifespan = 545
    return enabled and lifespan > 0


def lifespan_active_days(cfg: Any) -> int:
    value = cfg_get(cfg, "lifespan_active_days", 545)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 545
    return value


__all__ = [
    "DEFAULT_FINITUDE_MODEL",
    "DEFAULT_FINITUDE_MODEL_PARAMS",
    "DEFAULT_FINITUDE_EPOCH_TRACK",
    "DEFAULT_ACTIVE_BUDGET_CAP",
    "VALID_MODEL_IDS",
    "VALID_EPOCH_TRACKS",
    "cfg_get",
    "finitude_model_id",
    "finitude_model_params",
    "finitude_epoch_track",
    "active_budget_cap",
    "finitude_globally_on",
    "lifespan_active_days",
]
