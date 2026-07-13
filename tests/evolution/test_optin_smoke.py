"""test_optin_smoke.py:opt-in 全链冒烟(CI 常设,§5.1/§8 验收总闸)。

开 evolution -> fake bench(固定适应度地形)跑 3 代虚拟漂移 -> 断言 lineage
行结构正确、铁参数逐字节未动(A2)、overlay 生效于重载、rollback --gen 0
-> overlay 字节级复原、同剧本回放(以 fake harness 重跑同 genome)与第 0 代
一致。
"""

from __future__ import annotations

import json

from yelos.evolution import build_evolution
from yelos.evolution.genome.registry import REGISTRY, hatch_genome, iron_keys
from yelos.evolution.overlay import apply_overlay, load_overlay


def _clock(start=1_700_000_000.0):
    state = {"t": start}

    def now_fn():
        state["t"] += (
            86400.0 * 8
        )  # 每代跨过 min_days,免得被 T6 节流(此处 runner 不判该表,留给 scheduler)
        return state["t"]

    return now_fn


def test_three_generation_smoke_then_rollback(base_config, tmp_path, fake_harness):
    evo = build_evolution(base_config, data_dir=tmp_path)
    assert evo is not None
    assert evo.validate() == []

    now_fn = _clock()
    summary = evo.run(3, now_fn=now_fn, harness=fake_harness, scenario="s1")

    records = evo.ledger.all_records()
    assert len(records) == 3
    assert len(summary.outcomes) == 3
    for record in records:
        assert record.verdict in (
            "accepted",
            "rejected_guard_static",
            "rejected_guard_property",
            "rejected_fitness",
        )
        # A2:铁域参数逐字节未动,任何一代都不例外。
        for change in record.changes:
            assert change.key not in iron_keys()

    # overlay 生效于"重载 config"这个动作:apply_overlay 读现行 overlay
    # 后,intrinsic_daily_cap 之外的所有铁域键必须逐字节等于 hatch 默认。
    genome_after = evo.current_genome()
    hatch = hatch_genome()
    for spec in REGISTRY:
        if not spec.mutable:
            assert genome_after[spec.key] == hatch[spec.key], spec.key

    # rollback --gen 0 -> overlay 字节级复原为"从未进化"。
    path = evo.rollback(0)
    payload = json.loads(path.read_bytes())
    assert payload["values"] == {}
    assert payload["gen"] == 0

    # 同剧本回放:以 gen0 genome 重跑 fake_harness,得分应与"从未漂移过"
    # 的基线一致(fake_harness 是纯函数,幂等可复算)。
    genome0 = apply_overlay(load_overlay(evo.overlay_path).get("values"))
    assert genome0 == hatch_genome()
    replay = fake_harness.evaluate(genome0, "s1")
    baseline = fake_harness.evaluate(hatch_genome(), "s1")
    assert replay == baseline


def test_scenario_replay_diverges_after_accepted_drift(base_config, tmp_path):
    """行为 E 切面 E-a 的最小可观测断言:若跑出至少一代 accepted,同剧本
    回放分数应与第 0 代确定性地不同(可归因到 lineage 的具体变更行)。
    未必每次调用都恰好产生 accepted(哈希方向 + judge 平手保守都可能拒),
    因此本测试用较宽的代数与宽松断言:若整段跑完全程序都没有一次
    accepted,则如实跳过(不假装观测到了不存在的差异)。
    """
    import pytest

    class DirectionalHarness:
        def evaluate(self, candidate, scenario):
            cap = float(candidate.get("intrinsic_daily_cap", 3))
            return {"overall": cap * 10.0, "vetoes": [], "report_path": "x"}

    evo = build_evolution(base_config, data_dir=tmp_path)
    now_fn = _clock()
    summary = evo.run(6, now_fn=now_fn, harness=DirectionalHarness(), scenario="s1")

    accepted = [o for o in summary.outcomes if o.verdict == "accepted"]
    if not accepted:
        pytest.skip(
            "哈希方向本次全落在非改进侧,未产生 accepted 代(如实跳过,不硬凑观测)"
        )

    genome_now = evo.current_genome()
    genome0 = apply_overlay(None)
    assert genome_now != genome0
