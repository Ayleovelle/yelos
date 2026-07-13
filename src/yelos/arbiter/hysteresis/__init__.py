"""hysteresis 子包在整个架构中的位置:本模块的深度正身(arbiter_BLUEPRINT §5)。

去掉它,平台缺哪个可观测行为:所有同配置的心永远同脾气——两颗经历完全
不同的心对同一探针永远同 verdict,阈值漂移曲线恒为水平线。T3/T-H5 把
这句话钉成机器凭据(见 tests/arbiter/test_hysteresis.py)。

三处生命周期挂点(W-2 接线清单,§9;本波只交付纯函数,session.py 的
真实接线是另一任务,见施工纪律"只建新文件"):
1. 介入(σ>=1)发生 -> ``register_intervention``(arbitrate 锁段)
2. 下一次 submit(user) -> ``settle_outcome``(submit 锁段)
3. 心跳 rollover 前仍未决 -> ``settle_silence``(心跳单 session 锁段)

三者均为纯函数(时间入参化,无 random/无时钟直读,A5.5);调用方负责
持锁与 store.save_into + BindingStore.save()。
"""

from __future__ import annotations

from dataclasses import replace

from .ema import ALPHA_FAST, ALPHA_SLOW, EmaState
from .params import BOX, BOX_VERTICES, MUTABLE_SET, STEP, Theta
from .signals import (
    PendingOutcome,
    SessionSignalState,
    compute_r,
    kind_for_intervention,
    med_mad,
)
from .store import HystState, default_block, dump, load, save_into
from .updater import ETA0, apply_update, learning_rate

__all__ = [
    "ALPHA_FAST",
    "ALPHA_SLOW",
    "EmaState",
    "BOX",
    "BOX_VERTICES",
    "MUTABLE_SET",
    "STEP",
    "Theta",
    "PendingOutcome",
    "SessionSignalState",
    "compute_r",
    "kind_for_intervention",
    "med_mad",
    "HystState",
    "default_block",
    "dump",
    "load",
    "save_into",
    "ETA0",
    "apply_update",
    "learning_rate",
    "register_intervention",
    "settle_outcome",
    "settle_silence",
]


def register_intervention(
    state: HystState, *, sid: str, turn_id: str, kind: str, ts_i: float
) -> HystState:
    """介入发生后登记待决账。新介入顶替未决旧账(§5.1:至多 1 条),
    旧账在顶替前**不**结算(不应期已保证介入稀疏,顶替是设计取舍,
    不是遗漏——沉默结算只覆盖"到 rollover 都未等到下一次 submit"的账)。
    """
    pending = PendingOutcome(sid=sid, turn_id=turn_id, kind=kind, ts_i=ts_i)
    new_signals = replace(state.signals, pending=pending)
    return replace(state, signals=new_signals)


def _settle_common(
    state: HystState, *, delta_t: float, length: int, silent: bool, p: float
) -> HystState:
    pending = state.signals.pending
    if pending is None:
        return state
    r = compute_r(
        delta_t=delta_t,
        length=length,
        gaps=state.signals.gaps,
        lens=state.signals.lens,
        silent=silent,
    )
    new_ema = state.ema.update(r)
    consensus = new_ema.consensus()
    new_theta = apply_update(
        state.theta, kind=pending.kind, r=r, consensus=consensus, p=p
    )
    # 显式拷贝环缓冲(而非 dataclasses.replace 的浅拷贝共享同一 list),
    # 保证每个 HystState 是独立快照,不会因后续 push 反向污染旧快照
    # ——这一点是 T-H3/T-H6 可回放性断言(比较历史快照序列)的前提。
    new_signals = SessionSignalState(
        gaps=list(state.signals.gaps), lens=list(state.signals.lens), pending=None
    )
    if not silent:
        new_signals.push_gap(delta_t)
        new_signals.push_len(float(length))
    return HystState(
        theta=new_theta, ema=new_ema, n_events=state.n_events + 1, signals=new_signals
    )


def settle_outcome(
    state: HystState, *, delta_t: float, length: int, p: float
) -> HystState:
    """下一次 submit(user) 的结算(§5.1);无待决账时原样返回。"""
    return _settle_common(state, delta_t=delta_t, length=length, silent=False, p=p)


def settle_silence(state: HystState, *, p: float) -> HystState:
    """心跳 rollover 前仍未等到 submit -> 沉默结算,r=-0.5(温和负)。"""
    return _settle_common(state, delta_t=0.0, length=0, silent=True, p=p)
