"""test_beat_pipeline.py:§10 决策表全行回放(fake bridge);默认配置
(K=1/Legacy/observe)与 v0.1 心跳步 5 **逐字节 golden 一致**(蓝图 §11)。
"""

from __future__ import annotations

import pytest

from yelos.core.shadow import extract_concern
from yelos.shadow import build_shadow_system

from .conftest import FakeBridge, new_binding_record, surface_with


@pytest.mark.asyncio
async def test_legacy_beat_matches_core_extract_concern_intensity(
    fake_bridge: FakeBridge,
) -> None:
    system = build_shadow_system(bridge=fake_bridge)  # 默认 detector_set="legacy"
    record = new_binding_record()
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))

    verdict = await system.beat(record, "sid-1", "2026-07-11", 1000.0)

    expected = extract_concern(surface_with(pressure=0.9), None)
    assert expected is not None
    assert verdict is not None
    assert verdict.intensity == pytest.approx(expected.intensity)
    assert fake_bridge.injected == [("sid-1", expected.intensity)]


@pytest.mark.asyncio
async def test_legacy_beat_disabled_returns_none(fake_bridge: FakeBridge) -> None:
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    record["mode"] = "steward"
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    verdict = await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    assert verdict is None
    assert fake_bridge.injected == []


@pytest.mark.asyncio
async def test_legacy_beat_no_trigger_returns_none(fake_bridge: FakeBridge) -> None:
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.0, warmth=0.9, damage=0.0))
    verdict = await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    assert verdict is None


@pytest.mark.asyncio
async def test_legacy_beat_supplies_daily_concern_count_x3(
    fake_bridge: FakeBridge,
) -> None:
    """X3 接缝:`shadow.daily.concern_count` 是 concern 的唯一权威源,
    Legacy 路径下每次真正 inject 记一次。
    """
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    assert record["shadow"]["daily"]["concern_count"] == 1


@pytest.mark.asyncio
async def test_legacy_beat_once_per_day_per_trigger(fake_bridge: FakeBridge) -> None:
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    await system.beat(record, "sid-1", "2026-07-11", 1060.0)  # 同日再拍,压力仍高
    assert len(fake_bridge.injected) == 1  # 当日一次纪律(F3c)
    assert record["shadow"]["daily"]["concern_count"] == 1


@pytest.mark.asyncio
async def test_concern_active_reflects_todays_injection(
    fake_bridge: FakeBridge,
) -> None:
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    assert system.concern_active(record, "2026-07-11") is False
    await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    assert system.concern_active(record, "2026-07-11") is True
    assert system.concern_active(record, "2026-07-12") is False


@pytest.mark.asyncio
async def test_sealed_record_short_circuits(fake_bridge: FakeBridge) -> None:
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    record["sealed"] = True
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    verdict = await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    assert verdict is None
    assert fake_bridge.injected == []


@pytest.mark.asyncio
async def test_guard_frozen_short_circuits(fake_bridge: FakeBridge) -> None:
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    record["daily"]["guard_frozen"] = True
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    verdict = await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    assert verdict is None


# --- v2 路径最小冒烟(golden 闸只锁 legacy 默认,v2 只做存在性冒烟)----------


@pytest.mark.asyncio
async def test_v2_pipeline_smoke(fake_bridge: FakeBridge) -> None:
    system = build_shadow_system(bridge=fake_bridge, detector_set="v2")
    record = new_binding_record()
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9, warmth=0.5, damage=0.0))
    verdict = await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    assert verdict is not None
    assert verdict.ctype in ("pressure_spike",)
    assert record["shadow"]["daily"]["concern_count"] >= 1


@pytest.mark.asyncio
async def test_v2_pipeline_engine_absent_returns_none(fake_bridge: FakeBridge) -> None:
    system = build_shadow_system(bridge=fake_bridge, detector_set="v2")
    record = new_binding_record()
    verdict = await system.beat(record, "sid-absent", "2026-07-11", 1000.0)
    assert verdict is None


@pytest.mark.asyncio
async def test_v2_pipeline_consumes_memory_familiarity(fake_bridge: FakeBridge) -> None:
    """X6 端到端消费断言:高 familiarity 与低 familiarity 下,同一触发的
    intensity 应不同(mutation 式:篡改 familiarity 值,verdict 可观测差异)。
    """
    from .conftest import FakeMemoryBaseline, FakeMemoryFacade

    low_mem = FakeMemoryFacade(FakeMemoryBaseline(familiarity=0.0))
    system_low = build_shadow_system(
        bridge=fake_bridge, memory_facade=low_mem, detector_set="v2"
    )
    record_low = new_binding_record()
    fake_bridge.set_h0("sid-low", surface_with(pressure=0.95, warmth=0.5, damage=0.0))
    verdict_low = await system_low.beat(record_low, "sid-low", "2026-07-11", 1000.0)

    high_mem = FakeMemoryFacade(FakeMemoryBaseline(familiarity=1.0))
    system_high = build_shadow_system(
        bridge=fake_bridge, memory_facade=high_mem, detector_set="v2"
    )
    record_high = new_binding_record()
    fake_bridge.set_h0("sid-high", surface_with(pressure=0.95, warmth=0.5, damage=0.0))
    verdict_high = await system_high.beat(record_high, "sid-high", "2026-07-11", 1000.0)

    assert verdict_low is not None and verdict_high is not None
    assert verdict_high.intensity > verdict_low.intensity
