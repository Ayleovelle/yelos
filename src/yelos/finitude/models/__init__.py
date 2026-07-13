"""models/__init__.py 在整个架构中的位置:MODEL_REGISTRY(finitude_BLUEPRINT §3.0)。

四模型的唯一注册表 + `build_model` 工厂(带未知 model_id 的保守回退)。域校验各模型
自己内部做防御式转换(见各模型 `_param`/`self.k` 等),这里只负责"认得 id 就造实例,
认不得就回退 linear 并显式报告 fallback=True"。
"""

from __future__ import annotations

from typing import Any

from .event_weighted import DEFAULT_PARAMS as EVENT_DEFAULT_PARAMS
from .event_weighted import EventWeighted
from .linear import DEFAULT_PARAMS as LINEAR_DEFAULT_PARAMS
from .linear import LinearDecay
from .protocol import AgingModel, DayFacts, SettleOutcome
from .reserve import DEFAULT_PARAMS as RESERVE_DEFAULT_PARAMS
from .reserve import ReserveModel
from .weibull import DEFAULT_PARAMS as WEIBULL_DEFAULT_PARAMS
from .weibull import WeibullWear

MODEL_REGISTRY: dict[str, type[AgingModel]] = {
    "linear": LinearDecay,
    "weibull": WeibullWear,
    "event": EventWeighted,
    "reserve": ReserveModel,
}

MODEL_DEFAULT_PARAMS: dict[str, dict[str, float]] = {
    "linear": LINEAR_DEFAULT_PARAMS,
    "weibull": WEIBULL_DEFAULT_PARAMS,
    "event": EVENT_DEFAULT_PARAMS,
    "reserve": RESERVE_DEFAULT_PARAMS,
}

DEFAULT_MODEL_ID = "linear"


def build_model(
    model_id: str, params: dict[str, Any] | None = None, fast: float = 1.0
) -> tuple[AgingModel, bool]:
    """按 model_id 造模型实例;未知 id → 保守回退 linear,返回 (model, fell_back)。

    §3.0:"未知 model_id(旧记录/手改)→ 保守回退 linear 并在 ledger settle 行记
    model_fallback: true(可考古,不静默吞)"。
    """
    cls = MODEL_REGISTRY.get(model_id)
    if cls is None:
        return LinearDecay(params=None, fast=fast), True
    return cls(params=params, fast=fast), False


__all__ = [
    "MODEL_REGISTRY",
    "MODEL_DEFAULT_PARAMS",
    "DEFAULT_MODEL_ID",
    "build_model",
    "AgingModel",
    "DayFacts",
    "SettleOutcome",
    "LinearDecay",
    "WeibullWear",
    "EventWeighted",
    "ReserveModel",
]
