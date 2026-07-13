"""policies/smooth.py 在整个架构中的位置。

SmoothPolicy:深化轨,θ 生效处。理论出身 = 连续得分 + 软阈值带,与
TablePolicy 的本质差异(非调参换皮,arbiter_BLUEPRINT §3.2):Table 是
action 分派后的**单变量阈值判定**(withdraw 只看 pressure,hold 只看
expr);Smooth 是**多维加权的连续证据合成**——高 expression 可以把边界
压力推过 swallow 带,低 warmth 可以抬升介入分。同一输入两者可产不同
verdict(区分度探针见 tests/arbiter/test_distinguishability.py)。

不变量:P0/不应期由管线守卫保证(本类不重复判定);SWALLOW 高强度记账
判据仍固定 0.75(N6,得分带只决定 verdict 种类,不决定记账);调制闸/
narrow 收窄由后置滤波 ``guards.post_mod_gate`` 统一处理,本类只产"裸"
verdict(不在此处调闸,避免与后置滤波重复判定 —— 管线语义表 §2.1:
非 Table 策略的后置滤波"逐条执行")。

设计取舍(施工纪律要求"照 spec 落地并记"的疑义,供红队核):
1. 八维特征的权重表是本实现的自著选择,蓝图只给出"score = Σw_i·x_i"
   的形状与七个维度名,未给出具体权重值——本文件的权重是达成
   "同一输入可产不同 verdict"的可测目标下的一组合理取值,不是唯一解。
2. 占用哈希币的 hold 二选一(N3)是 TablePolicy 内核私有机制;Smooth
   用连续得分带直接判定,不复用该哈希币(N3 只要求"不新增键",Smooth
   干脆不消费币,不算破约)。
3. occasion 词组的选取复用 core.arbiter 已用过的 occasion 字面量
   (withdraw_heavy/withdraw_soft/hold_hesitant/trim_tail),避免发明
   primal 词库未收录的新场合——若与 primal 白名单实际收录情况有出入,
   由 primal owner 在集成时核对(本波不改 primal)。
"""

from __future__ import annotations

from ...core import sget, split_sentences
from ...core.arbiter import Verdict
from ..inputs import PolicyInput
from .base import register

# --- 权重表(§3.2 八维特征;每维语义注释见行内) ---------------------------

W_PRESSURE = 1.00  # 主导维度:直接对应 v0.1 pressure 判据,量纲可比
W_EXPR = 0.30  # 高表达欲上抬评分(愿意多说,更难被压住)
W_FATIGUE = 0.15  # 疲惫(*号维,防御式 sget 缺省 0 → 贡献为零,保守方向)
W_WARMTH = -0.15  # 暖度抬升则评分下降(她更安心,不必咽/替换)
W_P = 0.20  # 可塑性 P 越高,越有主见去介入(中心化:(P-0.5))
W_LEN = 0.10  # 草稿越长,越倾向裁剪/替换(中心化:(len_norm-0.5))
W_ACTION = 0.10  # 引擎既有 action 的介入基调(见 ACTION_BIAS)
W_AGE = -0.08  # Surface 越陈旧,评分保守下调(不弃权,只降权,与
#                Conservative 的"弃权"机制正交、力度更弱)

# action 基调偏置(中心化,0 为中性;不影响 P0/不应期,那是守卫层职责)
ACTION_BIAS: dict[str, float] = {
    "withdraw": 0.5,
    "hold": 0.2,
    "recover": 0.1,
    "express": 0.0,
    "guard": -0.3,
    "reach_out": -0.3,
    "explore": -0.3,
}


def _score(pin: PolicyInput) -> tuple[float, str, float, float, int]:
    """返回 (score, action, pressure, expr, n_sentences)。"""
    b = pin.base
    surface = b.surface
    action = str(sget(surface, "decision.action", "hold"))
    pressure = float(sget(surface, "state.boundary.pressure", 0.0))
    expr = float(sget(surface, "state.needs.expression", 0.0))
    fatigue = float(sget(surface, "state.needs.fatigue", 0.0))
    warmth = sget(surface, "state.warmth", None)
    warmth_v = float(warmth) if isinstance(warmth, (int, float)) else 0.0
    sentences = split_sentences(b.draft)
    n = len(sentences)
    draft_len_norm = min(n / 8.0, 1.0)
    age_norm = min(max(pin.surface_age_s, 0.0) / 600.0, 1.0)
    action_bias = ACTION_BIAS.get(action, 0.0)

    score = (
        W_PRESSURE * pressure
        + W_EXPR * (expr - 0.5)
        + W_FATIGUE * fatigue
        + W_WARMTH * warmth_v
        + W_P * (b.p - 0.5)
        + W_LEN * (draft_len_norm - 0.5)
        + W_ACTION * action_bias
        + W_AGE * age_norm
    )
    return score, action, pressure, expr, n


def _occasion_for(action: str, pressure: float) -> str:
    if action == "withdraw":
        return "withdraw_heavy" if pressure >= 0.55 else "withdraw_soft"
    if action == "hold":
        return "hold_hesitant"
    return "withdraw_soft"


class SmoothPolicy:
    policy_id = "smooth"

    def decide(self, pin: PolicyInput) -> Verdict:
        b = pin.base
        score, action, pressure, expr, n = _score(pin)
        params = pin.params

        if action == "guard":
            return Verdict("PASS", freeze_today=True, reason="smooth_guard_freeze")
        if action == "reach_out":
            return Verdict("PASS", reach_out_signal=True, reason="smooth_reach_out")
        if action == "explore":
            return Verdict("PASS", reason="smooth_explore_exempt")

        if score >= params.swallow_th:
            delayed = "withdraw_heavy" if action == "withdraw" else None
            return Verdict(
                "SWALLOW",
                delayed_occasion=delayed,
                delay_seconds=90 if delayed else 0,
                high_intensity=pressure >= 0.75,
                reason=f"smooth_swallow:{action}",
            )
        if score >= params.replace_heavy_th:
            return Verdict(
                "REPLACE",
                occasion=_occasion_for(action, pressure),
                reason=f"smooth_replace:{action}",
            )
        if expr >= params.express_expr_th and score >= (params.replace_heavy_th - 0.15):
            sentences = split_sentences(b.draft)
            first = sentences[0] if sentences else b.draft
            return Verdict("TRIM", trimmed=first, reason=f"smooth_trim:{action}")
        return Verdict("PASS", reason=f"smooth_pass:{action}")


SMOOTH_POLICY = register(SmoothPolicy())
