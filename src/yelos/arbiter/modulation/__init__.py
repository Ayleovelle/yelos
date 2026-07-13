"""modulation 子包:曲线注册表。"""

from __future__ import annotations

from .base import ModulationCurve, Thresholds
from .logistic import LOGISTIC_CURVE, LogisticCurve
from .step import STEP_CURVE, StepCurve

CURVE_REGISTRY: dict[str, ModulationCurve] = {
    "step": STEP_CURVE,
    "logistic": LOGISTIC_CURVE,
}

__all__ = [
    "ModulationCurve",
    "Thresholds",
    "StepCurve",
    "STEP_CURVE",
    "LogisticCurve",
    "LOGISTIC_CURVE",
    "CURVE_REGISTRY",
]
