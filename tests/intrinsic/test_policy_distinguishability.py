"""T-DST-01..04:同一事件轨迹上的区分观测量(intrinsic_BLUEPRINT §3.2,维二机器凭据)。

三策略在**同一轨迹、同一场、同一闸配置**(此处按 §3.2"闸前触发序列"要求,
直接比较 `policy.propose()` 的 want,不经 `apply_gates`)下回放固化夹具
`tests/intrinsic/fixtures/trajectory_{step,ramp,silence}.json`(由
`gen_trajectories.py` 确定性生成)。

**简化说明(如实记录,§10 诚实纪律)**:三策略共享同一条物理场轨迹(用同一
组 Surface 序列积分一次得到),`FieldCrossingPolicy.recoil()` 的场回冲在
本对比测试中**不**反馈进共享轨迹——真实生产路径里 recoil 只影响该策略
自己观测到的后续场,三策略会因此各自读到略有分叉的场;为了满足§3.2
"同一轨迹、同一场"的可比性要求,本测试有意不引入这层反馈分叉,退化为
"策略只读同一份只读场"的对比,分叉效应本身不是本测试的度量对象。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from yelos.intrinsic.circadian.forcing import forcing
from yelos.intrinsic.field.impacts import from_surface
from yelos.intrinsic.field.integrators import EulerIntegrator
from yelos.intrinsic.field.state import FieldParams, FieldState
from yelos.intrinsic.impulses.field_crossing import (
    FieldCrossingPolicy,
    scalar_potential,
)
from yelos.intrinsic.impulses.poisson_budget import PoissonBudgetPolicy
from yelos.intrinsic.impulses.policy import PolicyContext
from yelos.intrinsic.impulses.threshold import ThresholdPolicy

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_EXPERIMENTS_DIR = (
    Path(__file__).resolve().parents[2] / "experiments" / "intrinsic" / "policy_compare"
)

TICKS_PER_DAY = 48
TICK_SECONDS = 1800

# 调参笔记:默认 FieldCrossingPolicy(theta_hi=0.32, theta_lo=0.18) 在本夹具的
# 数值范围内过于贴边(日内 s(t) 稳态振荡区间约 [0.17, 0.32]);为让"越阈+
# 迟滞回落再武装"在夹具上稳定可复现(而不是卡在浮点边界),本测试显式收紧
# 迟滞带为 (0.20, 0.28),仍满足 FieldCrossingPolicy 的构造约束
# (0 <= theta_lo < theta_hi)。夹具本身(gen_trajectories.py)的日周期设计
# 保证 s(t) 每日既下穿 0.20 又上穿 0.28。
_THETA_LO = 0.20
_THETA_HI = 0.28


def _fc_policy() -> FieldCrossingPolicy:
    return FieldCrossingPolicy(theta_hi=_THETA_HI, theta_lo=_THETA_LO)


def _load_fixture(name: str) -> list[dict]:
    path = _FIXTURES_DIR / f"trajectory_{name}.json"
    if not path.exists():
        from .fixtures.gen_trajectories import write_all

        write_all(_FIXTURES_DIR)
    return json.loads(path.read_text(encoding="utf-8"))


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


def _build_phi_trace(trajectory: list[dict], params: FieldParams) -> list[FieldState]:
    """三策略共享的物理场轨迹(积分一次,策略只读)。"""
    integ = EulerIntegrator()
    phi = FieldState.neutral(0.0)
    trace = []
    for rec in trajectory:
        surface = _surface_of(rec)
        events = tuple((k, i) for k, i in rec.get("events", ()))
        c = forcing(rec["local_minutes"])
        imp = from_surface(surface, events, params)
        phi = integ.step(phi, 1.0, c, imp, params)
        trace.append(phi)
    return trace


def _replay(trajectory: list[dict], phi_trace: list[FieldState], policy) -> list[bool]:
    policy_state: dict = {}
    wants = []
    for i, (rec, phi) in enumerate(zip(trajectory, phi_trace)):
        surface = _surface_of(rec)
        ctx = PolicyContext(
            phi=phi,
            surface=surface,
            p=1.0,
            now_ts=float(i * TICK_SECONDS),
            now_local_minutes=rec["local_minutes"],
            day_key=rec["day"],
            sent_today=0,
            last_proactive_ts=-1e9,
            unanswered_streak=0,
            reach_out_cached=False,
            phase="active",
            policy_state=policy_state,
            sid="dst-fixture",
            tick_index=i,
        )
        proposal = policy.propose(ctx)
        policy_state = proposal.new_policy_state
        wants.append(bool(proposal.want))
    return wants


def _circular_variance(tick_positions: list[int], period: int) -> float:
    if not tick_positions:
        return 0.0
    sx = sum(math.cos(2 * math.pi * t / period) for t in tick_positions)
    sy = sum(math.sin(2 * math.pi * t / period) for t in tick_positions)
    n = len(tick_positions)
    r = math.hypot(sx, sy) / n
    return 1.0 - r


def _median(values: list[float]) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def test_o1_trigger_time_sets_pairwise_differ() -> None:
    params = FieldParams()
    trajectory = _load_fixture("step")
    phi_trace = _build_phi_trace(trajectory, params)

    th_wants = _replay(trajectory, phi_trace, ThresholdPolicy())
    fc_wants = _replay(trajectory, phi_trace, _fc_policy())
    pb_wants = _replay(trajectory, phi_trace, PoissonBudgetPolicy())

    th_set = {i for i, w in enumerate(th_wants) if w}
    fc_set = {i for i, w in enumerate(fc_wants) if w}
    pb_set = {i for i, w in enumerate(pb_wants) if w}

    assert th_set != fc_set
    assert th_set != pb_set
    assert fc_set != pb_set


def test_o2_impact_to_trigger_latency_fieldcrossing_slower_on_ramp() -> None:
    params = FieldParams()
    trajectory = _load_fixture("ramp")
    phi_trace = _build_phi_trace(trajectory, params)

    th_wants = _replay(trajectory, phi_trace, ThresholdPolicy())
    fc_wants = _replay(trajectory, phi_trace, _fc_policy())

    th_latencies: list[float] = []
    fc_latencies: list[float] = []
    for day_start in range(0, len(trajectory), TICKS_PER_DAY):
        day_end = day_start + TICKS_PER_DAY
        th_hits = [i - day_start for i in range(day_start, day_end) if th_wants[i]]
        fc_hits = [i - day_start for i in range(day_start, day_end) if fc_wants[i]]
        if th_hits:
            th_latencies.append(float(th_hits[0]))
        if fc_hits:
            fc_latencies.append(float(fc_hits[0]))

    assert th_latencies, "Threshold 应在缓坡夹具上至少每日触发一次"
    assert fc_latencies, "FieldCrossing 应在缓坡夹具上至少每日触发一次"
    median_th = _median(th_latencies)
    median_fc = _median(fc_latencies)
    assert median_fc > median_th
    assert median_fc - median_th >= 1.0


def test_o3_intraday_dispersion_poisson_more_than_fieldcrossing_on_plateau() -> None:
    params = FieldParams()
    trajectory = _load_fixture("ramp")
    phi_trace = _build_phi_trace(trajectory, params)

    fc_wants = _replay(trajectory, phi_trace, _fc_policy())
    pb_wants = _replay(trajectory, phi_trace, PoissonBudgetPolicy(lambda_max=0.5))

    fc_ticks_of_day = [i % TICKS_PER_DAY for i, w in enumerate(fc_wants) if w]
    pb_ticks_of_day = [i % TICKS_PER_DAY for i, w in enumerate(pb_wants) if w]

    assert fc_ticks_of_day and pb_ticks_of_day
    circ_var_fc = _circular_variance(fc_ticks_of_day, TICKS_PER_DAY)
    circ_var_pb = _circular_variance(pb_ticks_of_day, TICKS_PER_DAY)
    assert circ_var_pb > circ_var_fc


def test_o4_trigger_crossing_alignment() -> None:
    params = FieldParams()
    trajectory = _load_fixture("ramp")
    phi_trace = _build_phi_trace(trajectory, params)

    s_values = [scalar_potential(phi) for phi in phi_trace]
    theta_hi = _fc_policy().theta_hi
    crossing_ticks = {
        i
        for i in range(len(s_values))
        if s_values[i] >= theta_hi and (i == 0 or s_values[i - 1] < theta_hi)
    }

    fc_wants = _replay(trajectory, phi_trace, _fc_policy())
    pb_wants = _replay(trajectory, phi_trace, PoissonBudgetPolicy(lambda_max=0.5))

    fc_hits = {i for i, w in enumerate(fc_wants) if w}
    pb_hits = {i for i, w in enumerate(pb_wants) if w}

    fc_ratio = len(fc_hits & crossing_ticks) / len(fc_hits) if fc_hits else 0.0
    pb_ratio = len(pb_hits & crossing_ticks) / len(pb_hits) if pb_hits else 0.0

    assert fc_ratio == 1.0
    assert pb_ratio < 1.0


def test_policy_compare_dump_written() -> None:
    """对比评测数据落盘(§3.2),供 bench 报告引用(W4)。"""
    params = FieldParams()
    summary: dict[str, dict] = {}
    for fixture_name in ("step", "ramp", "silence"):
        trajectory = _load_fixture(fixture_name)
        phi_trace = _build_phi_trace(trajectory, params)
        per_policy = {}
        for policy_name, policy in (
            ("threshold", ThresholdPolicy()),
            ("field_crossing", _fc_policy()),
            ("poisson_budget", PoissonBudgetPolicy()),
        ):
            wants = _replay(trajectory, phi_trace, policy)
            per_policy[policy_name] = {
                "trigger_count": sum(1 for w in wants if w),
                "trigger_ticks": [i for i, w in enumerate(wants) if w],
            }
        summary[fixture_name] = per_policy

    _EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _EXPERIMENTS_DIR / "policy_compare_summary.json"
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert out_path.exists()
