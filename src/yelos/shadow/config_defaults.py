"""config_defaults.py 在整个架构中的位置:shadow 侧配置键的默认值(蓝图 §13)。

施工纪律(与 intrinsic 波同款):本波**禁止编辑** `src/yelos/config.py`;真正
把 `shadow_hypotheses`/`shadow_intensity_fn`/`shadow_engine_calls_per_beat`/
`shadow_calibration_window` 四个键注册进 `YelosConfig`(config.py 单一入口)
是另一任务的编码前置义务。`shadow_enabled` 已在 v0.1 `YelosConfig` 落地
(§7.3),本文件不重复定义,只在 `cfg_get` 兜底读取时把它当已有键处理。

`build_shadow_system(cfg, ...)` 用 `cfg_get` 双形态兼容读取——`cfg` 可以是
尚未升级的 `YelosConfig` 实例(读不到新键,一律落默认)、一个已扩展的对象,
或一个普通 dict(测试常用)。

λ/ε_lo/ε_hi/w_obs/w_base/w_D/w_B 等 A5/§4.3 的算法常量按蓝图 §13"用户旋钮
最小化"纪律**不进配置面**,只在 `simulator/epsilon.py` 内部登记为模块常量,
留作 evolution genome 注册表(W5)的登记候选——本文件不重复声明它们。
"""

from __future__ import annotations

from typing import Any

DEFAULT_SHADOW_HYPOTHESES = 1
DEFAULT_SHADOW_INTENSITY_FN = "linear"
DEFAULT_SHADOW_ENGINE_CALLS_PER_BEAT = 4
DEFAULT_SHADOW_CALIBRATION_WINDOW = 60

# 迟滞/敏感化/校准阶梯等"读代码就懂但不该在 config.py 里当旋钮转"的常量,
# 仍然登记于此(集中一处方便审计),供各子模块 import 而不是各自散落字面量。
DEFAULT_REARM_RATIO = 0.6  # re-arm 阈 = 触发阈 * 此比例(A6)
DEFAULT_BETA_LO = -0.10
DEFAULT_BETA_HI = 0.15
DEFAULT_DELTA_HIT = 0.01
DEFAULT_DELTA_MISS = 0.02
DEFAULT_CALIBRATION_OBSERVE_MIN_N = 12
DEFAULT_BRIER_NORMAL_MAX = 0.20
DEFAULT_BRIER_TIGHT_MAX = 0.30


def cfg_get(cfg: Any, key: str, default: Any) -> Any:
    """dict / 对象双形态兼容读取,键缺失一律回落默认。"""
    if cfg is None:
        return default
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


__all__ = [
    "DEFAULT_SHADOW_HYPOTHESES",
    "DEFAULT_SHADOW_INTENSITY_FN",
    "DEFAULT_SHADOW_ENGINE_CALLS_PER_BEAT",
    "DEFAULT_SHADOW_CALIBRATION_WINDOW",
    "DEFAULT_REARM_RATIO",
    "DEFAULT_BETA_LO",
    "DEFAULT_BETA_HI",
    "DEFAULT_DELTA_HIT",
    "DEFAULT_DELTA_MISS",
    "DEFAULT_CALIBRATION_OBSERVE_MIN_N",
    "DEFAULT_BRIER_NORMAL_MAX",
    "DEFAULT_BRIER_TIGHT_MAX",
    "cfg_get",
]
