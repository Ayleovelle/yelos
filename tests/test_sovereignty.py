"""MCP 层测试:主权面(蓝图 §8.2 test_sovereignty.py)。

锁什么:
1. pause / reset / farewell **永不被任何状态阻断**(guard_frozen / 静默 /
   steward 与 companion 模式差异,主权铁律 §6.2)。
2. farewell **两段式**(红队 major④):首次调用不封存,只返一次性 token +
   她这一生的摘要;二次携有效 token 才真正 seal/export;过期 / 错 token /
   已消费 token 一律拒绝。
3. 封存后不进 ``bound_umos()``,不可逆(重复 farewell 只报 unbound_or_sealed)。
4. steward 门控矩阵:pause/reset/farewell 两模式恒可用(§5)。
5. speaker 冲突去重告警(major③):同文本短时窗内先后以不同方向提交 →
   记告警、当轮不喂影子。
6. per-session ``asyncio.Lock`` 并发用例(红队 major⑥/§7.2):并发
   ``affect_impulse``/``affect_farewell`` 对同一 sid 不得双出队 / 双 seal。

真实 fastmcp/mcp SDK 是否安装不影响本文件——直测 ``session.SessionManager``
+ ``sovereignty`` 逻辑层,不经 server.py 协议壳,`sylanne_core` 缺席时
``EngineBridge`` 安静降级(HAS_ENGINE=False),不需要假引擎桩。
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from yelos import outbox
from yelos.config import YelosConfig
from yelos.engine_bridge import EngineBridge
from yelos.session import SessionManager
from yelos.sovereignty import FarewellGate, REASON_TOKEN_INVALID, REASON_UNBOUND


async def _dummy_llm(_system: str, _user: str) -> str:
    raise RuntimeError("no llm configured (test stub)")


def make_manager(tmp_path, **overrides) -> SessionManager:
    cfg = YelosConfig(data_dir=str(tmp_path), **overrides)
    bridge = EngineBridge(_dummy_llm)
    mgr = SessionManager(cfg, bridge)
    mgr.load()
    return mgr


def run(coro):
    """在同步 test 函数里跑一个协程(不依赖 pytest-asyncio 插件配置)。"""
    return asyncio.run(coro)


# =========================================================================
# 1. pause / reset / farewell 永不被状态阻断
# =========================================================================


def test_pause_works_even_when_guard_frozen_and_silenced(tmp_path):
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-1", "阿澜", mode="companion")
        record = mgr._store.get("sid-1")
        record["daily"]["guard_frozen"] = True
        # 已经静默中也不挡 pause 本身(可以反复延长静默)
        mgr._store.set_silence("sid-1", mgr._now_ts() + 3600)
        return await mgr.pause("sid-1", hours=1.0)

    result = run(scenario())
    assert result["paused"] is True
    assert result["silence_until"] > 0


def test_reset_works_while_silenced_and_guard_frozen(tmp_path):
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-2", "", mode="companion")
        mgr._store.get("sid-2")["daily"]["guard_frozen"] = True
        await mgr.pause("sid-2", hours=1.0)  # 静默中
        return await mgr.reset("sid-2")

    result = run(scenario())
    assert result == {"reset": True}


def test_reset_keeps_binding_identity_but_evicts_cache(tmp_path):
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-3", "阿澜", mode="companion")
        mgr._surface_cache["sid-3"] = {"decision": {"action": "reach_out"}}
        mgr._reach_out_flag["sid-3"] = mgr._day_key()
        await mgr.reset("sid-3")

    run(scenario())
    record = mgr._store.get("sid-3")
    assert record is not None
    assert record.get("name") == "阿澜"
    assert record.get("mode") == "companion"
    assert not record.get("sealed", False)
    assert "sid-3" not in mgr._surface_cache
    assert "sid-3" not in mgr._reach_out_flag


def test_farewell_first_call_never_blocked_by_guard_or_silence(tmp_path):
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-4", "阿澜", mode="companion")
        record = mgr._store.get("sid-4")
        record["daily"]["guard_frozen"] = True
        await mgr.pause("sid-4", hours=6.0)
        return await mgr.farewell("sid-4")

    result = run(scenario())
    assert result["sealed"] is False
    assert result["pending_confirm"] is not None
    assert "token" in result["pending_confirm"]
    assert "summary" in result["pending_confirm"]
    # 首段不封存
    assert not mgr._store.get("sid-4").get("sealed", False)


# =========================================================================
# 2. farewell 两段式:首段不封存,二段携正确 token 才 seal
# =========================================================================


def test_farewell_two_step_seals_only_on_second_call_with_token(tmp_path):
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-5", "阿澜", mode="companion")
        first = await mgr.farewell("sid-5")
        token = first["pending_confirm"]["token"]
        # 二段之前仍在 bound_umos 里
        still_bound = "sid-5" in mgr._store.bound_umos()
        second = await mgr.farewell("sid-5", confirm_token=token)
        return first, second, still_bound

    first, second, still_bound = run(scenario())
    assert still_bound is True
    assert second["sealed"] is True
    assert second["anthology_path"] is not None
    assert second["days_lived"] is not None
    assert "sid-5" not in mgr._store.bound_umos()


def test_farewell_summary_reflects_swallowed_total_lifetime_counter(tmp_path):
    """摘要的被咽回句数走 record.swallowed_total(生命周期累加器,blocker②),
    不是仅当日 daily.swallowed——跨日也不掉。"""
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-6", "阿澜", mode="companion")
        record = mgr._store.get("sid-6")
        record["swallowed_total"] = 7
        record["daily"]["swallowed"] = 0  # 当日翻转后已清零,但生命周期计数还在
        return await mgr.farewell("sid-6")

    first = run(scenario())
    assert first["pending_confirm"]["summary"]["swallowed_total"] == 7


def test_farewell_wrong_token_rejected_and_does_not_consume_valid_one(tmp_path):
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-7", "", mode="companion")
        first = await mgr.farewell("sid-7")
        token = first["pending_confirm"]["token"]
        wrong = await mgr.farewell("sid-7", confirm_token="not-the-real-token")
        # 错 token 不消费真 token,真 token 仍可用
        real = await mgr.farewell("sid-7", confirm_token=token)
        return wrong, real

    wrong, real = run(scenario())
    assert wrong["sealed"] is False
    assert wrong["reason"] == REASON_TOKEN_INVALID
    assert real["sealed"] is True


def test_farewell_token_is_one_time_use(tmp_path):
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-8", "", mode="companion")
        first = await mgr.farewell("sid-8")
        token = first["pending_confirm"]["token"]
        ok = await mgr.farewell("sid-8", confirm_token=token)
        replay = await mgr.farewell("sid-8", confirm_token=token)
        return ok, replay

    ok, replay = run(scenario())
    assert ok["sealed"] is True
    assert replay["sealed"] is False
    assert replay["reason"] == REASON_UNBOUND  # 已封存,replay 走 unbound_or_sealed


def test_farewell_token_expiry_rejected():
    """token 过期(独立跑 FarewellGate,不依赖真实 sleep)。"""
    gate = FarewellGate(ttl_seconds=10)
    # 未过期(now < expires_ts)→ 校验通过且被一次性消费。
    tok_fresh = gate.issue("sid-x", now_ts=1000.0)
    assert gate.verify("sid-x", tok_fresh.token, now_ts=1005.0) is True
    # 恰好到期(now >= expires_ts)→ 拒绝。
    tok_edge = gate.issue("sid-x", now_ts=1000.0)
    assert gate.verify("sid-x", tok_edge.token, now_ts=1000.0 + 10.0) is False
    # 早于到期一瞬 → 仍通过。
    tok_ok = gate.issue("sid-x", now_ts=2000.0)
    assert gate.verify("sid-x", tok_ok.token, now_ts=2000.0 + 9.99) is True


def test_farewell_new_issue_invalidates_previous_token(tmp_path):
    """重新发起送别(再次首段调用)作废旧 token(FarewellGate 每 sid 至多一枚在途)。"""
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-9", "", mode="companion")
        first = await mgr.farewell("sid-9")
        old_token = first["pending_confirm"]["token"]
        second_issue = await mgr.farewell("sid-9")  # 再次首段,签发新 token
        stale_attempt = await mgr.farewell("sid-9", confirm_token=old_token)
        return second_issue, stale_attempt

    second_issue, stale_attempt = run(scenario())
    assert second_issue["sealed"] is False
    assert stale_attempt["sealed"] is False
    assert stale_attempt["reason"] == REASON_TOKEN_INVALID


def test_farewell_export_false_is_silent_return_no_anthology(tmp_path):
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-10", "", mode="steward")
        first = await mgr.farewell("sid-10", export=False)
        token = first["pending_confirm"]["token"]
        return await mgr.farewell("sid-10", export=False, confirm_token=token)

    second = run(scenario())
    assert second["sealed"] is True
    assert second["seal_kind"] == "returned"
    assert second["anthology_path"] is None


def test_farewell_on_unbound_session_reports_unbound(tmp_path):
    mgr = make_manager(tmp_path)
    result = run(mgr.farewell("never-bound"))
    assert result["sealed"] is False
    assert result["reason"] == REASON_UNBOUND
    assert result["pending_confirm"] is None


def test_sealed_session_not_in_bound_umos_and_further_farewell_is_unbound(tmp_path):
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-11", "", mode="companion")
        first = await mgr.farewell("sid-11")
        await mgr.farewell("sid-11", confirm_token=first["pending_confirm"]["token"])
        return await mgr.farewell("sid-11")  # 封存后再叫,应安静报 unbound

    result = run(scenario())
    assert "sid-11" not in mgr._store.bound_umos()
    assert result["sealed"] is False
    assert result["reason"] == REASON_UNBOUND


# =========================================================================
# 3. steward 门控矩阵:主权三通道两模式恒可用(§5)
# =========================================================================


@pytest.mark.parametrize("mode", ["steward", "companion"])
def test_sovereignty_tools_available_in_both_modes(tmp_path, mode):
    mgr = make_manager(tmp_path)

    async def scenario():
        sid = f"sid-mode-{mode}"
        await mgr.bind(sid, "", mode=mode)
        pause_res = await mgr.pause(sid, hours=1.0)
        reset_res = await mgr.reset(sid)
        farewell_first = await mgr.farewell(sid)
        return pause_res, reset_res, farewell_first

    pause_res, reset_res, farewell_first = run(scenario())
    assert pause_res["paused"] is True
    assert reset_res == {"reset": True}
    assert farewell_first["sealed"] is False
    assert farewell_first["pending_confirm"] is not None


def test_steward_arbitrate_always_pass_but_sovereignty_unaffected(tmp_path):
    """steward 恒 PASS(D5)与主权三通道正交:steward 也能立即 pause/farewell。"""
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-12", "", mode="steward")
        arb_res = await mgr.arbitrate("sid-12", "在忙，等下回你")
        pause_res = await mgr.pause("sid-12", hours=1.0)
        return arb_res, pause_res

    arb_res, pause_res = run(scenario())
    assert arb_res["verdict"] == "PASS"
    assert arb_res["final_text"] == "在忙，等下回你"
    assert pause_res["paused"] is True


# =========================================================================
# 4. speaker 冲突去重告警(major③)
# =========================================================================


def test_speaker_direction_conflict_skips_shadow_feed_and_warns(tmp_path, caplog):
    mgr = make_manager(tmp_path, shadow_enabled=True)
    calls: list[str] = []

    async def fake_submit_shadow(sid, text, msg_id):
        calls.append(text)
        return None

    async def fake_submit_user(sid, text, msg_id):
        return None

    async def scenario():
        await mgr.bind("sid-13", "", mode="companion")
        mgr._bridge.submit_shadow = fake_submit_shadow
        mgr._bridge.submit_user = fake_submit_user
        same_text = "今天有点累"
        # agent 先标注同一段文本,随后短时窗内又被标成 user(方向标注冲突)。
        await mgr.submit("sid-13", same_text, speaker="agent")
        with caplog.at_level(logging.WARNING, logger="yelos.session"):
            await mgr.submit("sid-13", same_text, speaker="user")

    run(scenario())
    assert calls == []  # 冲突轮不喂影子
    assert any("speaker direction conflict" in rec.message for rec in caplog.records)


def test_speaker_no_conflict_when_texts_differ_feeds_shadow_normally(tmp_path):
    mgr = make_manager(tmp_path, shadow_enabled=True)
    calls: list[str] = []

    async def fake_submit_shadow(sid, text, msg_id):
        calls.append(text)
        return None

    async def fake_submit_user(sid, text, msg_id):
        return None

    async def scenario():
        await mgr.bind("sid-14", "", mode="companion")
        mgr._bridge.submit_shadow = fake_submit_shadow
        mgr._bridge.submit_user = fake_submit_user
        await mgr.submit("sid-14", "早安", speaker="agent")
        await mgr.submit("sid-14", "今天天气不错", speaker="user")

    run(scenario())
    assert calls == ["今天天气不错"]


def test_speaker_conflict_window_expires_after_interval(tmp_path):
    """冲突判定只在短时窗(intrinsic_interval_seconds)内生效,过窗不再算冲突。"""
    mgr = make_manager(tmp_path, shadow_enabled=True, intrinsic_interval_seconds=1)
    calls: list[str] = []

    async def fake_submit_shadow(sid, text, msg_id):
        calls.append(text)
        return None

    async def fake_submit_user(sid, text, msg_id):
        return None

    async def scenario():
        await mgr.bind("sid-15", "", mode="companion")
        mgr._bridge.submit_shadow = fake_submit_shadow
        mgr._bridge.submit_user = fake_submit_user
        same_text = "重复的话"
        await mgr.submit("sid-15", same_text, speaker="agent")
        await asyncio.sleep(1.2)  # 超过 1s 窗口
        await mgr.submit("sid-15", same_text, speaker="user")

    run(scenario())
    assert calls == ["重复的话"]  # 过窗后不算冲突,正常喂影子


# =========================================================================
# 5. per-session asyncio.Lock 并发用例(红队 major⑥/§7.2)
# =========================================================================


def test_concurrent_impulse_does_not_double_drain_same_outbox_item(tmp_path):
    """并发两次 affect_impulse 对同一 sid,唯一到期项只能被取走一次
    (per-session asyncio.Lock 串行化 drain+记账+save,§7.2)。"""
    mgr = make_manager(tmp_path, heartbeat_enabled=False)

    async def slow_tick_state(_sid):
        # 心跳关时 impulse 内联走 _heartbeat_step,其中的 await 是唯一能被
        # 并发任务插队的窗口;人为拉长它来暴露"没锁就会双出队"的风险面。
        await asyncio.sleep(0.03)
        return None

    async def scenario():
        await mgr.bind("sid-16", "", mode="companion")
        mgr._bridge.tick_state = slow_tick_state
        now_ts = mgr._now_ts()
        mgr._outbox.enqueue("sid-16", outbox.make_proactive(now_ts, "contact_seek"))
        assert mgr._outbox.size("sid-16") == 1
        r1, r2 = await asyncio.gather(mgr.impulse("sid-16"), mgr.impulse("sid-16"))
        return r1, r2

    r1, r2 = run(scenario())
    total = len(r1["utterances"]) + len(r2["utterances"])
    assert total == 1, "同一到期项被双出队了,per-session 锁失效"
    assert mgr._outbox.size("sid-16") == 0


def test_concurrent_farewell_same_token_only_one_seals(tmp_path):
    """并发两次携同一有效 token 的 farewell,只能有一次真正 seal
    (token 一次性消费 + per-sid 锁,防"agent 自主/竞态双送别")。"""
    mgr = make_manager(tmp_path)

    async def scenario():
        await mgr.bind("sid-17", "", mode="companion")
        first = await mgr.farewell("sid-17")
        token = first["pending_confirm"]["token"]
        return await asyncio.gather(
            mgr.farewell("sid-17", confirm_token=token),
            mgr.farewell("sid-17", confirm_token=token),
        )

    r1, r2 = run(scenario())
    sealed_flags = [r1["sealed"], r2["sealed"]]
    assert sealed_flags.count(True) == 1
    assert sealed_flags.count(False) == 1
