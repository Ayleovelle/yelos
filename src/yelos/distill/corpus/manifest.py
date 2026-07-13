"""在整个架构中的位置:语料版本化(蓝图 §3.2)。

``CorpusManifest`` 是训练/打包/viz 三方共读的哈希清单;``corpus_hash`` 是
DA3 确定性键成分之一(同语料 ⇒ 同训练 ⇒ 同模型 ⇒ 同输出)。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CorpusEntry:
    """她说过的话(唯一文本字段;DA4:恒为她的话,零用户原文)。

    真实上游契约(INTEGRATION_SPEC §1.1 C4)只给 ``text/occasion/day_key/
    affect``——蓝图草稿设想的 ``epoch/provider`` 字段上游不产,故此处按
    实际可得字段收窄,不臆造不存在的上游数据(疑义已记入交付报告)。
    """

    text: str
    occasion: str
    day_key: str
    source: str  # "memory_l1" | "anthology"(装配来源,非上游产者字段)
    features: dict = field(default_factory=dict)  # 结构化特征,无自由文本


@dataclass(frozen=True)
class CorpusManifest:
    corpus_hash: str
    n_entries: int
    sources: dict  # 逐来源计数(viz 桑基的数据源)
    created_day: str
    schema_version: int = 1

    def to_dict(self) -> dict:
        return {
            "corpus_hash": self.corpus_hash,
            "n_entries": self.n_entries,
            "sources": dict(self.sources),
            "created_day": self.created_day,
            "schema_version": self.schema_version,
        }

    @staticmethod
    def from_dict(raw: dict) -> "CorpusManifest":
        return CorpusManifest(
            corpus_hash=str(raw.get("corpus_hash", "")),
            n_entries=int(raw.get("n_entries", 0)),
            sources=dict(raw.get("sources", {})),
            created_day=str(raw.get("created_day", "")),
            schema_version=int(raw.get("schema_version", 1)),
        )


__all__ = ["CorpusEntry", "CorpusManifest"]
