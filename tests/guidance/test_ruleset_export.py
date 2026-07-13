"""T9(收窄版):``ruleset_export()`` 结构稳定、覆盖 DEFAULT_RULESET 全量、
JSON 可序列化往返。"""

from __future__ import annotations

import json

from yelos.guidance import ruleset_export
from yelos.guidance.rules import DEFAULT_RULESET


def test_ruleset_export_covers_all_rules() -> None:
    exported = ruleset_export()
    assert len(exported["rules"]) == len(DEFAULT_RULESET)
    ids = {r["rule_id"] for r in exported["rules"]}
    assert ids == {r.rule_id for r in DEFAULT_RULESET}


def test_ruleset_export_is_json_serializable_round_trip() -> None:
    exported = ruleset_export()
    blob = json.dumps(exported, ensure_ascii=False)
    restored = json.loads(blob)
    assert restored == exported


def test_ruleset_export_schema_keys_stable() -> None:
    exported = ruleset_export()
    for rule in exported["rules"]:
        assert set(rule.keys()) == {
            "rule_id",
            "trigger",
            "effect",
            "hint_key",
            "priority",
            "truncation",
            "exclusive_group",
        }


def test_composite_trigger_export_shape() -> None:
    exported = ruleset_export()
    express_rule = next(r for r in exported["rules"] if r["rule_id"] == "R06_express")
    assert express_rule["trigger"]["kind"] == "all_of"
    assert len(express_rule["trigger"]["clauses"]) == 2
