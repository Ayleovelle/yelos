"""lineage/records.py 在整个架构中的位置:LineageRecord schema(蓝图 §3.3)。"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ChangeEntry:
    key: str
    before: object
    after: object


@dataclass(frozen=True)
class LineageRecord:
    """一条谱系账本记录(§3.3)。被拒代 / rollback 记录同 schema,``verdict``
    区分种类:``accepted`` / ``rejected_guard_static`` /
    ``rejected_guard_property`` / ``rejected_fitness`` / ``rollback`` /
    ``skipped`` / ``corruption``。"""

    gen: int
    parent_gen: int | None
    ts: str
    deployment_id: str
    strategy: str
    changes: tuple[ChangeEntry, ...]
    guard: dict
    fitness: dict
    incumbent_fitness: float | None
    verdict: str
    to_gen: int | None = None  # rollback 记录专用

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["changes"] = [asdict(c) for c in self.changes]
        return payload

    @staticmethod
    def from_dict(payload: dict) -> "LineageRecord":
        changes = tuple(
            ChangeEntry(key=c["key"], before=c["before"], after=c["after"])
            for c in payload.get("changes", [])
        )
        return LineageRecord(
            gen=int(payload["gen"]),
            parent_gen=payload.get("parent_gen"),
            ts=str(payload.get("ts", "")),
            deployment_id=str(payload.get("deployment_id", "")),
            strategy=str(payload.get("strategy", "")),
            changes=changes,
            guard=dict(payload.get("guard", {})),
            fitness=dict(payload.get("fitness", {})),
            incumbent_fitness=payload.get("incumbent_fitness"),
            verdict=str(payload.get("verdict", "")),
            to_gen=payload.get("to_gen"),
        )


__all__ = ["ChangeEntry", "LineageRecord"]
