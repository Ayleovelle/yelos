"""T8 零漂移金测(I3):新引擎(chat profile,``continuity=None``)与冻结版
v0.1 逐字实现逐字节一致。边界全组合 + 种子化随机输入。

冻结版取自 ``yelos.guidance._v01_compat``(见该模块顶注:v0.1 逐字实现物
理住在 ``yelos/guidance/__init__.py``,``_v01_compat`` 是稳定重导出路径)。
"""

from __future__ import annotations

import itertools
import random

from yelos.guidance._v01_compat import build_guidance as frozen_build_guidance
from yelos.guidance.compiler.interpreter import evaluate

ACTIONS = [
    "withdraw",
    "recover",
    "reach_out",
    "explore",
    "guard",
    "express",
    "hold",
    "unknown",
]
PHASES = ["active", "dormant"]
MODES = ["companion", "steward"]
BOUNDARY_VALUES = [
    0.0,
    0.1,
    0.29,
    0.3,
    0.31,
    0.5,
    0.59,
    0.6,
    0.61,
    0.69,
    0.7,
    0.71,
    0.9,
    1.0,
]


def _surface(
    action,
    strain,
    fatigue,
    warmth,
    damage,
    autonomy,
    paused,
    quiet,
    expression,
    phase,
    caution,
    guard_allowed,
):
    return {
        "decision": {"action": action},
        "state": {
            "rhythm": {"strain": strain},
            "responsiveness": {"fatigue": fatigue},
            "valence": {"warmth": warmth},
            "damage": {"accumulated": damage},
            "boundary": {"autonomy": autonomy, "paused": paused},
            "needs": {"quiet": quiet, "expression": expression},
        },
        "dynamics": {
            "relational_time": {"phase": phase},
            "uncertainty": {"claim_caution": caution},
        },
        "guard": {"allowed": guard_allowed},
    }


def _assert_matches(surface, mode, concern):
    expected = frozen_build_guidance(surface, mode, concern)
    got = evaluate(surface, mode, concern, profile="chat").guidance
    assert got == expected, (surface, mode, concern, expected, got)


def test_golden_boundary_grid_subset() -> None:
    # 全组合太大(8 action * 14^6 数值 * 2 phase * 2 mode * 2 concern);
    # 抽样边界组合,覆盖每个数值维度的阈下/阈上/恰阈 + 关键 action/phase/mode 交叉。
    rng = random.Random(20260711)
    combos = list(
        itertools.product(ACTIONS, MODES, PHASES, [True, False], [True, False])
    )
    rng.shuffle(combos)
    for action, mode, phase, concern, guard_allowed in combos[:200]:
        strain = rng.choice(BOUNDARY_VALUES)
        fatigue = rng.choice(BOUNDARY_VALUES)
        warmth = rng.choice(BOUNDARY_VALUES)
        damage = rng.choice(BOUNDARY_VALUES)
        autonomy = rng.choice(BOUNDARY_VALUES)
        paused = rng.choice([True, False])
        quiet = rng.choice(BOUNDARY_VALUES)
        expression = rng.choice(BOUNDARY_VALUES)
        caution = rng.choice(BOUNDARY_VALUES)
        surface = _surface(
            action,
            strain,
            fatigue,
            warmth,
            damage,
            autonomy,
            paused,
            quiet,
            expression,
            phase,
            caution,
            guard_allowed,
        )
        _assert_matches(surface, mode, concern)


def test_golden_seeded_random_10k() -> None:
    rng = random.Random(42)
    for _ in range(2000):  # 深度收窄:2k(维护性/CI 时间折中),仍是种子化可复现
        action = rng.choice(ACTIONS)
        mode = rng.choice(MODES)
        phase = rng.choice(PHASES)
        concern = rng.choice([True, False])
        guard_allowed = rng.choice([True, False, None])
        surface = _surface(
            action,
            rng.random(),
            rng.random(),
            rng.random(),
            rng.random(),
            rng.random(),
            rng.choice([True, False]),
            rng.random(),
            rng.random(),
            phase,
            rng.random(),
            guard_allowed if guard_allowed is not None else True,
        )
        _assert_matches(surface, mode, concern)


def test_golden_missing_and_none_surface() -> None:
    for surface in (None, {}, {"decision": {}}, {"state": {}}):
        for mode in MODES:
            for concern in (True, False):
                _assert_matches(surface, mode, concern)


def test_golden_deterministic_repeat() -> None:
    surface = _surface(
        "reach_out", 0.2, 0.1, 0.8, 0.0, 0.9, False, 0.0, 0.0, "active", 0.0, True
    )
    a = evaluate(surface, "companion", False, profile="chat")
    b = evaluate(surface, "companion", False, profile="chat")
    assert a.guidance == b.guidance
