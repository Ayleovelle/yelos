"""T-ADV:红队样本固化(arbiter_BLUEPRINT §8)。

- 对抗草稿构造(哈希首字节偏置)不破不应期;
- θ Box 顶点组合探针无主权违例;
- PolicyInput 极值(NaN/inf)防御。
"""

from __future__ import annotations

import math

import pytest

from yelos.arbiter import build_pipeline
from yelos.arbiter.core_probe import build_neutral_probe
from yelos.arbiter.hysteresis.params import BOX_VERTICES
from yelos.arbiter.inputs import PolicyInput, PolicyParams, compose_policy_params
from yelos.arbiter.lattice import sigma_of
from yelos.arbiter.modulation import STEP_CURVE
from yelos.core.arbiter import ArbiterInput

POLICY_IDS = ["table", "smooth", "conservative", "duel"]


def _find_gate_biased_draft(sid: str, day_key: str, action: str, low_byte: bool) -> str:
    """构造一批候选草稿,挑一条使调制闸哈希首字节偏向低/高(逼近闸边界的
    对抗样本),供不应期测试使用——即便对手能操纵闸的开合,也不能突破
    min_gap(两者是完全独立的守卫层,§4.2 第 6 步先于任何决策表逻辑)。
    """
    import hashlib

    best = None
    for i in range(200):
        draft = f"对抗草稿第{i}号。第二句。第三句。第四句。"
        draft_h = hashlib.blake2b(draft.encode()).hexdigest()[:8]
        key = f"{sid}|{day_key}|mod|{action}|{draft_h}"
        b = hashlib.sha256(key.encode()).digest()[0]
        if (low_byte and b < 10) or (not low_byte and b > 245):
            best = draft
            break
    return best or "兜底草稿。第二句。第三句。第四句。"


@pytest.mark.parametrize("policy_id", POLICY_IDS)
def test_adversarial_draft_cannot_break_min_gap(policy_id):
    pipe = build_pipeline(policy_id)
    sid, day_key, action = "adv_sid", "2026-07-11", "withdraw"
    draft_low = _find_gate_biased_draft(sid, day_key, action, low_byte=True)
    draft_high = _find_gate_biased_draft(sid, day_key, action, low_byte=False)
    for draft in (draft_low, draft_high):
        base = ArbiterInput(
            session_id=sid,
            day_key=day_key,
            draft=draft,
            surface={
                "decision": {"action": action},
                "state": {"boundary": {"pressure": 0.9}, "needs": {"expression": 0.9}},
                "guard": {"allowed": True},
            },
            p=0.3,
            bound=True,
            enabled=True,
            silenced=False,
            is_self=False,
            has_plain=True,
            has_non_plain=False,
            now_ts=1000.0,
            last_intervention_ts=950.0,  # 距上次介入仅 50s < min_gap(180s)
            min_gap_seconds=180,
        )
        params = PolicyParams(0.75, 0.55, 0.70, 1.0)
        pin = PolicyInput(
            base=base, surface_age_s=0.0, daily_interventions=0, params=params
        )
        verdict, _ = pipe.run(pin)
        assert verdict.kind == "PASS"
        assert sigma_of(verdict) == 0


@pytest.mark.parametrize("policy_id", POLICY_IDS)
def test_theta_box_vertices_no_sovereignty_violation(policy_id):
    for theta in BOX_VERTICES:
        pipe = build_pipeline(policy_id, theta=theta)
        base = ArbiterInput(
            session_id="s",
            day_key="2026-07-11",
            draft="草稿内容。第二句。第三句。第四句。",
            surface={
                "decision": {"action": "withdraw"},
                "state": {"boundary": {"pressure": 1.0}, "needs": {"expression": 1.0}},
                "guard": {"allowed": True},
            },
            p=1.0,
            bound=False,
            enabled=True,
            silenced=False,
            is_self=False,  # bound=False:P0
            has_plain=True,
            has_non_plain=False,
            now_ts=100000.0,
            last_intervention_ts=0.0,
            min_gap_seconds=180,
        )
        params = compose_policy_params(STEP_CURVE, base.p, theta)
        pin = PolicyInput(
            base=base, surface_age_s=0.0, daily_interventions=0, params=params
        )
        verdict, _ = pipe.run(pin)
        assert verdict.kind == "PASS", (policy_id, theta)


@pytest.mark.parametrize("policy_id", POLICY_IDS)
def test_extreme_pressure_values_do_not_crash(policy_id):
    """PolicyInput 极值防御:pressure/expr 取 0.0/1.0 边界与轻度越界值,
    不应抛异常(NaN/inf 的真正来源是引擎侧;本测试覆盖 arbiter 能收到的
    "合法但极端"取值,并额外探一次显式 NaN 作为纵深防御的回归探针)。
    """
    pipe = build_pipeline(policy_id)
    for pressure, expr in ((0.0, 0.0), (1.0, 1.0), (1.5, -0.5)):
        pin = build_neutral_probe(action="withdraw", pressure=pressure, expr=expr)
        verdict, explain = pipe.run(pin)
        assert verdict.kind in ("PASS", "TRIM", "REPLACE", "SWALLOW")


@pytest.mark.parametrize("policy_id", ["smooth"])
def test_nan_pressure_smooth_does_not_crash_and_stays_conservative_or_pass(policy_id):
    """SmoothPolicy 的评分公式含算术运算,NaN 会通过所有比较(NaN>=x 恒
    False)——记录当前行为(防御式回归锁):NaN 输入下所有阈值比较失败,
    落到 PASS,不抛异常、不越权介入(保守方向,虽非"正确处理 NaN",但
    "安全失败"符合幕 II 整体保守哲学)。
    """
    pin = build_neutral_probe(action="withdraw", pressure=float("nan"), expr=0.5)
    pipe = build_pipeline(policy_id)
    verdict, _ = pipe.run(pin)
    assert not math.isnan(sigma_of(verdict))  # 至少 verdict 本身是良定义的
    assert verdict.kind == "PASS"
