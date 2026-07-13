"""30 虚拟日长程 golden(intrinsic_BLUEPRINT §8.2 test_sim_30d.py,三策略各一份)。

用 `scheduler.virtual_clock.VirtualClock` 真实推进(不是自造 day_key 字符串),
驱动同一条固化夹具(`trajectory_ramp.json`)在 30 虚拟日上完整回放;每策略
产出的"每日是否触发"01 序列做自举 golden(首跑落盘,复跑逐字节比对)——
锁住"跨模块改动不改变既有主动节律"的回归线。
"""

from __future__ import annotations

import json
from pathlib import Path

from yelos.intrinsic.circadian.forcing import forcing
from yelos.intrinsic.field.impacts import from_surface
from yelos.intrinsic.field.integrators import EulerIntegrator
from yelos.intrinsic.field.state import FieldParams, FieldState
from yelos.intrinsic.impulses.field_crossing import FieldCrossingPolicy
from yelos.intrinsic.impulses.poisson_budget import PoissonBudgetPolicy
from yelos.intrinsic.impulses.policy import PolicyContext
from yelos.intrinsic.impulses.threshold import ThresholdPolicy
from yelos.intrinsic.scheduler.virtual_clock import VirtualClock

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "trajectory_ramp.json"
_GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden_sim30d"
TICKS_PER_DAY = 48
TICK_SECONDS = 1800


def _load_ramp() -> list[dict]:
    if not _FIXTURE_PATH.exists():
        from .fixtures.gen_trajectories import write_all

        write_all(_FIXTURE_PATH.parent)
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _surface_of(rec: dict) -> dict:
    return {
        "state": {
            "needs": {
                "contact": rec["contact"],
                "expression": rec["expression"],
                "quiet": rec["quiet"],
            },
            "boundary": {"pressure": rec["pressure"], "interruption_budget": 1.0},
        }
    }


def _run_30day(policy, *, lambda_max_for_poisson: float | None = None) -> list[str]:
    trajectory = _load_ramp()
    # 起点对齐本地日历零点(而非任意 epoch 秒):否则 30*86400 秒的推进会跨
    # 31 个不同 day_key(首尾各一个"半天"),与"30 虚拟日"的日历语义不符。
    # 用本机时区把偏移量算出来,不依赖测试运行环境处于哪个时区(可重现)。
    _probe = VirtualClock(0.0)
    _offset_seconds = ((1440 - _probe.local_minutes()) % 1440) * 60
    clock = VirtualClock(float(_offset_seconds))
    params = FieldParams()
    integ = EulerIntegrator()
    phi = FieldState.neutral(clock.now_ts())
    policy_state: dict = {}
    per_day_send: dict[str, bool] = {}

    for i, rec in enumerate(trajectory):
        surface = _surface_of(rec)
        events = tuple((k, v) for k, v in rec.get("events", ()))
        local_minutes = clock.local_minutes()
        c = forcing(local_minutes)
        imp = from_surface(surface, events, params)
        phi = integ.step(phi, 1.0, c, imp, params)

        ctx = PolicyContext(
            phi=phi,
            surface=surface,
            p=1.0,
            now_ts=clock.now_ts(),
            now_local_minutes=local_minutes,
            day_key=clock.day_key(),
            sent_today=0,
            last_proactive_ts=-1e9,
            unanswered_streak=0,
            reach_out_cached=False,
            phase="active",
            policy_state=policy_state,
            sid="sim30d",
            tick_index=i,
        )
        proposal = policy.propose(ctx)
        policy_state = proposal.new_policy_state
        day = clock.day_key()
        per_day_send[day] = per_day_send.get(day, False) or bool(proposal.want)

        clock.advance(TICK_SECONDS)

    return ["1" if per_day_send[d] else "0" for d in sorted(per_day_send)]


def _golden_check(name: str, sequence: list[str]) -> None:
    _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = _GOLDEN_DIR / name
    payload = "".join(sequence)
    if not path.exists():
        path.write_text(payload, encoding="utf-8")
        return
    expected = path.read_text(encoding="utf-8")
    assert payload == expected, f"{name} 30 日触发序列 golden 不一致"


def test_sim30d_threshold_golden() -> None:
    seq = _run_30day(ThresholdPolicy())
    assert len(seq) == 30
    _golden_check("threshold.txt", seq)


def test_sim30d_field_crossing_golden() -> None:
    seq = _run_30day(FieldCrossingPolicy(theta_hi=0.28, theta_lo=0.20))
    assert len(seq) == 30
    _golden_check("field_crossing.txt", seq)


def test_sim30d_poisson_budget_golden() -> None:
    seq = _run_30day(PoissonBudgetPolicy(lambda_max=0.3))
    assert len(seq) == 30
    _golden_check("poisson_budget.txt", seq)


def test_sim30d_reproducible_across_two_runs() -> None:
    """确定性(AX-7):同夹具双跑,三策略逐日触发序列完全一致。"""
    for policy_factory in (
        lambda: ThresholdPolicy(),
        lambda: FieldCrossingPolicy(theta_hi=0.28, theta_lo=0.20),
        lambda: PoissonBudgetPolicy(lambda_max=0.3),
    ):
        seq_a = _run_30day(policy_factory())
        seq_b = _run_30day(policy_factory())
        assert seq_a == seq_b
