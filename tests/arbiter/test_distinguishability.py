"""T-P4:区分度矩阵 golden(arbiter_BLUEPRINT §3.5)——维二正身的机器凭据。

64 条合成 PolicyInput 探针(``fixtures/probes.jsonl``)喂给四套策略,产
4×4(此处退化为 3 套两两配对 + duel vs table)verdict 差异矩阵。验收:
- 每对策略 ∈ {table,smooth,conservative}(异对)至少 3 条探针 verdict 不同;
- duel 至少 3 条探针上 ≠ table;
- 具名示例探针 P1/P2/P3(§3.5)verdict 符合蓝图描述。
矩阵有任何策略对全同 ⇒ 本测试红,策略按换皮剔除、维二计数如实下调
——判据长在测试里,不长在承诺里。
"""

from __future__ import annotations

import json
from pathlib import Path

from yelos.arbiter import build_pipeline
from yelos.arbiter.inputs import PolicyInput, PolicyParams
from yelos.core.arbiter import ArbiterInput

FIXTURE = Path(__file__).parent / "fixtures" / "probes.jsonl"

POLICY_IDS = ["table", "smooth", "conservative", "duel"]


def _load_probes() -> list[dict]:
    rows = []
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _draft_for(n_sentences: int) -> str:
    return "。".join(f"第{i + 1}句" for i in range(n_sentences)) + "。"


def _pin_for(row: dict) -> PolicyInput:
    base = ArbiterInput(
        session_id="probe",
        day_key="2026-07-11",
        draft=_draft_for(row["n_sentences"]),
        surface={
            "decision": {"action": row["action"]},
            "state": {
                "boundary": {"pressure": row["pressure"]},
                "needs": {"expression": row["expr"]},
            },
            "guard": {"allowed": True},
        },
        p=row["p"],
        bound=True,
        enabled=True,
        silenced=False,
        is_self=False,
        has_plain=True,
        has_non_plain=False,
        now_ts=1_000_000.0,
        last_intervention_ts=0.0,
        min_gap_seconds=180,
    )
    params = PolicyParams(0.75, 0.55, 0.70, 1.0)
    return PolicyInput(
        base=base,
        surface_age_s=row["surface_age_s"],
        daily_interventions=row["daily_interventions"],
        params=params,
    )


def _matrix() -> dict[str, list[str]]:
    rows = _load_probes()
    pipes = {pid: build_pipeline(pid) for pid in POLICY_IDS}
    matrix: dict[str, list[str]] = {pid: [] for pid in POLICY_IDS}
    for row in rows:
        pin = _pin_for(row)
        for pid in POLICY_IDS:
            v, _ = pipes[pid].run(pin)
            matrix[pid].append(v.kind)
    return matrix


def test_probe_fixture_has_64_rows():
    assert len(_load_probes()) == 64


def test_pairwise_distinguishability_at_least_three_differ():
    matrix = _matrix()
    pairs = [("table", "smooth"), ("table", "conservative"), ("smooth", "conservative")]
    for a, b in pairs:
        diff = sum(1 for x, y in zip(matrix[a], matrix[b]) if x != y)
        assert diff >= 3, f"{a} vs {b} 只有 {diff} 条探针不同(<3),疑似换皮"


def test_duel_differs_from_table_at_least_three():
    matrix = _matrix()
    diff = sum(1 for x, y in zip(matrix["duel"], matrix["table"]) if x != y)
    assert diff >= 3, f"duel vs table 只有 {diff} 条探针不同(<3)"


def test_no_pair_is_globally_identical():
    matrix = _matrix()
    for a in ("table", "smooth", "conservative"):
        for b in ("table", "smooth", "conservative"):
            if a >= b:
                continue
            assert matrix[a] != matrix[b], (
                f"{a} 与 {b} 在全部 64 条探针上逐字节相同 ⇒ 换皮"
            )


def test_named_example_probes_p1_p2_p3():
    rows = _load_probes()
    by_id = {r["id"]: r for r in rows}
    pipes = {pid: build_pipeline(pid) for pid in ("table", "smooth", "conservative")}

    p1 = _pin_for(by_id["P1"])
    v_table, _ = pipes["table"].run(p1)
    v_smooth, _ = pipes["smooth"].run(p1)
    assert v_table.kind == "REPLACE"
    assert v_smooth.kind == "SWALLOW"

    p2 = _pin_for(by_id["P2"])
    v_table2, _ = pipes["table"].run(p2)
    v_cons2, _ = pipes["conservative"].run(p2)
    assert v_table2.kind in ("TRIM", "REPLACE")
    assert v_cons2.kind == "PASS"
    assert v_cons2.reason == "conservative_stale_abstain"

    p3 = _pin_for(by_id["P3"])
    v_cons3, _ = pipes["conservative"].run(p3)
    assert v_cons3.kind == "PASS"
    assert v_cons3.reason == "conservative_budget_exhausted"
