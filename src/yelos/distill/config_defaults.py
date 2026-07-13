"""config_defaults.py 在整个架构中的位置:distill 侧配置键默认值(施工纪律:

禁编辑 config.py)。真正把 ``[distill]`` 段注册进 ``YelosConfig`` 是另一
任务的编码前置义务(与 finitude/intrinsic/shadow 侧 ``config_defaults.py``
同款留白)。本文件先把默认值与 ``cfg_get`` 立好——``cfg_get`` 支持
dict / 带同名属性对象(含尚未升级的 ``YelosConfig`` 实例)两种输入,缺键
一律回落默认。

蓝图 §4.3 的 ``[distill]`` TOML 段逐键对应本文件的 ``DEFAULT_DISTILL_*``。
``build_distill_provider`` 全程走本文件的 getter,永不假设 config.py 已
注册这些键——这是"opt-in 默认关不等于死代码"与"config.py 零改动"两条
纪律的交汇点。
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_DISTILL_ENABLED = False
DEFAULT_DISTILL_MODEL_DIR = "~/.yelos/models/distill"
DEFAULT_DISTILL_TIER = "ngram"
DEFAULT_DISTILL_BUDGET_MS = 50
DEFAULT_DISTILL_K_CANDIDATES = 8
DEFAULT_DISTILL_RERANKER = "hash"
DEFAULT_DISTILL_ALLOWED_OCCASIONS: tuple[str, ...] = ()  # 空 = 全场合(闸兜底)

VALID_TIERS = ("ngram", "rnn", "transformer")
VALID_RERANKERS = ("hash", "fidelity")


def cfg_get(cfg: Any, key: str, default: Any) -> Any:
    """dict / 对象双形态兼容读取,键缺失一律回落默认(与 finitude 侧同款)。"""
    if cfg is None:
        return default
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def distill_enabled(cfg: Any) -> bool:
    return bool(cfg_get(cfg, "distill_enabled", DEFAULT_DISTILL_ENABLED))


def distill_model_dir(cfg: Any) -> str:
    value = cfg_get(cfg, "distill_model_dir", DEFAULT_DISTILL_MODEL_DIR)
    return (
        value if isinstance(value, str) and value.strip() else DEFAULT_DISTILL_MODEL_DIR
    )


def distill_tier(cfg: Any) -> str:
    value = cfg_get(cfg, "distill_tier", DEFAULT_DISTILL_TIER)
    return value if value in VALID_TIERS else DEFAULT_DISTILL_TIER


def distill_budget_ms(cfg: Any) -> int:
    value = cfg_get(cfg, "distill_budget_ms", DEFAULT_DISTILL_BUDGET_MS)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DISTILL_BUDGET_MS
    return value if value > 0 else DEFAULT_DISTILL_BUDGET_MS


def distill_k_candidates(cfg: Any) -> int:
    value = cfg_get(cfg, "distill_k_candidates", DEFAULT_DISTILL_K_CANDIDATES)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DISTILL_K_CANDIDATES
    return value if value > 0 else DEFAULT_DISTILL_K_CANDIDATES


def distill_reranker(cfg: Any) -> str:
    value = cfg_get(cfg, "distill_reranker", DEFAULT_DISTILL_RERANKER)
    return value if value in VALID_RERANKERS else DEFAULT_DISTILL_RERANKER


def distill_allowed_occasions(cfg: Any) -> tuple[str, ...]:
    """空元组 = 全场合允许(安全性不靠此白名单,靠 whitelist_gate,§4.2)。"""
    raw = cfg_get(cfg, "distill_allowed_occasions", DEFAULT_DISTILL_ALLOWED_OCCASIONS)
    if isinstance(raw, (list, tuple)):
        return tuple(str(x) for x in raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return DEFAULT_DISTILL_ALLOWED_OCCASIONS
        if isinstance(parsed, list):
            return tuple(str(x) for x in parsed)
    return DEFAULT_DISTILL_ALLOWED_OCCASIONS


__all__ = [
    "DEFAULT_DISTILL_ENABLED",
    "DEFAULT_DISTILL_MODEL_DIR",
    "DEFAULT_DISTILL_TIER",
    "DEFAULT_DISTILL_BUDGET_MS",
    "DEFAULT_DISTILL_K_CANDIDATES",
    "DEFAULT_DISTILL_RERANKER",
    "DEFAULT_DISTILL_ALLOWED_OCCASIONS",
    "VALID_TIERS",
    "VALID_RERANKERS",
    "cfg_get",
    "distill_enabled",
    "distill_model_dir",
    "distill_tier",
    "distill_budget_ms",
    "distill_k_candidates",
    "distill_reranker",
    "distill_allowed_occasions",
]
