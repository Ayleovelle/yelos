"""test_hysteresis.py:[SHTOM-A6] armed/disarmed 三分支(蓝图 §11)。"""

from __future__ import annotations

from yelos.shadow.signals.hysteresis import step


def test_armed_fires_once_and_disarms() -> None:
    state = {"armed": True, "injected_day": ""}
    new_state, fire = step(state, 1.0, 1.0, 0.6, "2026-07-11")
    assert fire is True
    assert new_state["armed"] is False
    assert new_state["injected_day"] == "2026-07-11"


def test_armed_same_day_second_trigger_does_not_refire() -> None:
    # 已经在今天 fire 过一次(injected_day==today),即便 armed 又回到 True
    # (例如上一轮 re-arm 了),同类型当日不得二次 fire(F3c)。
    state = {"armed": True, "injected_day": "2026-07-11"}
    new_state, fire = step(state, 1.0, 1.0, 0.6, "2026-07-11")
    assert fire is False
    assert new_state["armed"] is True
    assert new_state["injected_day"] == "2026-07-11"


def test_armed_persists_across_days_when_not_triggering() -> None:
    state = {"armed": True, "injected_day": ""}
    new_state, fire = step(state, 0.0, 1.0, 0.6, "2026-07-11")
    assert fire is False
    assert new_state["armed"] is True


def test_disarmed_stays_disarmed_across_days_until_rearm() -> None:
    # F11b:disarmed 跨日持久,直到信号回落到 re-arm 阈下才重新武装。
    state = {"armed": False, "injected_day": "2026-07-11"}
    new_state, fire = step(state, 0.8, 1.0, 0.6, "2026-07-12")
    assert fire is False
    assert new_state["armed"] is False  # 0.8 >= rearm_th(0.6),仍不重新武装


def test_disarmed_rearms_below_rearm_threshold() -> None:
    state = {"armed": False, "injected_day": "2026-07-11"}
    new_state, fire = step(state, 0.5, 1.0, 0.6, "2026-07-12")
    assert fire is False
    assert new_state["armed"] is True
    assert new_state["injected_day"] == "2026-07-11"  # injected_day 不因 re-arm 改变


def test_full_cycle_rearm_then_refire_next_day() -> None:
    state = {"armed": True, "injected_day": ""}
    state, fire1 = step(state, 1.0, 1.0, 0.6, "d1")
    assert fire1 is True and state["armed"] is False
    state, fire2 = step(state, 0.0, 1.0, 0.6, "d1")  # 回落,重新武装(同日)
    assert fire2 is False and state["armed"] is True
    state, fire3 = step(state, 1.0, 1.0, 0.6, "d1")  # 同日再次越阈:不应二次 fire
    assert fire3 is False
    state, fire4 = step(state, 1.0, 1.0, 0.6, "d2")  # 次日越阈:应可正常 fire
    assert fire4 is True
