"""test_calibration.py:[SHTOM-A3/T3] 预测落账 / 结果代理 / Brier 与分箱 /
tier 迁移迟滞 / 故意让影子错→闸收紧 / 网格扫 B→tier 单调 / silent 档行为
(蓝图 §11)。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yelos.shadow.binding_v2 import default_shadow_block
from yelos.shadow.calibration import gate_policy, outcome
from yelos.shadow.calibration.ledger import (
    CalibrationLedger,
    check_and_resolve_silence,
    record_prediction,
    resolve_prediction,
)
from yelos.shadow.contracts import OutcomeRecord, PredictionRecord


def _ledger(tmp_path: Path) -> CalibrationLedger:
    return CalibrationLedger(tmp_path / "calib.jsonl")


def test_record_prediction_then_resolve_updates_brier(tmp_path: Path) -> None:
    block = default_shadow_block()
    ledger = _ledger(tmp_path)
    pred = PredictionRecord(ts=0.0, day="d1", ctype="warmth_drop", q=0.9, features={})
    record_prediction(block, pred)
    assert block["pending_prediction"]["warmth_drop"] is not None

    outcome_rec = OutcomeRecord(
        ts=10.0, pred_ts=0.0, ctype="warmth_drop", y=1, proxy={}
    )
    resolve_prediction(block, ledger, "warmth_drop", outcome_rec, window=60)
    calib = block["calibration"]["warmth_drop"]
    assert calib["n"] == 1
    assert calib["brier"] == pytest.approx((0.9 - 1) ** 2)
    assert block["pending_prediction"]["warmth_drop"] is None


def test_overwriting_pending_prediction_counts_unresolved(tmp_path: Path) -> None:
    block = default_shadow_block()
    pred1 = PredictionRecord(
        ts=0.0, day="d1", ctype="pressure_spike", q=0.6, features={}
    )
    record_prediction(block, pred1)
    pred2 = PredictionRecord(
        ts=5.0, day="d1", ctype="pressure_spike", q=0.7, features={}
    )
    record_prediction(block, pred2)
    assert block["calibration"]["pressure_spike"]["unresolved"] == 1
    # 新预测覆盖了旧的,pending 是 pred2 而非硬造出的 y。
    assert block["pending_prediction"]["pressure_spike"]["q"] == 0.7


def test_silence_timeout_forces_y1(tmp_path: Path) -> None:
    block = default_shadow_block()
    ledger = _ledger(tmp_path)
    pred = PredictionRecord(ts=0.0, day="d1", ctype="withdrawal", q=0.5, features={})
    record_prediction(block, pred)
    resolved = check_and_resolve_silence(block, ledger, now_ts=37 * 3600.0)
    assert resolved == ["withdrawal"]
    assert block["calibration"]["withdrawal"]["brier"] == pytest.approx((0.5 - 1) ** 2)


def test_silence_timeout_not_triggered_before_36h(tmp_path: Path) -> None:
    block = default_shadow_block()
    ledger = _ledger(tmp_path)
    pred = PredictionRecord(ts=0.0, day="d1", ctype="withdrawal", q=0.5, features={})
    record_prediction(block, pred)
    resolved = check_and_resolve_silence(block, ledger, now_ts=10 * 3600.0)
    assert resolved == []


def test_bad_calibration_tightens_gate(tmp_path: Path) -> None:
    """[SHTOM-A3] 故意让影子错(q 高、y 全 0):Brier 应显著偏高,tier 收紧
    到 tight/silent(需连续 2 次窗评确认收紧,§7.3 迟滞纪律,故跑两轮)。
    """
    block = default_shadow_block()
    ledger = _ledger(tmp_path)
    ctype = "warmth_drop"
    for i in range(20):
        pred = PredictionRecord(ts=float(i), day="d1", ctype=ctype, q=0.95, features={})
        record_prediction(block, pred)
        out = OutcomeRecord(
            ts=float(i) + 1, pred_ts=float(i), ctype=ctype, y=0, proxy={}
        )
        resolve_prediction(block, ledger, ctype, out, window=60)
    calib = block["calibration"][ctype]
    assert calib["brier"] > gate_policy.DEFAULT_TIGHT_MAX
    assert calib["tier"] == "silent"
    effects = gate_policy.gate_effects(calib["tier"])
    assert effects["allow_enqueue"] is False


def test_good_calibration_stays_normal(tmp_path: Path) -> None:
    block = default_shadow_block()
    ledger = _ledger(tmp_path)
    ctype = "pressure_spike"
    for i in range(20):
        pred = PredictionRecord(ts=float(i), day="d1", ctype=ctype, q=0.05, features={})
        record_prediction(block, pred)
        out = OutcomeRecord(
            ts=float(i) + 1, pred_ts=float(i), ctype=ctype, y=0, proxy={}
        )
        resolve_prediction(block, ledger, ctype, out, window=60)
    calib = block["calibration"][ctype]
    assert calib["brier"] <= gate_policy.DEFAULT_NORMAL_MAX
    assert calib["tier"] == "normal"


def test_gate_monotone_in_brier_grid() -> None:
    """[SHTOM-T3] 网格扫 B → tier 单调收紧(与迟滞无关的原始阶梯判定)。"""
    grid = [0.0, 0.05, 0.15, 0.19, 0.20, 0.21, 0.25, 0.30, 0.31, 0.5, 0.9]
    tiers = [gate_policy.tier_for_brier(b, n=100) for b in grid]
    severity = {"observe": 0, "normal": 0, "tight": 1, "silent": 2}
    for a, b in zip(tiers, tiers[1:]):
        assert severity[a] <= severity[b]
    assert tiers[0] == "normal"
    assert tiers[-1] == "silent"


def test_tier_observe_below_min_n() -> None:
    assert gate_policy.tier_for_brier(0.5, n=5) == "observe"


def test_tier_hysteresis_requires_two_consecutive_to_tighten() -> None:
    calib = {"tier": "normal", "pending_tier": None, "pending_streak": 0}
    t1 = gate_policy.tier_with_hysteresis(calib, "tight")
    assert t1 == "normal"  # 第一次候选,还没确认
    t2 = gate_policy.tier_with_hysteresis(calib, "tight")
    assert t2 == "tight"  # 第二次同候选,确认生效


def test_tier_hysteresis_loosens_immediately() -> None:
    calib = {"tier": "silent", "pending_tier": None, "pending_streak": 0}
    t1 = gate_policy.tier_with_hysteresis(calib, "normal")
    assert t1 == "normal"  # 放松即时生效,不需要连续确认


def test_outcome_delay_and_len_evidence() -> None:
    pending = {"ts": 0.0, "ctype": "withdrawal"}
    turn_feats = {
        "gap_seconds": 100.0,
        "msg_len": 10.0,
        "week_gap_median": 20.0,
        "msg_len_ewma": 50.0,
    }
    out = outcome.extract_outcome_from_turn(pending, turn_feats, now_ts=100.0)
    assert out.y == 1  # delay_delta=5.0>2.0 且 len_delta=0.2<0.4,两条证据都命中


def test_outcome_no_evidence_gives_y0() -> None:
    pending = {"ts": 0.0, "ctype": "withdrawal"}
    turn_feats = {
        "gap_seconds": 10.0,
        "msg_len": 50.0,
        "week_gap_median": 20.0,
        "msg_len_ewma": 50.0,
    }
    out = outcome.extract_outcome_from_turn(pending, turn_feats, now_ts=10.0)
    assert out.y == 0
