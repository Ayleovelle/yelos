"""schedule.py 在架构中的位置。

夜窗步序常量 + 向量重训(refit)决策表(§3.2.3,裁决 M10)。night_key 的
判定(quiet 窗起点归属日)由 session 层算好传入(与 v0.1 session._night_of
同算法),本文件不触碰 time/datetime.now,只做纯决策。
"""

from __future__ import annotations

NIGHT_STEPS: tuple[str, ...] = (
    "l1_day_seal",
    "l2_summarize",
    "vocab_update",
    "vec_refit",
    "l3_lifecycle",
    "forgetting_sweep",
    "l2_capacity",
    "viz_export",
)

DEFAULT_MIN_L2_FOR_VECTORS = 30
DEFAULT_NEW_TOKEN_RATIO_THRESHOLD = 0.15
DEFAULT_REFIT_INTERVAL_NIGHTS = 14


def should_refit(
    *,
    has_basis: bool,
    l2_count: int,
    new_token_ratio: float,
    nights_since_refit: int,
    min_l2_for_vectors: int = DEFAULT_MIN_L2_FOR_VECTORS,
    new_token_ratio_threshold: float = DEFAULT_NEW_TOKEN_RATIO_THRESHOLD,
    refit_interval_nights: int = DEFAULT_REFIT_INTERVAL_NIGHTS,
) -> str:
    """返回 "skip" | "refit" | "fold_in"(§3.2.3 决策表,全确定性)。"""
    if l2_count < min_l2_for_vectors:
        return "skip"
    if not has_basis:
        return "refit"
    if (
        new_token_ratio >= new_token_ratio_threshold
        or nights_since_refit >= refit_interval_nights
    ):
        return "refit"
    return "fold_in"
