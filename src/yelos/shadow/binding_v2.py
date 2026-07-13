"""在整个架构中的位置:binding schema v2 的权威结构定义(蓝图 §3.3 /
INTEGRATION_SPEC §2.1 第 5 行)。全部函数纯字典操作,零 I/O——迁移脚本
(`migrations/migrate_binding_v1_to_v2.py`)与运行时(`orchestrator.py`)共用
本文件,保证"迁移产出的结构"与"运行时期望读到的结构"永远同一套字面量,
不会出现两处描述漂移。

四检测器类型枚举(`CTYPES`)与基线通道枚举(`BASELINE_CHANNELS`)是本模块
唯一权威定义,其余文件一律 `from .binding_v2 import CTYPES` 复用,不重复
拼字面量列表(防打字漂移)。

**对 INTEGRATION_SPEC §2.1 示例 schema 的一处加性细化**:该文档给出的
`calibration`/`pending_prediction` 是单块示例;蓝图 §7.3 明确要求
"per-ctype 分账:Brier 按检测器类型分列,某型 silent 不连坐他型",故本实现
把 `calibration` 与 `pending_prediction` 落成"按 ctype 分桶的 dict"而非
单一 dict——这是 schema 的加性精化(只增结构层级,不删减 spec 列出的任何
字段名),与"只增不删"总纪律一致,记入交付说明供红队核对。
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 2

CTYPES: tuple[str, ...] = (
    "warmth_drop",
    "pressure_spike",
    "rhythm_break",
    "withdrawal",
)

# pressure/warmth/damage 是引擎 Surface 观测通道;rhythm 是交互间隔(session
# 记账,非引擎);msg_len/interactions 是 withdrawal 检测器需要的活动量通道
# (同样纯 session 记账)。六通道共用同一套三窗口滚动分位数机制(baseline/
# rolling.py),对 INTEGRATION_SPEC §2.1 "baselines{4ch}" 示例的加性扩展
# (4ch 示例只列了 warmth/pressure/damage/rhythm,msg_len/interactions 是
# withdrawal 检测器決策表(蓝图 §6.2)明确需要的额外参照量)。
BASELINE_CHANNELS: tuple[str, ...] = (
    "pressure",
    "warmth",
    "damage",
    "rhythm",
    "msg_len",
    "interactions",
)

_BUCKETS = 8


def _new_baseline_channel() -> dict[str, Any]:
    return {
        "day": None,
        "week": None,
        "month": None,
        "ewma_var": 0.0,
        "ewma_mean": None,
        "day_ticks": 0,
        "week_bins": [0.0] * _BUCKETS,
        "week_active_days": 0,
        "week_last_day": "",
        "month_bins": [0.0] * _BUCKETS,
        "month_active_days": 0,
        "month_last_day": "",
    }


def _new_hysteresis_entry() -> dict[str, Any]:
    return {"armed": True, "injected_day": ""}


def _new_sensitization_entry() -> dict[str, Any]:
    return {"beta": 0.0, "hits": 0, "misses": 0}


def _new_calibration_entry() -> dict[str, Any]:
    return {
        "brier": None,
        "n": 0,
        "tier": "observe",
        "bins": [],
        # 加性字段(calibration/ledger.py + gate_policy.py 消费,§7.1/§7.3):
        "unresolved": 0,  # 被新 fire 覆盖前未结账的预测计数(不计入 Brier)
        "pending_tier": None,  # 迟滞升档候选(连续 2 次窗评才真正生效)
        "pending_streak": 0,
    }


def default_shadow_block() -> dict[str, Any]:
    """全新绑定的 `shadow` 顶层块初始值(§3.3 schema v2)。"""
    return {
        "schema": SCHEMA_VERSION,
        "baselines": {ch: _new_baseline_channel() for ch in BASELINE_CHANNELS},
        "hysteresis": {ct: _new_hysteresis_entry() for ct in CTYPES},
        "sensitization": {ct: _new_sensitization_entry() for ct in CTYPES},
        "calibration": {ct: _new_calibration_entry() for ct in CTYPES},
        "pending_prediction": {ct: None for ct in CTYPES},
        "daily": {"day": "", "concern_count": 0, "inject_types": []},
    }


def ensure_shadow_block(record: dict[str, Any]) -> dict[str, Any]:
    """确保 `record["shadow"]` 存在且结构完整;缺块/缺子键一律补默认,不 raise。

    幂等:已完整的块原样返回(同一对象引用,允许调用方原地写)。
    """
    block = record.get("shadow")
    if not isinstance(block, dict):
        block = default_shadow_block()
        record["shadow"] = block
        return block

    if block.get("schema") != SCHEMA_VERSION:
        block["schema"] = SCHEMA_VERSION

    baselines = block.setdefault("baselines", {})
    for ch in BASELINE_CHANNELS:
        if ch not in baselines or not isinstance(baselines[ch], dict):
            baselines[ch] = _new_baseline_channel()
        else:
            for k, v in _new_baseline_channel().items():
                baselines[ch].setdefault(k, v)

    hysteresis = block.setdefault("hysteresis", {})
    for ct in CTYPES:
        if ct not in hysteresis or not isinstance(hysteresis[ct], dict):
            hysteresis[ct] = _new_hysteresis_entry()

    sensitization = block.setdefault("sensitization", {})
    for ct in CTYPES:
        if ct not in sensitization or not isinstance(sensitization[ct], dict):
            sensitization[ct] = _new_sensitization_entry()

    calibration = block.setdefault("calibration", {})
    for ct in CTYPES:
        if ct not in calibration or not isinstance(calibration[ct], dict):
            calibration[ct] = _new_calibration_entry()

    pending = block.setdefault("pending_prediction", {})
    if not isinstance(pending, dict):
        pending = {}
        block["pending_prediction"] = pending
    for ct in CTYPES:
        pending.setdefault(ct, None)

    daily = block.setdefault("daily", {})
    daily.setdefault("day", "")
    daily.setdefault("concern_count", 0)
    daily.setdefault("inject_types", [])

    return block


def reset_daily_if_new_day(shadow_block: dict[str, Any], day_key: str) -> bool:
    """跨日翻转 `shadow.daily`(concern_count/inject_types 逐日重置)。

    注意:核心 `daily`(record["daily"])的翻转由 `core/binding.py` 的 rollover
    单入口负责,`shadow.daily` 是 shadow 私有块、不受那个入口管辖——本模块
    自己在 `beat()` 首步判日翻转(§4 施工纪律"世代键/日结时序自管")。
    返回是否发生了翻转(供调用方决定是否需要持久化)。
    """
    daily = shadow_block.setdefault(
        "daily", {"day": "", "concern_count": 0, "inject_types": []}
    )
    if daily.get("day") == day_key:
        return False
    daily["day"] = day_key
    daily["concern_count"] = 0
    daily["inject_types"] = []
    return True


def reset_for_new_incarnation() -> dict[str, Any]:
    """seal/incarnation 时的整块重置(§3.3:重生不继承前世疤痕与校准史)。"""
    return default_shadow_block()


__all__ = [
    "SCHEMA_VERSION",
    "CTYPES",
    "BASELINE_CHANNELS",
    "default_shadow_block",
    "ensure_shadow_block",
    "reset_daily_if_new_day",
    "reset_for_new_incarnation",
]
