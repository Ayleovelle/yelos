"""T-INV-01(公共不变量千轨迹 property)+ T-GAT-01(策略×闸矩阵)+ T-DET-01(双跑一致)。"""

from __future__ import annotations

import itertools
import random

from yelos.core.intrinsic import IntrinsicDecision
from yelos.intrinsic.field.state import FieldState
from yelos.intrinsic.impulses.field_crossing import FieldCrossingPolicy
from yelos.intrinsic.impulses.gates import GateInput, apply_gates
from yelos.intrinsic.impulses.poisson_budget import PoissonBudgetPolicy
from yelos.intrinsic.impulses.policy import PolicyContext, PolicyProposal
from yelos.intrinsic.impulses.threshold import ThresholdPolicy

_POLICIES = [ThresholdPolicy(), FieldCrossingPolicy(), PoissonBudgetPolicy()]


def _rand_phi(rng: random.Random, ts: float) -> FieldState:
    return FieldState(
        drive=rng.random(),
        languor=rng.random(),
        longing=rng.random(),
        afterglow=rng.random(),
        ts=ts,
    ).clipped()


def _rand_surface(rng: random.Random) -> dict:
    return {
        "state": {
            "needs": {
                "contact": rng.random(),
                "expression": rng.random(),
                "quiet": rng.random(),
            },
            "boundary": {
                "pressure": rng.random(),
                "interruption_budget": rng.random(),
            },
        }
    }


def test_inv01_public_invariants_never_broken_1000_trajectories() -> None:
    rng = random.Random(20260711)
    for i in range(1000):
        phi = _rand_phi(rng, float(i))
        surface = _rand_surface(rng)
        ctx = PolicyContext(
            phi=phi,
            surface=surface,
            p=rng.random(),
            now_ts=float(i * 60),
            now_local_minutes=rng.randint(0, 1439),
            day_key="2026-07-11",
            sent_today=rng.randint(0, 5),
            last_proactive_ts=float(i * 60) - rng.uniform(0, 3 * 3600),
            unanswered_streak=rng.randint(0, 3),
            reach_out_cached=rng.random() < 0.3,
            phase=rng.choice(["active", "cooling", "dormant"]),
            policy_state={"armed": rng.random() < 0.5},
            sid="s1",
            tick_index=i,
        )
        cap = rng.randint(0, 5)
        gate = GateInput(
            surface=surface,
            p=ctx.p,
            enabled=True,
            silenced=False,
            sealed=False,
            guard_frozen_today=rng.random() < 0.2,
            now_local_minutes=ctx.now_local_minutes,
            quiet_start_min=60,
            quiet_end_min=480,
            daily_cap_base=cap,
            sent_today=ctx.sent_today,
            last_proactive_ts=ctx.last_proactive_ts,
            now_ts=ctx.now_ts,
            unanswered_streak=ctx.unanswered_streak,
            contact_night_sent_today=rng.random() < 0.5,
            phase=ctx.phase,
        )

        for policy in _POLICIES:
            proposal = policy.propose(ctx)
            decision = apply_gates(proposal, gate)

            if decision.send:
                # cap 预算恒不破
                import math

                effective_cap = math.ceil(cap * ctx.p) if ctx.p > 0 else 0
                assert gate.sent_today < effective_cap
                # quiet 硬窗恒不破
                from yelos.intrinsic.impulses.gates import _in_interval

                assert not _in_interval(gate.now_local_minutes, 60, 480)
                # min_gap 恒守
                assert gate.now_ts - gate.last_proactive_ts >= 2 * 3600
                # dormant/guard_frozen 时恒不发
                assert gate.phase != "dormant"
                assert not gate.guard_frozen_today
                assert gate.unanswered_streak < 2


def test_gat01_p0_always_wins_regardless_of_policy() -> None:
    """P0 恒最高:sealed/silenced/!enabled 时,即便策略 want=True 也恒不发。"""
    proposal_true = PolicyProposal(want=True, intensity=1.0, trace={})
    base = dict(
        surface=None,
        p=1.0,
        guard_frozen_today=False,
        now_local_minutes=700,
        quiet_start_min=60,
        quiet_end_min=480,
        daily_cap_base=10,
        sent_today=0,
        last_proactive_ts=-1e9,
        now_ts=0.0,
        unanswered_streak=0,
        contact_night_sent_today=False,
        phase="active",
    )
    for sealed, silenced, enabled in itertools.product([True, False], repeat=3):
        if not (sealed or silenced or not enabled):
            continue
        gate = GateInput(enabled=enabled, silenced=silenced, sealed=sealed, **base)
        decision = apply_gates(proposal_true, gate)
        assert decision == IntrinsicDecision(False, reason="p0")


def test_gat01_full_matrix_reason_ordering() -> None:
    """闸链顺序:各闸位单独触发时,reason 与决策表(§2.2)一致(want=True 恒定)。"""
    proposal_true = PolicyProposal(want=True, intensity=1.0, trace={})
    permissive = dict(
        surface=None,
        p=1.0,
        enabled=True,
        silenced=False,
        sealed=False,
        guard_frozen_today=False,
        now_local_minutes=700,
        quiet_start_min=0,
        quiet_end_min=0,
        daily_cap_base=10,
        sent_today=0,
        last_proactive_ts=-1e9,
        now_ts=0.0,
        unanswered_streak=0,
        contact_night_sent_today=False,
        phase="active",
    )

    # dormant
    g = GateInput(**{**permissive, "phase": "dormant"})
    assert apply_gates(proposal_true, g).reason == "dormant"

    # guard_frozen
    g = GateInput(**{**permissive, "guard_frozen_today": True})
    assert apply_gates(proposal_true, g).reason == "guard_frozen"

    # unanswered
    g = GateInput(**{**permissive, "unanswered_streak": 2})
    assert apply_gates(proposal_true, g).reason == "unanswered"

    # daily_cap
    g = GateInput(**{**permissive, "daily_cap_base": 1, "sent_today": 1})
    assert apply_gates(proposal_true, g).reason == "daily_cap"

    # min_gap
    g = GateInput(**{**permissive, "last_proactive_ts": 0.0, "now_ts": 100.0})
    assert apply_gates(proposal_true, g).reason == "min_gap"

    # quiet_hours
    g = GateInput(
        **{
            **permissive,
            "quiet_start_min": 0,
            "quiet_end_min": 1440 // 2,
            "now_local_minutes": 100,
        }
    )
    assert apply_gates(proposal_true, g).reason == "quiet_hours"

    # no_trigger
    proposal_false = PolicyProposal(want=False, intensity=0.0, trace={})
    g = GateInput(**permissive)
    assert apply_gates(proposal_false, g).reason == "no_trigger"

    # 全放行 → send
    g = GateInput(**permissive)
    d = apply_gates(proposal_true, g)
    assert d.send is True


def test_det01_deterministic_double_run_identical() -> None:
    """[AX-7] 同状态同时刻同配置 ⇒ 同决策,双跑一致。"""
    phi = FieldState(drive=0.6, languor=0.3, longing=0.5, afterglow=0.1, ts=100.0)
    surface = {
        "state": {
            "needs": {"contact": 0.7, "expression": 0.5, "quiet": 0.2},
            "boundary": {"pressure": 0.1, "interruption_budget": 0.9},
        }
    }
    ctx = PolicyContext(
        phi=phi,
        surface=surface,
        p=1.0,
        now_ts=100.0,
        now_local_minutes=600,
        day_key="2026-07-11",
        sent_today=0,
        last_proactive_ts=0.0,
        unanswered_streak=0,
        reach_out_cached=False,
        phase="active",
        policy_state={"armed": True},
        sid="s1",
        tick_index=42,
    )
    for policy in _POLICIES:
        p1 = policy.propose(ctx)
        p2 = policy.propose(ctx)
        assert p1 == p2
