"""config_defaults.py 在整个架构中的位置:intrinsic 侧配置键的默认值(§6.4)。

施工纪律:本波**禁止编辑** `src/yelos/config.py`(见模块任务书);真正把
`intrinsic_policy`/`intrinsic_integrator`/`intrinsic_field_params`/
`dream_generator`/`moments_enabled`/`max_catchup_steps` 六个键注册进
`YelosConfig`(config.py 单一入口)是另一任务的编码前置义务。本文件先把
默认值与读取辅助函数立好,`build_intrinsic(cfg)` 用 `getattr`/`dict.get`
双形态兼容读取——`cfg` 可以是尚未升级的 `YelosConfig` 实例(读不到新键,
一律落默认)、一个已扩展的对象,或一个普通 dict(测试常用)。
"""

from __future__ import annotations

from typing import Any

DEFAULT_INTRINSIC_POLICY = "threshold"
DEFAULT_INTRINSIC_INTEGRATOR = "euler"
DEFAULT_DREAM_GENERATOR = "residue"
DEFAULT_MOMENTS_ENABLED = True
DEFAULT_MAX_CATCHUP_STEPS = 240
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 60.0


def cfg_get(cfg: Any, key: str, default: Any) -> Any:
    """dict / 对象双形态兼容读取,键缺失一律回落默认(§2.1 总纪律②同精神)。"""
    if cfg is None:
        return default
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


__all__ = [
    "DEFAULT_INTRINSIC_POLICY",
    "DEFAULT_INTRINSIC_INTEGRATOR",
    "DEFAULT_DREAM_GENERATOR",
    "DEFAULT_MOMENTS_ENABLED",
    "DEFAULT_MAX_CATCHUP_STEPS",
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "cfg_get",
]
