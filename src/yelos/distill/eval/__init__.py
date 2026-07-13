"""eval/ 在整个架构中的位置:蒸馏侧质量与安全评测(蓝图 §1 D4 波)。

依赖图:``eval → runtime + corpus``(单向;runtime 不反向 import 本包,
见 ``runtime/rerank.py`` 头注)。
"""

from __future__ import annotations

from .fallback_probe import fallback_probe, probe_one
from .fidelity import fidelity_by_occasion, fidelity_js, js_divergence
from .report import EvalReport, distinct_n, write_report
from .violation import ViolationResult, violation_rate

__all__ = [
    "fallback_probe",
    "probe_one",
    "fidelity_by_occasion",
    "fidelity_js",
    "js_divergence",
    "EvalReport",
    "distinct_n",
    "write_report",
    "ViolationResult",
    "violation_rate",
]
