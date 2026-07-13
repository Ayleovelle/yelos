"""test_lineage_integrity.py:每现行值溯源 hatch/唯一 accepted 行;坏行跳过、缺行拒回滚(A4, T4)。"""

from __future__ import annotations

import json

import pytest

from yelos.evolution.lineage.ledger import LineageIntegrityError, LineageLedger
from yelos.evolution.lineage.records import ChangeEntry, LineageRecord


def _accept(ledger: LineageLedger, gen: int, parent_gen: int, key: str, before, after):
    record = LineageRecord(
        gen=gen,
        parent_gen=parent_gen,
        ts="2026-01-01T00:00:00+00:00",
        deployment_id=ledger.deployment_id(),
        strategy="pattern_search",
        changes=(ChangeEntry(key=key, before=before, after=after),),
        guard={"static": "ok", "property": "ok"},
        fitness={},
        incumbent_fitness=None,
        verdict="accepted",
    )
    ledger.append(record)


def test_provenance_traces_every_value_to_hatch_or_one_accepted_line(tmp_path):
    ledger = LineageLedger(tmp_path / "lineage.jsonl")
    _accept(ledger, 1, 0, "intrinsic_daily_cap", 3, 4)

    provenance = ledger.current_provenance()
    assert provenance["intrinsic_daily_cap"] == "gen:1"
    assert provenance["arbiter_min_gap_seconds"] == "hatch"


def test_bad_json_line_is_skipped_not_fatal(tmp_path):
    path = tmp_path / "lineage.jsonl"
    ledger = LineageLedger(path)
    _accept(ledger, 1, 0, "intrinsic_daily_cap", 3, 4)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")
    _accept(ledger, 2, 1, "intrinsic_daily_cap", 4, 5)

    records = ledger.all_records()
    assert len(records) == 2  # 坏行不计入,也不炸
    assert ledger.reconstruct(2)["intrinsic_daily_cap"] == 5


def test_missing_dependency_line_rejects_reconstruct(tmp_path):
    path = tmp_path / "lineage.jsonl"
    ledger = LineageLedger(path)
    _accept(ledger, 1, 0, "intrinsic_daily_cap", 3, 4)
    _accept(ledger, 2, 1, "intrinsic_daily_cap", 4, 5)

    # 手工删掉 gen=1 那一行(模拟依赖行损坏/丢失),保留 gen=2。
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if json.loads(ln)["gen"] != 1]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    with pytest.raises(LineageIntegrityError):
        ledger.reconstruct(2)


def test_reconstruct_gen_zero_is_hatch_default(tmp_path):
    ledger = LineageLedger(tmp_path / "lineage.jsonl")
    _accept(ledger, 1, 0, "intrinsic_daily_cap", 3, 4)
    from yelos.evolution.genome.registry import hatch_genome

    assert ledger.reconstruct(0) == hatch_genome()
