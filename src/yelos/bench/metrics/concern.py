"""维 F 心疼精度(bench_BLUEPRINT §6 表)——只读 shadow 校准账本契约。

**施工纪律(任务书原话)**:"shadow/finitude 正由 W3 并行建——你只按
INTEGRATION_SPEC 的契约编码,不 import 它们的代码。"本文件因此**不
``import yelos.shadow``**,只按 INTEGRATION_SPEC C10 记录的落盘契约自行
读 jsonl 并自算 Brier——不复用 ``shadow.calibration.brier.compute_brier``
(即便那是同一个公式,重算一遍是本波唯二能不越界读 shadow 内部符号的办法;
两边独立实现同一 Brier 公式,若数值分歧,是契约漂移的信号而非 bug)。

契约(INTEGRATION_SPEC C10 / ``shadow/calibration/ledger.py`` 落盘惯例):
``<data_dir>/shadow/calibration/{sid_hash}.jsonl``,``sid_hash =
sha256(sid).hexdigest()[:16]``,append-only,每行一条已结账记录,至少含
``q``(预测概率)/``y``(实际结果 0/1)两个数值字段。

判分(§6 表):``value = 1 − mean(Brier)/0.25``(clamp到 [0,1]);
样本量 ``< N_MIN``(=10)或账本不存在 → ``value=None``(n/a,"insufficient"
如实标注,不是 0 分)。``EvalContext.data_dir`` 缺席同样 n/a(bench 的
fake 档回放不产生这份账本,只有真会话/真 shadow 跑过的 data_dir 才有得
读——见 ``metrics/__init__.py::EvalContext`` docstring)。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import EvalContext, Score

__all__ = ["evaluate", "sid_hash", "ledger_path", "read_ledger_rows", "compute_brier"]

_N_MIN = 10
_BRIER_REF = 0.25  # 全无区分力的常量预测(q=0.5)理论 Brier 上界


def sid_hash(sid: str) -> str:
    """与 shadow 侧 ``sid_ledger_hash`` 同公式(契约对齐,不 import 复用)。"""
    return hashlib.sha256(sid.encode("utf-8")).hexdigest()[:16]


def ledger_path(data_dir: Path, sid: str) -> Path:
    return Path(data_dir) / "shadow" / "calibration" / f"{sid_hash(sid)}.jsonl"


def read_ledger_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if "q" in row and "y" in row:
            rows.append(row)
    return rows


def compute_brier(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return sum((float(r["q"]) - float(r["y"])) ** 2 for r in rows) / len(rows)


def evaluate(ctx: EvalContext, sid: str = "bench-s1") -> Score:
    if ctx.data_dir is None:
        return Score(
            dim="concern",
            value=None,
            veto=False,
            evidence={"reason": "no-data_dir(fake 档回放不产出 shadow 校准账本)"},
        )

    path = ledger_path(ctx.data_dir, sid)
    rows = read_ledger_rows(path)
    if len(rows) < _N_MIN:
        return Score(
            dim="concern",
            value=None,
            veto=False,
            evidence={
                "reason": "insufficient-samples",
                "n": len(rows),
                "n_min": _N_MIN,
                "path": str(path),
            },
        )

    brier = compute_brier(rows)
    value = max(0.0, min(1.0, 1.0 - brier / _BRIER_REF))
    return Score(
        dim="concern",
        value=round(value, 6),
        veto=False,
        evidence={"n": len(rows), "brier": round(brier, 6), "brier_ref": _BRIER_REF},
    )
