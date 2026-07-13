"""T7:A3 溯源——每条入选 hint 有 trace 且 margin 计算正确;被抑制候选带
suppressed_by;trace 重放复现同 guidance;concern 条目 path=="concern_active"
且不含任何 shadow 字段名。"""

from __future__ import annotations

from yelos.guidance.audit import aggregate_spectrum
from yelos.guidance.compiler.interpreter import evaluate


def _surface(**overrides) -> dict:
    base = {
        "decision": {"action": "hold"},
        "state": {
            "rhythm": {"strain": 0.9},
            "responsiveness": {"fatigue": 0.0},
            "valence": {"warmth": 0.9},
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


def test_selected_hints_have_matching_traces_with_margin() -> None:
    result = evaluate(_surface(), "companion")
    selected = [t for t in result.audit if t.suppressed_by is None]
    assert selected, "该场景应至少一条入选 trace"
    strain_trace = next(t for t in selected if t.hint_key == "STRAIN")
    assert strain_trace.op == "ge"
    assert strain_trace.threshold == 0.6
    assert strain_trace.observed == 0.9
    assert strain_trace.margin is not None
    assert abs(strain_trace.margin - 0.3) < 1e-9


def test_suppressed_candidates_are_tagged() -> None:
    # autonomy<=0.3 与 paused 同时触发同一 hint_key(AUTONOMY)→ 其一 dedup。
    surface = _surface(
        **{"state.boundary.autonomy": 0.1, "state.boundary.paused": True}
    )
    result = evaluate(surface, "companion")
    autonomy_traces = [t for t in result.audit if t.hint_key == "AUTONOMY"]
    assert len(autonomy_traces) == 2
    suppressed = [t for t in autonomy_traces if t.suppressed_by is not None]
    selected = [t for t in autonomy_traces if t.suppressed_by is None]
    assert len(selected) == 1
    assert len(suppressed) == 1
    assert suppressed[0].suppressed_by == "dedup"


def test_cap_suppression_beyond_hint_cap() -> None:
    surface = _surface(
        **{
            "state.responsiveness.fatigue": 0.9,
            "state.needs.quiet": 0.9,
            "state.damage.accumulated": 0.9,
            "state.boundary.autonomy": 0.1,
        }
    )
    result = evaluate(surface, "companion", profile="chat")
    assert len(result.guidance["hints"]) <= 3
    capped = [t for t in result.audit if t.suppressed_by == "cap"]
    # 候选远多于 cap=3,必有被截断的
    assert capped


def test_concern_trace_path_is_concern_active_no_shadow_field_names() -> None:
    result = evaluate(_surface(), "companion", concern_active=True)
    concern_trace = next(t for t in result.audit if t.hint_key == "CONCERN")
    assert concern_trace.path == "concern_active"
    for forbidden in ("shadow", "theory_of_mind", "internal_model"):
        assert forbidden not in concern_trace.path


def test_trace_replay_reproduces_same_guidance() -> None:
    surface = _surface(**{"decision.action": "guard", "state.valence.warmth": 0.9})
    result = evaluate(surface, "companion")
    # "重放"即用相同输入重算一次(确定性系统,§4.4 蓝图 A3:重放规则即复现)。
    replay = evaluate(surface, "companion")
    assert replay.guidance == result.guidance
    assert replay.audit == result.audit


def test_aggregate_spectrum_counts() -> None:
    result = evaluate(_surface(**{"decision.action": "withdraw"}), "companion")
    spectrum = aggregate_spectrum(result.audit)
    assert spectrum["total_candidates"] == len(result.audit)
    assert sum(spectrum["selected"].values()) + sum(
        spectrum["suppressed"].values()
    ) == len(result.audit)
