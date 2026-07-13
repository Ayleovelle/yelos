"""T-G1:θ≡0 + table 策略与冻结 core.arbiter.arbitrate 逐字节一致(兼容闸,
arbiter_BLUEPRINT §8/§10 B2:"B2 的兼容 golden 是全蓝图的一号闸")。

覆盖:穷举网格(action × pressure × expr × P × narrow)+ v0.1
tests/test_arbiter.py 原样保持全绿(该文件本身未改动,由 CI 独立跑)。
"""

from __future__ import annotations

import itertools

from yelos.arbiter.inputs import PolicyInput, PolicyParams
from yelos.arbiter.policies.table import TABLE_POLICY
from yelos.core.arbiter import ArbiterInput, arbitrate

ACTIONS = [
    "withdraw",
    "hold",
    "guard",
    "recover",
    "reach_out",
    "explore",
    "express",
    "weird_future_action",
]
PRESSURES = [
    0.0,
    0.1,
    0.14,
    0.16,
    0.3,
    0.54,
    0.55,
    0.56,
    0.69,
    0.7,
    0.74,
    0.75,
    0.76,
    0.9,
    1.0,
]
EXPRS = [0.0, 0.1, 0.29, 0.3, 0.31, 0.5, 0.69, 0.7, 0.71, 1.0]
PS = [0.0, 0.1, 0.14, 0.15, 0.16, 0.3, 0.49, 0.5, 0.51, 0.8, 1.0]


def _grid():
    sid_counter = 0
    for action, pressure, expr, p in itertools.islice(
        itertools.product(ACTIONS, PRESSURES, EXPRS, PS), 0, None
    ):
        sid_counter += 1
        yield action, pressure, expr, p, sid_counter


def test_table_policy_matches_frozen_core_exhaustive_grid():
    checked = 0
    for action, pressure, expr, p, i in _grid():
        base = ArbiterInput(
            session_id=f"sid{i % 7}",
            day_key="2026-07-11",
            draft="今天天气不错,我们出去走走吧,好不好。这是第二句。这是第三句。这是第四句。",
            surface={
                "decision": {"action": action},
                "state": {
                    "boundary": {"pressure": pressure},
                    "needs": {"expression": expr},
                },
                "guard": {"allowed": True},
            },
            p=p,
            bound=True,
            enabled=True,
            silenced=False,
            is_self=False,
            has_plain=True,
            has_non_plain=False,
            now_ts=100000.0,
            last_intervention_ts=0.0,
            min_gap_seconds=180,
        )
        expected = arbitrate(base)
        pin = PolicyInput(
            base=base,
            surface_age_s=0.0,
            daily_interventions=0,
            params=PolicyParams(0.75, 0.55, 0.70, 1.0),
        )
        actual = TABLE_POLICY.decide(pin)
        assert actual == expected, (action, pressure, expr, p, actual, expected)
        checked += 1
    assert checked == len(ACTIONS) * len(PRESSURES) * len(EXPRS) * len(PS)


def test_table_policy_matches_frozen_core_guard_paths():
    variants = [
        dict(bound=False),
        dict(enabled=False),
        dict(silenced=True),
        dict(is_self=True),
        dict(has_plain=False),
        dict(has_non_plain=True),
        dict(draft="   "),
        dict(surface=None),
    ]
    for overrides in variants:
        kwargs = dict(
            session_id="sidx",
            day_key="2026-07-11",
            draft="草稿。",
            surface={
                "decision": {"action": "hold"},
                "state": {"boundary": {"pressure": 0.5}, "needs": {"expression": 0.5}},
                "guard": {"allowed": True},
            },
            p=0.8,
            bound=True,
            enabled=True,
            silenced=False,
            is_self=False,
            has_plain=True,
            has_non_plain=False,
            now_ts=100000.0,
            last_intervention_ts=0.0,
            min_gap_seconds=180,
        )
        kwargs.update(overrides)
        base = ArbiterInput(**kwargs)
        expected = arbitrate(base)
        pin = PolicyInput(
            base=base,
            surface_age_s=0.0,
            daily_interventions=0,
            params=PolicyParams(0.75, 0.55, 0.70, 1.0),
        )
        actual = TABLE_POLICY.decide(pin)
        assert actual == expected, (overrides, actual, expected)


def test_table_policy_ignores_theta_and_params():
    """TablePolicy 忽略 θ 生效后的 PolicyParams(N2:内核阈值硬编码)。"""
    base = ArbiterInput(
        session_id="sidy",
        day_key="2026-07-11",
        draft="今天天气不错。这是第二句。这是第三句。这是第四句。",
        surface={
            "decision": {"action": "withdraw"},
            "state": {"boundary": {"pressure": 0.6}, "needs": {"expression": 0.5}},
            "guard": {"allowed": True},
        },
        p=0.8,
        bound=True,
        enabled=True,
        silenced=False,
        is_self=False,
        has_plain=True,
        has_non_plain=False,
        now_ts=100000.0,
        last_intervention_ts=0.0,
        min_gap_seconds=180,
    )
    expected = arbitrate(base)
    for params in (
        PolicyParams(0.60, 0.45, 0.55, 0.8),
        PolicyParams(0.90, 0.65, 0.85, 1.2),
    ):
        pin = PolicyInput(
            base=base, surface_age_s=999.0, daily_interventions=99, params=params
        )
        assert TABLE_POLICY.decide(pin) == expected
