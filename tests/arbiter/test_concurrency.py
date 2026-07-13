"""T-C1:并发性质(arbiter_BLUEPRINT §5.5)。

N8 铁律:hysteresis 不开新锁,真正的锁路径归 session.py 既有的五条
(本波"只建新文件",不改 session.py——见包顶层 docstring)。本文件在
纯函数层面锁定两条可独立验证的并发相关不变量:

1. 顶替语义:未决账在结算前若再次介入,新账顶替旧账(不双结算旧账)。
2. 幂等性:同一 state 上重复调用 settle(pending 已清)不产生副作用
   (线程安全的必要条件——若结算不是幂等的,锁外的重复调用会重复扣血)。
3. 纯函数无共享可变全局态:多线程各自对独立 HystState 副本并发调用
   register/settle,互不干扰(线程安全的直接验证,不依赖任何锁)。
"""

from __future__ import annotations

import threading

from yelos.arbiter.hysteresis import (
    HystState,
    register_intervention,
    settle_outcome,
)
from yelos.arbiter.hysteresis.ema import EmaState
from yelos.arbiter.hysteresis.params import Theta
from yelos.arbiter.hysteresis.signals import SessionSignalState


def _fresh_state() -> HystState:
    return HystState(
        theta=Theta(), ema=EmaState(), n_events=0, signals=SessionSignalState()
    )


def test_new_intervention_replaces_undecided_pending_not_double_settle():
    state = _fresh_state()
    state = register_intervention(
        state, sid="s", turn_id="t1", kind="SWALLOW", ts_i=100.0
    )
    assert state.signals.pending.turn_id == "t1"
    # 未结算 t1,直接来了 t2:顶替,不产生"两条 pending"。
    state = register_intervention(
        state, sid="s", turn_id="t2", kind="REPLACE", ts_i=110.0
    )
    assert state.signals.pending.turn_id == "t2"
    assert state.signals.pending.kind == "REPLACE"
    # 结算只影响 t2 这一条账(n_events 只 +1,不会因为 t1 被顶替过而多算)。
    settled = settle_outcome(state, delta_t=5.0, length=10, p=0.8)
    assert settled.n_events == state.n_events + 1
    assert settled.signals.pending is None


def test_settle_is_idempotent_when_no_pending():
    state = _fresh_state()
    settled_once = settle_outcome(state, delta_t=5.0, length=10, p=0.8)
    assert settled_once == state  # 无待决账时结算是恒等函数
    settled_twice = settle_outcome(settled_once, delta_t=5.0, length=10, p=0.8)
    assert settled_twice == settled_once


def test_concurrent_calls_on_independent_states_do_not_cross_talk():
    """纯函数层面的线程安全直接验证:N 个线程各自持有独立 HystState 副本,
    并发调用 register/settle;断言互不影响(证明模块无隐藏共享可变态)。
    """
    results: list[HystState] = [None] * 8  # type: ignore[list-item]

    def worker(i: int) -> None:
        state = _fresh_state()
        state = register_intervention(
            state, sid=f"s{i}", turn_id=f"t{i}", kind="SWALLOW", ts_i=float(i)
        )
        state = settle_outcome(state, delta_t=float(i + 1), length=i * 3, p=0.5)
        results[i] = state

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i, state in enumerate(results):
        assert state is not None
        assert state.n_events == 1
        assert state.signals.pending is None
        # gaps/lens 只记了自己那一条,没被别的线程污染。
        assert state.signals.gaps == [float(i + 1)]
        assert state.signals.lens == [float(i * 3)]
