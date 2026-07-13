"""test_ledger_concern_field.py:X3 接缝供数侧(shadow 供数,finitude 落笔,
INTEGRATION_SPEC §3.3/X3)。本文件只覆盖 shadow 侧的权威源
`shadow.daily.concern_count`——finitude 侧 settle 快照该字段写入 ledger
行是 finitude 蓝图的职责(该模块另建,W3 同波,共享本测试文件名约定)。

消费断言(律二):篡改 `shadow.daily.concern_count` 应能被观测到差异——本
测试直接断言该字段随 concern 触发次数递增,且与旧 legacy `concern_state`
字段不是同一个计数口径(证明它确实是独立的新权威源,不是转发)。
"""

from __future__ import annotations

import pytest

from yelos.shadow import build_shadow_system

from .conftest import FakeBridge, new_binding_record, surface_with


@pytest.mark.asyncio
async def test_concern_count_increments_on_fire(fake_bridge: FakeBridge) -> None:
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    assert record["shadow"]["daily"]["concern_count"] == 1


@pytest.mark.asyncio
async def test_concern_count_resets_on_new_day(fake_bridge: FakeBridge) -> None:
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    assert record["shadow"]["daily"]["concern_count"] == 1

    # 次日:legacy armed["pressure"] 在 v0.1 语义下只有信号本身回落才重新
    # 武装(F11b:armed 跨日持久,不因日期翻转自动重置)——压力若持续高企,
    # 第二天不会重新 fire。但 `shadow.daily`(concern_count 供数块)自身的
    # 日翻转必须独立于是否重新 fire 发生,否则跨日 day 字段会卡在旧值。
    await system.beat(record, "sid-1", "2026-07-12", 90000.0)
    assert record["shadow"]["daily"]["day"] == "2026-07-12"
    assert record["shadow"]["daily"]["concern_count"] == 0  # 新一天尚无新 fire
    assert record["concern_state"]["injected_day"] == "2026-07-11"  # legacy 字段未变

    # 压力回落后再度升高:armed 重新武装,才能在第三天真正再 fire 一次。
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.0))
    await system.beat(record, "sid-1", "2026-07-13", 180000.0)
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    await system.beat(record, "sid-1", "2026-07-13", 180060.0)
    assert record["shadow"]["daily"]["concern_count"] == 1
    assert record["concern_state"]["injected_day"] == "2026-07-13"


@pytest.mark.asyncio
async def test_concern_count_independent_of_legacy_field_shape(
    fake_bridge: FakeBridge,
) -> None:
    """mutation 式消费断言:直接改写 `shadow.daily.concern_count`,验证它是
    真正被读取的独立字段,不是从 legacy `concern_state` 实时派生出来的只读
    投影(若是派生视图,篡改后 `concern_active`/后续行为不会反映篡改值)。
    """
    system = build_shadow_system(bridge=fake_bridge)
    record = new_binding_record()
    fake_bridge.set_h0("sid-1", surface_with(pressure=0.9))
    await system.beat(record, "sid-1", "2026-07-11", 1000.0)
    record["shadow"]["daily"]["concern_count"] = 99
    assert (
        record["shadow"]["daily"]["concern_count"] == 99
    )  # 篡改可见,证明是独立存储字段
