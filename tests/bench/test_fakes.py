"""FakeBridge(bench_BLUEPRINT §5.1/§8.2 test_fakes.py)——确定性 + Surface 字段路径。"""

from __future__ import annotations

import asyncio

import pytest

from yelos.bench.clock import VirtualClock
from yelos.bench.harness.fakes import FakeBridge
from yelos.core import sget

# sget 消费过的字段路径全集(见 session.py/arbiter.py/shadow.py 等既有调用点)。
_CONSUMED_PATHS = [
    "decision.action",
    "state.boundary.pressure",
    "state.boundary.paused",
    "state.needs.contact",
    "state.needs.expression",
    "state.needs.quiet",
    "state.valence.warmth",
    "state.pad.label",
    "dynamics.relational_time.phase",
    "guard.allowed",
]


def _run(coro):
    return asyncio.run(coro)


def test_fake_surface_schema_covers_consumed_paths():
    clock = VirtualClock(start_ts=0.0)
    bridge = FakeBridge(clock)
    surface = _run(bridge.submit_user("s1", "calm_00", msg_id=0))
    assert surface is not None
    for path in _CONSUMED_PATHS:
        default = object()
        val = sget(surface, path, default)
        assert val is not default, f"Surface 缺字段路径:{path}"


def test_fake_bridge_deterministic_same_inputs_same_outputs():
    clock1 = VirtualClock(start_ts=1000.0)
    b1 = FakeBridge(clock1)
    clock2 = VirtualClock(start_ts=1000.0)
    b2 = FakeBridge(clock2)

    s1 = _run(b1.submit_user("s1", "pressure_02", msg_id=0))
    s2 = _run(b2.submit_user("s1", "pressure_02", msg_id=0))
    assert s1 == s2

    clock1.advance(60.0)
    clock2.advance(60.0)
    s1b = _run(b1.tick_state("s1"))
    s2b = _run(b2.tick_state("s1"))
    assert s1b == s2b


def test_fake_bridge_sealed_blocks_submit_and_tick():
    clock = VirtualClock(start_ts=0.0)
    bridge = FakeBridge(clock)
    _run(bridge.submit_user("s1", "calm_00", msg_id=0))
    bridge.seal("s1")
    assert bridge.is_sealed("s1")
    assert _run(bridge.submit_user("s1", "calm_01", msg_id=1)) is None
    assert _run(bridge.tick_state("s1")) is None


def test_fake_bridge_pause_sets_guard_and_action_hold():
    clock = VirtualClock(start_ts=0.0)
    bridge = FakeBridge(clock)
    _run(bridge.submit_user("s1", "pressure_00", msg_id=0))
    bridge.set_paused("s1", True)
    surface = bridge.peek_surface("s1")
    assert surface["state"]["boundary"]["paused"] is True
    assert surface["guard"]["allowed"] is False
    assert surface["decision"]["action"] == "hold"


def test_fake_bridge_reset_clears_state():
    clock = VirtualClock(start_ts=0.0)
    bridge = FakeBridge(clock)
    _run(bridge.submit_user("s1", "pressure_04", msg_id=0))
    _run(bridge.reset_session("s1"))
    surface = bridge.peek_surface("s1")
    # reset 后回到构造默认值(warmth=0.5)
    assert surface["state"]["valence"]["warmth"] == pytest.approx(0.5)


def test_fake_bridge_health_and_detach():
    clock = VirtualClock(start_ts=0.0)
    bridge = FakeBridge(clock)
    assert _run(bridge.health()) == "running"
    _run(bridge.submit_user("s1", "calm_00", msg_id=0))
    bridge.detach()
    # detach 后视为全新态
    surface = bridge.peek_surface("s1")
    assert surface["state"]["valence"]["warmth"] == pytest.approx(0.5)
