"""synth.py(bench_BLUEPRINT §4.3/§8.2 test_synth.py)——确定性/可区分性/poll 修饰器。"""

from __future__ import annotations

import pytest

from yelos.bench.scenarios.synth import ARCHETYPES, synthesize


def test_synth_same_seed_same_scenario_byte_identical():
    a = synthesize("fatigue", 10, "seed-w1")
    b = synthesize("fatigue", 10, "seed-w1")
    assert a == b


def test_synth_different_seed_different_scenario():
    a = synthesize("fatigue", 10, "seed-w1")
    b = synthesize("fatigue", 10, "seed-w2")
    assert a != b


def test_synth_rejects_unknown_archetype():
    with pytest.raises(ValueError):
        synthesize("nonexistent", 5, "s")


def test_synth_zero_days_yields_empty_scenario():
    s = synthesize("silence", 0, "s")
    assert s.days == ()


def _event_density(scenario) -> float:
    total_events = sum(len(d.events) for d in scenario.days)
    return total_events / max(1, len(scenario.days))


def _tier_histogram(scenario) -> dict[str, int]:
    hist: dict[str, int] = {}
    for day in scenario.days:
        for e in day.events:
            if e.kind != "user_msg":
                continue
            tier = e.payload["text_key"].split("_")[0]
            hist[tier] = hist.get(tier, 0) + 1
    return hist


def test_archetype_distinguishable():
    """五原型在同 seed 下产生互不相同的事件密度/强度直方图。"""
    seed = "distinguish-w1"
    days = 20
    scenarios = {a: synthesize(a, days, seed) for a in ARCHETYPES}

    densities = {a: _event_density(s) for a, s in scenarios.items()}
    assert len(set(densities.values())) > 1, f"密度全同,不可区分:{densities}"

    histograms = {
        a: tuple(sorted(_tier_histogram(s).items())) for a, s in scenarios.items()
    }
    assert len(set(histograms.values())) > 1, f"强度直方图全同,不可区分:{histograms}"

    # honeymoon 应比 silence 消息更密集(强意图设计,非偶然)
    assert densities["honeymoon"] > densities["silence"]


def test_poll_discipline_never_produces_no_polls():
    s = synthesize("pressure", 5, "seed-poll", poll_discipline="never")
    polls = [e for d in s.days for e in d.events if e.kind == "impulse_poll"]
    assert polls == []


def test_poll_discipline_lazy_skips_some_but_not_all():
    faithful = synthesize("pressure", 10, "seed-poll", poll_discipline="faithful")
    lazy = synthesize("pressure", 10, "seed-poll", poll_discipline="lazy")

    n_faithful = sum(
        1 for d in faithful.days for e in d.events if e.kind == "impulse_poll"
    )
    n_lazy = sum(1 for d in lazy.days for e in d.events if e.kind == "impulse_poll")

    assert n_faithful > 0
    assert 0 < n_lazy < n_faithful


def test_synth_scenario_origin_is_synth():
    s = synthesize("honeymoon", 3, "seed-origin")
    assert s.origin == "synth"
    assert s.scenario_id == "synth-honeymoon-3d-seed-origin"
