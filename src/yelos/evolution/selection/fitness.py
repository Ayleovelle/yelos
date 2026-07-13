"""selection/fitness.py 在整个架构中的位置:适应度装配(蓝图 §2.1/§5.3)。

适应度 = bench 分(读 M10 ``BenchReport`` 契约,§3 集成点)+ 在线信号
(默认权 0.0,读 arbiter.accounting 已落盘聚合统计,只读)。``evaluate`` 是
runner T2 阶段 5 的直接调用点(消费断言:篡改 harness 返回值 → verdict 翻
转,见 wiring manifest §5.1)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..genome.spec import Genome


class BenchHarness(Protocol):
    """§3.3 集成点的最小接口:只读 M10 报告契约,不改 bench。"""

    def evaluate(self, candidate: Genome, scenario: str) -> Any:
        """返回具备 ``overall``/``vetoes`` 属性或键的报告样对象。"""
        ...


@dataclass(frozen=True)
class Fitness:
    bench_score: float
    online_score: float
    sovereignty_violations: int
    report_path: str


def _get(obj: Any, name: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def total(fitness: Fitness, online_weight: float) -> float:
    """T3 的 total 公式:``bench_score + online_weight * online_score``。"""
    return fitness.bench_score + online_weight * fitness.online_score


def online_signal(accounting_stats: dict | None) -> float:
    """在线信号项(§5.3 集成点):只读 arbiter.accounting 已落盘聚合统计。

    默认权 0.0(§0.3-3,渐近贡献,如实标薄)。本函数把"swallowed 率越低越
    好、hysteresis 参数越稳越好"的方向性收敛成 [0,1] 的单一读数,供
    ``evaluate`` 在权重非零时消费(消费断言:``test_selection.py`` 以
    ``online_weight=1.0`` 断言其影响 verdict)。
    """
    if not accounting_stats:
        return 0.0
    swallowed_rate = float(accounting_stats.get("swallowed_rate", 0.0))
    theta_stability = float(accounting_stats.get("theta_stability", 1.0))
    swallowed_rate = min(max(swallowed_rate, 0.0), 1.0)
    theta_stability = min(max(theta_stability, 0.0), 1.0)
    return (1.0 - swallowed_rate) * 0.5 + theta_stability * 0.5


def evaluate(
    candidate: Genome,
    harness: BenchHarness,
    scenario: str,
    *,
    online_weight: float = 0.0,
    accounting_stats: dict | None = None,
) -> Fitness:
    report = harness.evaluate(candidate, scenario)
    overall = _get(report, "overall", 0.0)
    bench_score = float(overall) if isinstance(overall, (int, float)) else 0.0
    vetoes = _get(report, "vetoes", [])
    sovereignty_violations = len(vetoes) if isinstance(vetoes, (list, tuple)) else 0
    report_path = str(_get(report, "report_path", ""))
    online_score = online_signal(accounting_stats) if online_weight else 0.0
    return Fitness(
        bench_score=bench_score,
        online_score=online_score,
        sovereignty_violations=sovereignty_violations,
        report_path=report_path,
    )


__all__ = ["BenchHarness", "Fitness", "evaluate", "total", "online_signal"]
