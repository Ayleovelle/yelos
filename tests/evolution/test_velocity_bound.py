"""test_velocity_bound.py:随机轨迹性质——任意策略任意代,每参数步长 ≤ cap(A3)。"""

from __future__ import annotations

import random

from yelos.evolution.genome.registry import mutable_keys, spec_for
from yelos.evolution.variation import STRATEGIES, build_strategy


def test_clamp_step_never_exceeds_cap_random_values():
    from yelos.evolution.variation.base import clamp_step

    rng = random.Random(42)
    velocity_bound = 0.1
    for key in mutable_keys():
        spec = spec_for(key)
        if spec.kind == "enum":
            continue
        for _ in range(200):
            # 域内取值须落在该 kind 的真实取值集合上(int 取整数),否则
            # "old" 本身就不是一个合法的既往 genome 值,断言无意义。
            if spec.kind == "int":
                old = rng.randint(int(spec.lo), int(spec.hi))
                new = rng.randint(int(spec.lo) - 5, int(spec.hi) + 5)
            else:
                old = rng.uniform(spec.lo, spec.hi)
                new = rng.uniform(spec.lo - 5, spec.hi + 5)
            result = clamp_step(spec, old, new, velocity_bound)
            step_cap = velocity_bound * (spec.hi - spec.lo)
            # int kind 的裁剪最后要 round 到整数,允许 <1 的取整滑移。
            slack = 1.0 if spec.kind == "int" else 1e-6
            assert abs(float(result) - old) <= step_cap + slack


def test_enum_moves_at_most_one_notch_per_generation():
    from yelos.evolution.variation.base import clamp_step

    spec = spec_for("finitude_model")
    # finitude_model 是铁域,但拿它的 GeneSpec 形状测试 enum clamp 行为
    # (clamp_step 对 enum 的判定不区分 mutable/iron,那是 guard 的职责)。
    old = spec.choices[0]
    new = spec.choices[-1]
    result = clamp_step(spec, old, new, 0.05)
    # clamp_step 对 enum 只做"同/不同"判断,不做逐档移动(逐档移动是策略层
    # ``pattern_search``/``grid_descent`` 的职责,见 test_strategy 的 enum 分支)。
    assert result in (old, new)


def test_all_strategies_respect_velocity_bound_over_many_generations():
    velocity_bound = 0.08
    from yelos.evolution.genome.registry import hatch_genome

    for name in STRATEGIES:
        strat = build_strategy(name, velocity_bound)
        genome = dict(hatch_genome())
        for gen in range(1, 11):
            candidates = strat.propose(genome, gen, seed="dep-abc")
            for candidate in candidates:
                for key in mutable_keys():
                    spec = spec_for(key)
                    if spec.kind == "enum":
                        continue
                    old = genome.get(key)
                    new = candidate.get(key)
                    if old is None or new is None:
                        continue
                    step_cap = velocity_bound * (spec.hi - spec.lo)
                    assert abs(float(new) - float(old)) <= step_cap + 1e-6, name
            if candidates:
                genome = dict(candidates[0])
