"""唯一正典算法:表驱动解释器(A4)。

``evaluate(surface, mode, concern_active, profile, continuity, lang)`` 是
guidance 包里唯一真正"跑规则"的函数;``__init__.py`` 里冻结的 v0.1 逐字
实现(chat/companion 默认路径)是独立的第二实现,两者的输出一致性由
``tests/guidance/test_zero_drift_golden.py``(T8)做差分校验——这正是本模块
唯一容许的"两套实现"(A4:决策树预编译属维四技术;这里则是深化前后两代
实现的零漂移校验,同一性质,不同来源)。

[强制] 纯逻辑:零 fastmcp / 零 sylanne_core / 零 random / 零 time / 零 I/O;
不 import yelos.memory —— continuity 由调用方以结构化对象或 None 传入
(X4,INTEGRATION_SPEC §3.4 路线 A)。
"""

from __future__ import annotations

from typing import Any

from ...core import ordinal7, sget
from ..audit import make_trace
from ..conflict.lattice import join_length, join_pace, join_respect_pause, join_tone
from ..model import CompositeTrigger, GuidanceResult, HintTrace, Trigger
from ..phrasebook import get_phrase
from ..profiles import profile_keeps_hint_at_dropped_priority, resolve_profile
from ..rules import DEFAULT_RULESET

# eq 触发的 surface 字段各自的保守默认值(缺字段时的行为锚点,与 v0.1 一致)。
_EQ_DEFAULTS: dict[str, str] = {
    "decision.action": "hold",
    "dynamics.relational_time.phase": "active",
}


def _num(surface: dict | None, path: str) -> float | None:
    """防御式取数值字段:缺失/非数值/布尔一律回 None(保守默认,v0.1 语义)。"""
    v = sget(surface, path, None)
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _read(
    trigger: Trigger,
    surface: dict | None,
    concern_active: bool,
    continuity: Any,
) -> Any:
    if trigger.source == "mode_input":
        if trigger.path == "concern_active":
            return bool(concern_active)
        if trigger.path == "continuity.reunion":
            if continuity is None:
                return False
            return bool(getattr(continuity, "reunion", False))
        return None  # 未登记的 mode_input path:保守不触发
    # source == "surface"
    if trigger.op == "eq":
        default = _EQ_DEFAULTS.get(trigger.path, "")
        return str(sget(surface, trigger.path, default))
    if trigger.op == "is_false":
        return sget(surface, trigger.path, True)
    if trigger.op == "flag":
        return bool(sget(surface, trigger.path, False))
    # ge / le:数值防御式取值
    return _num(surface, trigger.path)


def _fires(
    trigger: Trigger | CompositeTrigger,
    surface: dict | None,
    concern_active: bool,
    continuity: Any,
) -> bool:
    if isinstance(trigger, CompositeTrigger):
        return all(
            _fires(t, surface, concern_active, continuity) for t in trigger.all_of
        )
    value = _read(trigger, surface, concern_active, continuity)
    if trigger.op == "eq":
        return value == trigger.value
    if trigger.op == "is_false":
        return value is False
    if trigger.op == "flag":
        return bool(value)
    if value is None:  # ge/le 缺字段/非数值 → 保守不触发
        return False
    if trigger.op == "ge":
        return value >= float(trigger.value)  # type: ignore[arg-type]
    if trigger.op == "le":
        return value <= float(trigger.value)  # type: ignore[arg-type]
    return False


def _trigger_leaf(trigger: Trigger | CompositeTrigger) -> Trigger:
    """取复合触发的代表叶子(用于 audit path/op/threshold 展示,§3.3 溯源)。"""
    if isinstance(trigger, CompositeTrigger):
        return trigger.all_of[-1]
    return trigger


def evaluate(
    surface: dict | None,
    mode: str,
    concern_active: bool = False,
    *,
    profile: str = "chat",
    continuity: Any = None,
    lang: str = "zh",
) -> GuidanceResult:
    """Surface → :class:`GuidanceResult`(guidance dict + 全量溯源)。

    参数与语义见蓝图 §3.5 / §4。``continuity`` 是 X4 增量:鸭子类型读取
    ``continuity.reunion``,不 import memory 的 ``ContinuityFlags`` 类型。
    """
    eff = resolve_profile(profile, mode)

    tones: list[str] = []
    lengths: list[str] = []
    paces: list[str] = []
    respect_flags: list[bool] = []

    # 候选:(priority, rule_index, hint_key, trace) —— 尚未套用 profile/steward
    # 抑制,全部候选进 audit(A3),抑制原因逐条标注。
    candidates: list[tuple[int, int, str, HintTrace]] = []
    exclusive_hit: set[str] = set()

    for idx, rule in enumerate(DEFAULT_RULESET):
        if rule.exclusive_group is not None and rule.exclusive_group in exclusive_hit:
            continue
        if not _fires(rule.trigger, surface, concern_active, continuity):
            continue
        if rule.exclusive_group is not None:
            exclusive_hit.add(rule.exclusive_group)

        eff_contrib = rule.effect
        if eff_contrib.tone is not None:
            tones.append(eff_contrib.tone)
        if eff_contrib.length is not None:
            if not (eff_contrib.length == "short" and eff.neutralize_short):
                lengths.append(eff_contrib.length)
        if eff_contrib.pace is not None and not eff.neutralize_pace:
            paces.append(eff_contrib.pace)
        if eff_contrib.respect_pause:
            respect_flags.append(True)

        if rule.hint_key is None:
            continue

        leaf = _trigger_leaf(rule.trigger)
        observed = _read(leaf, surface, concern_active, continuity)
        path = (
            "concern_active"
            if leaf.source == "mode_input" and leaf.path == "concern_active"
            else leaf.path
        )
        trace = make_trace(
            hint_key=rule.hint_key,
            rule_id=rule.rule_id,
            path=path,
            op=leaf.op,
            threshold=leaf.value,
            observed=observed,
        )
        candidates.append((rule.priority, idx, rule.hint_key, trace))

    # --- steward 截答/给空间类抑制(minor⑧):只影响 hint 候选,不影响效果 ----
    stage1: list[tuple[int, int, str, HintTrace]] = []
    all_traces: list[HintTrace] = []
    for prio, idx, hint_key, trace in candidates:
        rule = DEFAULT_RULESET[idx]
        if eff.drop_truncation_hints and rule.truncation:
            all_traces.append(
                HintTrace(**{**trace.__dict__, "suppressed_by": "steward"})
            )
            continue
        stage1.append((prio, idx, hint_key, trace))

    # --- profile drop_priorities(coding 砍温度类,CAUTION 例外) --------------
    stage2: list[tuple[int, int, str, HintTrace]] = []
    for prio, idx, hint_key, trace in stage1:
        if prio in eff.drop_priorities and not profile_keeps_hint_at_dropped_priority(
            eff.name, hint_key
        ):
            all_traces.append(
                HintTrace(**{**trace.__dict__, "suppressed_by": "profile_drop"})
            )
            continue
        stage2.append((prio, idx, hint_key, trace))

    # --- 稳定排序 (priority, rule_index) → 去重保首现 → 截 hint_cap --------
    stage2.sort(key=lambda c: (c[0], c[1]))
    hints: list[str] = []
    seen: set[str] = set()
    for prio, idx, hint_key, trace in stage2:
        if hint_key in seen:
            all_traces.append(HintTrace(**{**trace.__dict__, "suppressed_by": "dedup"}))
            continue
        if len(hints) >= eff.hint_cap:
            all_traces.append(HintTrace(**{**trace.__dict__, "suppressed_by": "cap"}))
            continue
        seen.add(hint_key)
        hints.append(get_phrase(hint_key, lang))
        all_traces.append(trace)

    tone = join_tone(tones)
    length = join_length(lengths)
    pace = join_pace(paces)
    respect_pause = join_respect_pause(respect_flags)

    warmth_raw = sget(surface, "state.valence.warmth", 0.0) or 0.0
    warmth_label = ordinal7(float(warmth_raw))

    guidance: dict[str, Any] = {
        "tone": tone,
        "length": length,
        "pace": pace,
        "warmth_label": warmth_label,
        "hints": hints,
        "respect_pause": respect_pause,
    }
    if eff.voice_fields:
        guidance["speech_rate"] = (
            "slow" if (length == "short" or tone in ("brief", "gentle")) else "normal"
        )
        guidance["pause_before_reply"] = pace == "give_space"

    return GuidanceResult(guidance=guidance, audit=tuple(all_traces))


__all__ = ["evaluate"]
