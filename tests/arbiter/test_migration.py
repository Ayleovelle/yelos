"""T-H7:binding schema 迁移(arbiter_BLUEPRINT §5.5 / INTEGRATION_SPEC §2.1)。

v0.1 binding record 无 ``arbiter_hyst`` 块 ⇒ 加载即初始化默认值(不 raise);
往返(load -> save_into -> load)保真。
"""

from __future__ import annotations

import pytest

from yelos.arbiter.hysteresis.ema import EmaState
from yelos.arbiter.hysteresis.params import Theta
from yelos.arbiter.hysteresis.signals import PendingOutcome, SessionSignalState
from yelos.arbiter.hysteresis.store import (
    HystState,
    default_block,
    dump,
    load,
    save_into,
)


def test_missing_block_initializes_default():
    record = {"name": "x", "p": 1.0}  # v0.1 record,无 arbiter_hyst 块
    state = load(record)
    assert state.theta == Theta()
    assert state.ema == EmaState()
    assert state.n_events == 0
    assert state.signals.pending is None
    assert state.signals.gaps == []
    assert state.signals.lens == []


def test_default_block_shape():
    block = default_block()
    assert block["v"] == 1
    assert block["theta"] == {"d_sw": 0.0, "d_rp": 0.0, "d_ex": 0.0, "gamma": 1.0}
    assert block["pending"] is None


def test_roundtrip_preserves_state():
    theta = Theta(d_sw=0.01, d_rp=-0.02, d_ex=0.03, gamma_offset=0.1)
    ema = EmaState(fast=0.2, slow=-0.1)
    pending = PendingOutcome(sid="s1", turn_id="t1", kind="SWALLOW", ts_i=123.0)
    signals = SessionSignalState(gaps=[10.0, 20.0], lens=[5.0, 6.0], pending=pending)
    state = HystState(theta=theta, ema=ema, n_events=7, signals=signals)

    record: dict = {"name": "x"}
    save_into(record, state)
    reloaded = load(record)

    # gamma 以 gamma = 1.0 + gamma_offset 形式序列化(store.py 的 to_dict/
    # from_dict 约定),往返会有浮点误差(1.0 + 0.1 - 1.0 != 0.1),
    # 故这里按浮点近似比较而非逐位相等。
    assert reloaded.theta.d_sw == theta.d_sw
    assert reloaded.theta.d_rp == theta.d_rp
    assert reloaded.theta.d_ex == theta.d_ex
    assert reloaded.theta.gamma == pytest.approx(theta.gamma)
    assert reloaded.ema == ema
    assert reloaded.n_events == 7
    assert reloaded.signals.gaps == [10.0, 20.0]
    assert reloaded.signals.lens == [5.0, 6.0]
    assert reloaded.signals.pending == pending


def test_ring_buffer_truncated_to_32_on_load():
    block = default_block()
    block["gaps"] = list(range(50))
    block["lens"] = list(range(50))
    record = {"arbiter_hyst": block}
    state = load(record)
    assert len(state.signals.gaps) == 32
    assert len(state.signals.lens) == 32
    assert state.signals.gaps[-1] == 49


def test_dump_is_json_serializable():
    import json

    state = HystState(
        theta=Theta(), ema=EmaState(), n_events=0, signals=SessionSignalState()
    )
    payload = dump(state)
    json.dumps(payload)  # 不抛异常即通过
