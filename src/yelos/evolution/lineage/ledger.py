"""lineage/ledger.py 在整个架构中的位置:追加式谱系账本 + reconstruct + rollback(蓝图 §2.1/A4)。

追加写单行 flush+fsync(同 ``persistence.PlasticityLedger`` 纪律,§6.1
persistence 原子写)——"作业中途 kill 再跑"断点安全:半写不会产生半行,坏行
在读侧被跳过并告警(T4 表)。

**实现选择(如实记,交付说明重复)**:蓝图 §2.1 把 ``append``/``reconstruct``/
``rollback``/``current_provenance`` 写作模块级自由函数;本实现包成
``LineageLedger`` 类(持 ``path``),因为账本路径随 ``data_dir`` 而非全局
唯一,自由函数会被迫用隐式全局态或每次传 path——类持有路径更利于测试
(多账本互不干扰)与依赖注入(runner 显式传入实例)。对外行为与签名意图
逐条对齐,只是调用形态从 ``module.append(x)`` 变成 ``ledger.append(x)``。
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from ..genome.registry import hatch_genome, spec_for
from ..genome.spec import Genome
from .records import LineageRecord

ACCEPTED = "accepted"
REJECTED_GUARD_STATIC = "rejected_guard_static"
REJECTED_GUARD_PROPERTY = "rejected_guard_property"
REJECTED_FITNESS = "rejected_fitness"
ROLLBACK = "rollback"
SKIPPED = "skipped"
CORRUPTION = "corruption"


class LineageIntegrityError(RuntimeError):
    """``reconstruct``/``rollback`` 在缺依赖行时的诚实失败(T4:不猜)。"""


class LineageLedger:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    # -- deployment_id(首条记录生成,落账本头,之后恒定,§2.2)-------------

    def deployment_id(self) -> str:
        records, _ = self._read_all()
        if records:
            return records[0].deployment_id
        return uuid.uuid4().hex

    # -- 追加写(原子单行,同 PlasticityLedger 纪律)-----------------------

    def append(self, record: LineageRecord) -> None:
        line = json.dumps(record.to_dict(), ensure_ascii=False) + "\n"
        fd = os.open(self._path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    # -- 读(坏行跳过并计数告警,T4)----------------------------------------

    def _read_all(self) -> tuple[list[LineageRecord], int]:
        if not self._path.exists():
            return [], 0
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return [], 0
        records: list[LineageRecord] = []
        bad_lines = 0
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                records.append(LineageRecord.from_dict(payload))
            except (ValueError, KeyError, TypeError):
                bad_lines += 1
                continue
        return records, bad_lines

    def all_records(self) -> list[LineageRecord]:
        records, _ = self._read_all()
        return records

    def accepted_gens(self) -> list[int]:
        return [r.gen for r in self.all_records() if r.verdict == ACCEPTED]

    # -- A4 回滚完备性 ----------------------------------------------------

    def reconstruct(self, gen: int) -> Genome:  # EVO-A4
        """gen=0 → hatch 默认。否则重放 gen 0..gen 的 accepted 变更链;
        缺某代 accepted 记录 → 诚实拒(``LineageIntegrityError``),不猜。
        """
        genome = dict(hatch_genome())
        if gen == 0:
            return genome
        accepted_by_gen = {
            r.gen: r for r in self.all_records() if r.verdict == ACCEPTED
        }
        # 按 parent_gen 反向链回溯到 0(hatch),而非假设"每个整数序号都有
        # accepted 行"——账本 gen 是全记录(含 rejected/skipped)的单调序号,
        # 中间夹杂非 accepted 序号是正常的,不算依赖缺失;真正的缺失是
        # "链上某一环的 accepted 记录本身不存在/被删"(T4:diff 行损坏)。
        chain: list[LineageRecord] = []
        cursor = gen
        seen: set[int] = set()
        while cursor != 0:
            if cursor in seen:
                raise LineageIntegrityError(
                    f"cannot reconstruct gen={gen}: cyclic parent_gen chain at {cursor}"
                )
            seen.add(cursor)
            record = accepted_by_gen.get(cursor)
            if record is None:
                raise LineageIntegrityError(
                    f"cannot reconstruct gen={gen}: missing accepted record for gen={cursor}"
                )
            chain.append(record)
            cursor = record.parent_gen if record.parent_gen is not None else 0
        for record in reversed(chain):
            for change in record.changes:
                genome[change.key] = change.after
        return genome

    def rollback(self, gen: int, overlay_writer, *, now_fn=None) -> Path:  # EVO-A4
        """重建 ``gen`` 的 overlay 并原子写盘,账本追加一条 rollback 记录。

        ``overlay_writer(values: dict) -> Path``:由调用方(runner/CLI)注入
        的原子写函数(overlay.py),ledger 不直接依赖 overlay 模块以保持
        子包依赖方向无环(guards/lineage 不 import overlay,overlay 反向
        依赖 lineage 读)。``now_fn``:时间入参化(core 纪律沿用,禁
        ``time.time()``);未传时退化为墙钟(仅供未接线的最小可跑场景/
        CLI 边界使用,真实部署应始终传入)。
        """
        accepted = set(self.accepted_gens())
        if gen != 0 and gen not in accepted:
            raise LineageIntegrityError(
                f"gen={gen} is not an accepted generation; "
                f"available: {sorted(accepted)}"
            )
        genome = self.reconstruct(gen)
        delta = {
            key: value
            for key, value in genome.items()
            if spec_for(key) is not None and value != spec_for(key).default
        }
        path = overlay_writer(delta)

        latest_gen = max([r.gen for r in self.all_records()], default=gen) + 1
        record = LineageRecord(
            gen=latest_gen,
            parent_gen=None,
            ts=_iso_now(now_fn),
            deployment_id=self.deployment_id(),
            strategy="rollback",
            changes=(),
            guard={"static": "ok", "property": "ok"},
            fitness={},
            incumbent_fitness=None,
            verdict=ROLLBACK,
            to_gen=gen,
        )
        self.append(record)
        return path

    def current_provenance(self) -> dict[str, str]:
        """key -> "hatch" | "gen:N"(§2.1,溯源完备,A4 推论)。"""
        provenance: dict[str, str] = {
            key: "hatch" for key in (spec_for(k).key for k in _all_keys())
        }
        for record in self.all_records():
            if record.verdict != ACCEPTED:
                continue
            for change in record.changes:
                provenance[change.key] = f"gen:{record.gen}"
        return provenance


def _all_keys() -> list[str]:
    from ..genome.registry import REGISTRY

    return [spec.key for spec in REGISTRY]


def _iso_now(now_fn=None) -> str:
    """记录时间戳的显示格式;不参与任何确定性判断(纯展示)。``now_fn``
    未提供时退化为墙钟(仅 CLI 边界/未接线最小场景使用,同 ``bench.
    RealClock`` 的合法落点;runner 内部路径恒显式传入 ``now_fn``)。
    """
    from datetime import datetime, timezone

    if now_fn is not None:
        return datetime.fromtimestamp(float(now_fn()), tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "LineageLedger",
    "LineageIntegrityError",
    "ACCEPTED",
    "REJECTED_GUARD_STATIC",
    "REJECTED_GUARD_PROPERTY",
    "REJECTED_FITNESS",
    "ROLLBACK",
    "SKIPPED",
    "CORRUPTION",
]
