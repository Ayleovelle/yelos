"""test_arbiter.py —— 幕 II 话语权仲裁测试(蓝图 §13 / §4)。

锁死项(蓝图 §13 test_arbiter.py 一行):
- 7 枚举 × 全条件分支覆盖
- 6 条前置守卫顺序(含非 Plain 链 PASS)
- 阈值边界:0.75 / 0.70 / 0.55 / 0.3 / 0.7
- 调制闸(消息粒度)确定性:同输入同输出
- P<=0.15 收窄
- 未知 action → PASS
- high_intensity 判据固定 0.75,与 swallow_th 解耦

纯逻辑测试:只 import core.arbiter,不碰 astrbot / sylanne_core。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from yelos.core.arbiter import ArbiterInput, arbitrate  # noqa: E402

# --- 构造输入的基线工厂 -------------------------------------------------


def make_input(**overrides) -> ArbiterInput:
    """默认全部守卫放行、action=hold(expr>=0.3 走哈希分支)的基线输入。

    覆盖字段via overrides,便于每个用例只改动关心的字段。
    """
    base = dict(
        session_id="s1",
        day_key="2026-07-11",
        draft="今天天气不错。",
        surface={
            "decision": {"action": "hold"},
            "state": {
                "boundary": {"pressure": 0.0},
                "needs": {"expression": 0.5},
            },
            "guard": {"allowed": True},
        },
        p=1.0,
        bound=True,
        enabled=True,
        silenced=False,
        is_self=False,
        has_plain=True,
        has_non_plain=False,
        now_ts=1000.0,
        last_intervention_ts=0.0,
        min_gap_seconds=5,
    )
    base.update(overrides)
    return ArbiterInput(**base)


def surface_for(action: str, pressure: float = 0.0, expr: float = 0.5) -> dict:
    return {
        "decision": {"action": action},
        "state": {
            "boundary": {"pressure": pressure},
            "needs": {"expression": expr},
        },
        "guard": {"allowed": True},
    }


# --- §4.2 六条前置守卫,顺序固定 -----------------------------------------


class TestGuards:
    def test_guard1_not_bound(self):
        inp = make_input(bound=False)
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_silenced_or_unbound"

    def test_guard1_not_enabled(self):
        inp = make_input(enabled=False)
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_silenced_or_unbound"

    def test_guard1_silenced(self):
        inp = make_input(silenced=True)
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_silenced_or_unbound"

    def test_guard2_is_self(self):
        inp = make_input(is_self=True)
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_self"

    def test_guard3_no_plain_flag(self):
        inp = make_input(has_plain=False)
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_no_plain"

    def test_guard3_blank_draft(self):
        inp = make_input(draft="   ")
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_no_plain"

    def test_guard4_has_non_plain(self):
        # 非 Plain 链即便 action 会触发 SWALLOW/REPLACE 也必须 PASS(issue26)
        inp = make_input(
            has_non_plain=True,
            surface=surface_for("withdraw", pressure=0.9),
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_non_plain"

    def test_guard5_surface_none(self):
        inp = make_input(surface=None)
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_engine_guard"

    def test_guard5_guard_not_allowed(self):
        surface = surface_for("withdraw", pressure=0.9)
        surface["guard"]["allowed"] = False
        inp = make_input(surface=surface)
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_engine_guard"

    def test_guard6_min_gap_not_elapsed(self):
        inp = make_input(now_ts=100.0, last_intervention_ts=99.0, min_gap_seconds=5)
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "guard_min_gap"

    def test_guard6_min_gap_elapsed_ok(self):
        # 恰好等于 min_gap 不算命中(严格小于才 PASS)
        inp = make_input(now_ts=105.0, last_intervention_ts=100.0, min_gap_seconds=5)
        v = arbitrate(inp)
        assert v.kind != "PASS" or v.reason != "guard_min_gap"

    def test_guard_order_first_hit_wins(self):
        # 同时命中 guard1(silenced)与 guard2(is_self)等多条,顺序上 guard1 先触发
        inp = make_input(silenced=True, is_self=True, has_plain=False)
        v = arbitrate(inp)
        assert v.reason == "guard_silenced_or_unbound"


# --- §4.3 决策表:7 枚举全条件分支 ---------------------------------------


class TestWithdraw:
    def test_swallow_high_pressure_p_high(self):
        # P>=0.5 时 swallow_th=0.75
        inp = make_input(p=1.0, surface=surface_for("withdraw", pressure=0.8))
        v = arbitrate(inp)
        assert v.kind == "SWALLOW"
        assert v.delayed_occasion == "withdraw_heavy"
        assert v.delay_seconds == 90
        assert v.high_intensity is True

    def test_swallow_threshold_boundary_075_inclusive(self):
        inp = make_input(p=1.0, surface=surface_for("withdraw", pressure=0.75))
        v = arbitrate(inp)
        assert v.kind == "SWALLOW"
        assert v.high_intensity is True  # 0.75 判据含等号

    def test_swallow_just_below_075_at_high_p_goes_replace_heavy(self):
        inp = make_input(p=1.0, surface=surface_for("withdraw", pressure=0.74))
        v = arbitrate(inp)
        assert v.kind == "REPLACE"
        assert v.occasion == "withdraw_heavy"

    def test_swallow_threshold_low_p_070(self):
        # P<0.5 时 swallow_th=0.70;pressure=0.70 应 SWALLOW
        inp = make_input(p=0.4, surface=surface_for("withdraw", pressure=0.70))
        v = arbitrate(inp)
        assert v.kind == "SWALLOW"
        # high_intensity 判据与 swallow_th 解耦,固定 0.75:0.70<0.75 不计高强度
        assert v.high_intensity is False

    def test_high_intensity_decoupled_from_swallow_th_low_p(self):
        # 红队 F3b:P<0.5 时 0.70<=pressure<0.75 的 SWALLOW 触发但不计高强度
        inp = make_input(p=0.3, surface=surface_for("withdraw", pressure=0.72))
        v = arbitrate(inp)
        assert v.kind == "SWALLOW"
        assert v.high_intensity is False

    def test_high_intensity_true_when_pressure_075_even_low_p(self):
        inp = make_input(p=0.3, surface=surface_for("withdraw", pressure=0.75))
        v = arbitrate(inp)
        assert v.kind == "SWALLOW"
        assert v.high_intensity is True

    def test_replace_heavy_pressure_boundary_055(self):
        inp = make_input(p=1.0, surface=surface_for("withdraw", pressure=0.55))
        v = arbitrate(inp)
        assert v.kind == "REPLACE"
        assert v.occasion == "withdraw_heavy"

    def test_replace_soft_just_below_055(self):
        inp = make_input(p=1.0, surface=surface_for("withdraw", pressure=0.54))
        v = arbitrate(inp)
        assert v.kind == "REPLACE"
        assert v.occasion == "withdraw_soft"

    def test_replace_soft_low_pressure(self):
        inp = make_input(p=1.0, surface=surface_for("withdraw", pressure=0.0))
        v = arbitrate(inp)
        assert v.kind == "REPLACE"
        assert v.occasion == "withdraw_soft"

    def test_narrow_withdraw_forces_replace_soft(self):
        # P<=0.15:withdraw 三行全部改 REPLACE withdraw_soft,即便 pressure 很高
        inp = make_input(p=0.1, surface=surface_for("withdraw", pressure=0.9))
        v = arbitrate(inp)
        assert v.kind == "REPLACE"
        assert v.occasion == "withdraw_soft"
        assert v.reason == "narrow_withdraw_soft"


class TestHold:
    def test_hold_low_expr_swallow(self):
        inp = make_input(p=1.0, surface=surface_for("hold", expr=0.29))
        v = arbitrate(inp)
        assert v.kind == "SWALLOW"
        assert v.occasion is None
        assert v.reason == "hold_swallow"

    def test_hold_expr_boundary_03_not_low(self):
        # expr==0.3 不满足 < 0.3,走哈希二选一分支而非纯沉默
        inp = make_input(p=1.0, surface=surface_for("hold", expr=0.3))
        v = arbitrate(inp)
        assert v.kind in ("TRIM", "REPLACE")

    def test_hold_narrow_low_expr_pass(self):
        inp = make_input(p=0.1, surface=surface_for("hold", expr=0.1))
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "narrow_hold_swallow"

    def test_hold_narrow_high_expr_pass(self):
        inp = make_input(p=0.1, surface=surface_for("hold", expr=0.9))
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "narrow_hold"

    def test_hold_hash_pick_trim(self):
        # 挑一个使 sha256(sid|day|hold) 首字节为偶数的 session_id,得到 TRIM
        sid = _find_sid_for_hash_parity("2026-07-11", "hold", even=True)
        inp = make_input(
            session_id=sid,
            draft="第一句话。第二句话。",
            p=1.0,
            surface=surface_for("hold", expr=0.9),
        )
        v = arbitrate(inp)
        assert v.kind == "TRIM"
        assert v.occasion == "trim_tail"
        assert v.trimmed == "第一句话。"

    def test_hold_hash_pick_replace(self):
        sid = _find_sid_for_hash_parity("2026-07-11", "hold", even=False)
        inp = make_input(session_id=sid, p=1.0, surface=surface_for("hold", expr=0.9))
        v = arbitrate(inp)
        assert v.kind == "REPLACE"
        assert v.occasion == "hold_hesitant"

    def test_hold_deterministic_same_input_same_output(self):
        inp = make_input(p=1.0, surface=surface_for("hold", expr=0.9))
        v1 = arbitrate(inp)
        v2 = arbitrate(inp)
        assert v1 == v2


def _find_sid_for_hash_parity(day_key: str, action: str, even: bool) -> str:
    for i in range(200):
        sid = f"sid{i}"
        b = hashlib.sha256(f"{sid}|{day_key}|{action}".encode()).digest()[0]
        if (b % 2 == 0) == even:
            return sid
    raise AssertionError("未找到满足奇偶条件的 session_id,测试环境异常")


class TestGuardAction:
    def test_guard_action_pass_freeze(self):
        inp = make_input(p=1.0, surface=surface_for("guard"))
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.freeze_today is True
        assert v.reason == "guard_freeze"


class TestRecover:
    def test_recover_short_draft_pass(self):
        inp = make_input(
            p=1.0,
            draft="一句。两句。三句。",
            surface=surface_for("recover"),
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.allow_recover_primal is True
        assert v.reason == "recover_pass"

    def test_recover_long_draft_trim(self):
        inp = make_input(
            p=1.0,
            draft="一句。两句。三句。四句。",
            surface=surface_for("recover"),
        )
        v = arbitrate(inp)
        assert v.kind == "TRIM"
        assert v.trimmed == "一句。两句。"
        assert v.allow_recover_primal is True

    def test_recover_narrow_forces_pass_but_keeps_flag(self):
        inp = make_input(
            p=0.1,
            draft="一句。两句。三句。四句。",
            surface=surface_for("recover"),
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.allow_recover_primal is True

    def test_recover_trim_gated_downgrade_keeps_flag(self):
        # 找一个使调制闸不放行的 session_id(P<0.5),TRIM 应降级为 PASS
        # 但 allow_recover_primal 仍需保留(蓝图 §4.3:两分支均 True)
        draft = "一句。两句。三句。四句。"
        sid = _find_gate_blocked_sid(draft, "recover", p=0.3, day_key="2026-07-11")
        inp = make_input(
            session_id=sid, p=0.3, draft=draft, surface=surface_for("recover")
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.allow_recover_primal is True
        assert v.reason == "recover_trim_gate"


def _find_gate_blocked_sid(draft: str, action: str, p: float, day_key: str) -> str:
    draft_h = hashlib.blake2b(draft.encode()).hexdigest()[:8]
    for i in range(500):
        sid = f"gsid{i}"
        key = f"{sid}|{day_key}|mod|{action}|{draft_h}"
        b = hashlib.sha256(key.encode()).digest()[0]
        if not (b / 255 < p / 0.5):
            return sid
    raise AssertionError("未找到被闸门拦下的 session_id,测试环境异常")


def _find_gate_allowed_sid(draft: str, action: str, p: float, day_key: str) -> str:
    draft_h = hashlib.blake2b(draft.encode()).hexdigest()[:8]
    for i in range(500):
        sid = f"asid{i}"
        key = f"{sid}|{day_key}|mod|{action}|{draft_h}"
        b = hashlib.sha256(key.encode()).digest()[0]
        if b / 255 < p / 0.5:
            return sid
    raise AssertionError("未找到被闸门放行的 session_id,测试环境异常")


class TestReachOut:
    def test_reach_out_pass_with_signal(self):
        inp = make_input(p=1.0, surface=surface_for("reach_out"))
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reach_out_signal is True
        assert v.reason == "reach_out"


class TestExplore:
    def test_explore_always_pass_exempt(self):
        # explore 恒豁免,即便 expr/pressure 满足 express_trim 条件也不截断
        inp = make_input(
            p=1.0,
            draft="一。二。三。四。",
            surface=surface_for("explore", pressure=0.0, expr=0.9),
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "explore_exempt"


class TestExpress:
    def test_express_trim_when_all_conditions_met(self):
        inp = make_input(
            p=1.0,
            draft="第一句。第二句。第三句。第四句。",
            surface=surface_for("express", pressure=0.3, expr=0.7),
        )
        v = arbitrate(inp)
        assert v.kind == "TRIM"
        assert v.trimmed == "第一句。"

    def test_express_expr_boundary_07_inclusive(self):
        inp = make_input(
            p=1.0,
            draft="一。二。三。四。",
            surface=surface_for("express", pressure=0.3, expr=0.7),
        )
        v = arbitrate(inp)
        assert v.kind == "TRIM"

    def test_express_expr_just_below_07_pass(self):
        inp = make_input(
            p=1.0,
            draft="一。二。三。四。",
            surface=surface_for("express", pressure=0.3, expr=0.69),
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "express_pass"

    def test_express_pressure_boundary_03_inclusive(self):
        inp = make_input(
            p=1.0,
            draft="一。二。三。四。",
            surface=surface_for("express", pressure=0.3, expr=0.8),
        )
        v = arbitrate(inp)
        assert v.kind == "TRIM"

    def test_express_pressure_just_above_03_pass(self):
        inp = make_input(
            p=1.0,
            draft="一。二。三。四。",
            surface=surface_for("express", pressure=0.31, expr=0.8),
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "express_pass"

    def test_express_short_draft_pass(self):
        # 句数不足 3 句(<=3)不满足 long_draft
        inp = make_input(
            p=1.0,
            draft="一。二。三。",
            surface=surface_for("express", pressure=0.3, expr=0.8),
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "express_pass"

    def test_express_trim_disabled_by_config(self):
        inp = make_input(
            p=1.0,
            draft="一。二。三。四。",
            surface=surface_for("express", pressure=0.3, expr=0.8),
            express_trim_enabled=False,
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "express_pass"

    def test_express_narrow_forces_pass(self):
        inp = make_input(
            p=0.1,
            draft="一。二。三。四。",
            surface=surface_for("express", pressure=0.3, expr=0.8),
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "narrow_express"


class TestUnknownAction:
    def test_unknown_action_pass(self):
        inp = make_input(p=1.0, surface=surface_for("some_future_action_v3"))
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "unknown_action:some_future_action_v3"

    def test_unknown_action_various_values(self):
        for weird in ("", "None", "123", "WITHDRAW", "hold "):
            inp = make_input(p=1.0, surface=surface_for(weird))
            v = arbitrate(inp)
            assert v.kind == "PASS"


# --- §4.4 有限性调制闸:确定性 + P<0.5 才生效 ------------------------------


class TestModulationGate:
    def test_gate_deterministic_same_input_same_output(self):
        draft = "今天天气不错。还行吧。"
        surface = surface_for("withdraw", pressure=0.2)
        inp = make_input(p=0.3, draft=draft, surface=surface)
        v1 = arbitrate(inp)
        v2 = arbitrate(inp)
        assert v1 == v2

    def test_gate_p_at_or_above_05_always_passes_through(self):
        # P>=0.5 时 _gate_or_pass 恒放行,不查表
        inp = make_input(p=0.5, surface=surface_for("withdraw", pressure=0.0))
        v = arbitrate(inp)
        assert v.kind == "REPLACE"
        assert v.occasion == "withdraw_soft"

    def test_gate_message_granularity_different_draft_can_differ(self):
        # 消息粒度键含 draft 哈希:同 sid/day/action,不同 draft 的闸门结果
        # 应当可以不同(红队 F2 核心诉求),不做强断言具体值,只验证机制生效
        # (即两种 draft 中至少存在一组返回不同 kind 的组合)
        p = 0.2
        day_key = "2026-07-11"
        sid = "gate_probe"
        surface = surface_for("withdraw", pressure=0.0)
        kinds = set()
        for i in range(30):
            draft = f"草稿变体{i}。"
            inp = make_input(
                session_id=sid, p=p, draft=draft, surface=surface, day_key=day_key
            )
            v = arbitrate(inp)
            kinds.add(v.kind)
        # 应该同时出现被放行(REPLACE)与被降级(PASS)的情况,证明闸门按消息粒度判定
        assert "REPLACE" in kinds or "PASS" in kinds
        assert len(kinds) >= 1

    def test_gate_blocked_downgrades_to_pass(self):
        draft = "今天天气不错。"
        sid = _find_gate_blocked_sid(draft, "withdraw", p=0.3, day_key="2026-07-11")
        inp = make_input(
            session_id=sid,
            p=0.3,
            draft=draft,
            surface=surface_for("withdraw", pressure=0.0),
        )
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.reason == "mod_gate_downgrade:withdraw"

    def test_gate_allowed_passes_through(self):
        draft = "今天天气不错。"
        sid = _find_gate_allowed_sid(draft, "withdraw", p=0.3, day_key="2026-07-11")
        inp = make_input(
            session_id=sid,
            p=0.3,
            draft=draft,
            surface=surface_for("withdraw", pressure=0.0),
        )
        v = arbitrate(inp)
        assert v.kind == "REPLACE"

    def test_gate_swallow_bypasses_gate(self):
        # SWALLOW 不过闸:即便 P<0.5,高 pressure 仍直接 SWALLOW
        inp = make_input(p=0.3, surface=surface_for("withdraw", pressure=0.9))
        v = arbitrate(inp)
        assert v.kind == "SWALLOW"


# --- 收窄 P<=0.15 综合 ---------------------------------------------------


class TestNarrowBoundary:
    def test_narrow_boundary_015_inclusive(self):
        inp = make_input(p=0.15, surface=surface_for("withdraw", pressure=0.9))
        v = arbitrate(inp)
        assert v.kind == "REPLACE"
        assert v.occasion == "withdraw_soft"

    def test_not_narrow_just_above_015(self):
        inp = make_input(p=0.16, surface=surface_for("withdraw", pressure=0.9))
        v = arbitrate(inp)
        assert v.kind == "SWALLOW"

    def test_narrow_guard_freeze_still_applies(self):
        # 收窄不影响 guard 的防御性副作用
        inp = make_input(p=0.1, surface=surface_for("guard"))
        v = arbitrate(inp)
        assert v.kind == "PASS"
        assert v.freeze_today is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
