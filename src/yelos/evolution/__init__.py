"""evolution/ 在整个架构中的位置:默认关闭的 opt-in extra(蓝图 §0)。

组合根:``build_evolution(config) -> Evolution | None``——``evolution_
enabled=false``(默认)时 **不读 overlay 文件、不建对象**(T1 表,D-E3;
默认部署零感知在代码路径上成立)。核心五幕不 import 本包(§2 依赖方向,
单向:evolution 读别人的产物、写自己的 overlay)。

子包依赖方向(无环):
```
genome/variation/selection/guards/lineage → 仅 spec + registry + 标准库
overlay   → genome(读 REGISTRY 做合并校验)
runner    → genome/variation/selection/guards/lineage/overlay(唯一装配点)
viz       → lineage(只读账本)
__main__  → 本文件的组合根 + runner + viz
```
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config_defaults import (
    evolution_dir,
    evolution_enabled,
    evolution_min_days,
    evolution_online_weight,
    evolution_overlay_path,
    evolution_strategy,
    evolution_velocity_bound,
)
from .genome.registry import validate_registry
from .lineage.ledger import LineageLedger
from .overlay import apply_overlay, load_overlay, make_overlay_writer
from .runner import RunSummary, run_generations
from .selection.fitness import BenchHarness

__all__ = ["Evolution", "build_evolution"]


@dataclass
class Evolution:
    """已装配的 evolution 子系统句柄(仅在 opt-in 时存在)。"""

    data_dir: Path
    overlay_path: Path
    ledger: LineageLedger
    velocity_bound: float
    min_days: int
    online_weight: float
    strategy_name: str
    config: Any

    def current_genome(self) -> dict:
        """现行 genome(hatch 默认 + overlay 增量,D-E2 的"file/env 压过
        overlay"由 config 装配层负责,本方法只管 overlay 自身)。"""
        overlay = load_overlay(self.overlay_path)
        values = overlay.get("values") if overlay else None
        return apply_overlay(values)

    def run(
        self,
        n: int,
        *,
        now_fn,
        harness: BenchHarness | None = None,
        scenario: str = "default",
        accounting_stats: dict | None = None,
    ) -> RunSummary:
        return run_generations(
            self.config,
            n,
            now_fn=now_fn,
            ledger=self.ledger,
            overlay_path=self.overlay_path,
            velocity_bound=self.velocity_bound,
            online_weight=self.online_weight,
            strategy_name=self.strategy_name,
            harness=harness,
            scenario=scenario,
            accounting_stats=accounting_stats,
        )

    def rollback(self, gen: int, *, now_fn=None) -> Path:
        deployment_id = self.ledger.deployment_id()
        writer = make_overlay_writer(
            self.overlay_path, deployment_id=deployment_id, gen=gen
        )
        return self.ledger.rollback(gen, writer, now_fn=now_fn)

    def validate(self) -> list[str]:
        return validate_registry(self.config)


def build_evolution(
    config: Any, *, data_dir: str | Path | None = None
) -> Evolution | None:
    """组合根(T1 opt-in 门控)。``evolution_enabled=false``(默认)→ ``None``,
    不留半活对象、不读 overlay 文件(D-E3)。
    """
    if not evolution_enabled(config):
        return None

    resolved_dir = Path(data_dir) if data_dir is not None else _resolve_data_dir(config)
    evo_dir = evolution_dir(resolved_dir)
    evo_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = evolution_overlay_path(resolved_dir)
    ledger = LineageLedger(evo_dir / "lineage.jsonl")

    return Evolution(
        data_dir=resolved_dir,
        overlay_path=overlay_path,
        ledger=ledger,
        velocity_bound=evolution_velocity_bound(config),
        min_days=evolution_min_days(config),
        online_weight=evolution_online_weight(config),
        strategy_name=evolution_strategy(config),
        config=config,
    )


def _resolve_data_dir(config: Any) -> Path:
    if hasattr(config, "resolved_data_dir"):
        return config.resolved_data_dir()
    if isinstance(config, dict) and "data_dir" in config:
        import os

        return Path(os.path.expanduser(config["data_dir"])).resolve()
    return Path("~/.yelos").expanduser().resolve()
