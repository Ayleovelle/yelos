"""guidance:Surface → 行为建议的确定性编译器(蓝图 G:/Yelos/_build/modules/guidance_BLUEPRINT.md)。

包结构说明(与蓝图 §2 的关键差异,记录在案,不原地改史):
    v0.1 单文件 ``guidance.py``(306 行,两个纯函数)升级为本包。蓝图 §2 原计
    划让本文件"无逻辑,纯重导出",逐字实现冻在 ``_v01_compat.py``。**实测发
    现该计划与既有兼容闸冲突**:``tests/test_guidance_mcp.py`` 用
    ``inspect.getfile(import yelos.guidance as guidance_module)`` 取源码做
    AST 扫描(锁 ``add_hint`` 只能引用 ``_HINT_*`` 白名单常量);对常规包而
    言 ``inspect.getfile(pkg)`` 返回的是 ``__init__.py`` 本身,而不是任何子
    模块——如果 ``__init__.py`` 真的"无逻辑",AST 扫描会在这份文件里找不到
    任何 ``add_hint`` 调用,直接判定"guidance.py 被改动/迁移"而失败,炸穿
    I7(测试文件一行不许改)。
    **裁定**:v0.1 的逐字实现(``_legacy_build_guidance`` /
    ``_legacy_build_compact_surface``,含全部 ``_HINT_*`` 常量与
    ``add_hint`` 闭包)物理留在本文件——它是 ``profile="chat"`` 默认路径的
    真实运行代码,不是摆着不用的僵尸文本;深化后的规则对象引擎
    (``model``/``rules``/``conflict``/``phrasebook``/``profiles``/
    ``compiler.interpreter``)作为独立第二实现,承担 ``profile != "chat"``
    或 ``continuity`` 非空的路径,两者的一致性由零漂移金测
    (``tests/guidance/test_zero_drift_golden.py``)做差分校验。
    ``_v01_compat.py`` 改为“反向”角色:从本文件重导出这两个函数,给需要
    稳定 ``yelos.guidance._v01_compat`` 导入路径的消费者(差分测试等)用。

[强制] 本文件与全包纯逻辑:零 fastmcp / 零 sylanne_core import、零
random、零 time/datetime、零持久化、零 I/O。Surface/模式/元信息一律入参
传入。所有用户可见字符串取自封闭白名单(本文件的 ``_HINT_*`` 或
``phrasebook`` 句库),不拼接自由文本、不提具体话题、不对用户下诊断。
"""

from __future__ import annotations

from typing import Any

from ..core import ordinal7, sget
from .compiler.interpreter import evaluate
from .model import Rule
from .rules import DEFAULT_RULESET

# --- 白名单句式(封闭集,逐字照 §4.2 表;v0.1 原样收编,零漂移) --------------
_HINT_WITHDRAW = "她想收一收，别追问，给点空间。"
_HINT_RECOVER = "她在缓，温和点，别施压。"
_HINT_REACH_OUT = "她像是想靠近，可以主动搭句话。"
_HINT_EXPLORE = "她有点好奇，可以聊点新的。"
_HINT_GUARD_DECISION = "她在守边界，简短些，别越线。"
_HINT_EXPRESS = "她有话想说，给她展开的空间。"
_HINT_STRAIN = "节律紧，回短一点。"
_HINT_FATIGUE = "她累了，别拖长。"
_HINT_WARM_HIGH = "心情不错，语气可以活泼些。"
_HINT_WARM_LOW = "情绪低，语气温柔些。"
_HINT_DAMAGE = "她受过些伤，整体软一点。"
_HINT_AUTONOMY = "自主权紧，别命令式，给选择。"
_HINT_QUIET = "她想静一静，少说点。"
_HINT_EXPRESSION = "她想表达，别打断。"
_HINT_DORMANT = "很久没联系了，重新开口温和些。"
_HINT_CAUTION = "她不太笃定，回复别下绝对结论。"
_HINT_CONCERN = "她像是有点担心你，可以关心一句。"
_HINT_GUARD_BLOCKED = "她在克制，别硬推这个方向。"

_P_DEFENSE = 0
_P_CONCERN = 1
_P_FATIGUE = 2
_P_TEMP = 3

_TONE_RANK: dict[str, int] = {
    "brief": 4,
    "gentle": 3,
    "neutral": 2,
    "direct": 1,
    "warm": 0,
}


def _num(surface: dict | None, path: str) -> float | None:
    v = sget(surface, path, None)
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _legacy_build_guidance(
    surface: dict | None,
    mode: str,
    concern_active: bool = False,
) -> dict:
    """v0.1 逐字实现(byte-identical,I3)。``profile="chat"`` 默认路径消费。"""
    steward = mode == "steward"

    action = str(sget(surface, "decision.action", "hold"))
    strain = _num(surface, "state.rhythm.strain")
    fatigue = _num(surface, "state.responsiveness.fatigue")
    warmth = _num(surface, "state.valence.warmth")
    damage = _num(surface, "state.damage.accumulated")
    autonomy = _num(surface, "state.boundary.autonomy")
    paused = bool(sget(surface, "state.boundary.paused", False))
    quiet = _num(surface, "state.needs.quiet")
    expression = _num(surface, "state.needs.expression")
    phase = str(sget(surface, "dynamics.relational_time.phase", "active"))
    caution = _num(surface, "dynamics.uncertainty.claim_caution")
    guard_allowed = sget(surface, "guard.allowed", True)

    tones: list[str] = []
    lengths: list[str] = []
    paces: list[str] = []
    respect_pause = False
    hint_items: list[tuple[int, int, str, bool]] = []
    _order = [0]

    def add_hint(priority: int, text: str, *, truncation: bool) -> None:
        hint_items.append((priority, _order[0], text, truncation))
        _order[0] += 1

    if action == "withdraw":
        tones.append("gentle")
        lengths.append("short")
        paces.append("give_space")
        add_hint(_P_FATIGUE, _HINT_WITHDRAW, truncation=True)
    elif action == "recover":
        tones.append("warm")
        add_hint(_P_TEMP, _HINT_RECOVER, truncation=False)
    elif action == "reach_out":
        tones.append("warm")
        add_hint(_P_TEMP, _HINT_REACH_OUT, truncation=False)
    elif action == "explore":
        tones.append("neutral")
        paces.append("relaxed")
        add_hint(_P_TEMP, _HINT_EXPLORE, truncation=False)
    elif action == "guard":
        tones.append("brief")
        lengths.append("short")
        add_hint(_P_DEFENSE, _HINT_GUARD_DECISION, truncation=True)
    elif action == "express" and warmth is not None and warmth >= 0.7:
        tones.append("warm")
        lengths.append("long")
        add_hint(_P_TEMP, _HINT_EXPRESS, truncation=False)
    elif action == "hold":
        tones.append("neutral")

    if strain is not None and strain >= 0.6:
        lengths.append("short")
        paces.append("give_space")
        add_hint(_P_FATIGUE, _HINT_STRAIN, truncation=True)
    if fatigue is not None and fatigue >= 0.7:
        lengths.append("short")
        add_hint(_P_FATIGUE, _HINT_FATIGUE, truncation=True)
    if warmth is not None and warmth >= 0.7:
        tones.append("warm")
        add_hint(_P_TEMP, _HINT_WARM_HIGH, truncation=False)
    if warmth is not None and warmth <= 0.3:
        tones.append("gentle")
        add_hint(_P_TEMP, _HINT_WARM_LOW, truncation=False)
    if damage is not None and damage >= 0.3:
        tones.append("gentle")
        add_hint(_P_TEMP, _HINT_DAMAGE, truncation=False)
    if (autonomy is not None and autonomy <= 0.3) or paused:
        respect_pause = True
        tones.append("brief")
        add_hint(_P_DEFENSE, _HINT_AUTONOMY, truncation=False)
    if quiet is not None and quiet >= 0.6:
        lengths.append("short")
        paces.append("give_space")
        add_hint(_P_FATIGUE, _HINT_QUIET, truncation=True)
    if expression is not None and expression >= 0.7:
        lengths.append("long")
        add_hint(_P_TEMP, _HINT_EXPRESSION, truncation=False)
    if phase == "dormant":
        tones.append("gentle")
        add_hint(_P_TEMP, _HINT_DORMANT, truncation=False)
    if caution is not None and caution >= 0.6:
        add_hint(_P_TEMP, _HINT_CAUTION, truncation=False)
    if concern_active:
        tones.append("gentle")
        add_hint(_P_CONCERN, _HINT_CONCERN, truncation=False)
    if guard_allowed is False:
        respect_pause = True
        add_hint(_P_DEFENSE, _HINT_GUARD_BLOCKED, truncation=False)

    if tones:
        tone = max(tones, key=lambda t: _TONE_RANK.get(t, _TONE_RANK["neutral"]))
    else:
        tone = "neutral"

    if "long" in lengths and (steward or "short" not in lengths):
        length = "long"
    elif not steward and "short" in lengths:
        length = "short"
    else:
        length = "medium"

    if steward:
        pace = "steady"
    elif "give_space" in paces:
        pace = "give_space"
    elif "relaxed" in paces:
        pace = "relaxed"
    else:
        pace = "steady"

    items = hint_items
    if steward:
        items = [it for it in items if not it[3]]
    items = sorted(items, key=lambda it: (it[0], it[1]))
    hints: list[str] = []
    seen: set[str] = set()
    for _prio, _idx, text, _trunc in items:
        if text in seen:
            continue
        seen.add(text)
        hints.append(text)
        if len(hints) >= 3:
            break

    warmth_raw = sget(surface, "state.valence.warmth", 0.0) or 0.0
    warmth_label = ordinal7(float(warmth_raw))

    return {
        "tone": tone,
        "length": length,
        "pace": pace,
        "warmth_label": warmth_label,
        "hints": hints,
        "respect_pause": respect_pause,
    }


def _legacy_build_compact_surface(
    surface: dict | None,
    *,
    session_id: str,
    name: str | None,
    bound: bool,
    mode: str,
    sealed: bool,
    silenced: bool,
    epoch: str | None,
    days_lived: int | None,
    self_words_today: int,
    proxy_sentences_today: int,
    swallowed_today: int,
    pending: int,
    concern_active: bool = False,
) -> dict:
    pad_label = sget(surface, "state.pad.label", None) or sget(
        surface, "pad.label", "neutral"
    )
    decision_action = str(sget(surface, "decision.action", "hold"))
    warmth = ordinal7(float(sget(surface, "state.valence.warmth", 0.0) or 0.0))
    pressure = ordinal7(float(sget(surface, "state.boundary.pressure", 0.0) or 0.0))
    contact = ordinal7(float(sget(surface, "state.needs.contact", 0.0) or 0.0))
    quiet = ordinal7(float(sget(surface, "state.needs.quiet", 0.0) or 0.0))
    phase = str(sget(surface, "dynamics.relational_time.phase", "active"))

    guidance = _legacy_build_guidance(surface, mode, concern_active)

    return {
        "session_id": session_id,
        "name": name,
        "bound": bound,
        "mode": mode,
        "sealed": sealed,
        "silenced": silenced,
        "pad_label": pad_label,
        "decision_action": decision_action,
        "warmth": warmth,
        "pressure": pressure,
        "contact": contact,
        "quiet": quiet,
        "phase": phase,
        "epoch": epoch,
        "days_lived": days_lived,
        "self_words_today": self_words_today,
        "proxy_sentences_today": proxy_sentences_today,
        "swallowed_today": swallowed_today,
        "pending": pending,
        "guidance": guidance,
    }


# --- 公开门面(I1/I2:签名与返回形状不变;profile/continuity/lang 为新增 ----
# keyword-only 参数,带默认值,现有调用零改动) -------------------------------


def build_guidance(
    surface: dict | None,
    mode: str,
    concern_active: bool = False,
    *,
    profile: str = "chat",
    continuity: Any = None,
    lang: str = "zh",
) -> dict:
    """Surface → 行为提示(白名单、确定性、禁诊断)。

    ``profile="chat"``(默认)且未传 ``continuity`` 时,严格走 v0.1 逐字实现
    (I3:零语义漂移)。传入非默认 ``profile`` 或非空 ``continuity`` 时,走
    深化后的规则对象解释器(:func:`evaluate`);后者对 ``profile="chat"`` /
    ``continuity=None`` 的输出与前者逐字节一致(T8 零漂移金测校验)。

    ``continuity``:X4 增量(INTEGRATION_SPEC §3.4 路线 A)。承接
    ``memory.facade.continuity_flags(...)`` 的 ``ContinuityFlags``(鸭子类型
    读取 ``.reunion``,不 import memory)。``None`` 时行为与 v0.1 完全一致。
    """
    if profile == "chat" and continuity is None:
        return _legacy_build_guidance(surface, mode, concern_active)
    return evaluate(
        surface,
        mode,
        concern_active,
        profile=profile,
        continuity=continuity,
        lang=lang,
    ).guidance


def build_compact_surface(
    surface: dict | None,
    *,
    session_id: str,
    name: str | None,
    bound: bool,
    mode: str,
    sealed: bool,
    silenced: bool,
    epoch: str | None,
    days_lived: int | None,
    self_words_today: int,
    proxy_sentences_today: int,
    swallowed_today: int,
    pending: int,
    concern_active: bool = False,
    profile: str = "chat",
    continuity: Any = None,
    lang: str = "zh",
) -> dict:
    """Surface + session 层元信息 → CompactSurface(§4.3),内联 guidance。

    ``profile``/``continuity``/``lang`` 同 :func:`build_guidance`,原样透传。
    """
    if profile == "chat" and continuity is None:
        return _legacy_build_compact_surface(
            surface,
            session_id=session_id,
            name=name,
            bound=bound,
            mode=mode,
            sealed=sealed,
            silenced=silenced,
            epoch=epoch,
            days_lived=days_lived,
            self_words_today=self_words_today,
            proxy_sentences_today=proxy_sentences_today,
            swallowed_today=swallowed_today,
            pending=pending,
            concern_active=concern_active,
        )

    pad_label = sget(surface, "state.pad.label", None) or sget(
        surface, "pad.label", "neutral"
    )
    decision_action = str(sget(surface, "decision.action", "hold"))
    warmth = ordinal7(float(sget(surface, "state.valence.warmth", 0.0) or 0.0))
    pressure = ordinal7(float(sget(surface, "state.boundary.pressure", 0.0) or 0.0))
    contact = ordinal7(float(sget(surface, "state.needs.contact", 0.0) or 0.0))
    quiet = ordinal7(float(sget(surface, "state.needs.quiet", 0.0) or 0.0))
    phase = str(sget(surface, "dynamics.relational_time.phase", "active"))

    guidance = build_guidance(
        surface, mode, concern_active, profile=profile, continuity=continuity, lang=lang
    )

    return {
        "session_id": session_id,
        "name": name,
        "bound": bound,
        "mode": mode,
        "sealed": sealed,
        "silenced": silenced,
        "pad_label": pad_label,
        "decision_action": decision_action,
        "warmth": warmth,
        "pressure": pressure,
        "contact": contact,
        "quiet": quiet,
        "phase": phase,
        "epoch": epoch,
        "days_lived": days_lived,
        "self_words_today": self_words_today,
        "proxy_sentences_today": proxy_sentences_today,
        "swallowed_today": swallowed_today,
        "pending": pending,
        "guidance": guidance,
    }


def ruleset_export() -> dict:
    """WebUI 契约用:规则集 JSON schema 化(蓝图 §3.2/§5.2)。"""

    def _trigger_dict(t: Rule) -> dict:
        trig = t.trigger
        if hasattr(trig, "all_of"):
            return {
                "kind": "all_of",
                "clauses": [
                    {"path": c.path, "op": c.op, "value": c.value, "source": c.source}
                    for c in trig.all_of
                ],
            }
        return {
            "path": trig.path,
            "op": trig.op,
            "value": trig.value,
            "source": trig.source,
        }

    return {
        "rules": [
            {
                "rule_id": r.rule_id,
                "trigger": _trigger_dict(r),
                "effect": {
                    "tone": r.effect.tone,
                    "length": r.effect.length,
                    "pace": r.effect.pace,
                    "respect_pause": r.effect.respect_pause,
                },
                "hint_key": r.hint_key,
                "priority": r.priority,
                "truncation": r.truncation,
                "exclusive_group": r.exclusive_group,
            }
            for r in DEFAULT_RULESET
        ],
    }


__all__ = [
    "build_guidance",
    "build_compact_surface",
    "evaluate",
    "ruleset_export",
]
