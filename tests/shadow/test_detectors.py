"""test_detectors.py:四检测器逐一,触发谓词全分支/strength 端点/th_eff 含
β 偏置(蓝图 §11,§6.2 决策表逐行)。
"""

from __future__ import annotations

from yelos.shadow.contracts import BaselineView, DayContext, ShadowView
from yelos.shadow.signals import pressure_spike, rhythm_break, warmth_drop, withdrawal


def _day_ctx(**overrides) -> DayContext:
    base = dict(
        day_key="d1",
        interactions_today=0,
        last_gap_seconds=0.0,
        msg_len_ewma=0.0,
        th_eff={
            "warmth_drop": 0.25,
            "pressure_spike": 0.6,
            "rhythm_break": 3.0,
            "withdrawal": 0.2,
        },
        pressure_slope=0.0,
        in_quiet=False,
        week_gap_median=0.0,
        interactions_7d_avg=0.0,
        interactions_month_avg=0.0,
        msg_len_month_avg=0.0,
    )
    base.update(overrides)
    return DayContext(**base)


def _view(**overrides) -> ShadowView:
    base = dict(pressure=None, warmth=None, damage=None, hyp_id=0)
    base.update(overrides)
    return ShadowView(**base)


# --- warmth_drop ------------------------------------------------------------


def test_warmth_drop_fires_on_day_drop_below_floor() -> None:
    base = {"warmth": BaselineView(day=0.9, week=None, month=None, dispersion=0.0)}
    view = _view(warmth=0.4)
    raw = warmth_drop.detect(view, base, _day_ctx())
    assert raw is not None
    assert raw.strength > 0.0


def test_warmth_drop_blocked_by_absolute_floor() -> None:
    base = {"warmth": BaselineView(day=0.9, week=None, month=None, dispersion=0.0)}
    view = _view(warmth=0.6)  # 跌幅够但未跌破 0.45 绝对下限
    assert warmth_drop.detect(view, base, _day_ctx()) is None


def test_warmth_drop_none_without_baseline() -> None:
    view = _view(warmth=0.2)
    assert warmth_drop.detect(view, {}, _day_ctx()) is None


def test_warmth_drop_th_eff_from_sensitization() -> None:
    base = {"warmth": BaselineView(day=0.6, week=None, month=None, dispersion=0.0)}
    view = _view(warmth=0.44)  # drop=0.16,跌破绝对下限但小于默认阈 0.25
    assert warmth_drop.detect(view, base, _day_ctx()) is None
    # 敏感化后 th_eff 降到 0.1,同样的 0.16 跌幅应能触发。
    sensitized_ctx = _day_ctx(
        th_eff={
            "warmth_drop": 0.10,
            "pressure_spike": 0.6,
            "rhythm_break": 3.0,
            "withdrawal": 0.2,
        }
    )
    raw = warmth_drop.detect(view, base, sensitized_ctx)
    assert raw is not None


# --- pressure_spike -----------------------------------------------------


def test_pressure_spike_fires_on_level() -> None:
    raw = pressure_spike.detect(_view(pressure=0.9), {}, _day_ctx())
    assert raw is not None
    assert "pressure_level" in raw.evidence


def test_pressure_spike_fires_on_slope() -> None:
    ctx = _day_ctx(pressure_slope=0.2)
    raw = pressure_spike.detect(_view(pressure=0.55), {}, ctx)
    assert raw is not None
    assert "pressure_slope" in raw.evidence


def test_pressure_spike_fires_on_legacy_damage() -> None:
    raw = pressure_spike.detect(_view(damage=0.9), {}, _day_ctx())
    assert raw is not None
    assert "damage" in raw.evidence


def test_pressure_spike_none_when_all_below_threshold() -> None:
    assert (
        pressure_spike.detect(_view(pressure=0.1, damage=0.1), {}, _day_ctx()) is None
    )


# --- rhythm_break --------------------------------------------------------


def test_rhythm_break_fires_on_large_gap_ratio() -> None:
    ctx = _day_ctx(
        interactions_today=0,
        last_gap_seconds=1000.0,
        week_gap_median=100.0,
        in_quiet=False,
    )
    raw = rhythm_break.detect(_view(), {}, ctx)
    assert raw is not None


def test_rhythm_break_blocked_in_quiet_window() -> None:
    ctx = _day_ctx(
        interactions_today=0,
        last_gap_seconds=1000.0,
        week_gap_median=100.0,
        in_quiet=True,
    )
    assert rhythm_break.detect(_view(), {}, ctx) is None


def test_rhythm_break_blocked_when_interacted_today() -> None:
    ctx = _day_ctx(interactions_today=1, last_gap_seconds=1000.0, week_gap_median=100.0)
    assert rhythm_break.detect(_view(), {}, ctx) is None


def test_rhythm_break_none_without_baseline_gap() -> None:
    ctx = _day_ctx(interactions_today=0, last_gap_seconds=1000.0, week_gap_median=0.0)
    assert rhythm_break.detect(_view(), {}, ctx) is None


# --- withdrawal -----------------------------------------------------------


def test_withdrawal_fires_with_two_conditions() -> None:
    base = {"warmth": BaselineView(day=None, week=None, month=0.8, dispersion=0.0)}
    ctx = _day_ctx(
        interactions_7d_avg=1.0,
        interactions_month_avg=10.0,  # th=5.0,1.0<5.0 满足
        msg_len_month_avg=100.0,
        msg_len_ewma=100.0,  # 不满足(等于阈值不算低于)
    )
    view = _view(warmth=0.5)  # 0.5 < 0.8-0.2=0.6 满足
    raw = withdrawal.detect(view, base, ctx)
    assert raw is not None
    assert len(raw.evidence) >= 2


def test_withdrawal_none_with_only_one_condition() -> None:
    base = {"warmth": BaselineView(day=None, week=None, month=0.8, dispersion=0.0)}
    ctx = _day_ctx(
        interactions_7d_avg=10.0,
        interactions_month_avg=10.0,
        msg_len_month_avg=100.0,
        msg_len_ewma=100.0,
    )
    view = _view(warmth=0.5)  # 只满足 warmth 一条
    assert withdrawal.detect(view, base, ctx) is None
