"""intrinsic 深化接线集成测试(session.py W-1 场步进 + 三处 decide 接管点 +
梦语状态机;intrinsic_BLUEPRINT §8.1 对应的"接线波"验收)。

覆盖:

- ``intrinsic_field_enabled`` 默认关 -> ``self._intrinsic_system is None``,
  三处 decide 调用点原样回落 ``core.intrinsic.decide``,字节不变(v0.1 兼容)。
- flag 开 + 默认 policy/integrator(threshold/euler)时构造不崩(回归:
  ``YelosConfig.intrinsic_field_params`` 默认值 "{}" 是 JSON 字符串而非 dict,
  直接透传给 ``build_intrinsic`` 会在 ``FieldParams.from_dict`` 里
  ``AttributeError``——session 层 cfg 桥接必须先解析)。
- flag 开时默认策略(threshold)+ 全通行闸门与 core.intrinsic.decide 结果
  逐字段一致(默认配置零漂移)。
- P0 铁律(沉默恒优先):intrinsic_field_enabled 开时,静默会话即便场态/
  surface 触发条件拉满也不入队,不被深化管线抢先。
- 场步进异常 / policy.propose 异常均安静回退 core 行为,不崩心跳主链。
- 心跳步端到端:flag 开时 want_to_speak 触发 -> 主动 outbox 入队。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from yelos import core as core_pkg  # noqa: E402
from yelos.config import YelosConfig  # noqa: E402
from yelos.core import intrinsic as intr  # noqa: E402
from yelos.engine_bridge import EngineBridge  # noqa: E402
from yelos.session import SessionManager  # noqa: E402

assert core_pkg is not None  # 仅确认包可导入,不做他用


def make_manager(tmp_path: Path, **overrides) -> SessionManager:
    cfg = YelosConfig(
        data_dir=str(tmp_path),
        heartbeat_enabled=False,
        arbiter_min_gap_seconds=0,
        **overrides,
    )
    return SessionManager(cfg, EngineBridge(llm_fn=None))


_HOT_SURFACE = {
    "state": {
        "needs": {"contact": 0.9, "expression": 0.9, "quiet": 0.0},
        "boundary": {"pressure": 0.0, "interruption_budget": 1.0},
    },
    "decision": {"action": "hold"},
    "dynamics": {"relational_time": {"phase": "active"}},
}


# =====================================================================
# flag 默认关:零漂移
# =====================================================================


def test_intrinsic_system_none_by_default(tmp_path: Path) -> None:
    sm = make_manager(tmp_path)
    assert sm._intrinsic_system is None


@pytest.mark.asyncio
async def test_intrinsic_decide_disabled_matches_core(tmp_path: Path) -> None:
    """flag 关时 `_intrinsic_decide` 与直接调用 `core.intrinsic.decide` 逐字段一致。"""
    sm = make_manager(tmp_path)
    await sm.bind("sid-off", "阿", mode="companion")
    record = sm._store.get("sid-off")
    now_ts = sm._now_ts()
    now_min = sm._now_local_minutes()
    day_key = sm._day_key()
    qstart, qend = sm._cfg.quiet_minutes()

    got = sm._intrinsic_decide(
        "sid-off", record, _HOT_SURFACE, day_key, now_ts, now_min, qstart, qend, False,
        authoritative=True,
    )
    expected = intr.decide(
        sm._intrinsic_input(
            "sid-off", record, _HOT_SURFACE, day_key, now_ts, now_min, qstart, qend, False
        )
    )
    assert got == expected
    assert got.send is True
    assert got.occasion == "contact_seek"
    # flag 关时不应留下 intrinsic_field 持久块的场态推进痕迹(零 import extras)。
    assert record.get("intrinsic_field", {}).get("phi") in (None, {})


# =====================================================================
# flag 开:构造回归 + 默认策略字节校验
# =====================================================================


def test_intrinsic_system_builds_with_default_config(tmp_path: Path) -> None:
    """回归:YelosConfig 默认 intrinsic_field_params="{}"(JSON 字符串)不应让
    build_intrinsic 崩(此前 bug:直接透传给 FieldParams.from_dict 会
    AttributeError,session 层需现场解析成 dict/None)。
    """
    sm = make_manager(tmp_path, intrinsic_field_enabled=True)
    assert sm._intrinsic_system is not None
    assert sm._intrinsic_system.policy_name == "threshold"
    assert sm._intrinsic_system.integrator.name == "euler"


@pytest.mark.asyncio
async def test_intrinsic_decide_enabled_default_policy_matches_core(
    tmp_path: Path,
) -> None:
    """flag 开 + 默认 threshold policy/euler integrator:深化管线（policy.propose
    + apply_gates)与 core.intrinsic.decide 在同一输入下逐字段一致——默认配置
    零漂移(ThresholdPolicy 本就是 core.decide 触发段的零改动包装,gates.py
    的闸链常量与 core 逐字一致)。
    """
    sm = make_manager(tmp_path, intrinsic_field_enabled=True)
    assert sm._intrinsic_system is not None
    await sm.bind("sid-on", "阿", mode="companion")
    record = sm._store.get("sid-on")
    now_ts = sm._now_ts()
    now_min = sm._now_local_minutes()
    day_key = sm._day_key()
    qstart, qend = sm._cfg.quiet_minutes()

    got = sm._intrinsic_decide(
        "sid-on", record, _HOT_SURFACE, day_key, now_ts, now_min, qstart, qend, False,
        authoritative=True,
    )
    expected = intr.decide(
        sm._intrinsic_input(
            "sid-on", record, _HOT_SURFACE, day_key, now_ts, now_min, qstart, qend, False
        )
    )
    assert got.send == expected.send
    assert got.occasion == expected.occasion
    assert got.reason == expected.reason
    # authoritative=True 应落盘 policy_state + tick_index 前进。
    block = record["intrinsic_field"]
    assert block["tick_index"] == 1


# =====================================================================
# P0 铁律:沉默恒优先,不被深化管线抢先
# =====================================================================


@pytest.mark.asyncio
async def test_p0_silence_wins_even_with_intrinsic_enabled(tmp_path: Path) -> None:
    sm = make_manager(tmp_path, intrinsic_field_enabled=True)
    await sm.bind("sid-p0", "阿", mode="companion")
    await sm.pause("sid-p0", hours=1.0)
    record = sm._store.get("sid-p0")
    now_ts = sm._now_ts()
    now_min = sm._now_local_minutes()
    day_key = sm._day_key()
    qstart, qend = sm._cfg.quiet_minutes()

    got = sm._intrinsic_decide(
        "sid-p0", record, _HOT_SURFACE, day_key, now_ts, now_min, qstart, qend, True,
        authoritative=True,
    )
    assert got.send is False
    assert got.reason == "p0"


@pytest.mark.asyncio
async def test_p0_silence_blocks_heartbeat_enqueue_end_to_end(tmp_path: Path) -> None:
    """端到端:静默 + intrinsic_field_enabled 开,heartbeat 步不应入队任何主动项,
    即使 surface 拉满触发条件(P0 在深化管线内部也是 apply_gates 第一梯队)。
    """
    sm = make_manager(tmp_path, intrinsic_field_enabled=True)
    await sm.bind("sid-p0b", "阿", mode="companion")
    await sm.pause("sid-p0b", hours=1.0)

    async def _fake_tick_state(_umo):
        return _HOT_SURFACE

    sm._bridge.tick_state = _fake_tick_state  # type: ignore[method-assign]
    await sm._heartbeat_step("sid-p0b")
    assert sm._pending("sid-p0b", sm._now_ts()) == 0


# =====================================================================
# 退化兜底:场步进 / policy 异常安静回落,不崩心跳主链
# =====================================================================


@pytest.mark.asyncio
async def test_intrinsic_field_advance_survives_bad_persisted_phi(tmp_path: Path) -> None:
    sm = make_manager(tmp_path, intrinsic_field_enabled=True)
    await sm.bind("sid-adv", "阿", mode="companion")
    record = sm._store.get("sid-adv")
    record["intrinsic_field"] = {"phi": {"drive": "not-a-number"}}
    now_ts = sm._now_ts()
    now_min = sm._now_local_minutes()
    # 不应抛异常;场态异常时原地不动(安静跳过)。
    sm._intrinsic_field_advance(record, _HOT_SURFACE, now_ts, now_min)


@pytest.mark.asyncio
async def test_intrinsic_decide_degrades_to_core_on_policy_exception(
    tmp_path: Path,
) -> None:
    sm = make_manager(tmp_path, intrinsic_field_enabled=True)
    await sm.bind("sid-boom", "阿", mode="companion")
    record = sm._store.get("sid-boom")
    now_ts = sm._now_ts()
    now_min = sm._now_local_minutes()
    day_key = sm._day_key()
    qstart, qend = sm._cfg.quiet_minutes()

    from dataclasses import replace as dataclass_replace

    class BoomPolicy:
        name = "boom"

        def propose(self, ctx):
            raise RuntimeError("boom")

    sm._intrinsic_system = dataclass_replace(sm._intrinsic_system, policy=BoomPolicy())
    got = sm._intrinsic_decide(
        "sid-boom", record, _HOT_SURFACE, day_key, now_ts, now_min, qstart, qend, False,
        authoritative=True,
    )
    expected = intr.decide(
        sm._intrinsic_input(
            "sid-boom", record, _HOT_SURFACE, day_key, now_ts, now_min, qstart, qend, False
        )
    )
    assert got == expected  # 深化崩溃安静回落 core,永不失声/永不崩溃


# =====================================================================
# 心跳步端到端:flag 开时主动仍能正确入队(功能对等,非仅结构对等)
# =====================================================================


@pytest.mark.asyncio
async def test_intrinsic_heartbeat_enqueues_proactive_end_to_end(tmp_path: Path) -> None:
    sm = make_manager(tmp_path, intrinsic_field_enabled=True)
    await sm.bind("sid-hb", "阿", mode="companion")

    async def _fake_tick_state(_umo):
        return _HOT_SURFACE

    sm._bridge.tick_state = _fake_tick_state  # type: ignore[method-assign]
    await sm._heartbeat_step("sid-hb")
    assert sm._pending("sid-hb", sm._now_ts()) > 0
    record = sm._store.get("sid-hb")
    assert record["intrinsic_field"]["phi"] is not None
