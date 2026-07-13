"""T6:§4.4 profile 行为矩阵逐格——coding 砍温度类留 CAUTION/CONCERN、cap=2;
voice 附加键的派生规则;chat 输出 6 键无附加键。"""

from __future__ import annotations

from yelos.guidance import build_guidance


def _surface(**overrides) -> dict:
    base = {
        "decision": {"action": "hold"},
        "state": {
            "rhythm": {"strain": 0.0},
            "responsiveness": {"fatigue": 0.0},
            "valence": {"warmth": 0.9},  # 温度类候选(WARM_HIGH)
            "damage": {"accumulated": 0.0},
            "boundary": {"autonomy": 1.0, "paused": False},
            "needs": {"quiet": 0.0, "expression": 0.0},
        },
        "dynamics": {
            "relational_time": {"phase": "active"},
            "uncertainty": {"claim_caution": 0.9},  # CAUTION 候选
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


def test_chat_has_exactly_six_keys_no_extras() -> None:
    out = build_guidance(_surface(), mode="companion", profile="chat")
    assert set(out.keys()) == {
        "tone",
        "length",
        "pace",
        "warmth_label",
        "hints",
        "respect_pause",
    }


def test_coding_drops_temperature_hints_keeps_caution_and_concern() -> None:
    surface = _surface()
    out = build_guidance(
        surface, mode="companion", profile="coding", concern_active=True
    )
    assert "她心情不错，语气可以活泼些。" not in out["hints"]
    assert "心情不错，语气可以活泼些。" not in out["hints"]
    assert "她不太笃定，回复别下绝对结论。" in out["hints"]
    assert "她像是有点担心你，可以关心一句。" in out["hints"]
    assert len(out["hints"]) <= 2


def test_coding_hint_cap_is_two() -> None:
    surface = _surface(
        **{
            "state.rhythm.strain": 0.9,
            "state.responsiveness.fatigue": 0.9,
            "state.needs.quiet": 0.9,
        }
    )
    out = build_guidance(
        surface, mode="companion", profile="coding", concern_active=True
    )
    assert len(out["hints"]) <= 2


def test_coding_tone_length_pace_unaffected_same_as_chat() -> None:
    surface = _surface(**{"state.damage.accumulated": 0.5})
    chat_out = build_guidance(surface, mode="companion", profile="chat")
    coding_out = build_guidance(surface, mode="companion", profile="coding")
    assert chat_out["tone"] == coding_out["tone"]
    assert chat_out["length"] == coding_out["length"]
    assert chat_out["pace"] == coding_out["pace"]


def test_voice_adds_speech_rate_and_pause_before_reply() -> None:
    surface = _surface(**{"decision.action": "withdraw"})
    out = build_guidance(surface, mode="companion", profile="voice")
    assert out["pause_before_reply"] is True  # pace == give_space
    assert out["speech_rate"] in {"slow", "normal"}
    assert set(out.keys()) == {
        "tone",
        "length",
        "pace",
        "warmth_label",
        "hints",
        "respect_pause",
        "speech_rate",
        "pause_before_reply",
    }


def test_voice_hint_cap_and_dimensions_same_as_chat() -> None:
    surface = _surface()
    chat_out = build_guidance(surface, mode="companion", profile="chat")
    voice_out = build_guidance(surface, mode="companion", profile="voice")
    assert chat_out["hints"] == voice_out["hints"]
