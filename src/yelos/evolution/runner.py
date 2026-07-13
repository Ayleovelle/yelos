"""runner.py 在整个架构中的位置:世代循环编排,CLI 与夜窗作业共用的唯一入口(蓝图 §2.1/T2/T6)。

时间入参化(core 纪律沿用,禁 ``time.time()``):调用方传 ``now_fn() -> float``
(epoch 秒),默认用 ``yelos.core.clock`` 的 ``Clock`` 协议实现注入,测试用
``bench.VirtualClock`` 或裸函数。

T2 单代守卫链(阶段 1-5,顺序不可调换,静态先于动态、动态先于适应度):
静态守卫 → 动态性质闸 → judge。全过 → 原子写 overlay + lineage 追加
accepted;任一步不过 → 只追加对应 verdict 的记录,不动 overlay。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .genome.registry import spec_for, validate_registry
from .guards.property_gate import run_property_gate
from .guards.static_check import check_mutation_set
from .lineage.ledger import (
    ACCEPTED,
    REJECTED_FITNESS,
    REJECTED_GUARD_PROPERTY,
    REJECTED_GUARD_STATIC,
    SKIPPED,
    LineageLedger,
)
from .lineage.records import ChangeEntry, LineageRecord
from .overlay import make_overlay_writer
from .selection.fitness import BenchHarness, evaluate
from .selection.judge import judge
from .variation import build_strategy


@dataclass(frozen=True)
class GenerationOutcome:
    gen: int
    verdict: str
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RunSummary:
    outcomes: tuple[GenerationOutcome, ...]
    final_gen: int


def _changes_between(parent: dict, candidate: dict) -> tuple[ChangeEntry, ...]:
    return tuple(
        ChangeEntry(key=k, before=parent.get(k), after=candidate[k])
        for k in sorted(candidate.keys())
        if parent.get(k) != candidate.get(k)
    )


def run_generations(
    config: object,
    n: int,
    *,
    now_fn,
    ledger: LineageLedger,
    overlay_path,
    velocity_bound: float = 0.05,
    online_weight: float = 0.0,
    strategy_name: str = "pattern_search",
    harness: BenchHarness | None = None,
    scenario: str = "default",
    accounting_stats: dict | None = None,
) -> RunSummary:
    """唯一世代循环入口。``harness=None`` 时(T6"bench 报告缺席")本调用
    对 ``n`` 全部代记 ``skipped`` 事件,不评估、不落地(诚实降级,不猜分)。
    """
    problems = validate_registry(config)
    if problems:
        # 注册表本身不一致(幽灵参数/默认值漂移)——不跑,交调用方处理告警。
        return RunSummary(outcomes=(), final_gen=_last_accepted_gen(ledger))

    outcomes: list[GenerationOutcome] = []
    strategy = build_strategy(strategy_name, velocity_bound)
    deployment_id = ledger.deployment_id()

    for _ in range(max(0, n)):
        current_gen = _last_accepted_gen(ledger)
        next_seq = _next_seq(ledger)
        parent = ledger.reconstruct(current_gen)

        if harness is None:
            record = LineageRecord(
                gen=next_seq,
                parent_gen=current_gen,
                ts=_iso_now(now_fn),
                deployment_id=deployment_id,
                strategy=strategy_name,
                changes=(),
                guard={"static": "skip", "property": "skip"},
                fitness={},
                incumbent_fitness=None,
                verdict=SKIPPED,
            )
            ledger.append(record)
            outcomes.append(
                GenerationOutcome(
                    gen=record.gen, verdict=SKIPPED, reasons=("no fitness source",)
                )
            )
            continue

        seed = deployment_id
        candidates = strategy.propose(parent, next_seq, seed)
        if not candidates:
            record = LineageRecord(
                gen=next_seq,
                parent_gen=current_gen,
                ts=_iso_now(now_fn),
                deployment_id=deployment_id,
                strategy=strategy_name,
                changes=(),
                guard={"static": "skip", "property": "skip"},
                fitness={},
                incumbent_fitness=None,
                verdict=SKIPPED,
            )
            ledger.append(record)
            outcomes.append(
                GenerationOutcome(
                    gen=record.gen, verdict=SKIPPED, reasons=("no candidate",)
                )
            )
            continue

        candidate = candidates[0]
        outcome = _run_one_generation(
            parent=parent,
            candidate=candidate,
            gen=next_seq,
            parent_gen=current_gen,
            deployment_id=deployment_id,
            strategy_name=strategy_name,
            velocity_bound=velocity_bound,
            online_weight=online_weight,
            harness=harness,
            scenario=scenario,
            accounting_stats=accounting_stats,
            ledger=ledger,
            overlay_path=overlay_path,
            now_fn=now_fn,
        )
        outcomes.append(outcome)

    return RunSummary(outcomes=tuple(outcomes), final_gen=_last_accepted_gen(ledger))


def _run_one_generation(
    *,
    parent: dict,
    candidate: dict,
    gen: int,
    parent_gen: int,
    deployment_id: str,
    strategy_name: str,
    velocity_bound: float,
    online_weight: float,
    harness: BenchHarness,
    scenario: str,
    accounting_stats: dict | None,
    ledger: LineageLedger,
    overlay_path,
    now_fn,
) -> GenerationOutcome:
    changes = _changes_between(parent, candidate)
    ts = _iso_now(now_fn)

    # T2 阶段 1-3:静态守卫。
    static_verdict = check_mutation_set(
        parent, candidate, velocity_bound=velocity_bound
    )
    if not static_verdict.ok:
        record = LineageRecord(
            gen=gen,
            parent_gen=parent_gen,
            ts=ts,
            deployment_id=deployment_id,
            strategy=strategy_name,
            changes=changes,
            guard={"static": ",".join(static_verdict.reasons), "property": "not_run"},
            fitness={},
            incumbent_fitness=None,
            verdict=REJECTED_GUARD_STATIC,
        )
        ledger.append(record)
        return GenerationOutcome(
            gen=gen, verdict=REJECTED_GUARD_STATIC, reasons=static_verdict.reasons
        )

    # T2 阶段 4:动态性质闸。
    property_verdict = run_property_gate(candidate)
    if not property_verdict.ok:
        record = LineageRecord(
            gen=gen,
            parent_gen=parent_gen,
            ts=ts,
            deployment_id=deployment_id,
            strategy=strategy_name,
            changes=changes,
            guard={"static": "ok", "property": ",".join(property_verdict.reasons)},
            fitness={},
            incumbent_fitness=None,
            verdict=REJECTED_GUARD_PROPERTY,
        )
        ledger.append(record)
        return GenerationOutcome(
            gen=gen, verdict=REJECTED_GUARD_PROPERTY, reasons=property_verdict.reasons
        )

    # T2 阶段 5:适应度 + judge。
    incumbent_fitness = evaluate(
        parent,
        harness,
        scenario,
        online_weight=online_weight,
        accounting_stats=accounting_stats,
    )
    candidate_fitness = evaluate(
        candidate,
        harness,
        scenario,
        online_weight=online_weight,
        accounting_stats=accounting_stats,
    )
    verdict = judge(candidate_fitness, incumbent_fitness, online_weight=online_weight)

    fitness_dict = {
        "bench_score": candidate_fitness.bench_score,
        "online_score": candidate_fitness.online_score,
        "sovereignty_violations": candidate_fitness.sovereignty_violations,
        "report": candidate_fitness.report_path,
    }

    if verdict == "reject":
        record = LineageRecord(
            gen=gen,
            parent_gen=parent_gen,
            ts=ts,
            deployment_id=deployment_id,
            strategy=strategy_name,
            changes=changes,
            guard={"static": "ok", "property": "ok"},
            fitness=fitness_dict,
            incumbent_fitness=incumbent_fitness.bench_score,
            verdict=REJECTED_FITNESS,
        )
        ledger.append(record)
        return GenerationOutcome(gen=gen, verdict=REJECTED_FITNESS)

    # accepted:原子写 overlay + lineage 追加。
    delta = {
        key: value
        for key, value in candidate.items()
        if spec_for(key) is not None and value != spec_for(key).default
    }
    writer = make_overlay_writer(overlay_path, deployment_id=deployment_id, gen=gen)
    writer(delta)

    record = LineageRecord(
        gen=gen,
        parent_gen=parent_gen,
        ts=ts,
        deployment_id=deployment_id,
        strategy=strategy_name,
        changes=changes,
        guard={"static": "ok", "property": "ok"},
        fitness=fitness_dict,
        incumbent_fitness=incumbent_fitness.bench_score,
        verdict=ACCEPTED,
    )
    ledger.append(record)
    return GenerationOutcome(gen=gen, verdict=ACCEPTED)


def _last_accepted_gen(ledger: LineageLedger) -> int:
    accepted = ledger.accepted_gens()
    return max(accepted) if accepted else 0


def _next_seq(ledger: LineageLedger) -> int:
    """下一条账本记录的序号(全记录计数,含 rejected/skipped,避免同代号
    碰撞——与 ``_last_accepted_gen``(仅 accepted)语义不同,故拆两个函数)。"""
    records = ledger.all_records()
    return (max((r.gen for r in records), default=0)) + 1


def _iso_now(now_fn) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(float(now_fn()), tz=timezone.utc).isoformat()


__all__ = ["run_generations", "RunSummary", "GenerationOutcome"]
