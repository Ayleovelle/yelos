"""在整个架构中的位置:shadow 包内跨子模块共享的数据结构与协议(dataclass +
Protocol),避免 simulator/baseline/signals/calibration/sensitization/gates
互相 import 造成环。这是对蓝图 §2 文件树的一处显式补登——蓝图树本身没列
这个文件,但 memory 包已示范同样的"contracts.py 收口"手法(见
`yelos.memory.contracts`),shadow 依样画葫芦,理由记入模块交付说明。

dict 进、dataclass 出(core 纪律继承,§3 前言)。本文件零 import 其余
shadow 子模块,只被它们 import——单向依赖的根。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


# --- §3.1 运行时结构 -----------------------------------------------------


@dataclass(frozen=True)
class ShadowView:
    """单条影子轨迹的通道读数(引擎 Surface 的防御式投影)。"""

    pressure: float | None  # state.boundary.pressure
    warmth: float | None  # state.valence.warmth
    damage: float | None  # state.damage.open
    hyp_id: int  # 0=正典轨迹,1..K-1=扰动假设


@dataclass(frozen=True)
class EnsembleReading:
    """多假设一拍读数(simulator/ensemble.py 的产出)。"""

    views: tuple[ShadowView, ...]  # len ∈ {1..K};[0] 恒为正典
    disagreement: float  # D_t ∈ [0,1]
    epsilon_used: float  # 本拍 ε_t(记账/可视化,不进决策)
    degraded: bool  # 预算降档标志(K 被压到 1)


@dataclass(frozen=True)
class BaselineView:
    """某通道的基线族快照(baseline/rolling.py 的产出)。"""

    day: float | None
    week: float | None
    month: float | None
    dispersion: float  # σ_family ∈ [0,1]


@dataclass(frozen=True)
class RawConcern:
    """检测器裸输出(闸前)。"""

    ctype: str
    strength: float  # [0,1] 归一信号强度(未折减)
    evidence: tuple[str, ...]  # 机器可读触发特征名(ASCII,禁原文)


@dataclass(frozen=True)
class ConcernVerdict:
    """闸后裁定(gates/exit.py 的像,SHTOM-T1)。"""

    ctype: str
    intensity: float  # 折减后强度,量化到 3 位
    q: float  # 校准用预测确定度 ∈ [0,1]
    do_inject: bool
    do_enqueue: bool  # concern 原语入 outbox(仍需幕 III probe 闸)
    gate_trace: tuple[str, ...]  # 逐闸判定轨迹(ASCII 标签)


# --- §3.2 校准与敏感化结构 ------------------------------------------------


@dataclass(frozen=True)
class PredictionRecord:
    """calibration/ledger.py 追加行(jsonl,脱敏:只存数值特征)。"""

    ts: float
    day: str
    ctype: str
    q: float
    features: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class OutcomeRecord:
    ts: float
    pred_ts: float
    ctype: str
    y: int  # 0/1 结果代理
    proxy: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CalibrationState:
    """brier.py 滚动产出(binding 持久,per ctype)。"""

    brier: float | None
    n: int
    bins: tuple[tuple[float, float, int], ...]
    tier: str  # "observe"|"normal"|"tight"|"silent"


@dataclass(frozen=True)
class SensitizationState:
    """scar.py(binding 持久,per ctype)。"""

    beta: float
    hits: int
    misses: int


@dataclass(frozen=True)
class DayContext:
    """检测器协议第三入参:当日互动统计与有效阈值(signals/protocol.py 消费)。"""

    day_key: str
    interactions_today: int
    last_gap_seconds: float
    msg_len_ewma: float
    th_eff: dict[str, float]  # ctype -> th_base + beta_c
    pressure_slope: float = 0.0  # Δp / 拍(短窗斜率,pressure_spike 用)
    in_quiet: bool = False  # rhythm_break 用:quiet 窗内不判节奏骤变
    week_gap_median: float = 0.0  # rhythm_break 参照:周基线交互间隔中位(秒)
    interactions_7d_avg: float = 0.0  # withdrawal 参照
    interactions_month_avg: float = 0.0
    msg_len_month_avg: float = 0.0


@dataclass(frozen=True)
class ShadowConfig:
    """本包读取的配置快照(组合根从 cfg 防御式抽取,§13 配置增量表)。"""

    shadow_enabled: bool = True
    shadow_hypotheses: int = 1
    shadow_intensity_fn: str = "linear"
    shadow_engine_calls_per_beat: int = 4
    shadow_calibration_window: int = 60


# --- 组合根依赖的外部协议(duck-typed,零 import 具体实现) -------------------


class BridgeProto(Protocol):
    """`ShadowSystem` 依赖的引擎桥协议子集。

    `submit_shadow`/`shadow_state`/`inject_concern` 是当前 `engine_bridge.py`
    已有的方法(v0.1 契约不破)。`submit_shadow_hyp`/`shadow_state_hyp`/
    `inject_shadow_perturb` 是蓝图 §4.1 要求的"一处 bridge 微改"——本任务
    只建新文件、不编辑 `engine_bridge.py`,故这三个方法用
    ``getattr(bridge, name, None)`` 做特性探测:真实桥未实现时,多假设路径
    静默退化为 K=1(与默认配置行为一致,不 raise),真正把这三个方法接上
    `engine_bridge.py` 是本任务范围外的后续接线义务(交付说明里显式记录)。
    """

    async def submit_shadow(self, umo: str, text: str, msg_id: str) -> None: ...

    async def shadow_state(self, umo: str) -> dict | None: ...

    async def inject_concern(self, umo: str, intensity: float) -> None: ...


class DeterminismProto(Protocol):
    """确定性哈希族协议(复用 `primal.determinism` 的函数即可满足)。"""

    def h_byte(self, key: str) -> int: ...


class MemoryBaselineProto(Protocol):
    """X6 裁定消费的 `memory.BaselineContext` 子集(鸭子类型,零 import
    `yelos.memory`)。真实类型见 `yelos.memory.contracts.BaselineContext`,
    字段名逐字对齐,duck-typing 免去跨模块硬依赖。
    """

    familiarity: float
    typical_warmth: float
    typical_pressure: float


class MemoryFacadeProto(Protocol):
    """X6 裁定消费的 `memory.MemoryFacade` 子集(供冷启动兜底与 familiarity
    折减调用)。组合根注入可选,未注入时全部消费点安静跳过(§3.6 非硬依赖)。
    """

    def baseline_context(
        self, sid: str, gen: int, day_key: str
    ) -> MemoryBaselineProto: ...


__all__ = [
    "ShadowView",
    "EnsembleReading",
    "BaselineView",
    "RawConcern",
    "ConcernVerdict",
    "PredictionRecord",
    "OutcomeRecord",
    "CalibrationState",
    "SensitizationState",
    "DayContext",
    "ShadowConfig",
    "BridgeProto",
    "DeterminismProto",
    "MemoryBaselineProto",
    "MemoryFacadeProto",
]
