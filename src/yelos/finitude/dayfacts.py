"""dayfacts.py 在整个架构中的位置:DayFacts 提取(finitude_BLUEPRINT §3.0/§2)。

从 `record`(bindings 记录)与被结算的 `daily` 快照(rollover 传入的昨日 daily,尚未
重置)提取一份不可变 `DayFacts`,是模型族 `spend()` 的唯一输入面。

**接缝 X3(INTEGRATION_SPEC §3.3)**:`concern_fired` 的权威源是
`record["shadow"]["daily"]["concern_count"]`(shadow 模块 W3 维护,四检测器语义正确);
shadow 模块/该块尚未落地时(本仓当前状态,shadow 未建包)回退读 legacy
`record["concern_state"]["injected_types"]`(仅当 `injected_day == day` 时取其长度)。
两侧共享测试 `test_ledger_ext.py`/`test_models_property.py` 核对来源切换。

**疑义记录(照录蓝图字面,施工期显式标注)**:`epoch_shift_yesterday` 蓝图字面定义为
"milestones 末条 day == 被结算日"。由于纪元跃迁 milestone 是在**同一次** settle 内、
拿到新 P 之后才追加的(dualtrack 观测在 gate 之后),对"正在被结算的这一天"而言这是
自指的——本实现按字面从**结算前**的 milestones 列表读取(即上一次 settle 循环遗留的
状态),故在单日单次 settle 的正常流程下该字段通常为 False,只有在"追赶结算"
(一次 rollover 处理多个历史天)等非常规路径下才可能命中。此处不假装消歧义已解决,
留给红队/未来 catch-up 结算实现核验。
"""

from __future__ import annotations

from typing import Any

from .models.protocol import DayFacts

_MISSING = object()


def _bool_field(daily: dict, key: str) -> bool:
    return bool(daily.get(key, False))


def _int_field(daily: dict, key: str, default: int = 0) -> int:
    value = daily.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value if value > 0 else 0
    return default


def _concern_fired(record: dict, day: str) -> int:
    """接缝 X3:权威源 shadow.daily.concern_count,回退 legacy concern_state。"""
    shadow = record.get("shadow")
    if isinstance(shadow, dict):
        shadow_daily = shadow.get("daily")
        if isinstance(shadow_daily, dict):
            count = shadow_daily.get("concern_count")
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                return count
    concern_state = record.get("concern_state")
    if isinstance(concern_state, dict) and concern_state.get("injected_day") == day:
        injected_types = concern_state.get("injected_types")
        if isinstance(injected_types, list):
            return len(injected_types)
    return 0


def _epoch_shift_yesterday(record: dict, day: str) -> bool:
    milestones = record.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        return False
    last = milestones[-1]
    if not isinstance(last, dict):
        return False
    return last.get("day") == day and "epoch" in last


def _active_days_settled(record: dict) -> int:
    aging = record.get("aging")
    if isinstance(aging, dict):
        value = aging.get("active_days_settled", 0)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return 0


def extract_dayfacts(
    record: dict[str, Any],
    daily: dict[str, Any],
    lifespan_active_days: int,
) -> DayFacts:
    """从 record + 昨日 daily 快照提取 DayFacts(纯函数,不改动入参)。"""
    day = str(daily.get("day", ""))
    was_active = _bool_field(daily, "interacted") or _bool_field(daily, "active_seen")
    return DayFacts(
        day=day,
        was_active_day=was_active,
        high_intensity=_int_field(daily, "high_intensity"),
        concern_fired=_concern_fired(record, day),
        swallowed=_int_field(daily, "swallowed"),
        proactive_sent=_int_field(daily, "proactive_sent"),
        epoch_shift_yesterday=_epoch_shift_yesterday(record, day),
        active_days_settled=_active_days_settled(record),
        lifespan_active_days=int(lifespan_active_days) if lifespan_active_days else 0,
    )


__all__ = ["extract_dayfacts"]
