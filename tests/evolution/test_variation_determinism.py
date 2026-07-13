"""test_variation_determinism.py:同 parent/gen/seed 同提案;AST 扫描零 random/time.time(§2.2)。"""

from __future__ import annotations

import ast
from pathlib import Path

from yelos.evolution.genome.registry import hatch_genome
from yelos.evolution.variation import STRATEGIES, build_strategy

_PKG_ROOT = Path(__file__).resolve().parents[2] / "src" / "yelos" / "evolution"


def test_same_parent_gen_seed_gives_same_proposal():
    genome = hatch_genome()
    for name in STRATEGIES:
        strat_a = build_strategy(name, 0.05)
        strat_b = build_strategy(name, 0.05)
        out_a = strat_a.propose(genome, 3, seed="dep-xyz")
        out_b = strat_b.propose(genome, 3, seed="dep-xyz")
        assert out_a == out_b, name


def test_different_seed_can_change_proposal_direction():
    genome = hatch_genome()
    strat = build_strategy("pattern_search", 0.3)
    out_a = strat.propose(genome, 1, seed="dep-1")
    out_b = strat.propose(genome, 1, seed="dep-2")
    # 不强求必然不同(哈希可能撞向同方向),但至少两次调用本身是确定性的。
    assert strat.propose(genome, 1, seed="dep-1") == out_a
    assert strat.propose(genome, 1, seed="dep-2") == out_b


def test_evolution_package_has_no_hashlib_or_random_imports():
    """primal/determinism.py 是全平台唯一 hashlib 落点(蓝图 §10 纪律);
    本包一律经 ``primal.determinism`` 间接调用,零直接 ``hashlib``/``random``。
    """
    forbidden_modules = {"random", "hashlib"}
    for path in _PKG_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden_modules, (
                        f"{path}: import {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden_modules, (
                    f"{path}: from {node.module}"
                )


def test_core_logic_files_never_call_time_time():
    """纯逻辑层(genome/variation/selection/guards/lineage/overlay/runner)
    禁 ``time.time()``——时间一律入参化。``__main__.py`` 是 CLI 边界,同
    ``bench.RealClock`` 一样是"注入真实时间"的合法落点,不在此扫描范围内。
    """
    scanned = [p for p in _PKG_ROOT.rglob("*.py") if p.name != "__main__.py"]
    for path in scanned:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "time"
                and isinstance(node.value, ast.Name)
                and node.value.id == "time"
            ):
                raise AssertionError(f"{path}: time.time() usage forbidden")
