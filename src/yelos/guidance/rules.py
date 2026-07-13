"""``DEFAULT_RULESET``:规则集即数据,逐字对齐 v0.1 §4.2 决策表(蓝图 §4.1),
零语义漂移收编 + X4(continuity.reunion)一处明示增量。

优先级常量语义与 v0.1 一致:数字越小越先,决定 ≤hint_cap 上限下谁留下。
"""

from __future__ import annotations

from .model import CompositeTrigger, Effect, Rule, Trigger

_P_DEFENSE = 0  # 主权/防御:guard.allowed=False、autonomy 低、decision==guard
_P_CONCERN = 1  # 关心(只读影子/companion 影子活跃)
_P_FATIGUE = 2  # 疲劳/静默/收敛:fatigue、strain、quiet、withdraw
_P_TEMP = 3  # 温度/表达/决策倾向

DEFAULT_RULESET: tuple[Rule, ...] = (
    Rule(
        rule_id="R01_withdraw",
        trigger=Trigger("decision.action", "eq", "withdraw"),
        effect=Effect(tone="gentle", length="short", pace="give_space"),
        hint_key="WITHDRAW",
        priority=_P_FATIGUE,
        truncation=True,
        exclusive_group="decision_action",
    ),
    Rule(
        rule_id="R02_recover",
        trigger=Trigger("decision.action", "eq", "recover"),
        effect=Effect(tone="warm"),
        hint_key="RECOVER",
        priority=_P_TEMP,
        truncation=False,
        exclusive_group="decision_action",
    ),
    Rule(
        rule_id="R03_reach_out",
        trigger=Trigger("decision.action", "eq", "reach_out"),
        effect=Effect(tone="warm"),
        hint_key="REACH_OUT",
        priority=_P_TEMP,
        truncation=False,
        exclusive_group="decision_action",
    ),
    Rule(
        rule_id="R04_explore",
        trigger=Trigger("decision.action", "eq", "explore"),
        effect=Effect(tone="neutral", pace="relaxed"),
        hint_key="EXPLORE",
        priority=_P_TEMP,
        truncation=False,
        exclusive_group="decision_action",
    ),
    Rule(
        rule_id="R05_guard",
        trigger=Trigger("decision.action", "eq", "guard"),
        effect=Effect(tone="brief", length="short"),
        hint_key="GUARD_DECISION",
        priority=_P_DEFENSE,
        truncation=True,
        exclusive_group="decision_action",
    ),
    Rule(
        rule_id="R06_express",
        trigger=CompositeTrigger(
            all_of=(
                Trigger("decision.action", "eq", "express"),
                Trigger("state.valence.warmth", "ge", 0.7),
            )
        ),
        effect=Effect(tone="warm", length="long"),
        hint_key="EXPRESS",
        priority=_P_TEMP,
        truncation=False,
        exclusive_group="decision_action",
    ),
    Rule(
        rule_id="R07_hold",
        trigger=Trigger("decision.action", "eq", "hold"),
        effect=Effect(tone="neutral"),
        hint_key=None,
        priority=_P_TEMP,
        truncation=False,
        exclusive_group="decision_action",
    ),
    Rule(
        rule_id="R08_strain",
        trigger=Trigger("state.rhythm.strain", "ge", 0.6),
        effect=Effect(length="short", pace="give_space"),
        hint_key="STRAIN",
        priority=_P_FATIGUE,
        truncation=True,
    ),
    Rule(
        rule_id="R09_fatigue",
        trigger=Trigger("state.responsiveness.fatigue", "ge", 0.7),
        effect=Effect(length="short"),
        hint_key="FATIGUE",
        priority=_P_FATIGUE,
        truncation=True,
    ),
    Rule(
        rule_id="R10_warm_hi",
        trigger=Trigger("state.valence.warmth", "ge", 0.7),
        effect=Effect(tone="warm"),
        hint_key="WARM_HIGH",
        priority=_P_TEMP,
        truncation=False,
    ),
    Rule(
        rule_id="R11_warm_lo",
        trigger=Trigger("state.valence.warmth", "le", 0.3),
        effect=Effect(tone="gentle"),
        hint_key="WARM_LOW",
        priority=_P_TEMP,
        truncation=False,
    ),
    Rule(
        rule_id="R12_damage",
        trigger=Trigger("state.damage.accumulated", "ge", 0.3),
        effect=Effect(tone="gentle"),
        hint_key="DAMAGE",
        priority=_P_TEMP,
        truncation=False,
    ),
    Rule(
        rule_id="R13_autonomy",
        trigger=Trigger("state.boundary.autonomy", "le", 0.3),
        effect=Effect(tone="brief", respect_pause=True),
        hint_key="AUTONOMY",
        priority=_P_DEFENSE,
        truncation=False,
    ),
    Rule(
        rule_id="R14_paused",
        trigger=Trigger("state.boundary.paused", "flag"),
        effect=Effect(tone="brief", respect_pause=True),
        hint_key="AUTONOMY",
        priority=_P_DEFENSE,
        truncation=False,
    ),
    Rule(
        rule_id="R15_quiet",
        trigger=Trigger("state.needs.quiet", "ge", 0.6),
        effect=Effect(length="short", pace="give_space"),
        hint_key="QUIET",
        priority=_P_FATIGUE,
        truncation=True,
    ),
    Rule(
        rule_id="R16_expression",
        trigger=Trigger("state.needs.expression", "ge", 0.7),
        effect=Effect(length="long"),
        hint_key="EXPRESSION",
        priority=_P_TEMP,
        truncation=False,
    ),
    Rule(
        rule_id="R17_dormant",
        trigger=Trigger("dynamics.relational_time.phase", "eq", "dormant"),
        effect=Effect(tone="gentle"),
        hint_key="DORMANT",
        priority=_P_TEMP,
        truncation=False,
    ),
    # X4(INTEGRATION_SPEC §3.4 路线 A):continuity.reunion 触发升级 DORMANT。
    # OR 语义按 v0.1 R13/R14 的既有手法处理:两条同 hint_key 规则,靠去重
    # 管线天然合并,不引入 OR 组合子(封闭算子集越小越好)。
    Rule(
        rule_id="R17b_reunion",
        trigger=Trigger("continuity.reunion", "flag", source="mode_input"),
        effect=Effect(tone="gentle"),
        hint_key="DORMANT",
        priority=_P_TEMP,
        truncation=False,
    ),
    Rule(
        rule_id="R18_caution",
        trigger=Trigger("dynamics.uncertainty.claim_caution", "ge", 0.6),
        effect=Effect(),
        hint_key="CAUTION",
        priority=_P_TEMP,
        truncation=False,
    ),
    Rule(
        rule_id="R19_concern",
        trigger=Trigger("concern_active", "flag", source="mode_input"),
        effect=Effect(tone="gentle"),
        hint_key="CONCERN",
        priority=_P_CONCERN,
        truncation=False,
    ),
    Rule(
        rule_id="R20_guard_blk",
        trigger=Trigger("guard.allowed", "is_false"),
        effect=Effect(respect_pause=True),
        hint_key="GUARD_BLOCKED",
        priority=_P_DEFENSE,
        truncation=False,
    ),
)

__all__ = ["DEFAULT_RULESET", "_P_DEFENSE", "_P_CONCERN", "_P_FATIGUE", "_P_TEMP"]
