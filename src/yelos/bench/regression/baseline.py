"""基线存取(bench_BLUEPRINT §7.2)——``experiments/bench/baselines/
{scenario_id}.json``,report 的裁剪副本(overall + per-dim + trace 哈希)。

重铸基线是显式命令(``python -m yelos.bench regress --rebless``,W4 CLI),
提交须附理由行——本文件的 ``save_baseline`` 强制要求 ``blessed_by``/
``reason`` 两个非空字符串参数,防止"顺手静默改基线"(§7.2"防无声漂移")。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..reports.report import BenchReport

__all__ = ["BASELINE_SCHEMA_VER", "baseline_path", "load_baseline", "save_baseline"]

BASELINE_SCHEMA_VER = 1
_DEFAULT_ROOT = Path("experiments") / "bench" / "baselines"


def baseline_path(scenario_id: str, root: Path | None = None) -> Path:
    base = Path(root) if root is not None else _DEFAULT_ROOT
    return base / f"{scenario_id}.json"


def load_baseline(path: Path) -> dict | None:
    path = Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_baseline(
    path: Path,
    report: BenchReport,
    *,
    blessed_by: str,
    reason: str,
    trace_digest: str = "",
) -> None:
    if not blessed_by.strip():
        raise ValueError("save_baseline: blessed_by 不得为空(§7.2 防无声漂移)")
    if not reason.strip():
        raise ValueError("save_baseline: reason 不得为空(§7.2 防无声漂移)")

    payload = {
        "schema_ver": BASELINE_SCHEMA_VER,
        "scenario_id": report.scenario_id,
        "blessed_by": blessed_by,
        "reason": reason,
        "overall": report.overall,
        "vetoes": list(report.vetoes),
        "dims": {
            dim: {"value": info.get("value")} for dim, info in report.dims.items()
        },
        "trace_digest": trace_digest,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
