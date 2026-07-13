"""test_arbitrate_mcp.py —— MCP 层幕 II 仲裁全流程测试(蓝图 §3.2 / §8.2)。

锁死项(对应 §8.2 test_arbitrate_flow.py 一行 + 本任务指派范围):
- verdict→final_text 五路:PASS / REPLACE / TRIM / SWALLOW(+delayed) 全覆盖
- **回喂 phase(blocker①)**:PASS / TRIM / REPLACE 均 feed_back(text,"response")；
  SWALLOW 不回喂(沉默由引擎经时间流逝原生感知)
- **SWALLOW 双记账(blocker②)**:每次 SWALLOW 同步写 daily.swallowed(日,可被
  rollover 清零)+ record.swallowed_total(生命周期累加器,跨日不清零)
- **delayed 入队预告(D1/§3.2.1)**:SWALLOW 高压返回 delayed={occasion,90} 只是
  预告,真正送达要等 due_ts 到期后由 affect_impulse(session.impulse)出队;90s
  内 pending==0,到期后单次出队即清空(无双送达)
- steward 模式恒 PASS(D5),不回喂、不夺话

环境说明:本机未装 ``sylanne_core``(HAS_ENGINE=False),EngineBridge 全部方法
安静降级为 no-op/None——因此测试直接构造真实 ``SessionManager`` + 真实
``EngineBridge``,monkeypatch ``feed_back`` 为记录桩以断言回喂调用,而非另造
fake bridge:引擎缺席时的安全降级本就是生产路径,无需额外绕过。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from yelos.config import YelosConfig  # noqa: E402
from yelos.engine_bridge import EngineBridge  # noqa: E402
from yelos.session import SessionManager  # noqa: E402

pytestmark = pytest.mark.asyncio


# --- helpers -------------------------------------------------------------


def make_manager(tmp_path: Path, **overrides) -> SessionManager:
    cfg = YelosConfig(
        data_dir=str(tmp_path),
        heartbeat_enabled=False,
        arbiter_min_gap_seconds=0,
        **overrides,
    )
    bridge = EngineBridge(llm_fn=None)
    return SessionManager(cfg, bridge)


async def drain_spawned(sm: SessionManager) -> None:
    """等待 fire-and-forget 回喂任务跑完(§3.1 竞态纪律:旗标先置,真正完成异步)。"""
    pending = [t for t in sm._tasks if not t.done()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def surface_for(action: str, *, pressure: float = 0.0, expr: float = 0.5) -> dict:
    return {
        "decision": {"action": action},
        "state": {
            "boundary": {"pressure": pressure},
            "needs": {"expression": expr},
        },
        "guard": {"allowed": True},
    }


async def bind_companion(sm: SessionManager, sid: str) -> None:
    res = await sm.bind(sid, "阿澜", mode="companion")
    assert res["mode"] == "companion"


# --- PASS:她原样放行,但仍开口应了这轮(blocker①)-------------------------


class TestPass:
    async def test_pass_feeds_back_response(self, tmp_path):
        sm = make_manager(tmp_path)
        sid = "s-pass"
        await bind_companion(sm, sid)
        # action=explore 恒 PASS,不依赖调制闸哈希(确定性用例)。
        sm._surface_cache[sid] = surface_for("explore", pressure=0.1, expr=0.5)

        feeds: list[tuple[str, str, str]] = []

        async def spy_feed_back(umo, text, phase):
            feeds.append((umo, text, phase))

        sm._bridge.feed_back = spy_feed_back

        draft = "今天天气不错。"
        out = await sm.arbitrate(sid, draft)
        await drain_spawned(sm)

        assert out["verdict"] == "PASS"
        assert out["final_text"] == draft
        assert out["changed"] is False
        assert out["delayed"] is None
        # PASS 亦回喂 response(blocker①:她原样放行也算应了这轮)。
        assert feeds == [(sid, draft, "response")]
        record = sm._store.get(sid)
        assert record["daily"]["proxy_sentences"] >= 1
        # PASS 非介入,不占 min_gap 不应期。
        assert record["daily"]["last_intervention_ts"] == 0.0

    async def test_steward_always_pass_no_feed(self, tmp_path):
        sm = make_manager(tmp_path)
        sid = "s-steward"
        res = await sm.bind(sid, "", mode="steward")
        assert res["mode"] == "steward"
        sm._surface_cache[sid] = surface_for("withdraw", pressure=0.9)

        feeds: list[tuple] = []

        async def spy_feed_back(umo, text, phase):
            feeds.append((umo, text, phase))

        sm._bridge.feed_back = spy_feed_back

        draft = "我今天有点累。"
        out = await sm.arbitrate(sid, draft)
        await drain_spawned(sm)

        assert out["verdict"] == "PASS"
        assert out["final_text"] == draft
        assert out["reason"] == "steward_pass"
        assert "advice" in out
        # steward 不夺话:恒不回喂(D5/§3.2 步1)。
        assert feeds == []


# --- REPLACE / TRIM:她开了口,均回喂 response -----------------------------


class TestReplaceAndTrim:
    async def test_replace_feeds_back_response(self, tmp_path):
        sm = make_manager(tmp_path)
        sid = "s-replace"
        await bind_companion(sm, sid)
        # withdraw + 0.55<=pressure<0.75 + 非收窄 → REPLACE withdraw_heavy,
        # p=1.0 不过调制闸约束(_gate_or_pass 在 p>=0.5 直接放行)。
        sm._surface_cache[sid] = surface_for("withdraw", pressure=0.6)

        feeds: list[tuple] = []

        async def spy_feed_back(umo, text, phase):
            feeds.append((umo, text, phase))

        sm._bridge.feed_back = spy_feed_back

        out = await sm.arbitrate(sid, "我不太想说这个。")
        await drain_spawned(sm)

        assert out["verdict"] == "REPLACE"
        assert out["final_text"] != ""
        assert out["changed"] is True
        assert len(feeds) == 1
        assert feeds[0][0] == sid
        assert feeds[0][1] == out["final_text"]
        assert feeds[0][2] == "response"
        record = sm._store.get(sid)
        assert record["daily"]["last_intervention_ts"] > 0.0
        assert len(record["utterances"]) == 1

    async def test_trim_feeds_back_response(self, tmp_path):
        sm = make_manager(tmp_path)
        sid = "s-trim"
        await bind_companion(sm, sid)
        # express + expr>=0.7 + pressure<=0.3 + >3 句 → TRIM 至首句(确定性,
        # 不依赖 hold 分支的哈希二选一)。
        sm._surface_cache[sid] = surface_for("express", pressure=0.1, expr=0.8)

        feeds: list[tuple] = []

        async def spy_feed_back(umo, text, phase):
            feeds.append((umo, text, phase))

        sm._bridge.feed_back = spy_feed_back

        draft = "第一句话。第二句话。第三句话。第四句话。"
        out = await sm.arbitrate(sid, draft)
        await drain_spawned(sm)

        assert out["verdict"] == "TRIM"
        assert out["final_text"] == "第一句话。"
        assert out["changed"] is True
        assert len(feeds) == 1
        assert feeds[0] == (sid, out["final_text"], "response")


# --- SWALLOW:真沉默,不回喂 + 双记账 + delayed 只是预告 -------------------


class TestSwallowAndDelayed:
    async def test_swallow_no_feed_and_dual_bookkeeping(self, tmp_path):
        sm = make_manager(tmp_path)
        sid = "s-swallow"
        await bind_companion(sm, sid)
        # withdraw + pressure>=0.75(p=1.0 时 swallow_th=0.75)→ SWALLOW,
        # high_intensity(判据固定 0.75,与 swallow_th 解耦)。
        sm._surface_cache[sid] = surface_for("withdraw", pressure=0.9)

        feeds: list[tuple] = []

        async def spy_feed_back(umo, text, phase):
            feeds.append((umo, text, phase))

        sm._bridge.feed_back = spy_feed_back

        out = await sm.arbitrate(sid, "我不想再说了。")
        await drain_spawned(sm)

        assert out["verdict"] == "SWALLOW"
        assert out["final_text"] == ""
        assert out["changed"] is True
        # 沉默由引擎经时间流逝原生感知:SWALLOW 不回喂。
        assert feeds == []

        record = sm._store.get(sid)
        # 双记账(blocker②):日计数 + 生命周期累加器同步 +1。
        assert record["daily"]["swallowed"] == 1
        assert record["swallowed_total"] == 1
        assert record["daily"]["high_intensity"] == 1

        # delayed 只是预告(D1):90s 内 pending==0,90s 后才到期。
        assert out["delayed"] == {"occasion": "withdraw_heavy", "due_in_seconds": 90}
        now = sm._now_ts()
        assert sm._outbox.pending_count(sid, now) == 0
        assert sm._outbox.pending_count(sid, now + 91) == 1

        # 第二次 SWALLOW(同日,min_gap=0 已放开):日计数与生命周期累加器同步累加。
        sm._surface_cache[sid] = surface_for("withdraw", pressure=0.9)
        out2 = await sm.arbitrate(sid, "还是不想说。")
        await drain_spawned(sm)
        assert out2["verdict"] == "SWALLOW"
        record = sm._store.get(sid)
        assert record["daily"]["swallowed"] == 2
        assert record["swallowed_total"] == 2

        # 日翻转:daily.swallowed 清零,但 swallowed_total 是生命周期累加器不清零
        # (blocker②:finitude.assemble_anthology 靠它读全量"被咽回句数")。
        sm._do_rollover(sid, "2099-01-01")
        record = sm._store.get(sid)
        assert record["daily"]["swallowed"] == 0
        assert record["swallowed_total"] == 2

    async def test_delayed_delivers_once_via_impulse_no_double_send(self, tmp_path):
        """delayed 真正送达只经 affect_impulse 单一出队点,不会在到期后重复送达。"""
        sm = make_manager(tmp_path)
        sid = "s-delayed"
        await bind_companion(sm, sid)
        sm._surface_cache[sid] = surface_for("withdraw", pressure=0.95)

        async def noop_feed_back(umo, text, phase):
            return None

        sm._bridge.feed_back = noop_feed_back

        out = await sm.arbitrate(sid, "别问了。")
        await drain_spawned(sm)
        assert out["delayed"]["due_in_seconds"] == 90

        # 提前 poll:还没到期,取不到。
        early = await sm.impulse(sid)
        assert early["utterances"] == []

        # monkeypatch 时钟到 90s 之后(直接操纵队列到期判定改走 outbox 内部 now,
        # 简化为直接调用 outbox.drain_due 验证到期后单次出队即清空)。
        now = sm._now_ts()
        first = sm._outbox.drain_due(sid, now + 91)
        assert len(first.items) == 1
        assert first.items[0].occasion == "withdraw_heavy"
        # 同一到期时刻再次 drain:队列已空,不会双送达(单一出队点纪律)。
        second = sm._outbox.drain_due(sid, now + 91)
        assert second.items == []


# --- has_non_plain 契约(issue26 教训的 MCP 落法,D10)----------------------


class TestNonPlainAndEmptyDraft:
    async def test_empty_draft_passes(self, tmp_path):
        sm = make_manager(tmp_path)
        sid = "s-empty"
        await bind_companion(sm, sid)
        sm._surface_cache[sid] = surface_for("withdraw", pressure=0.95)
        out = await sm.arbitrate(sid, "   ")
        assert out["verdict"] == "PASS"
        assert out["final_text"] == "   "

    async def test_unbound_session_pass(self, tmp_path):
        sm = make_manager(tmp_path)
        out = await sm.arbitrate("never-bound", "随便说点什么。")
        assert out["verdict"] == "PASS"
        assert out["reason"] == "unbound_or_sealed"


# --- P0:静默期的 PASS 不回喂(红队 medium 回归锁)---------------------------


class TestSilencedPassNoFeed:
    async def test_silenced_pass_returns_draft_but_never_feeds(self, tmp_path):
        """静默中 arbitrate 恒 PASS 放行原文,但绝不以 response 回喂引擎——
        她的嘴被静默时,"她应了这轮"的感知一并静默(P0,红队 medium)。"""
        sm = make_manager(tmp_path)
        sid = "s-silenced"
        await bind_companion(sm, sid)
        sm._surface_cache[sid] = surface_for("explore", pressure=0.1, expr=0.5)

        feeds: list[tuple[str, str, str]] = []

        async def spy_feed_back(umo, text, phase):
            feeds.append((umo, text, phase))

        sm._bridge.feed_back = spy_feed_back

        res = await sm.pause(sid, hours=1.0)
        assert res.get("paused") or res.get("silence_until")

        draft = "这句话不该被她的心经历。"
        out = await sm.arbitrate(sid, draft)
        await drain_spawned(sm)

        assert out["verdict"] == "PASS"
        assert out["final_text"] == draft
        # 核心断言:零回喂。
        assert feeds == []
