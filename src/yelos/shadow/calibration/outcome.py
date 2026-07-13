"""outcome.py 在整个架构中的位置:结果代理提取(蓝图 §7.2)。

```
delay_delta = (本轮距上轮间隔) / (week 基线间隔中位)     # >2.0 计退缩证据
len_delta   = 本轮长度 / msg_len_ewma                      # <0.4 计退缩证据
silence     = 36h 内无用户轮 → y=1 直接判(最强低谷证据)
y = 1 if (silence ∨ 证据数≥1) else 0
```

诚实标注(README + theory 双落,§7.2):`y` 是行为代理不是心理真值;代理的
粗糙度正是 A4 折减存在的理由。特征只有数值,无原文(隐私纪律)。
"""

from __future__ import annotations

from typing import Any

from ..contracts import OutcomeRecord

SILENCE_TIMEOUT_HOURS = 36.0
_DELAY_RATIO_TH = 2.0
_LEN_RATIO_TH = 0.4


def extract_outcome_from_turn(
    pending: dict[str, Any], turn_feats: dict[str, float], now_ts: float
) -> OutcomeRecord:
    """下一有效用户轮到达时提取结果代理。`pending` 是
    `shadow.pending_prediction[ctype]` 的字典快照(非 None)。`turn_feats`:
    `{"gap_seconds": float, "msg_len": float, "week_gap_median": float,
    "msg_len_ewma": float}`(由 orchestrator 从 baseline 视图 + 本轮观测拼装)。
    """
    week_gap = turn_feats.get("week_gap_median", 0.0)
    msg_len_ewma = turn_feats.get("msg_len_ewma", 0.0)
    gap_seconds = turn_feats.get("gap_seconds", 0.0)
    msg_len = turn_feats.get("msg_len", 0.0)

    delay_delta = gap_seconds / week_gap if week_gap > 0 else 0.0
    len_delta = msg_len / msg_len_ewma if msg_len_ewma > 0 else 1.0

    evidence = 0
    if delay_delta > _DELAY_RATIO_TH:
        evidence += 1
    if len_delta < _LEN_RATIO_TH:
        evidence += 1

    y = 1 if evidence >= 1 else 0
    proxy = {"delay_delta": delay_delta, "len_delta": len_delta, "silence": 0.0}
    return OutcomeRecord(
        ts=now_ts,
        pred_ts=float(pending.get("ts", now_ts)),
        ctype=str(pending.get("ctype", "")),
        y=y,
        proxy=proxy,
    )


def silence_outcome(pending: dict[str, Any], now_ts: float) -> OutcomeRecord:
    """36h 静默判 y=1(最强低谷证据,§7.2)。"""
    return OutcomeRecord(
        ts=now_ts,
        pred_ts=float(pending.get("ts", now_ts)),
        ctype=str(pending.get("ctype", "")),
        y=1,
        proxy={"delay_delta": 0.0, "len_delta": 0.0, "silence": 1.0},
    )


def is_silence_timeout(
    pending: dict[str, Any], now_ts: float, timeout_hours: float = SILENCE_TIMEOUT_HOURS
) -> bool:
    age_hours = (now_ts - float(pending.get("ts", now_ts))) / 3600.0
    return age_hours >= timeout_hours


__all__ = [
    "SILENCE_TIMEOUT_HOURS",
    "extract_outcome_from_turn",
    "silence_outcome",
    "is_silence_timeout",
]
