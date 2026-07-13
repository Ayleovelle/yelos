"""T5:§4.5 steward 抑制矩阵逐格;三 profile 的 steward 变体只收窄不放宽;
expression/express 展开在 steward 下仍生效(minor⑧)。"""

from __future__ import annotations

from yelos.guidance import build_guidance


def _surface(**overrides) -> dict:
    base = {
        "decision": {"action": "hold"},
        "state": {
            "rhythm": {"strain": 0.9},
            "responsiveness": {"fatigue": 0.9},
            "valence": {"warmth": 0.5},
            "damage": {"accumulated": 0.0},
            "boundary": {"autonomy": 1.0, "paused": False},
            "needs": {"quiet": 0.9, "expression": 0.0},
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


def test_steward_neutralizes_short_and_pace_across_all_profiles() -> None:
    surface = _surface(**{"decision.action": "withdraw"})
    for profile in ("coding", "chat", "voice"):
        out = build_guidance(surface, mode="steward", profile=profile)
        assert out["length"] == "medium", profile
        assert out["pace"] == "steady", profile


def test_steward_drops_truncation_hints_across_all_profiles() -> None:
    surface = _surface(**{"decision.action": "withdraw"})
    for profile in ("coding", "chat", "voice"):
        out = build_guidance(surface, mode="steward", profile=profile)
        assert "她想收一收，别追问，给点空间。" not in out["hints"], profile
        assert "节律紧，回短一点。" not in out["hints"], profile


def test_steward_still_expands_expression_and_express() -> None:
    expr_surface = _surface(**{"state.needs.expression": 0.9})
    out = build_guidance(expr_surface, mode="steward")
    assert out["length"] == "long"

    express_surface = _surface(
        **{"decision.action": "express", "state.valence.warmth": 0.8}
    )
    out2 = build_guidance(express_surface, mode="steward")
    assert out2["length"] == "long"
    assert "她有话想说，给她展开的空间。" in out2["hints"]


def test_steward_still_honors_tone_concern_caution_respect_pause() -> None:
    surface = _surface(
        **{
            "state.damage.accumulated": 0.5,
            "guard.allowed": False,
        }
    )
    out = build_guidance(surface, mode="steward", concern_active=True)
    assert out["tone"] == "gentle"
    assert out["respect_pause"] is True
    assert "她像是有点担心你，可以关心一句。" in out["hints"]


def test_companion_is_not_neutralized() -> None:
    surface = _surface(**{"decision.action": "withdraw"})
    out = build_guidance(surface, mode="companion")
    assert out["length"] == "short"
    assert out["pace"] == "give_space"
