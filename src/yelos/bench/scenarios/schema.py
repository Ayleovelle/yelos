"""剧本规范形(bench_BLUEPRINT §4.1)。

三个冻结 dataclass:``ScenarioEvent``/``ScenarioDay``/``Scenario``。
文本纪律(§4.1/§B-D3):剧本不携自由用户文本,``payload`` 里的文本一律是
``corpus_zh.yel`` 语料表的键(``text_key``),不是原文——本 W1 版语料表
尚未落地(W4 交付),先以最小内建常量表兜底(见 ``scenarios/corpus.py``
若后续需要;W1 阶段 synth/dsl 直接产出的 text_key 字符串本身即语料键,
不解析成原文,判分器与 trace 也只搬运键名,天然不违反纪律)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 事件种类全集(bench_BLUEPRINT §4.1 docstring 枚举)。
EVENT_KINDS = frozenset(
    {
        "user_msg",
        "agent_draft",
        "agent_submit",
        "impulse_poll",
        "state",
        "guidance",
        "tick",
        "pause",
        "reset",
        "bind",
        "farewell_begin",
        "farewell_confirm",
        "probe_recall",
    }
)

# config_overrides 白名单键(§4.1;与 bench_BLUEPRINT §7.3 已有配置键对齐,
# W1 先收敛到 harness/FakeBridge 实际会读的几个,超集留待真正接 config.py 时再扩)。
CONFIG_OVERRIDE_KEYS = frozenset(
    {
        "min_gap_seconds",
        "quiet_hours_start_min",
        "quiet_hours_end_min",
        "cap",
        "lifespan_days",
    }
)


@dataclass(frozen=True)
class ScenarioEvent:
    """单个事件:当日第 ``at_min`` 分钟发生 ``kind``,携 ``payload``。"""

    at_min: int
    kind: str
    payload: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0 <= self.at_min <= 1439):
            raise ValueError(f"ScenarioEvent.at_min 越界(0..1439):{self.at_min}")
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"ScenarioEvent.kind 未知:{self.kind!r}")


@dataclass(frozen=True)
class ScenarioDay:
    """一虚拟日的事件序列,``events`` 必须按 ``at_min`` 非降序排列。"""

    day_index: int
    events: tuple[ScenarioEvent, ...] = ()

    def __post_init__(self) -> None:
        if self.day_index < 0:
            raise ValueError(f"ScenarioDay.day_index 不得为负:{self.day_index}")
        mins = [e.at_min for e in self.events]
        if mins != sorted(mins):
            raise ValueError(
                f"ScenarioDay(day_index={self.day_index}) 的 events 未按 at_min "
                "升序排列(schema 强制,bench_BLUEPRINT §4.1)"
            )


@dataclass(frozen=True)
class Scenario:
    """一份完整剧本。``origin`` 标出身(策略族可观测差异的机器凭据)。"""

    scenario_id: str
    mode: str
    days: tuple[ScenarioDay, ...] = ()
    config_overrides: dict = field(default_factory=dict)
    origin: str = "dsl"

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("Scenario.scenario_id 不得为空")
        if self.mode not in ("steward", "companion"):
            raise ValueError(f"Scenario.mode 未知:{self.mode!r}")
        if self.origin not in ("dsl", "synth"):
            raise ValueError(f"Scenario.origin 未知:{self.origin!r}")
        bad = set(self.config_overrides) - CONFIG_OVERRIDE_KEYS
        if bad:
            raise ValueError(f"Scenario.config_overrides 含非白名单键:{sorted(bad)}")
        idxs = [d.day_index for d in self.days]
        if idxs != sorted(idxs):
            raise ValueError("Scenario.days 未按 day_index 升序排列")
