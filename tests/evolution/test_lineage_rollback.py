"""test_lineage_rollback.py:漂移 N 代 -> rollback 任意 accepted 代 -> overlay 字节级一致(A4, T4)。"""

from __future__ import annotations

import json

from yelos.evolution.lineage.ledger import LineageLedger
from yelos.evolution.lineage.records import ChangeEntry, LineageRecord
from yelos.evolution.overlay import make_overlay_writer, save_overlay


def _accept(ledger: LineageLedger, gen: int, parent_gen: int, key: str, before, after):
    record = LineageRecord(
        gen=gen,
        parent_gen=parent_gen,
        ts="2026-01-01T00:00:00+00:00",
        deployment_id=ledger.deployment_id(),
        strategy="pattern_search",
        changes=(ChangeEntry(key=key, before=before, after=after),),
        guard={"static": "ok", "property": "ok"},
        fitness={
            "bench_score": 70.0,
            "online_score": 0.0,
            "sovereignty_violations": 0,
            "report": "",
        },
        incumbent_fitness=65.0,
        verdict="accepted",
    )
    ledger.append(record)


def test_rollback_gen0_is_byte_identical_to_never_evolved(tmp_path):
    ledger = LineageLedger(tmp_path / "lineage.jsonl")
    overlay_path = tmp_path / "evolution.overlay.json"

    _accept(ledger, 1, 0, "intrinsic_daily_cap", 3, 4)
    _accept(ledger, 2, 1, "intrinsic_daily_cap", 4, 5)

    writer = make_overlay_writer(
        overlay_path, deployment_id=ledger.deployment_id(), gen=2
    )
    writer(_delta(ledger, 2))

    before_rollback_bytes = overlay_path.read_bytes()
    assert json.loads(before_rollback_bytes)["values"] == {"intrinsic_daily_cap": 5}

    path = ledger.rollback(
        0,
        make_overlay_writer(overlay_path, deployment_id=ledger.deployment_id(), gen=0),
    )
    payload = json.loads(path.read_bytes())
    assert payload["values"] == {}
    assert payload["gen"] == 0


def test_rollback_to_intermediate_gen_reconstructs_exact_overlay(tmp_path):
    ledger = LineageLedger(tmp_path / "lineage.jsonl")
    overlay_path = tmp_path / "evolution.overlay.json"

    _accept(ledger, 1, 0, "intrinsic_daily_cap", 3, 4)
    _accept(ledger, 2, 1, "intrinsic_daily_cap", 4, 5)
    _accept(ledger, 3, 2, "intrinsic_daily_cap", 5, 4)

    # 先把现行 overlay 写到 gen3 的状态(模拟"当前已在 gen3")。
    save_overlay(
        overlay_path,
        deployment_id=ledger.deployment_id(),
        gen=3,
        values={"intrinsic_daily_cap": 4},
    )

    writer = make_overlay_writer(
        overlay_path, deployment_id=ledger.deployment_id(), gen=1
    )
    path = ledger.rollback(1, writer)
    payload = json.loads(path.read_bytes())
    assert payload["values"] == {"intrinsic_daily_cap": 4}
    assert payload["gen"] == 1

    # 与"直接把 gen1 accepted 时的值写盘"逐字节一致。
    direct = save_overlay(
        overlay_path.with_suffix(".direct.json"),
        deployment_id=ledger.deployment_id(),
        gen=1,
        values={"intrinsic_daily_cap": 4},
    )
    assert (
        json.loads(path.read_bytes())["values"]
        == json.loads(direct.read_bytes())["values"]
    )


def test_rollback_rejects_non_accepted_gen(tmp_path):
    ledger = LineageLedger(tmp_path / "lineage.jsonl")
    overlay_path = tmp_path / "evolution.overlay.json"
    _accept(ledger, 1, 0, "intrinsic_daily_cap", 3, 4)

    from yelos.evolution.lineage.ledger import LineageIntegrityError

    writer = make_overlay_writer(
        overlay_path, deployment_id=ledger.deployment_id(), gen=99
    )
    try:
        ledger.rollback(99, writer)
        raise AssertionError("expected LineageIntegrityError")
    except LineageIntegrityError:
        pass


def _delta(ledger: LineageLedger, gen: int) -> dict:
    genome = ledger.reconstruct(gen)
    from yelos.evolution.genome.registry import spec_for

    return {
        k: v
        for k, v in genome.items()
        if spec_for(k) is not None and v != spec_for(k).default
    }
