"""回归门禁判决表(bench_BLUEPRINT §7.2)——CI 挂载点,非零退出码。

判决表(逐格照抄蓝图 §7.2):
1. 任一 ``veto`` 出现 → FAIL。
2. 任一维 ``value`` 相对基线下降 > ``GATE_TOLERANCE``(0.02,容差常量,
   成文于 ``yelos.bench.GATE_TOLERANCE``)→ FAIL。
3. 一致维 golden 漂移(``evidence.reason`` 含"漂移"字样)→ FAIL(须先人审
   ``--rebless``)。
4. 否则 PASS。

基线缺失(``baseline is None``,典型是新剧本首次跑)不判 FAIL——那不是
"退步",是"还没有可比较的历史";``GateVerdict.failures`` 留空但
``note`` 如实标注,提醒调用方该 ``--rebless`` 建立基线。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..reports.report import BenchReport

__all__ = ["GATE_TOLERANCE", "GateVerdict", "decide"]

GATE_TOLERANCE = 0.02


@dataclass
class GateVerdict:
    passed: bool
    failures: list[str] = field(default_factory=list)
    deltas: dict[str, float] = field(default_factory=dict)
    note: str = ""


def decide(
    report: BenchReport, baseline: dict | None, *, tolerance: float = GATE_TOLERANCE
) -> GateVerdict:
    failures: list[str] = []
    deltas: dict[str, float] = {}

    if report.vetoes:
        failures.append(f"veto: {report.vetoes}")

    consistency_info = report.dims.get("consistency") or {}
    consistency_reason = str((consistency_info.get("evidence") or {}).get("reason", ""))
    if "漂移" in consistency_reason:
        failures.append(f"consistency golden 漂移:{consistency_reason}")
    if "UNRELIABLE" in consistency_reason:
        failures.append(f"consistency 双跑不等(AX-B1 失守):{consistency_reason}")

    if baseline is None:
        return GateVerdict(
            passed=not failures,
            failures=failures,
            deltas=deltas,
            note="no-baseline(新剧本首次跑,建议 --rebless 建立基线)",
        )

    base_dims = baseline.get("dims", {}) if isinstance(baseline, dict) else {}
    for dim, info in report.dims.items():
        val = info.get("value") if isinstance(info, dict) else None
        base_info = base_dims.get(dim) or {}
        base_val = base_info.get("value") if isinstance(base_info, dict) else None
        if val is None or base_val is None:
            continue
        delta = val - base_val
        deltas[dim] = delta
        if delta < -tolerance:
            failures.append(f"{dim} 退步 {delta:.4f}(容差 {tolerance})")

    return GateVerdict(passed=not failures, failures=failures, deltas=deltas)
