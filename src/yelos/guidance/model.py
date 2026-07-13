"""guidance 数据模型:规则/触发/效果/溯源/档位对象(全 frozen dataclass,可序列化)。

蓝图 §3。规则对象化是本模块深化的自著核心:触发谓词是数据(``Trigger``),
不是 lambda;解释器(``compiler/interpreter.py``)是消费这份数据的纯函数。

[强制] 本文件零 fastmcp / 零 sylanne_core / 零 random / 零 time / 零 I/O。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# 封闭比较算子集(A1 的一部分:解释器只认这几个算子,不接受自由代码)。
OP = Literal["ge", "le", "eq", "is_false", "flag"]

# mode_input 源的合法 path 白名单(不是 Surface 字段,是入参/派生标志)。
# X4(INTEGRATION_SPEC §3.4 路线 A):追加 "continuity.reunion",承接
# memory.ContinuityFlags 的 reunion 事实,guidance 仍不 import memory
# (continuity 由调用方以结构化对象/None 传入,这里只按 path 字符串读字段)。
MODE_INPUT_PATHS: frozenset[str] = frozenset(
    {"concern_active", "paused_or_autonomy", "continuity.reunion"}
)


@dataclass(frozen=True)
class Trigger:
    """单一触发谓词。``source="surface"`` 时 ``path`` 是 ``core.sget`` 路径;
    ``source="mode_input"`` 时 ``path`` 必须在 :data:`MODE_INPUT_PATHS` 内。
    """

    path: str
    op: OP
    value: float | str | None = None
    source: Literal["surface", "mode_input"] = "surface"


@dataclass(frozen=True)
class CompositeTrigger:
    """仅 AND 的复合触发(封闭算子集越小越好,不引入 OR 组合子)。

    现库唯一用例:R06_express = express ∧ warmth≥0.7。OR 语义(如 v0.1 的
    ``autonomy<=0.3 or paused``)按 v0.1 原样拆成两条同 ``hint_key`` 的规则,
    靠去重管线天然合并(见 rules.py R13/R14、R17/R17b)。
    """

    all_of: tuple[Trigger, ...]


@dataclass(frozen=True)
class Effect:
    """一条规则命中后对四个输出维度的贡献(每维可为 None = 无贡献)。"""

    tone: str | None = None
    length: str | None = None  # "short" | "long"(medium 恒为默认,不显式置)
    pace: str | None = None  # "give_space" | "relaxed"
    respect_pause: bool = False


@dataclass(frozen=True)
class Rule:
    """规则集即数据。``rules.DEFAULT_RULESET`` 是这个类型的元组。"""

    rule_id: str
    trigger: Trigger | CompositeTrigger
    effect: Effect
    hint_key: str | None  # HintKey 名;None = 无 hint(hold)
    priority: int  # 0=_P_DEFENSE 1=_P_CONCERN 2=_P_FATIGUE 3=_P_TEMP
    truncation: bool  # steward 抑制矩阵作用位(minor⑧)
    exclusive_group: str | None = None  # "decision_action":互斥单选组


@dataclass(frozen=True)
class HintTrace:
    """A3 可审计溯源:一条候选 hint(入选或被抑制)的完整重放记录。"""

    hint_key: str
    rule_id: str
    path: str
    op: OP
    threshold: float | str | None
    observed: float | str | bool | None
    margin: float | None
    suppressed_by: str | None = None  # None=入选;"steward"|"profile_drop"|"dedup"|"cap"


@dataclass(frozen=True)
class GuidanceResult:
    """``evaluate()`` 的返回值:I1 的 6 键 dict + 全量溯源。"""

    guidance: dict
    audit: tuple[HintTrace, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EffectiveProfile:
    """3 档 profile 的参数化档位(profiles.py 消费)。"""

    name: str  # "coding" | "chat" | "voice"
    hint_cap: int
    drop_priorities: frozenset[int] = frozenset()
    # steward 抑制位(mode=="steward" 时由 resolve_profile 置位):
    neutralize_short: bool = False
    neutralize_pace: bool = False
    drop_truncation_hints: bool = False
    # voice 附加档位语义:
    voice_fields: bool = False
