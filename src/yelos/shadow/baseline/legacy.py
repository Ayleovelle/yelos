"""legacy.py 在整个架构中的位置:v0.1 兼容成员 + X6 冷启动兜底(蓝图 §5 /
INTEGRATION_SPEC §3.6)。

两件事:
1. `legacy_single_point`:把 `rolling.py` 的 day-窗首拍单点值折成 v0.1
   `shadow_baseline.warmth` 语义的等价读数,供 `signals/legacy_compat.py`
   的 `LegacyDetector` 在默认配置(K=1/Legacy 检测器集)下复现逐字节 v0.1
   行为(golden 闸)。
2. `bootstrap_from_memory`:X6 裁定——"W3 shadow 基线族起步/交叉校验源"。
   `memory.BaselineContext.typical_warmth/typical_pressure` 仅在该通道
   `day_ticks==0`(尚无任何观测)时作为冷启动锚点写入,一旦真实观测到达
   立即被覆盖(不做长期融合,避免与自身滚动基线打架,§3.6 语义分层裁定)。
"""

from __future__ import annotations

from typing import Any

# X6 裁定:只有这两个通道有 memory 侧对应的 typical_* 兜底源。
_MEMORY_BOOTSTRAP_CHANNELS = {
    "warmth": "typical_warmth",
    "pressure": "typical_pressure",
}


def legacy_single_point(channel_state: dict[str, Any]) -> float | None:
    """当日单点值(legacy 语义):优先 `_legacy_anchor`(首拍值),否则当前 day 估计。"""
    anchor = channel_state.get("_legacy_anchor")
    if anchor is not None:
        return anchor
    return channel_state.get("day")


def bootstrap_from_memory(
    channel_state: dict[str, Any], ch: str, memory_baseline: Any
) -> None:
    """X6 冷启动兜底:`memory_baseline` 具 `typical_warmth`/`typical_pressure`
    属性(鸭子类型,不 import `yelos.memory`)。`memory_baseline` 为 None 或
    通道已有观测(`day_ticks>0`)时安静跳过,不 raise。
    """
    if memory_baseline is None:
        return
    attr = _MEMORY_BOOTSTRAP_CHANNELS.get(ch)
    if attr is None:
        return
    if int(channel_state.get("day_ticks", 0) or 0) > 0:
        return
    value = getattr(memory_baseline, attr, None)
    if value is None:
        return
    try:
        value = float(value)
    except (TypeError, ValueError):
        return
    channel_state["_legacy_anchor"] = value
    channel_state["day"] = value


__all__ = ["legacy_single_point", "bootstrap_from_memory"]
