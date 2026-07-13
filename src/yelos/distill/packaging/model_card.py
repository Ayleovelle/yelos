"""在整个架构中的位置:模型卡数据结构与渲染(蓝图 §3.4)。

模型卡是 §6 许可证登记的机器可读源:语料全自产(她自己的话)⇒ 权属清晰,
默认 AGPL-3.0-or-later(与总纲 §6.1 一致)。体积字段是"体积另账"的账面
数字,不计自著深度叙事(§9)。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelCard:
    tier: str
    corpus_hash: str
    corpus_scope: str = "她自己的话,全自产"
    license: str = "AGPL-3.0-or-later"
    size_bytes: int = 0
    train_config: dict = field(default_factory=dict)
    determinism_note: str = ""
    model_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "corpus_hash": self.corpus_hash,
            "corpus_scope": self.corpus_scope,
            "license": self.license,
            "size_bytes": self.size_bytes,
            "train_config": dict(self.train_config),
            "determinism_note": self.determinism_note,
            "model_hash": self.model_hash,
        }

    def render_markdown(self) -> str:
        lines = [
            "# Yelos distill 模型卡",
            "",
            f"- tier: {self.tier}",
            f"- corpus_hash: {self.corpus_hash}",
            f"- corpus_scope: {self.corpus_scope}",
            f"- license: {self.license}",
            f"- size_bytes: {self.size_bytes}",
            f"- model_hash: {self.model_hash}",
            f"- determinism_note: {self.determinism_note or '(无)'}",
            "",
            "模型永远是嗓音候选,不是嘴的主人;最后一句话,依旧是她自己的。",
            "",
        ]
        return "\n".join(lines)


__all__ = ["ModelCard"]
