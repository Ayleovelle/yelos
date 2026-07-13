"""scheduler/heartbeat.py 在整个架构中的位置:心跳单 session 段编排(§6.1)。

收编 MCP 蓝图 §3.4 心跳步 0–9,只新增步 2b、替换步 4/7 内部实现(接线点
W-1/W-2/W-3,intrinsic_BLUEPRINT §8.1)。本文件不 import astrbot/session.py
(施工纪律禁改那五个文件);它是**新的编排层**,供未来 session.py 的注入式
改造调用——本波先把可独立测试的纯函数步骤立好。

时间(now_ts/local_minutes/day_key)全部经 `scheduler.virtual_clock.Clock`
协议入参([AX-8]),内联补算规则见 §6.2:同一离线时长同起点 ⇒ 同补算结果
(T-SCH-02)。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from ..circadian.forcing import forcing
from ..dreamwork.dream_state import (
    DreamGenerator,
    DreamState,
)
from ..dreamwork.dream_state import (
    arm as dream_arm,
)
from ..dreamwork.dream_state import (
    deliver as dream_deliver,
)
from ..dreamwork.dream_state import (
    push_trace,
)
from ..dreamwork.dream_state import (
    ready as dream_is_ready,
)
from ..dreamwork.dream_state import (
    rollover_day as dream_rollover_day,
)
from ..dreamwork.dream_state import (
    tick as dream_tick_step,
)
from ..field import impacts as impacts_mod
from ..field.integrators import Integrator
from ..field.state import FieldParams, FieldState
from ..impulses.gates import GateInput, apply_gates
from ..impulses.policy import PolicyContext, PolicyProposal, ProactivePolicy
from ..moments.taxonomy import MomentEntry, MomentKind, moment_kind_for_decision

MAX_CATCHUP_STEPS_DEFAULT = 240


# --- 步 2b:场步进(W-1)---------------------------------------------------


def step_field(
    phi: FieldState,
    dt: float,
    ts_after: float,
    local_minutes: int,
    phase_offset_min: float,
    params: FieldParams,
    integrator: Integrator,
    surface: dict | None,
    events: tuple[tuple[str, float], ...] = (),
) -> FieldState:
    """[W-1] 场步进:C(τ) + impacts → integrator.step。静默窗内本步照跑(§6.1 步 3)。

    **单位纪律**:`dt` 是**归一化拍数**(1.0 = 一个完整心跳间隔),不是真实
    秒数——`FieldParams.lam` / `circadian.forcing` 的振幅都按"每拍"标定
    (与 `tests/intrinsic/test_field_numerics.py` 等单元测试里恒用 `dt=1.0`
    一致)。真实时间戳(`ts_after`/`local_minutes`)仍是真实 epoch 秒/本地
    分钟——两套单位不可混用,调用方(`catchup_field`)负责换算。
    """
    c = forcing(local_minutes, phase_offset_min)
    imp = impacts_mod.from_surface(surface, events, params)
    return integrator.step(phi, dt, c, imp, params)


def _closed_form_decay(
    phi: FieldState, elapsed_ticks: float, ts_after: float, params: FieldParams
) -> FieldState:
    """TH-1 闭式衰减快进(§6.2 超上限段):连续极限下的精确指数衰减,忽略强迫/冲击。

    `elapsed_ticks` 同样是归一化拍数(见 `step_field` 单位纪律);`ts_after`
    是快进后对应的真实 epoch 秒(与拍数分开传入,避免二者单位混淆)。
    """
    vec = phi.vec()
    out = []
    for x, lam, eq in zip(vec, params.lam, params.eq):
        out.append(eq + (x - eq) * math.exp(-lam * elapsed_ticks))
    return FieldState.from_vec(tuple(out), ts_after)  # type: ignore[arg-type]


def catchup_field(
    phi: FieldState,
    now_ts: float,
    interval_seconds: float,
    local_minutes_fn: Callable[[float], int],
    params: FieldParams,
    integrator: Integrator,
    *,
    max_catchup_steps: int = MAX_CATCHUP_STEPS_DEFAULT,
) -> FieldState:
    """[§6.2] 内联 tick 模式(heartbeat_enabled=false)的确定性补算规则。

    把 `now-phi.ts` 切成 ≤interval_seconds 的块逐块积分(冲击=0,强迫照 τ
    算);块数超过 `max_catchup_steps` 时,超出部分先用 TH-1 闭式衰减快进,
    末段(`max_catchup_steps` 块)仍逐块积分(强迫近似保留)。同一起点同一
    离线时长 ⇒ 同一结果(T-SCH-02,纯函数,零 random/time.time())。
    """
    elapsed = now_ts - phi.ts
    if elapsed <= 0:
        return phi
    n_full = int(elapsed // interval_seconds)
    remainder = elapsed - n_full * interval_seconds
    n_steps = n_full + (1 if remainder > 1e-9 else 0)

    if n_steps <= max_catchup_steps:
        cur = phi
        remaining = elapsed
        t = phi.ts
        while remaining > 1e-9:
            step_seconds = min(interval_seconds, remaining)
            t_next = t + step_seconds
            dt_ticks = step_seconds / interval_seconds  # 秒 → 归一化拍数(单位纪律)
            cur = step_field(
                cur,
                dt_ticks,
                t_next,
                local_minutes_fn(t_next),
                0.0,
                params,
                integrator,
                None,
                (),
            )
            t = t_next
            remaining -= step_seconds
        return cur

    tail_seconds = max_catchup_steps * interval_seconds
    fast_forward_seconds = elapsed - tail_seconds
    fast_forward_ticks = fast_forward_seconds / interval_seconds
    cur = _closed_form_decay(
        phi, fast_forward_ticks, phi.ts + fast_forward_seconds, params
    )
    remaining = tail_seconds
    t = cur.ts
    while remaining > 1e-9:
        step_seconds = min(interval_seconds, remaining)
        t_next = t + step_seconds
        dt_ticks = step_seconds / interval_seconds
        cur = step_field(
            cur,
            dt_ticks,
            t_next,
            local_minutes_fn(t_next),
            0.0,
            params,
            integrator,
            None,
            (),
        )
        t = t_next
        remaining -= step_seconds
    return cur


# --- 步 4:梦语武装(W-2)---------------------------------------------------


@dataclass(frozen=True)
class DreamStepResult:
    state: DreamState
    trace: tuple[FieldState, ...]
    can_deliver: bool


def step_dream(
    dream_state: DreamState,
    night_trace: tuple[FieldState, ...],
    phi: FieldState,
    surface: dict | None,
    in_quiet_hours: bool,
    just_left_quiet: bool,
    day_key: str,
    day_moments: list[MomentEntry],
    l2_keywords: tuple[str, ...],
    hash_seed: str,
    generator: DreamGenerator,
    p: float,
    enabled: bool,
) -> DreamStepResult:
    """[W-2] 心跳步 4:dream_tick 计数 + 离开 quiet 窗时武装。"""
    state = dream_tick_step(dream_state, surface, in_quiet_hours)
    trace = list(night_trace)
    if in_quiet_hours:
        trace = push_trace(trace, phi)
    if just_left_quiet:
        state = dream_arm(
            state, day_key, trace, day_moments, l2_keywords, generator, hash_seed
        )
        trace = []
    can_deliver = dream_is_ready(state, p, enabled)
    return DreamStepResult(state=state, trace=tuple(trace), can_deliver=can_deliver)


def deliver_dream(state: DreamState) -> DreamState:
    """投递后状态收口(residue 交给 primal dream_murmur 渲染的调用点在编排层外侧)。"""
    return dream_deliver(state)


def rollover_dream_day(state: DreamState) -> DreamState:
    return dream_rollover_day(state)


# --- 步 7:主动策略(W-3)---------------------------------------------------


@dataclass(frozen=True)
class ProactiveStepResult:
    proposal: PolicyProposal
    decision_send: bool
    decision_occasion: str | None
    decision_reason: str
    moment_kind: MomentKind | None


def step_proactive(
    policy: ProactivePolicy, ctx: PolicyContext, gate_input: GateInput
) -> ProactiveStepResult:
    """[W-3] 策略提议 → 公共硬闸裁决([AX-6])→ 记账义务映射。"""
    proposal = policy.propose(ctx)
    decision = apply_gates(proposal, gate_input)
    kind = moment_kind_for_decision(decision)
    return ProactiveStepResult(
        proposal=proposal,
        decision_send=decision.send,
        decision_occasion=decision.occasion,
        decision_reason=decision.reason,
        moment_kind=kind,
    )


__all__ = [
    "MAX_CATCHUP_STEPS_DEFAULT",
    "step_field",
    "catchup_field",
    "DreamStepResult",
    "step_dream",
    "deliver_dream",
    "rollover_dream_day",
    "ProactiveStepResult",
    "step_proactive",
]
