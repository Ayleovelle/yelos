"""BenchReport 装配(bench_BLUEPRINT §7.1,数据契约②)。

W4 版:``aux``(辅助观测,``metrics.internal.evaluate_aux``)与 ``curves``
(``intervention_rate``——克制维滚动窗口介入率曲线;``p_by_day``——每虚拟日
末 ``persist.p`` 值序列)本波接线到位。``schema_ver`` 恒为 1,字段只增不删
(§7.1"仓内消费者③(W5)evolution 读本契约"要求)。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..harness.trace import RunTrace
from ..metrics import Score, aggregate
from ..metrics.internal import evaluate_aux
from ..metrics.restraint import rolling_rates

__all__ = ["BenchReport", "build"]


@dataclass
class BenchReport:
    schema_ver: int
    scenario_id: str
    git_rev: str
    engine: str
    config_hash: str
    overall: float | str | None
    vetoes: list[str]
    dims: dict = field(default_factory=dict)
    aux: dict = field(default_factory=dict)
    curves: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _p_by_day(rows: list[dict]) -> list[float]:
    """每虚拟日末(该日最后一条带 persist 快照的行)``p`` 值序列。"""
    last_p_by_day: dict[int, float] = {}
    for row in rows:
        persist = row.get("persist")
        vday = row.get("vday")
        if not persist or "p" not in persist or vday is None:
            continue
        last_p_by_day[vday] = persist["p"]
    return [last_p_by_day[d] for d in sorted(last_p_by_day)]


def build(trace: RunTrace, scores: list[Score]) -> BenchReport:
    agg = aggregate(scores)
    header = trace.header
    return BenchReport(
        schema_ver=int(header.get("schema_ver", 1)),
        scenario_id=header.get("scenario_id", ""),
        git_rev=header.get("git_rev", "no-git"),
        engine=header.get("engine", "fake"),
        config_hash=header.get("config_hash", ""),
        overall=agg["overall"],
        vetoes=agg["vetoes"],
        dims=agg["per_dim"],
        aux=evaluate_aux(trace.rows),
        curves={
            "intervention_rate": rolling_rates(trace.rows),
            "p_by_day": _p_by_day(trace.rows),
        },
    )
