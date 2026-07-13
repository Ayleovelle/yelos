"""explain.py 在整个架构中的位置。

Explain 是仲裁一次判定的结构化溯源:守卫触发轨迹 / 后置滤波轨迹 / θ 摘要。
N7/N1 铁律:Explain **只进** accounting/viz/bench,绝不进
`affect_arbitrate` 的工具返回体——工具面 `reason: str` 语义与字符串集
零漂移,由 tests/arbiter/test_explain.py::T-X1 的穷举映射测试锁定。

taxonomy 表覆盖 v0.1 `core.arbiter.arbitrate` 会产生的全部 reason 字符串
(冻结内核,§4 逐条抄自 core/arbiter.py 的字面量),用于 TablePolicy 路径
——该路径守卫链被跳过(§2.1 管线语义表),Explain 靠 reason 反查生成。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardFire:
    """一次守卫链走查记录(命中或放行)。"""

    guard_id: str
    fired: bool


@dataclass(frozen=True)
class Explain:
    verdict_kind: str
    policy_id: str
    guard_trace: tuple[GuardFire, ...]
    filter_trace: tuple[str, ...]
    theta_digest: str


def theta_digest(theta) -> str:
    """θ 快照摘要(8 hex),供 Explain/duel_corpus/viz 使用,非加密用途。"""
    import hashlib

    key = f"{theta.d_sw:.6f}|{theta.d_rp:.6f}|{theta.d_ex:.6f}|{theta.gamma:.6f}"
    return hashlib.blake2b(key.encode()).hexdigest()[:8]


# --- v0.1 reason 字符串 -> taxonomy 分类(T-X1 穷举测试的权威表) ------------

# 逐条抄自 core/arbiter.py 的字面量(冻结内核,§4.2/§4.3/§4.4);
# 值 = (category, 人类可读摘要)。category 供 viz 分组着色使用。
REASON_TAXONOMY: dict[str, tuple[str, str]] = {
    "guard_silenced_or_unbound": ("guard", "P0:未绑定/禁用/静默"),
    "guard_self": ("guard", "防自仲裁"),
    "guard_no_plain": ("guard", "链空或无 Plain 文本"),
    "guard_non_plain": ("guard", "链含非 Plain 组件(issue26)"),
    "guard_engine_guard": ("guard", "Surface 缺失或引擎风控"),
    "guard_min_gap": ("guard", "不应期"),
    "narrow_withdraw_soft": ("narrow", "收窄:withdraw 一律 REPLACE 轻声"),
    "withdraw_swallow": ("decision", "withdraw:高压 SWALLOW"),
    "withdraw_replace_heavy": ("decision", "withdraw:REPLACE 重声"),
    "withdraw_replace_soft": ("decision", "withdraw:REPLACE 轻声"),
    "narrow_hold_swallow": ("narrow", "收窄:hold 低表达降 PASS"),
    "hold_swallow": ("decision", "hold:纯沉默"),
    "narrow_hold": ("narrow", "收窄:hold 降 PASS"),
    "hold_trim": ("decision", "hold:裁剪尾句(哈希币)"),
    "hold_replace": ("decision", "hold:REPLACE 迟疑(哈希币)"),
    "guard_freeze": ("decision", "guard 动作:冻结当日"),
    "recover_pass": ("decision", "recover:短草稿放行"),
    "recover_trim": ("decision", "recover:裁前两句"),
    "recover_trim_gate": ("decision", "recover:调制闸降级"),
    "reach_out": ("decision", "reach_out:转交幕 III"),
    "explore_exempt": ("decision", "explore:豁免裁剪"),
    "express_trim": ("decision", "express:裁至首句"),
    "express_pass": ("decision", "express:放行"),
    "narrow_express": ("narrow", "收窄:express 降 PASS"),
    "mod_gate_downgrade": ("gate", "调制闸降级(消息粒度哈希)"),
}


def taxonomy_for_reason(reason: str) -> tuple[str, str]:
    """reason 字符串(可能带 ``:action`` 后缀)-> (category, 摘要)。

    调制闸 downgrade 的 reason 形如 ``mod_gate_downgrade:withdraw``,
    unknown action 的形如 ``unknown_action:xxx``——前缀匹配兜底。
    """
    if reason in REASON_TAXONOMY:
        return REASON_TAXONOMY[reason]
    prefix = reason.split(":", 1)[0]
    if prefix in REASON_TAXONOMY:
        return REASON_TAXONOMY[prefix]
    if prefix == "unknown_action":
        return ("decision", "未识别 action(向前兼容)")
    if prefix.startswith("narrow_collapse"):
        return ("narrow", "非 Table 策略:收窄折叠为 PASS")
    if prefix.startswith("conservative_stale_abstain"):
        return ("abstain", "证据陈旧弃权")
    if prefix.startswith("conservative_budget_exhausted"):
        return ("budget", "当日介入预算耗尽")
    if prefix.startswith("smooth_"):
        return ("decision", "Smooth 连续得分判定")
    return ("unknown", f"未登记 reason:{reason}")
