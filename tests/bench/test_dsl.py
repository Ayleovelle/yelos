"""DSL 雏形(bench_BLUEPRINT §4.2/§8.2 test_dsl.py)——文法子集/往返/行号报错。"""

from __future__ import annotations

import pytest

from yelos.bench.scenarios.dsl import DslSyntaxError, dump, parse
from yelos.bench.scenarios.schema import Scenario, ScenarioDay, ScenarioEvent

_FIXTURE = Scenario(
    scenario_id="demo-01",
    mode="companion",
    days=(
        ScenarioDay(
            day_index=0,
            events=(
                ScenarioEvent(
                    at_min=480, kind="user_msg", payload={"text_key": "calm_00"}
                ),
                ScenarioEvent(at_min=500, kind="impulse_poll", payload={}),
            ),
        ),
        ScenarioDay(day_index=1, events=()),
    ),
    config_overrides={"cap": 500, "lifespan_days": 3650},
    origin="dsl",
)


def test_dsl_roundtrip():
    text = dump(_FIXTURE)
    assert parse(text) == _FIXTURE


def test_dsl_roundtrip_empty_days():
    s = Scenario(
        scenario_id="empty", mode="steward", days=(), config_overrides={}, origin="dsl"
    )
    assert parse(dump(s)) == s


def test_dsl_parses_literal_text():
    text = (
        "scenario_id: hand-written\n"
        "mode: companion\n"
        "config: {}\n"
        "days:\n"
        "  - day_index: 0\n"
        "    events:\n"
        "      - at_min: 480\n"
        "        kind: user_msg\n"
        "        payload:\n"
        "          text_key: calm_01\n"
        "      - at_min: 481\n"
        "        kind: pause\n"
        "        payload: {}\n"
        "  - day_index: 1\n"
        "    events: []\n"
    )
    s = parse(text)
    assert s.scenario_id == "hand-written"
    assert s.mode == "companion"
    assert len(s.days) == 2
    assert s.days[0].events[0].kind == "user_msg"
    assert s.days[0].events[0].payload == {"text_key": "calm_01"}
    assert s.days[1].events == ()


def test_dsl_ignores_comments_and_blank_lines():
    text = (
        "# 顶部注释\n"
        "scenario_id: c1\n"
        "\n"
        "mode: steward  # 行内注释\n"
        "config: {}\n"
        "days: []\n"
    )
    s = parse(text)
    assert s.scenario_id == "c1"
    assert s.mode == "steward"
    assert s.days == ()


def test_dsl_syntax_error_reports_line_number():
    bad = "scenario_id demo\nmode: companion\nconfig: {}\ndays: []\n"
    with pytest.raises(DslSyntaxError) as exc:
        parse(bad)
    assert "第 1 行" in str(exc.value)


def test_dsl_rejects_unknown_event_kind():
    bad = (
        "scenario_id: bad\n"
        "mode: companion\n"
        "config: {}\n"
        "days:\n"
        "  - day_index: 0\n"
        "    events:\n"
        "      - at_min: 0\n"
        "        kind: not_a_real_kind\n"
        "        payload: {}\n"
    )
    with pytest.raises(ValueError):
        parse(bad)
