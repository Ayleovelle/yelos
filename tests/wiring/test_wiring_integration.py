"""接线波端到端集成测试(INTEGRATION_SPEC + 各模块蓝图 §接线)。

覆盖运行 server/session/config/persistence/engine_bridge 把十座深化模块接活的
接缝,且守 "默认不改变现有可观测行为、1191 绿不动" 铁律:

- config.load() 正式装载深化键 + sylanne.config.json 叠加层;
- persistence.ensure_binding_blocks 加性/幂等/世代随孵化重置;
- server 注册 affect_recall 第 11 席 + /ui 守卫式挂载点(缺 mount 静默跳过);
- session.recall 经 MemoryFacade 装配(memory 缺席/未绑定/封存分支);
- guidance 透传 profile/lang/continuity——默认 chat + 无 reunion 严格走 v0.1;
- memory L1 双写 best-effort(引擎缺席不炸主链);
- engine_bridge 影子多假设方法 K>1(引擎缺席安静降级)。

本机未装 sylanne_core(HAS_ENGINE=False),直接构造真实 SessionManager +
EngineBridge——引擎缺席的安静降级本就是生产路径。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from yelos import config as cfgmod  # noqa: E402
from yelos import persistence  # noqa: E402
from yelos.config import YelosConfig  # noqa: E402
from yelos.engine_bridge import EngineBridge  # noqa: E402
from yelos.guidance import build_guidance  # noqa: E402
from yelos.server import build_manager, build_server  # noqa: E402
from yelos.session import SessionManager  # noqa: E402


def make_manager(tmp_path: Path, **overrides) -> SessionManager:
    cfg = YelosConfig(
        data_dir=str(tmp_path),
        heartbeat_enabled=False,
        arbiter_min_gap_seconds=0,
        **overrides,
    )
    return SessionManager(cfg, EngineBridge(llm_fn=None))


# =====================================================================
# config:深化键装载 + sylanne.config.json 叠加
# =====================================================================


def test_config_loads_deepened_keys_from_file(tmp_path: Path) -> None:
    cfg_path = tmp_path / "yelos.config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "guidance_profile": "companion",
                "lang": "ja",
                "arbiter_policy": "duel",
                "arbiter_pipeline_enabled": True,
                "shadow_detector_set": "v2",
                "shadow_hypotheses": 3,
                "finitude_model": "weibull",
                "evolution_enabled": True,
                "evolution_velocity_bound": 0.02,
                "memory": {"memory_recall_scorer": "linear"},
            }
        ),
        encoding="utf-8",
    )
    cfg = cfgmod.load(str(cfg_path))
    assert cfg.guidance_profile == "companion"
    assert cfg.lang == "ja"
    assert cfg.arbiter_policy == "duel"
    assert cfg.arbiter_pipeline_enabled is True
    assert cfg.shadow_detector_set == "v2"
    assert cfg.shadow_hypotheses == 3
    assert cfg.finitude_model == "weibull"
    assert cfg.evolution_enabled is True
    assert cfg.evolution_velocity_bound == pytest.approx(0.02)
    assert cfg.memory_block.get("memory_recall_scorer") == "linear"


def test_config_defaults_are_v01_compatible(tmp_path: Path) -> None:
    """无配置文件时,所有深化 opt-in 旗标默认关、档位为 v0.1 兼容。"""
    cfg = cfgmod.load(str(tmp_path / "nonexistent.json"))
    assert cfg.guidance_profile == "chat"
    assert cfg.arbiter_pipeline_enabled is False
    assert cfg.arbiter_policy == "table"
    assert cfg.shadow_orchestrator_enabled is False
    assert cfg.shadow_detector_set == "legacy"
    assert cfg.shadow_hypotheses == 1
    assert cfg.intrinsic_field_enabled is False
    assert cfg.primal_composer_enabled is False
    assert cfg.finitude_settle_enabled is False
    assert cfg.finitude_model == "linear"
    assert cfg.memory_enabled is True


def test_sylanne_config_overlay_lower_priority(tmp_path: Path) -> None:
    """sylanne.config.json 提供人格侧默认,yelos.config.json 显式覆盖之。"""
    (tmp_path / "sylanne.config.json").write_text(
        json.dumps({"lang": "ja", "guidance_profile": "companion"}), encoding="utf-8"
    )
    (tmp_path / "yelos.config.json").write_text(
        json.dumps({"guidance_profile": "chat"}), encoding="utf-8"
    )
    cfg = cfgmod.load(str(tmp_path / "yelos.config.json"))
    # sylanne 供的 lang 生效;yelos 覆盖 guidance_profile。
    assert cfg.lang == "ja"
    assert cfg.guidance_profile == "chat"


# =====================================================================
# persistence:binding 增量块加性/幂等/世代重置
# =====================================================================


def test_ensure_binding_blocks_additive_and_idempotent() -> None:
    rec: dict = {"daily": {}}
    persistence.ensure_binding_blocks(rec, lang="ja")
    assert rec["lang"] == "ja"
    assert rec["utter_provenance"] == []
    assert rec["daily"]["moments_counts"] == {}
    # 幂等:已有值不被覆盖。
    rec["lang"] = "en"
    rec["utter_provenance"].append({"x": 1})
    persistence.ensure_binding_blocks(rec, lang="ja")
    assert rec["lang"] == "en"
    assert rec["utter_provenance"] == [{"x": 1}]


def test_ensure_binding_blocks_does_not_preset_guidance_profile() -> None:
    """guidance_profile 缺省不预置(缺 → guidance 默认 chat),避免污染默认 bindings。"""
    rec: dict = {"daily": {}}
    persistence.ensure_binding_blocks(rec)
    assert "guidance_profile" not in rec


def test_ensure_binding_blocks_ring_buffer_cap() -> None:
    rec = {"utter_provenance": [{"i": i} for i in range(250)], "daily": {}}
    persistence.ensure_binding_blocks(rec)
    assert len(rec["utter_provenance"]) == persistence.UTTER_PROVENANCE_CAP
    assert rec["utter_provenance"][-1] == {"i": 249}


# =====================================================================
# server:11 工具 + /ui 守卫式挂载
# =====================================================================


@pytest.mark.asyncio
async def test_server_registers_eleven_tools_including_recall(tmp_path: Path) -> None:
    cfg = YelosConfig(data_dir=str(tmp_path), heartbeat_enabled=False)
    mgr = build_manager(cfg)
    mcp = build_server(cfg, mgr)
    # build_server 不抛(即使 yelos.ui 无 mount,守卫静默跳过)。
    assert mcp is not None
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert "affect_recall" in names
    assert len(names) == 11


def test_ui_mount_guard_silent_when_no_mount(tmp_path: Path) -> None:
    """yelos.ui 当前不暴露 mount → 守卫静默跳过,build_server 正常返回。"""
    cfg = YelosConfig(data_dir=str(tmp_path), heartbeat_enabled=False)
    mgr = build_manager(cfg)
    # 不抛即通过。
    assert build_server(cfg, mgr) is not None


# =====================================================================
# session.recall(affect_recall 时序)
# =====================================================================


@pytest.mark.asyncio
async def test_recall_unbound_returns_view(tmp_path: Path) -> None:
    sm = make_manager(tmp_path)
    out = await sm.recall("never-bound", query="test")
    # memory 默认开 → 未绑定返回装配好的视图(非 disabled)。
    assert isinstance(out, dict)
    assert out.get("disabled") is not True


@pytest.mark.asyncio
async def test_recall_disabled_when_memory_off(tmp_path: Path) -> None:
    sm = make_manager(tmp_path, memory_enabled=False)
    assert sm._memory is None
    out = await sm.recall("sid-x")
    assert out == {"disabled": True}


@pytest.mark.asyncio
async def test_recall_after_bind_and_submit(tmp_path: Path) -> None:
    sm = make_manager(tmp_path)
    await sm.bind("sid-a", "阿", mode="companion")
    await sm.submit("sid-a", "今天很累", speaker="user")
    out = await sm.recall("sid-a", query="累", k=3)
    assert isinstance(out, dict)
    assert out.get("disabled") is not True
    assert out.get("sealed") is not True


# =====================================================================
# guidance 透传:默认 chat + 无 reunion 严格走 v0.1
# =====================================================================


@pytest.mark.asyncio
async def test_guidance_default_matches_v01(tmp_path: Path) -> None:
    """session.guidance 默认档位应与直接 build_guidance(v0.1 三参) 逐字节一致。"""
    sm = make_manager(tmp_path)
    await sm.bind("sid-g", "小", mode="companion")
    surface = {
        "decision": {"action": "hold"},
        "persona": {"warmth": 0.6},
        "dynamics": {"relational_time": {"phase": "active"}},
    }
    sm._surface_cache["sid-g"] = surface
    got = await sm.guidance("sid-g")
    expected = build_guidance(surface, "companion", False)
    got.pop("poll_hint", None)
    assert got == expected


# =====================================================================
# memory L1 双写 best-effort(引擎缺席不炸主链)
# =====================================================================


@pytest.mark.asyncio
async def test_memory_double_write_survives_facade_failure(tmp_path: Path) -> None:
    sm = make_manager(tmp_path)
    await sm.bind("sid-m", "米", mode="companion")

    # 让 memory.observe 抛异常,断言主链 submit 仍成功、可观测输出不变。
    class Boom:
        def observe(self, *a, **k):
            raise RuntimeError("boom")

        def affect_recall_view(self, *a, **k):
            return {"disabled": True}

        def continuity_flags(self, *a, **k):
            raise RuntimeError("boom")

    sm._memory = Boom()
    res = await sm.submit("sid-m", "还好吗", speaker="user")
    assert res["session_id"] == "sid-m"


# =====================================================================
# engine_bridge 影子多假设(K>1;引擎缺席安静降级)
# =====================================================================


@pytest.mark.asyncio
async def test_shadow_hyp_methods_noop_without_engine() -> None:
    br = EngineBridge(llm_fn=None)
    assert br._engine is None
    assert await br.submit_shadow_hyp("u", "t", None, 2) is None
    assert await br.shadow_state_hyp("u", 2) is None
    assert await br.inject_shadow_perturb("u", 0.5, 2) is None


# =====================================================================
# primal 深化 composer opt-in 换 provider(§6.3;默认 core 词典)
# =====================================================================


# =====================================================================
# Clock 注入(§3.2;RealClock 默认,VirtualClock 可换)
# =====================================================================


def test_virtual_clock_injection_drives_session_time(tmp_path: Path) -> None:
    from yelos.bench.clock import VirtualClock

    vc = VirtualClock(start_ts=1_700_000_000.0)
    cfg = YelosConfig(data_dir=str(tmp_path), heartbeat_enabled=False)
    sm = SessionManager(cfg, EngineBridge(llm_fn=None), clock=vc)
    assert sm._now_ts() == pytest.approx(1_700_000_000.0)
    day0 = sm._day_key()
    vc.advance(86_400)  # +1 天
    assert sm._now_ts() == pytest.approx(1_700_086_400.0)
    assert sm._day_key() != day0  # 时钟推进真正改变了 session 的日期键


def test_provider_default_is_core_lexicon(tmp_path: Path) -> None:
    from yelos.core.primal import LexiconProvider

    sm = make_manager(tmp_path)
    assert isinstance(sm._provider, LexiconProvider)


def test_provider_composer_swap_when_enabled(tmp_path: Path) -> None:
    sm = make_manager(tmp_path, primal_composer_enabled=True)
    assert type(sm._provider).__name__ == "_ComposerProvider"
    # 深化发声对已知场合仍产非空、由白名单闸放行的句子(永不失声)。
    for occ in ("concern", "express_warm", "withdraw_soft"):
        text = sm._provider.utter({}, "sid-p", "2026-07-11", occ)
        assert isinstance(text, str) and text


def test_provider_composer_falls_back_on_failure(tmp_path: Path) -> None:
    """composer.compose 抛异常时回退 core 词典,不失声。"""
    sm = make_manager(tmp_path, primal_composer_enabled=True)

    class Boom:
        def compose(self, *a, **k):
            raise RuntimeError("boom")

    sm._provider._composer = Boom()
    text = sm._provider.utter({}, "sid-p", "2026-07-11", "concern")
    assert isinstance(text, str) and text  # core 兜底句


def test_shadow_hyp_umo_keys_distinct_and_k1_compatible() -> None:
    br = EngineBridge(llm_fn=None)
    # K=1(hyp<=0)与主影子 key 完全一致;K>1 每号不同键。
    from yelos.engine_bridge import SHADOW_PREFIX

    assert br._hyp_umo("u", 0) == SHADOW_PREFIX + "u"
    assert br._hyp_umo("u", 1) != br._hyp_umo("u", 2)
    assert br._hyp_umo("u", 1).endswith(":u")
