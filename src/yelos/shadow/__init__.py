"""shadow/ 在整个架构中的位置:影子(ToM 模拟论)核心人格模块(蓝图全文)。

组合根:`build_shadow_system(cfg, bridge, ...) -> ShadowSystem`——检测器序/
闸链序/K/窗口参数在此显式列出;`session.py`(未来接线,超出本任务范围)只
持 `ShadowSystem` 一个句柄,心跳步 5 调 `system.beat(...)`。

`core/shadow.py`(v0.1)**原文件不删不改**,本包的 `signals/legacy_compat.py`
以适配壳方式复用它的 `extract_concern`(默认 `detector_set="legacy"` 路径,
golden 闸,§0 兼容纪律)。

子包依赖方向(无环,蓝图 §2):
```
simulator/baseline/signals/calibration/sensitization/gates → 仅 contracts + binding_v2 + 标准库
signals    → baseline(只读视图)
simulator  → baseline(σ_family)
gates      → calibration(档位)
viz        → 各账本只读
orchestrator → 其余全部(编排层,唯一装配点)
```
任何子模块不 import `orchestrator`,不 import `session`/`server`(下向依赖
禁止);引擎只经注入的 `bridge` 协议,本包内零 `sylanne_core` import。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .binding_v2 import CTYPES, default_shadow_block, ensure_shadow_block
from .calibration.ledger import CalibrationLedger, default_ledger_path
from .config_defaults import (
    DEFAULT_SHADOW_CALIBRATION_WINDOW,
    DEFAULT_SHADOW_ENGINE_CALLS_PER_BEAT,
    DEFAULT_SHADOW_HYPOTHESES,
    DEFAULT_SHADOW_INTENSITY_FN,
    cfg_get,
)
from .contracts import ShadowConfig
from .orchestrator import ShadowSystem

_VALID_DETECTOR_SETS = ("legacy", "v2")
_VALID_INTENSITY_FNS = ("linear", "saturating")


def build_shadow_system(
    cfg: Any = None,
    bridge: Any = None,
    *,
    memory_facade: Any = None,
    data_dir: str | Path | None = None,
    detector_set: str = "legacy",
) -> ShadowSystem:
    """组合根(蓝图 §2 组合根契约)。

    `cfg` 缺键一律回落默认(`cfg_get` 双形态兼容读取,intrinsic 波同惯例)。
    `data_dir` 用于装配 `CalibrationLedger` 的落盘路径工厂(§2.3
    "shadow 校准账本 jsonl");未提供时退化为进程当前目录下的单文件(仅供
    未接线的最小可跑场景,真实部署应始终传入)。

    `detector_set`:`"legacy"`(默认)= 与 v0.1 逐字节兼容;`"v2"` = 完整
    深化管线(ensemble/四检测器/校准/敏感化/闸链全部接通)。此参数不在蓝图
    §13 列出的四个正式配置键之列——是本实现为达成"默认配置下逐字节 v0.1
    兼容"这条硬约束而补的组合根参数,详见交付说明"疑义记录"。
    """
    if detector_set not in _VALID_DETECTOR_SETS:
        raise ValueError(
            f"unknown detector_set={detector_set!r}; choices: {_VALID_DETECTOR_SETS}"
        )

    shadow_enabled = bool(cfg_get(cfg, "shadow_enabled", True))
    shadow_hypotheses = int(
        cfg_get(cfg, "shadow_hypotheses", DEFAULT_SHADOW_HYPOTHESES)
    )
    shadow_intensity_fn = str(
        cfg_get(cfg, "shadow_intensity_fn", DEFAULT_SHADOW_INTENSITY_FN)
    )
    if shadow_intensity_fn not in _VALID_INTENSITY_FNS:
        raise ValueError(
            f"unknown shadow_intensity_fn={shadow_intensity_fn!r}; choices: {_VALID_INTENSITY_FNS}"
        )
    shadow_engine_calls_per_beat = int(
        cfg_get(
            cfg, "shadow_engine_calls_per_beat", DEFAULT_SHADOW_ENGINE_CALLS_PER_BEAT
        )
    )
    shadow_calibration_window = int(
        cfg_get(cfg, "shadow_calibration_window", DEFAULT_SHADOW_CALIBRATION_WINDOW)
    )

    shadow_cfg = ShadowConfig(
        shadow_enabled=shadow_enabled,
        shadow_hypotheses=shadow_hypotheses,
        shadow_intensity_fn=shadow_intensity_fn,
        shadow_engine_calls_per_beat=shadow_engine_calls_per_beat,
        shadow_calibration_window=shadow_calibration_window,
    )

    ledger_factory = None
    if data_dir is not None:
        root = Path(data_dir)

        def _factory(sid: str) -> CalibrationLedger:
            return CalibrationLedger(default_ledger_path(root, sid))

        ledger_factory = _factory

    return ShadowSystem(
        shadow_cfg,
        bridge,
        memory_facade=memory_facade,
        ledger_factory=ledger_factory,
        detector_set=detector_set,
    )


__all__ = [
    "build_shadow_system",
    "ShadowSystem",
    "ShadowConfig",
    "CTYPES",
    "default_shadow_block",
    "ensure_shadow_block",
]
