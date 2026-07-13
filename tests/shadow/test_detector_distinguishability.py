"""test_detector_distinguishability.py:维二机器凭据(蓝图 §11)。四组专属
触发样本——每检测器存在"仅触发自己不触发他者"的轨迹;同一混合轨迹上四者
决策序列可区分。
"""

from __future__ import annotations

from yelos.shadow.contracts import BaselineView, DayContext, ShadowView
from yelos.shadow.signals import pressure_spike, rhythm_break, warmth_drop, withdrawal

_TH_EFF = {
    "warmth_drop": 0.25,
    "pressure_spike": 0.6,
    "rhythm_break": 3.0,
    "withdrawal": 0.2,
}
_DETECTORS = {
    "warmth_drop": warmth_drop.detect,
    "pressure_spike": pressure_spike.detect,
    "rhythm_break": rhythm_break.detect,
    "withdrawal": withdrawal.detect,
}


def _ctx(**overrides) -> DayContext:
    base = dict(
        day_key="d1",
        interactions_today=1,
        last_gap_seconds=0.0,
        msg_len_ewma=100.0,
        th_eff=_TH_EFF,
        pressure_slope=0.0,
        in_quiet=False,
        week_gap_median=100.0,
        interactions_7d_avg=10.0,
        interactions_month_avg=10.0,
        msg_len_month_avg=100.0,
    )
    base.update(overrides)
    return DayContext(**base)


def _neutral_view() -> ShadowView:
    # 中性读数:任何检测器都不该触发的基线(warmth 高、pressure/damage 低)。
    return ShadowView(pressure=0.1, warmth=0.9, damage=0.0, hyp_id=0)


def _neutral_base() -> dict[str, BaselineView]:
    return {
        "warmth": BaselineView(day=0.9, week=0.9, month=0.9, dispersion=0.0),
        "pressure": BaselineView(day=0.1, week=0.1, month=0.1, dispersion=0.0),
        "damage": BaselineView(day=0.0, week=0.0, month=0.0, dispersion=0.0),
    }


_SCENARIOS = {
    "warmth_drop": {
        "view": ShadowView(pressure=0.1, warmth=0.3, damage=0.0, hyp_id=0),
        "base": {
            **_neutral_base(),
            "warmth": BaselineView(day=0.9, week=0.9, month=0.9, dispersion=0.0),
        },
        "ctx": _ctx(),
    },
    "pressure_spike": {
        "view": ShadowView(pressure=0.95, warmth=0.9, damage=0.0, hyp_id=0),
        "base": _neutral_base(),
        "ctx": _ctx(),
    },
    "rhythm_break": {
        "view": _neutral_view(),
        "base": _neutral_base(),
        "ctx": _ctx(
            interactions_today=0, last_gap_seconds=1000.0, week_gap_median=100.0
        ),
    },
    "withdrawal": {
        # base["warmth"].day 留空(None)使 warmth_drop 的日窗判定早退;withdrawal
        # 只吃 month 窗,两者互不干扰(warmth_drop 与 withdrawal 都读 warmth,
        # 但参照窗不同——day vs month,这正是"不同时间尺度的关切有不同参照系"
        # 的可区分性体现,蓝图 §5)。
        "view": ShadowView(pressure=0.1, warmth=0.3, damage=0.0, hyp_id=0),
        "base": {
            **_neutral_base(),
            "warmth": BaselineView(day=None, week=0.9, month=0.9, dispersion=0.0),
        },
        "ctx": _ctx(
            interactions_7d_avg=1.0,
            interactions_month_avg=10.0,
            msg_len_ewma=10.0,
            msg_len_month_avg=100.0,
        ),
    },
}


def test_each_detector_has_an_exclusive_trigger_sample() -> None:
    """每个检测器都存在"只触发自己不触发他者"的专属样本。"""
    for target_ctype, scenario in _SCENARIOS.items():
        fired = {
            ctype: fn(scenario["view"], scenario["base"], scenario["ctx"]) is not None
            for ctype, fn in _DETECTORS.items()
        }
        assert fired[target_ctype] is True, f"{target_ctype} 的专属样本未能触发自己"
        others_fired = [c for c, f in fired.items() if f and c != target_ctype]
        assert others_fired == [], f"{target_ctype} 的专属样本意外触发了 {others_fired}"


def test_neutral_baseline_triggers_nothing() -> None:
    ctx = _ctx()
    for ctype, fn in _DETECTORS.items():
        assert fn(_neutral_view(), _neutral_base(), ctx) is None, (
            f"{ctype} 在中性样本上不该触发"
        )


def test_mixed_trajectory_decision_sequence_is_distinguishable() -> None:
    """同一混合轨迹序列(逐拍切换场景)上,四者的 fire 序列两两不同。"""
    sequence = [
        "warmth_drop",
        None,
        "pressure_spike",
        None,
        "rhythm_break",
        None,
        "withdrawal",
    ]
    decisions: dict[str, list[bool]] = {c: [] for c in _DETECTORS}
    for step in sequence:
        if step is None:
            view, base, ctx = _neutral_view(), _neutral_base(), _ctx()
        else:
            view, base, ctx = (
                _SCENARIOS[step]["view"],
                _SCENARIOS[step]["base"],
                _SCENARIOS[step]["ctx"],
            )
        for ctype, fn in _DETECTORS.items():
            decisions[ctype].append(fn(view, base, ctx) is not None)

    series = [tuple(v) for v in decisions.values()]
    assert len(set(series)) == len(series), (
        f"四检测器决策序列出现重复,不可区分:{decisions}"
    )
