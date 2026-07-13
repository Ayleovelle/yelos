"""维 F 心疼精度(bench_BLUEPRINT §6 表)——契约读取器,不 import shadow。"""

from __future__ import annotations

import json
from pathlib import Path

from yelos.bench.harness.trace import RunTrace
from yelos.bench.metrics import EvalContext, concern

_HEADER = {
    "scenario_id": "t",
    "git_rev": "no-git",
    "engine": "fake",
    "config_hash": "x",
    "schema_ver": 1,
}


def _trace():
    return RunTrace(header=dict(_HEADER), rows=[])


def test_concern_no_data_dir_scores_none():
    score = concern.evaluate(EvalContext(trace=_trace()))
    assert score.value is None
    assert "no-data_dir" in score.evidence["reason"]


def test_concern_missing_ledger_file_scores_none(tmp_path: Path):
    score = concern.evaluate(EvalContext(trace=_trace(), data_dir=tmp_path))
    assert score.value is None
    assert score.evidence["reason"] == "insufficient-samples"
    assert score.evidence["n"] == 0


def _write_ledger(data_dir: Path, sid: str, rows: list[dict]) -> None:
    path = concern.ledger_path(data_dir, sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def test_concern_below_n_min_scores_none(tmp_path: Path):
    _write_ledger(tmp_path, "bench-s1", [{"q": 0.5, "y": 1} for _ in range(5)])
    score = concern.evaluate(EvalContext(trace=_trace(), data_dir=tmp_path))
    assert score.value is None
    assert score.evidence["n"] == 5


def test_concern_perfect_calibration_scores_one(tmp_path: Path):
    rows = [{"q": 1.0, "y": 1} for _ in range(6)] + [
        {"q": 0.0, "y": 0} for _ in range(6)
    ]
    _write_ledger(tmp_path, "bench-s1", rows)
    score = concern.evaluate(EvalContext(trace=_trace(), data_dir=tmp_path))
    assert score.value == 1.0
    assert score.evidence["brier"] == 0.0


def test_concern_worst_calibration_scores_zero(tmp_path: Path):
    rows = [{"q": 1.0, "y": 0} for _ in range(12)]
    _write_ledger(tmp_path, "bench-s1", rows)
    score = concern.evaluate(EvalContext(trace=_trace(), data_dir=tmp_path))
    assert score.value == 0.0
    assert score.evidence["brier"] == 1.0


def test_concern_sid_hash_matches_ledger_path_contract():
    p = concern.ledger_path(Path("/tmp/x"), "bench-s1")
    assert p.name == f"{concern.sid_hash('bench-s1')}.jsonl"
    assert p.parent.name == "calibration"
    assert p.parent.parent.name == "shadow"
