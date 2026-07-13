"""MCP 层测试:guidance 翻译层(蓝图 §8.2 test_guidance.py / §4.2)。

锁什么:
1. 白名单纪律(AST + 运行时双重):`build_guidance` 里"这句话要不要出给
   agent"的每一处 `add_hint(...)` 调用,第二个位置参数必须是引用模块级
   `_HINT_*` 常量的 `Name`,不能是内联字符串字面量——防止未来有人绕过白名单
   评审、直接塞一句临时诊断文案进去。运行时再断言 `build_guidance` 实际
   返回的每条 hint 都落在 `_HINT_*` 常量集合里、且不含第二人称"你"的诊断
   句式(§4.2 纪律 1/§6.3 输出面纪律)。
2. 冲突优先级(§4.2 表末尾):主权/防御类 > 疲劳/静默类 > 温度类;tone 冲突
   取更保守(gentle/brief 胜 warm/direct)。
3. steward 门控:length/pace 的截短/给空间档在 steward 下恒中性
   (medium/steady),只发 tone/warmth 语气类 + expression 高时的 length=long
   (红队 minor⑧);companion 下截短/给空间正常生效。
4. concern 唯一可见输出 = concern 词典组的白名单短句(幕 IV 输出面纪律)。
5. 确定性:同一 Surface 输入必产同一输出(不掺 random/时间)。

本文件是纯 `yelos.guidance` 单测,不经 server.py/session.py,不受
fastmcp/mcp SDK 是否安装影响。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import yelos.guidance as guidance_module
from yelos.guidance import build_compact_surface, build_guidance

GUIDANCE_SRC = Path(inspect.getfile(guidance_module))

_ALL_HINT_TEXTS = {
    getattr(guidance_module, name)
    for name in dir(guidance_module)
    if name.startswith("_HINT_")
}


# =========================================================================
# 1. AST 白名单锁:add_hint(...) 的文本参数必须引用 _HINT_* 常量
# =========================================================================


def _add_hint_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_hint"
    ]


def test_add_hint_calls_only_reference_whitelist_constants() -> None:
    """静态锁:禁止内联字符串字面量直接喂给 add_hint(第二个位置参数)。"""
    tree = ast.parse(
        GUIDANCE_SRC.read_text(encoding="utf-8"), filename=str(GUIDANCE_SRC)
    )
    calls = _add_hint_calls(tree)
    assert calls, "guidance.py 里没找到 add_hint 调用,检查文件是否被改动/迁移"
    for call in calls:
        assert len(call.args) >= 2, "add_hint 必须显式传 priority + text 两个位置参数"
        text_arg = call.args[1]
        assert isinstance(text_arg, ast.Name), (
            "add_hint 的第二个参数必须是 Name(引用模块级 _HINT_* 常量),"
            f"不得是内联字面量;命中一处违规:{ast.dump(text_arg)}"
        )
        assert text_arg.id.startswith("_HINT_"), (
            f"add_hint 引用的名字 {text_arg.id!r} 不在 _HINT_* 白名单命名之下"
        )


def test_no_bare_string_literal_passed_as_hint_text() -> None:
    """互补锁:确认每个引用名都能在模块里解析到真实的 _HINT_* 字符串常量。"""
    tree = ast.parse(
        GUIDANCE_SRC.read_text(encoding="utf-8"), filename=str(GUIDANCE_SRC)
    )
    for call in _add_hint_calls(tree):
        text_arg = call.args[1]
        assert isinstance(text_arg, ast.Name)
        assert hasattr(guidance_module, text_arg.id), (
            f"{text_arg.id} 未在 guidance 模块中定义为常量"
        )
        value = getattr(guidance_module, text_arg.id)
        assert isinstance(value, str) and value, f"{text_arg.id} 不是非空字符串常量"


def test_all_hint_constants_are_third_person_no_diagnosis_of_user() -> None:
    """禁诊断纪律(§4.2 纪律1):白名单句是对 agent 说"她怎样/该怎么回",不得
    对用户下"你[状态断言]"式诊断(如禁例"你压力很大")。唯一登记在案的例外是
    concern 唯一可见输出(§3.5:"她像是有点担心你，可以关心一句。"——"你"只是
    她关心的对象,不是对用户状态的断言),此句逐字白名单、不许再改。"""
    assert _ALL_HINT_TEXTS, "没有采集到任何 _HINT_* 常量,检查采集逻辑"
    for text in _ALL_HINT_TEXTS:
        if text == guidance_module._HINT_CONCERN:
            continue  # 登记在案的唯一例外(§3.5 逐字白名单)
        assert "你" not in text, f"白名单句 {text!r} 含第二人称诊断口吻,违反§4.2纪律1"
    assert guidance_module._HINT_CONCERN == "她像是有点担心你，可以关心一句。"


# =========================================================================
# 2. 运行时白名单:build_guidance 返回的 hints 全部落在白名单集合内
# =========================================================================


def _surface(**overrides) -> dict:
    base = {
        "decision": {"action": "hold"},
        "state": {
            "rhythm": {"strain": 0.0},
            "responsiveness": {"fatigue": 0.0},
            "valence": {"warmth": 0.5},
            "damage": {"accumulated": 0.0},
            "boundary": {"autonomy": 1.0, "paused": False},
            "needs": {"quiet": 0.0, "expression": 0.0},
        },
        "dynamics": {
            "relational_time": {"phase": "active"},
            "uncertainty": {"claim_caution": 0.0},
        },
        "guard": {"allowed": True},
    }
    for path, value in overrides.items():
        node = base
        keys = path.split(".")
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
    return base


def test_build_guidance_hints_are_subset_of_whitelist() -> None:
    surface = _surface(
        **{
            "decision.action": "withdraw",
            "state.rhythm.strain": 0.9,
            "state.boundary.autonomy": 0.1,
            "guard.allowed": False,
        }
    )
    out = build_guidance(surface, mode="companion", concern_active=True)
    assert out["hints"], "该场景应至少命中一条 hint"
    for h in out["hints"]:
        assert h in _ALL_HINT_TEXTS, f"运行时返回了不在白名单内的 hint:{h!r}"
    assert len(out["hints"]) <= 3


def test_concern_is_the_only_shadow_visible_output() -> None:
    """幕 IV 唯一可见输出 = concern 词典组的白名单短句(§3.5)。"""
    neutral_surface = _surface()
    out = build_guidance(neutral_surface, mode="companion", concern_active=True)
    assert guidance_module._HINT_CONCERN in out["hints"]
    # 不 concern_active 时不应出现 concern 句。
    out_off = build_guidance(neutral_surface, mode="companion", concern_active=False)
    assert guidance_module._HINT_CONCERN not in out_off["hints"]


# =========================================================================
# 3. 冲突优先级:主权/防御 > 疲劳/静默 > 温度;tone 取更保守
# =========================================================================


def test_defense_hint_beats_temperature_hint_under_three_cap() -> None:
    """guard 拦下 + 高 warmth 同时命中:防御类必须挤进 <=3 条,不被温度类顶掉。"""
    surface = _surface(
        **{
            "decision.action": "hold",
            "state.valence.warmth": 0.9,
            "guard.allowed": False,
            "state.boundary.autonomy": 0.1,
        }
    )
    out = build_guidance(surface, mode="companion")
    assert guidance_module._HINT_GUARD_BLOCKED in out["hints"]
    assert guidance_module._HINT_AUTONOMY in out["hints"]


def test_tone_conflict_resolves_to_more_conservative_brief_over_warm() -> None:
    """decision.action=guard(brief) 与高 warmth(warm)同时命中 → tone 取 brief。"""
    surface = _surface(**{"decision.action": "guard", "state.valence.warmth": 0.9})
    out = build_guidance(surface, mode="companion")
    assert out["tone"] == "brief"


def test_tone_gentle_beats_direct_via_damage() -> None:
    surface = _surface(**{"state.damage.accumulated": 0.5})
    out = build_guidance(surface, mode="companion")
    assert out["tone"] == "gentle"


# =========================================================================
# 4. steward 门控:length/pace 截短档恒中性,只留 tone/warmth 与展开
# =========================================================================


def test_steward_ignores_fatigue_strain_quiet_truncation_hints() -> None:
    surface = _surface(
        **{
            "state.rhythm.strain": 0.9,
            "state.responsiveness.fatigue": 0.9,
            "state.needs.quiet": 0.9,
            "decision.action": "withdraw",
        }
    )
    out = build_guidance(surface, mode="steward")
    assert out["length"] == "medium"
    assert out["pace"] == "steady"
    for truncation_hint in (
        guidance_module._HINT_STRAIN,
        guidance_module._HINT_FATIGUE,
        guidance_module._HINT_QUIET,
        guidance_module._HINT_WITHDRAW,
    ):
        assert truncation_hint not in out["hints"], (
            f"steward 下不应出现截短/给空间类 hint:{truncation_hint!r}(minor⑧)"
        )


def test_companion_honors_fatigue_strain_quiet_truncation_hints() -> None:
    surface = _surface(
        **{
            "state.rhythm.strain": 0.9,
            "decision.action": "withdraw",
        }
    )
    out = build_guidance(surface, mode="companion")
    assert out["length"] == "short"
    assert out["pace"] == "give_space"
    assert guidance_module._HINT_WITHDRAW in out["hints"]


def test_steward_still_allows_expression_expansion_not_a_truncation() -> None:
    """expression 高 → length=long 不算截答,steward 亦生效(§4.2 minor⑧ 例外)。"""
    surface = _surface(**{"state.needs.expression": 0.9})
    out = build_guidance(surface, mode="steward")
    assert out["length"] == "long"


def test_steward_express_action_also_expands_length() -> None:
    surface = _surface(**{"decision.action": "express", "state.valence.warmth": 0.8})
    out = build_guidance(surface, mode="steward")
    assert out["length"] == "long"
    assert guidance_module._HINT_EXPRESS in out["hints"]


# =========================================================================
# 5. 确定性:同输入同输出
# =========================================================================


def test_build_guidance_is_deterministic() -> None:
    surface = _surface(**{"decision.action": "reach_out", "state.valence.warmth": 0.8})
    out1 = build_guidance(surface, mode="companion", concern_active=True)
    out2 = build_guidance(surface, mode="companion", concern_active=True)
    assert out1 == out2


def test_missing_fields_fall_back_conservatively_no_crash() -> None:
    """字段缺失(空 dict / None)→ 保守默认,不触发任何阈值干预、不崩(§2.3)。"""
    out_none = build_guidance(None, mode="companion")
    assert out_none["tone"] == "neutral"
    assert out_none["length"] == "medium"
    assert out_none["pace"] == "steady"
    assert out_none["hints"] == []

    out_empty = build_guidance({}, mode="companion")
    assert out_empty["tone"] == "neutral"
    assert out_empty["hints"] == []


# =========================================================================
# 6. build_compact_surface:内联 guidance,通道值 ordinal7 化
# =========================================================================


def test_compact_surface_inlines_guidance_and_uses_ordinal_channels() -> None:
    surface = _surface(**{"state.valence.warmth": 0.8})
    surface.setdefault("state", {}).setdefault("boundary", {})["pressure"] = 0.2
    surface["state"].setdefault("needs", {})["contact"] = 0.4
    out = build_compact_surface(
        surface,
        session_id="sid-guidance-1",
        name="阿澜",
        bound=True,
        mode="companion",
        sealed=False,
        silenced=False,
        epoch=None,
        days_lived=3,
        self_words_today=0,
        proxy_sentences_today=0,
        swallowed_today=0,
        pending=0,
        concern_active=False,
    )
    assert out["session_id"] == "sid-guidance-1"
    assert isinstance(out["warmth"], str)  # ordinal7 序数词,非浮点
    assert "guidance" in out and isinstance(out["guidance"], dict)
    assert out["guidance"]["tone"] in {"warm", "gentle", "neutral", "direct", "brief"}
