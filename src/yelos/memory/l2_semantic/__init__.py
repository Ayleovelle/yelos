"""l2_semantic 子包在架构中的位置。

红队 major⑧ 承诺 1 的正身:字符/词 n-gram 计数 → PPMI 加权 → 自著截断 SVD,
零第三方 NLP 依赖、零 numpy、零 LLM。tokenizer→vocab→ppmi→linalg_lite 是
纯数值管线;summarize/emotion 产出 SemanticEntry 的文本与情感面;entries.py
是本子包对外的组装门面(consolidation 调它产 SemanticEntry)。
"""

from __future__ import annotations

from .emotion import aggregate_emotion
from .tokenizer import tokenize
from .vocab import Vocab

__all__ = ["aggregate_emotion", "tokenize", "Vocab"]
