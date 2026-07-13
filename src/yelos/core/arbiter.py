"""幕 II 话语权仲裁:6 条前置守卫 + 7 枚举决策表 + 有限性调制。

蓝图 §4 / YELOS_SPEC §7。纯逻辑,零 astrbot / 零 sylanne_core / 零 random。
arbiter 不产最终文本(trimmed 除外,它是纯文本操作);措辞由 main 拿
occasion 问 primal。措辞与执行分离,本模块是确定性纯函数。

确定性契约(蓝图 §2.1):
- 调制闸键 = f"{sid}|{day_key}|mod|{action}|{blake2b(draft)[:8]}",消息粒度
  (含草稿哈希,红队 F2:日粒度会退化成按日抽签)。
- hold 二选一键 = f"{sid}|{day_key}|hold"(日粒度,SPEC 明文同日同句)。
全部 sha256 取首字节;无 random。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from . import sget, split_sentences

# --- §4.1 输入/输出 -----------------------------------------------------


@dataclass(frozen=True)
class ArbiterInput:
    session_id: str
    day_key: str
    draft: str  # 草稿链里全部 Plain 拼接
    surface: dict | None  # 缓存的最新 Surface(可 None)
    p: float  # 可塑性预算
    bound: bool
    enabled: bool
    silenced: bool
    is_self: bool  # event extra yelos_l0
    has_plain: bool
    has_non_plain: bool  # 链含 At/Image/Record/File/Node 等非 Plain 组件(issue26)
    now_ts: float
    last_intervention_ts: float
    min_gap_seconds: int
    # 见文末疑义:§4.3 决策表所需,§4.1 未列,默认对齐 config
    express_trim_enabled: bool = True


@dataclass(frozen=True)
class Verdict:
    kind: str  # "PASS" | "SWALLOW" | "REPLACE" | "TRIM"
    occasion: str | None = None  # REPLACE 用词组;TRIM 时为尾缀组(仅 hold)
    trimmed: str | None = None  # TRIM 后的正文(不含尾缀)
    delayed_occasion: str | None = None  # SWALLOW 后 90s 补 withdraw_heavy
    delay_seconds: int = 0
    freeze_today: bool = False  # guard:冻结当日主动/梦语/撤回
    reach_out_signal: bool = False  # 转交幕 III
    allow_recover_primal: bool = False  # 当日一条延迟 recover 原语(≤1/日)
    high_intensity: bool = False  # 重咽:pressure≥0.75 的 SWALLOW(幕 V 记账)
    reason: str = ""  # 记账/日志用,非用户可见


# --- 确定性哈希族(§2.1)-----------------------------------------------


def _gate_allows(
    session_id: str, day_key: str, action: str, draft: str, p: float
) -> bool:
    """有限性调制闸(§2.1 / §4.4):消息粒度,含草稿哈希。

    byte/255 < P/0.5 才放行;调用方仅在 P<0.5 时使用本闸。
    """
    draft_h = hashlib.blake2b(draft.encode()).hexdigest()[:8]
    key = f"{session_id}|{day_key}|mod|{action}|{draft_h}"
    b = hashlib.sha256(key.encode()).digest()[0]
    return b / 255 < p / 0.5


def _gate_or_pass(
    verdict: Verdict, session_id: str, day_key: str, action: str, draft: str, p: float
) -> Verdict:
    """P<0.5 时把 TRIM/REPLACE 过调制闸,不放行则降级为纯 PASS。

    SWALLOW 不经此(它走阈值下调,§4.4)。recover 的 TRIM 需保留原语
    旗标,自行处理,不用本 helper。
    """
    if p >= 0.5:
        return verdict
    if _gate_allows(session_id, day_key, action, draft, p):
        return verdict
    return Verdict("PASS", reason=f"mod_gate_downgrade:{action}")


# --- 仲裁纯函数(§4.2 守卫 → §4.3 决策表 → §4.4 调制)-------------


def arbitrate(inp: ArbiterInput) -> Verdict:
    """幕 II 仲裁:命中守卫即 PASS;否则按 action 走决策表 + 有限性调制。"""
    # §4.2 前置守卫(命中即 PASS,顺序固定)
    # 1 静默是 P0,永远第一梯队
    if not inp.bound or not inp.enabled or inp.silenced:
        return Verdict("PASS", reason="guard_silenced_or_unbound")
    # 2 防自仲裁
    if inp.is_self:
        return Verdict("PASS", reason="guard_self")
    # 3 链空或无 Plain 文本
    if not inp.has_plain or not inp.draft.strip():
        return Verdict("PASS", reason="guard_no_plain")
    # 4 链含非 Plain 组件即不接管(issue26:防吞掉多模态)
    if inp.has_non_plain:
        return Verdict("PASS", reason="guard_non_plain")
    # 5 Surface 缺失或引擎风控 → 放行原文,不叠加
    if inp.surface is None or sget(inp.surface, "guard.allowed", True) is False:
        return Verdict("PASS", reason="guard_engine_guard")
    # 6 不应期
    if inp.now_ts - inp.last_intervention_ts < inp.min_gap_seconds:
        return Verdict("PASS", reason="guard_min_gap")

    # §4.3 决策表输入(防御式取值,保守默认 = 不触发干预)
    surface = inp.surface
    action = str(sget(surface, "decision.action", "hold"))
    pressure = sget(surface, "state.boundary.pressure", 0.0)
    expr = sget(surface, "state.needs.expression", 0.0)
    p = inp.p
    sid = inp.session_id
    day_key = inp.day_key
    draft = inp.draft

    # swallow_th:P≥0.5 → 0.75;P<0.5 → 0.70(§4.3 阈值下调 0.05)
    swallow_th = 0.75 if p >= 0.5 else 0.70
    # 高强度记账判据与 swallow_th 解耦,固定 0.75(SPEC §9.2 / 红队 F3b)
    # P≤0.15(静止前期):决策收窄(§4.4)
    narrow = p <= 0.15

    if action == "withdraw":
        if narrow:
            # 三行全部改 REPLACE withdraw_soft(仍过调制闸)
            v = Verdict(
                "REPLACE", occasion="withdraw_soft", reason="narrow_withdraw_soft"
            )
            return _gate_or_pass(v, sid, day_key, action, draft, p)
        if pressure >= swallow_th:
            # SWALLOW 不过闸;high_intensity 固定 pressure≥0.75(与 th 解耦)
            return Verdict(
                "SWALLOW",
                delayed_occasion="withdraw_heavy",
                delay_seconds=90,
                high_intensity=pressure >= 0.75,
                reason="withdraw_swallow",
            )
        if pressure >= 0.55:
            v = Verdict(
                "REPLACE", occasion="withdraw_heavy", reason="withdraw_replace_heavy"
            )
        else:
            v = Verdict(
                "REPLACE", occasion="withdraw_soft", reason="withdraw_replace_soft"
            )
        return _gate_or_pass(v, sid, day_key, action, draft, p)

    if action == "hold":
        if expr < 0.3:
            if narrow:
                return Verdict("PASS", reason="narrow_hold_swallow")
            return Verdict("SWALLOW", reason="hold_swallow")  # 纯沉默,无补句
        if narrow:
            # 收窄:hold 的 TRIM/REPLACE 均降级 PASS(SPEC §7.3)
            return Verdict("PASS", reason="narrow_hold")
        # 哈希二选一(日粒度键):0=TRIM、1=REPLACE hold_hesitant
        b = hashlib.sha256(f"{sid}|{day_key}|hold".encode()).digest()[0]
        if b % 2 == 0:
            sentences = split_sentences(draft)
            first = sentences[0] if sentences else draft
            v = Verdict("TRIM", occasion="trim_tail", trimmed=first, reason="hold_trim")
        else:
            v = Verdict("REPLACE", occasion="hold_hesitant", reason="hold_replace")
        return _gate_or_pass(v, sid, day_key, action, draft, p)

    if action == "guard":
        # 她在防御,不动她的话;freeze_today 防御性副作用,收窄下仍保留
        return Verdict("PASS", freeze_today=True, reason="guard_freeze")

    if action == "recover":
        sentences = split_sentences(draft)
        # 收窄或草稿≤3 句 → PASS;两分支均 allow_recover_primal=True
        if narrow or len(sentences) <= 3:
            return Verdict("PASS", allow_recover_primal=True, reason="recover_pass")
        v = Verdict(
            "TRIM",
            trimmed="".join(sentences[:2]),
            allow_recover_primal=True,
            reason="recover_trim",
        )
        # TRIM 过调制闸;降级也保留 recover 原语旗标(≤1/日)
        if p < 0.5 and not _gate_allows(sid, day_key, action, draft, p):
            return Verdict(
                "PASS", allow_recover_primal=True, reason="recover_trim_gate"
            )
        return v

    if action == "reach_out":
        # PASS;该信号转交幕 III 作主动触发条件
        return Verdict("PASS", reach_out_signal=True, reason="reach_out")

    if action == "explore":
        # PASS,且 express_trim 对其禁用(不截断她的好奇)
        return Verdict("PASS", reason="explore_exempt")

    if action == "express":
        sentences = split_sentences(draft)
        long_draft = len(sentences) > 3
        if inp.express_trim_enabled and expr >= 0.7 and pressure <= 0.3 and long_draft:
            if narrow:
                return Verdict("PASS", reason="narrow_express")
            first = sentences[0] if sentences else draft
            # TRIM 至首句,无尾缀
            v = Verdict("TRIM", trimmed=first, reason="express_trim")
            return _gate_or_pass(v, sid, day_key, action, draft, p)
        return Verdict("PASS", reason="express_pass")

    # 未识别 action:真身 action 是 str,向前兼容 3.0(§15.9)
    return Verdict("PASS", reason=f"unknown_action:{action}")
