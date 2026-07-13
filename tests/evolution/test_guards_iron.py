"""test_guards_iron.py:对抗集全拒(A2, T2)。"""

from __future__ import annotations

import json
from pathlib import Path

from yelos.evolution.genome.registry import hatch_genome
from yelos.evolution.guards.property_gate import run_property_gate
from yelos.evolution.guards.static_check import check_mutation_set

_ADVERSARIAL_PATH = (
    Path(__file__).parent / "adversarial" / "iron_mutation_requests.json"
)


def _load_adversarial() -> list[dict]:
    return json.loads(_ADVERSARIAL_PATH.read_text(encoding="utf-8"))


def test_adversarial_set_all_rejected_by_static_guard():
    parent = hatch_genome()
    for case in _load_adversarial():
        candidate = dict(parent)
        candidate[case["key"]] = case["attempted_value"]
        verdict = check_mutation_set(parent, candidate)
        assert not verdict.ok, case
        assert verdict.stage == "static"
        assert verdict.reasons, case


def test_iron_key_reasons_are_machine_readable():
    parent = hatch_genome()
    candidate = dict(parent)
    candidate["arbiter_min_gap_seconds"] = 1
    verdict = check_mutation_set(parent, candidate)
    assert not verdict.ok
    assert any(r.startswith("iron:") for r in verdict.reasons)


def test_unregistered_key_reason_is_machine_readable():
    parent = hatch_genome()
    candidate = dict(parent)
    candidate["ghost_key"] = 1
    verdict = check_mutation_set(parent, candidate)
    assert not verdict.ok
    assert any(r.startswith("unregistered:") for r in verdict.reasons)


def test_property_gate_rejects_drifted_iron_value():
    genome = dict(hatch_genome())
    genome["quiet_hours"] = "00:00-00:00"
    verdict = run_property_gate(genome)
    assert not verdict.ok
    assert verdict.stage == "property"
    assert any(r.startswith("iron_drifted:") for r in verdict.reasons)


def test_property_gate_accepts_hatch_genome():
    verdict = run_property_gate(hatch_genome())
    assert verdict.ok


def test_domain_and_step_violation_rejected():
    parent = hatch_genome()
    candidate = dict(parent)
    candidate["intrinsic_daily_cap"] = 6  # 亲代 3 -> 6 超过 A3 步长上界
    verdict = check_mutation_set(parent, candidate, velocity_bound=0.05)
    assert not verdict.ok
    assert any(r.startswith("domain/step:") for r in verdict.reasons)


def test_out_of_domain_value_rejected():
    parent = hatch_genome()
    candidate = dict(parent)
    candidate["intrinsic_daily_cap"] = 999
    verdict = check_mutation_set(parent, candidate)
    assert not verdict.ok
    assert any(r.startswith("domain:") for r in verdict.reasons)
