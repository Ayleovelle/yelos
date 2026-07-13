"""memory 包在整个架构中的位置。

memory 是全部 dataclass / 常量 / 配置默认值的唯一权威源(memory_BLUEPRINT v2
§2.1)。facade.py 与全部子包只依赖本文件互相耦合,不许跨子包直接互相 import
对方的私有类型——依赖图 contracts ← 子模块 ← facade,无环(蓝图 §3)。

纯 stdlib、零 astrbot、零 sylanne_core、零 random;不触碰 time/datetime。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# --- EVENT_KINDS(§2.1)---------------------------------------------------

EVENT_KINDS: tuple[str, ...] = (
    "user_turn",
    "agent_turn",
    "her_word",
    "swallowed",
    "moment",
    "dream",
    "concern",
    "epoch",
    "rite",
)
"""moment/dream 由 W2 起 intrinsic 写入(MEM-A17 白名单预留,校验表非功能路径,
本波 v0.1 期无写入方也不算死代码)。"""


def _sget(d: dict | None, path: str, default):
    """点路径防御式取值(与 yelos.core.sget 同语义,memory 自著避免跨包耦合)。"""
    if d is None:
        return default
    cur = d
    for seg in path.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return default
        cur = cur[seg]
    return cur


# --- AffectStamp(引擎借来面,§12.1 全模块唯一"借来"面)-------------------


@dataclass(frozen=True)
class AffectStamp:
    """引擎 Surface 伴随的情感快照;情感权重的唯一来源(MEM-A7)。"""

    warmth: float = 0.0
    pressure: float = 0.0
    contact: float = 0.0
    quiet: float = 0.0
    pad_label: str = ""
    decision: str = ""
    phase: str = ""

    @classmethod
    def from_compact(cls, compact: dict | None) -> "AffectStamp":
        """sget 防御式装配,缺失字段全部落中性默认(不 raise)。"""
        return cls(
            warmth=float(_sget(compact, "state.valence.warmth", 0.0) or 0.0),
            pressure=float(_sget(compact, "state.boundary.pressure", 0.0) or 0.0),
            contact=float(_sget(compact, "state.needs.contact", 0.0) or 0.0),
            quiet=float(_sget(compact, "state.needs.quiet", 0.0) or 0.0),
            pad_label=str(_sget(compact, "pad.label", "") or ""),
            decision=str(_sget(compact, "decision.action", "") or ""),
            phase=str(_sget(compact, "dynamics.relational_time.phase", "") or ""),
        )

    def to_dict(self) -> dict:
        return {
            "warmth": self.warmth,
            "pressure": self.pressure,
            "contact": self.contact,
            "quiet": self.quiet,
            "pad_label": self.pad_label,
            "decision": self.decision,
            "phase": self.phase,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "AffectStamp":
        if not d:
            return cls()
        return cls(
            warmth=float(d.get("warmth", 0.0) or 0.0),
            pressure=float(d.get("pressure", 0.0) or 0.0),
            contact=float(d.get("contact", 0.0) or 0.0),
            quiet=float(d.get("quiet", 0.0) or 0.0),
            pad_label=str(d.get("pad_label", "") or ""),
            decision=str(d.get("decision", "") or ""),
            phase=str(d.get("phase", "") or ""),
        )


_META_MAX_STR_LEN = 32
_META_ALLOWED_TYPES = (str, int, float, bool)


def validate_meta(meta: dict) -> None:
    """EpisodeEvent.meta 只放结构化小字段,禁自由文本(§2.1 schema 校验)。

    规则:一层平铺 dict;值只能是 str/int/float/bool;字符串值长度 <= 32
    (verdict、occasion 名、intensity 档、msg_id 哈希都在此界内;禁止把整句
    原文塞进 meta 绕过 L1 text 字段的隐私纪律)。
    """
    for key, value in meta.items():
        if not isinstance(key, str):
            raise ValueError(f"EpisodeEvent.meta key must be str: {key!r}")
        if not isinstance(value, _META_ALLOWED_TYPES):
            raise ValueError(
                f"EpisodeEvent.meta[{key!r}] must be a flat scalar, got {type(value)!r}"
            )
        if isinstance(value, str) and len(value) > _META_MAX_STR_LEN:
            raise ValueError(
                f"EpisodeEvent.meta[{key!r}] string too long "
                f"(>{_META_MAX_STR_LEN} chars); meta 禁自由文本"
            )


# --- L1: EpisodeEvent -----------------------------------------------------


@dataclass(frozen=True)
class EpisodeEvent:
    """L1 唯一写入单元(情景流水的一行)。"""

    kind: str
    ts: float
    day_key: str
    text: str = ""
    speaker: str = ""
    occasion: str = ""
    affect: AffectStamp | None = None
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown EpisodeEvent.kind: {self.kind!r}")
        validate_meta(self.meta)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "ts": self.ts,
            "day_key": self.day_key,
            "text": self.text,
            "speaker": self.speaker,
            "occasion": self.occasion,
            "affect": self.affect.to_dict() if self.affect is not None else None,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EpisodeEvent":
        return cls(
            kind=d["kind"],
            ts=float(d.get("ts", 0.0)),
            day_key=str(d.get("day_key", "")),
            text=str(d.get("text", "")),
            speaker=str(d.get("speaker", "")),
            occasion=str(d.get("occasion", "")),
            affect=AffectStamp.from_dict(d.get("affect")),
            meta=dict(d.get("meta") or {}),
        )


# --- L2: SemanticEntry ------------------------------------------------


@dataclass
class SemanticEntry:
    """L2 语义条目(自著 PPMI+SVD 承重的正身,MEM-A9)。"""

    id: str
    span: tuple[int, int]
    day_key: str
    keywords: list[str]
    summary: str
    vec: list[float]
    emotion: dict
    S: float = 1.0
    created_ts: float = 0.0
    last_access_ts: float = 0.0
    access_count: int = 0
    topic_id: str = ""
    source_kinds: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "span": list(self.span),
            "day_key": self.day_key,
            "keywords": self.keywords,
            "summary": self.summary,
            "vec": self.vec,
            "emotion": self.emotion,
            "S": self.S,
            "created_ts": self.created_ts,
            "last_access_ts": self.last_access_ts,
            "access_count": self.access_count,
            "topic_id": self.topic_id,
            "source_kinds": self.source_kinds,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SemanticEntry":
        span = d.get("span", [0, 0])
        return cls(
            id=str(d["id"]),
            span=(int(span[0]), int(span[1])),
            day_key=str(d.get("day_key", "")),
            keywords=list(d.get("keywords", [])),
            summary=str(d.get("summary", "")),
            vec=[float(x) for x in d.get("vec", [])],
            emotion=dict(d.get("emotion") or {}),
            S=float(d.get("S", 1.0)),
            created_ts=float(d.get("created_ts", 0.0)),
            last_access_ts=float(d.get("last_access_ts", 0.0)),
            access_count=int(d.get("access_count", 0)),
            topic_id=str(d.get("topic_id", "")),
            source_kinds=list(d.get("source_kinds", [])),
        )


# --- L3: TopicEvent / TopicNode ----------------------------------------

TOPIC_EVENT_KINDS: tuple[str, ...] = (
    "born",
    "grow",
    "merge_in",
    "merge_out",
    "split",
    "dormant",
    "wake",
    "dead",
)

TOPIC_STATES: tuple[str, ...] = ("nascent", "active", "dormant", "dead")


@dataclass(frozen=True)
class TopicEvent:
    kind: str
    day_key: str
    payload: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in TOPIC_EVENT_KINDS:
            raise ValueError(f"unknown TopicEvent.kind: {self.kind!r}")

    def to_dict(self) -> dict:
        return {"kind": self.kind, "day_key": self.day_key, "payload": self.payload}

    @classmethod
    def from_dict(cls, d: dict) -> "TopicEvent":
        return cls(
            kind=d["kind"],
            day_key=str(d.get("day_key", "")),
            payload=dict(d.get("payload") or {}),
        )


@dataclass
class TopicNode:
    id: str
    label_kw: list[str]
    centroid: list[float]
    born_day: str
    last_active_day: str
    state: str = "nascent"
    strength: float = 0.0
    members: list[str] = field(default_factory=list)
    events: list[TopicEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label_kw": self.label_kw,
            "centroid": self.centroid,
            "born_day": self.born_day,
            "last_active_day": self.last_active_day,
            "state": self.state,
            "strength": self.strength,
            "members": self.members,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TopicNode":
        return cls(
            id=str(d["id"]),
            label_kw=list(d.get("label_kw", [])),
            centroid=[float(x) for x in d.get("centroid", [])],
            born_day=str(d.get("born_day", "")),
            last_active_day=str(d.get("last_active_day", "")),
            state=str(d.get("state", "nascent")),
            strength=float(d.get("strength", 0.0)),
            members=list(d.get("members", [])),
            events=[TopicEvent.from_dict(e) for e in d.get("events", [])],
        )


# --- Recall ---------------------------------------------------------------


@dataclass(frozen=True)
class RecallQuery:
    text: str = ""
    now_ts: float = 0.0
    day_key: str = ""
    k: int = 5
    scope: str = "l2"
    affect: AffectStamp | None = None


@dataclass(frozen=True)
class RecallHit:
    entry_id: str
    layer: str
    score: float
    factors: dict
    summary: str
    keywords: list[str]
    day_key: str
    topic_id: str
    strength_label: str


@dataclass(frozen=True)
class RecallResult:
    hits: tuple[RecallHit, ...]
    scorer: str
    deterministic_key: str


# --- 下游供血契约(§5)-----------------------------------------------------


@dataclass(frozen=True)
class ThemeDigest:
    day_key: str
    themes: tuple[dict, ...]
    moments_kw: tuple[str, ...]


@dataclass(frozen=True)
class BaselineContext:
    familiarity: float
    days_since_last_contact: int
    typical_warmth: float
    typical_pressure: float
    sample_days: int


@dataclass(frozen=True)
class ContinuityFlags:
    reunion: bool
    long_bond: bool
    active_themes: int


# --- consolidation ----------------------------------------------------


@dataclass(frozen=True)
class JobBudget:
    """夜窗单步墙钟预算(软限,§2.3)。"""

    per_step_seconds: float = 5.0


@dataclass(frozen=True)
class ConsolidationReport:
    night_key: str
    steps_done: tuple[str, ...]
    steps_skipped: tuple[str, ...]
    resumed: bool
    elapsed_by_step: dict


# --- memory 配置(不碰 config.py,自持默认值,§7)-------------------------


@dataclass(frozen=True)
class MemoryConfig:
    memory_enabled: bool = True
    memory_recall_scorer: str = "linear"  # linear|rrf|emotion_first
    memory_decay_family: str = "exp"  # exp|pow
    memory_vec_dim: int = 64
    memory_similarity_fusion: float = 0.3
    memory_assessor_summary: bool = False
    memory_assessor_nightly_cap: int = 2
    memory_l1_segment_max: int = 5000
    memory_l2_cap: int = 4000
    memory_vocab_cap: int = 30000
    memory_reunion_days: int = 7
    memory_theta_assign: float = 0.55
    memory_theta_merge: float = 0.80
    memory_theta_split: float = 0.40
    memory_recall_k: int = 5
    memory_export_raw: bool = False
    memory_min_history_days: int = 3
    memory_long_bond_familiarity: float = 0.6

    @classmethod
    def from_dict(cls, d: dict | None) -> "MemoryConfig":
        """只增不删装配:未知键忽略,缺键落默认(§7.3 纪律)。"""
        if not d:
            return cls()
        fields = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in d.items() if k in fields}
        return cls(**kwargs)


def _tokens_iter(docs: Iterable[list[str]]) -> Iterable[list[str]]:
    """小工具:统一 docs 迭代形态(供 vocab/ppmi 内部复用,避免重复样板)。"""
    for doc in docs:
        yield list(doc)
