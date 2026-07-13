"""test_simulator.py:K 条轨迹喂入编排 / msg_id 去重后缀 / 扰动只碰假设
session(断言 h0 与主 session 零 inject)/ 引擎缺席安静降级(蓝图 §11,A1)。
"""

from __future__ import annotations

import pytest

from yelos.shadow.simulator.ensemble import (
    apply_daily_perturbation,
    compute_disagreement,
    feed_user_turn,
    read_ensemble,
    surface_to_view,
)
from yelos.shadow.baseline.rolling import CHANNEL_SPAN
from yelos.shadow.contracts import ShadowView

from .conftest import FakeBridge, MinimalBridge, surface_with


@pytest.mark.asyncio
async def test_feed_user_turn_reaches_h0_and_all_hypotheses(
    fake_bridge: FakeBridge,
) -> None:
    await feed_user_turn(fake_bridge, "sid-1", "hello", "m1", k_effective=3)
    assert fake_bridge.submitted == [("sid-1", "hello", "m1")]
    assert fake_bridge.submitted_hyp == [
        ("sid-1", 1, "hello", "m1#h1"),
        ("sid-1", 2, "hello", "m1#h2"),
    ]


@pytest.mark.asyncio
async def test_feed_user_turn_k1_only_h0(fake_bridge: FakeBridge) -> None:
    await feed_user_turn(fake_bridge, "sid-1", "hi", "m1", k_effective=1)
    assert fake_bridge.submitted == [("sid-1", "hi", "m1")]
    assert fake_bridge.submitted_hyp == []


@pytest.mark.asyncio
async def test_feed_user_turn_gracefully_degrades_without_hyp_support(
    minimal_bridge: MinimalBridge,
) -> None:
    # [SHTOM-A1] 引擎不支持多假设方法时,静默退化为只喂 h0,不 raise。
    await feed_user_turn(minimal_bridge, "sid-1", "hi", "m1", k_effective=3)


@pytest.mark.asyncio
async def test_apply_daily_perturbation_only_touches_hypotheses(
    fake_bridge: FakeBridge,
) -> None:
    eps = await apply_daily_perturbation(
        fake_bridge, "sid-1", "2026-07-11", 3, 0.1, 0.1
    )
    assert eps > 0
    assert len(fake_bridge.perturbed) == 2
    touched_ks = {k for (_sid, k, _i) in fake_bridge.perturbed}
    assert touched_ks == {1, 2}
    assert fake_bridge.injected == []  # h0/主 session 零 inject(A1 边界)


@pytest.mark.asyncio
async def test_apply_daily_perturbation_k1_noop(fake_bridge: FakeBridge) -> None:
    await apply_daily_perturbation(fake_bridge, "sid-1", "2026-07-11", 1, 0.1, 0.1)
    assert fake_bridge.perturbed == []


@pytest.mark.asyncio
async def test_read_ensemble_returns_h0_first(fake_bridge: FakeBridge) -> None:
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.5, warmth=0.6, damage=0.1))
    fake_bridge.set_hyp("sid-1", 1, surface_with(pressure=0.9, warmth=0.2, damage=0.1))
    views = await read_ensemble(fake_bridge, "sid-1", 2)
    assert len(views) == 2
    assert views[0].hyp_id == 0
    assert views[0].pressure == 0.5
    assert views[1].hyp_id == 1


@pytest.mark.asyncio
async def test_read_ensemble_engine_absent_gives_none_fields(
    fake_bridge: FakeBridge,
) -> None:
    views = await read_ensemble(fake_bridge, "sid-missing", 1)
    assert views[0].pressure is None
    assert views[0].warmth is None
    assert views[0].damage is None


def test_surface_to_view_defensive_on_bad_types() -> None:
    view = surface_to_view({"state": {"boundary": {"pressure": "not-a-number"}}}, 0)
    assert view.pressure is None


def test_compute_disagreement_zero_for_single_view() -> None:
    view = ShadowView(pressure=0.5, warmth=0.5, damage=0.5, hyp_id=0)
    assert compute_disagreement((view,), CHANNEL_SPAN) == 0.0


def test_compute_disagreement_reflects_spread() -> None:
    v0 = ShadowView(pressure=0.1, warmth=0.5, damage=0.0, hyp_id=0)
    v1 = ShadowView(pressure=0.9, warmth=0.5, damage=0.0, hyp_id=1)
    d = compute_disagreement((v0, v1), CHANNEL_SPAN)
    assert d == pytest.approx(0.8)
