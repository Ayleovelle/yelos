"""test_projection.py —— 预期投影单元/性质测试(finitude_BLUEPRINT §11/§8)。

确定性;样本不足 → None;P==0 → 0;weibull 暮年 est_spend > 早年(形状学投影);
不产出任何自由文本字段(schema 全是数值/字典)。
"""

from __future__ import annotations

from dataclasses import fields

from yelos.finitude.ledger_ext import LifeReplay
from yelos.finitude.projection.contracts import INFINITE_SENTINEL
from yelos.finitude.projection.estimate import project


def _record(model="linear", params=None, active_days_settled=0, p=0.5):
    return {
        "p": p,
        "aging": {
            "model": model,
            "params": params or {},
            "active_days_settled": active_days_settled,
            "fast": 1.0,
        },
    }


def _replay_with_days(days: list[str], hi=0, concern=0) -> LifeReplay:
    return LifeReplay(
        sid="u1",
        gen=1,
        model_id="linear",
        hi_by_day={d: hi for d in days},
        concern_by_day={d: concern for d in days},
        active_day_count=len(days),
    )


def test_determinism_same_input_same_output():
    record = _record()
    replay = _replay_with_days(["2026-01-01", "2026-01-02"])
    a = project(replay, record, "2026-01-05", lifespan_active_days=100)
    b = project(replay, record, "2026-01-05", lifespan_active_days=100)
    assert a == b


def test_p_zero_gives_zero_remaining():
    record = _record(p=0.0)
    replay = _replay_with_days([])
    proj = project(replay, record, "2026-01-05", lifespan_active_days=100)
    assert proj.est_remaining_active_days == 0


def test_lifespan_disabled_gives_infinite_sentinel():
    record = _record(p=0.9)
    replay = _replay_with_days([])
    proj = project(replay, record, "2026-01-05", lifespan_active_days=0)
    assert proj.est_remaining_active_days == INFINITE_SENTINEL


def test_calendar_estimate_none_when_sample_insufficient():
    record = _record(p=0.5)
    replay = _replay_with_days(["2026-01-01", "2026-01-02"])  # 只有 2 活跃日 < 7
    proj = project(replay, record, "2026-01-05", lifespan_active_days=100)
    assert proj.est_remaining_calendar_days is None


def test_calendar_estimate_present_with_enough_samples():
    days = [f"2026-01-{d:02d}" for d in range(1, 15)]  # 14 活跃日
    record = _record(p=0.5)
    replay = _replay_with_days(days)
    proj = project(replay, record, "2026-01-15", lifespan_active_days=100)
    assert proj.est_remaining_calendar_days is not None


def test_weibull_late_life_est_spend_exceeds_early_life():
    """weibull 暮年 est_spend > 早年(形状学投影兑现,不是全程均值)。"""
    lifespan = 100
    days = [f"2026-01-{d:02d}" for d in range(1, 10)]
    replay = _replay_with_days(days)

    record_early = _record(
        model="weibull", params={"k": 2.5}, active_days_settled=2, p=0.9
    )
    record_late = _record(
        model="weibull", params={"k": 2.5}, active_days_settled=90, p=0.2
    )

    proj_early = project(
        replay, record_early, "2026-01-10", lifespan_active_days=lifespan
    )
    proj_late = project(
        replay, record_late, "2026-01-10", lifespan_active_days=lifespan
    )

    assert proj_late.est_spend_per_active_day > proj_early.est_spend_per_active_day


def test_no_free_text_fields():
    """schema 全字段值只能是 str(日期)/数值/dict/None,不含她的台词。"""
    record = _record()
    replay = _replay_with_days(["2026-01-01"])
    proj = project(replay, record, "2026-01-05", lifespan_active_days=100)
    for f in fields(proj):
        value = getattr(proj, f.name)
        assert not isinstance(value, str) or f.name == "as_of_day"


def test_reserve_expr_p_uses_fast():
    record = _record(model="reserve", p=0.6)
    record["aging"]["fast"] = 0.55
    replay = _replay_with_days(["2026-01-01"])
    proj = project(replay, record, "2026-01-05", lifespan_active_days=100)
    assert proj.p_expr == 0.55
    assert proj.p == 0.6


def test_epoch_etas_empty_when_already_at_final_epoch():
    record = _record(p=0.0)
    replay = _replay_with_days([])
    proj = project(replay, record, "2026-01-05", lifespan_active_days=100)
    assert proj.epoch_etas == {}
