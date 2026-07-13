"""T1(收窄版):规则枚举——每条规则的边界三点(阈下/阈上/恰阈)在 chat
profile 下命中/不命中的行为与 §4.1 表一致;未知 action / 缺字段不炸,保守
默认(不触发)。"""

from __future__ import annotations

from yelos.guidance.compiler.interpreter import evaluate


def _base_surface(**overrides) -> dict:
    base = {
        "decision": {"action": "hold"},
        "state": {
            "rhythm": {"strain": 0.0},
            "responsiveness": {"fatigue": 0.0},
            "valence": {"warmth": 0.5},
            "damage": {"accumulated": 0.0},
            "boundary": {"autonomy": 1.0, "paused": False},
            "needs": {"quiet": 0.0, "expression": 0.0},
        },
        "dynamics": {
            "relational_time": {"phase": "active"},
            "uncertainty": {"claim_caution": 0.0},
        },
        "guard": {"allowed": True},
    }
    for path, value in overrides.items():
        node = base
        keys = path.split(".")
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
    return base


def _hint_keys(result) -> set[str]:
    return {t.hint_key for t in result.audit if t.suppressed_by is None}


def test_strain_threshold_boundary() -> None:
    below = evaluate(_base_surface(**{"state.rhythm.strain": 0.59}), "companion")
    at = evaluate(_base_surface(**{"state.rhythm.strain": 0.6}), "companion")
    above = evaluate(_base_surface(**{"state.rhythm.strain": 0.61}), "companion")
    assert "STRAIN" not in _hint_keys(below)
    assert "STRAIN" in _hint_keys(at)
    assert "STRAIN" in _hint_keys(above)


def test_warmth_low_and_high_thresholds() -> None:
    low = evaluate(_base_surface(**{"state.valence.warmth": 0.3}), "companion")
    mid = evaluate(_base_surface(**{"state.valence.warmth": 0.31}), "companion")
    high = evaluate(_base_surface(**{"state.valence.warmth": 0.7}), "companion")
    assert "WARM_LOW" in _hint_keys(low)
    assert "WARM_LOW" not in _hint_keys(mid)
    assert "WARM_HIGH" not in _hint_keys(mid)
    assert "WARM_HIGH" in _hint_keys(high)


def test_unknown_action_and_missing_fields_do_not_crash_no_effect() -> None:
    out_unknown = evaluate(
        _base_surface(**{"decision.action": "totally_unknown"}), "companion"
    )
    assert out_unknown.guidance["tone"] == "neutral"
    out_none = evaluate(None, "companion")
    assert out_none.guidance == {
        "tone": "neutral",
        "length": "medium",
        "pace": "steady",
        "warmth_label": out_none.guidance["warmth_label"],
        "hints": [],
        "respect_pause": False,
    }


def test_decision_action_exclusive_group_only_one_effect() -> None:
    out = evaluate(_base_surface(**{"decision.action": "guard"}), "companion")
    assert out.guidance["tone"] == "brief"
    assert out.guidance["length"] == "short"


def test_express_requires_composite_and() -> None:
    low_warmth = evaluate(
        _base_surface(**{"decision.action": "express", "state.valence.warmth": 0.5}),
        "companion",
    )
    high_warmth = evaluate(
        _base_surface(**{"decision.action": "express", "state.valence.warmth": 0.7}),
        "companion",
    )
    assert "EXPRESS" not in _hint_keys(low_warmth)
    assert "EXPRESS" in _hint_keys(high_warmth)


def test_guard_blocked_and_autonomy_low_both_set_respect_pause() -> None:
    out = evaluate(
        _base_surface(**{"guard.allowed": False, "state.boundary.autonomy": 0.1}),
        "companion",
    )
    assert out.guidance["respect_pause"] is True
    keys = _hint_keys(out)
    assert "GUARD_BLOCKED" in keys and "AUTONOMY" in keys
