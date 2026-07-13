"""T2:A2 保守偏序格性质测试——join 幂等/交换/结合;任意子集消解 ⊒ 最保守成员;
子集单调(加元素不减 join)。"""

from __future__ import annotations

import itertools
import random

from yelos.guidance.conflict.lattice import (
    LENGTH_RANK,
    PACE_RANK,
    TONE_RANK,
    join_length,
    join_pace,
    join_respect_pause,
    join_tone,
)

_JOINERS = {
    "tone": (join_tone, TONE_RANK),
    "length": (join_length, LENGTH_RANK),
    "pace": (join_pace, PACE_RANK),
}


def _rank_of(dim: str, value: str) -> int:
    _, rank = _JOINERS[dim]
    return rank[value]


def test_join_idempotent_commutative_associative() -> None:
    rng = random.Random(7)
    for dim, (fn, rank) in _JOINERS.items():
        values = list(rank.keys())
        for _ in range(200):
            subset = [rng.choice(values) for _ in range(rng.randint(0, 5))]
            a = fn(subset)
            b = fn(list(reversed(subset)))
            assert a == b, f"{dim} join 不满足交换律:{subset}"
            # 幂等:重复元素不改变结果
            doubled = subset + subset
            assert fn(doubled) == a, f"{dim} join 不满足幂等:{subset}"


def test_resolve_not_weaker_than_most_conservative_member() -> None:
    for dim, (fn, rank) in _JOINERS.items():
        values = list(rank.keys())
        for size in range(0, 4):
            for subset in itertools.permutations(values, size):
                if not subset:
                    continue
                result = fn(list(subset))
                most_conservative = max(subset, key=lambda v: rank[v])
                assert rank[result] >= rank[most_conservative]


def test_subset_monotone_adding_rules_never_gets_less_conservative() -> None:
    """加规则不变凶:仅比较"已有至少一条贡献"的子集 vs 超集——空子集回落到
    的展示默认值("neutral"/"medium"/"steady")是"无信号时的展示选择",不是
    格的 bottom 元素(v0.1 遗留:tone 的 "direct" 排名低于 "neutral" 默认,
    但从未被任何规则实际产生,§9 Q1 讨论过这类边角不装饰成新数学)。"""
    for dim, (fn, rank) in _JOINERS.items():
        values = list(rank.keys())
        rng = random.Random(hash(dim) & 0xFFFF)
        for _ in range(300):
            subset = [rng.choice(values) for _ in range(rng.randint(1, 4))]
            extra = rng.choice(values)
            superset = subset + [extra]
            assert rank[fn(superset)] >= rank[fn(subset)]


def test_respect_pause_is_boolean_or() -> None:
    assert join_respect_pause([]) is False
    assert join_respect_pause([False, False]) is False
    assert join_respect_pause([False, True]) is True
    assert join_respect_pause([True, True, False]) is True


def test_empty_subset_resolves_to_default() -> None:
    assert join_tone([]) == "neutral"
    assert join_length([]) == "medium"
    assert join_pace([]) == "steady"
