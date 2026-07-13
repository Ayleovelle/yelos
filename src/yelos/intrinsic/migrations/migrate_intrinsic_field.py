"""migrations/migrate_intrinsic_field.py 在整个架构中的位置:X10 结构迁移(§2.1/§6.4)。

v0.1 record 顶层散字段 `dream.{count,night_of,pending}` + `daily.dream_delivered`
→ 收编进 `intrinsic_field.dream.{count,night_of,pending,delivered_today}`,
同时给每条 record 初始化 `intrinsic_field` 全块(phi 中性态 / circadian 冷
启动 / policy_name=threshold / policy_state={})。

**只增不删**:legacy 顶层 `dream` 键与 `daily.dream_delivered` 原样保留
(不删除,呼应 shadow v2 迁移对 `concern_state` 的处置手法,§2.1),供 v0.1
兼容与回滚;迁移后运行时应只读写 `intrinsic_field.dream`(接线任务职责,
不在本脚本内)。

**幂等**:已有 `intrinsic_field` 块的 record 直接跳过。**原子写**:tmp +
os.replace;迁移前若无 `.premigrate.bak` 备份则先备份一次。

**X10 对表核对(finitude EXCLUDED 表)**:finitude(W3 未生)的 EXCLUDED 字段
表需把 `dream.pending`/`dream.night_of`/`dream.count`(以及新增的
`intrinsic_field.dream.*`)列为跨世不重置豁免或与年轮记账无关的字段——
本迁移脚本只按 intrinsic_BLUEPRINT §2.1 备契约,不代 finitude 落地该表,
留给 W3 对表核实(见模块任务书"先按 spec §2.1 备契约"要求)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from ..circadian.phase_learn import DEFAULT_MU_MIN

DEFAULT_PHI = [0.2, 0.2, 0.2, 0.0]


def _neutral_intrinsic_field(record: dict[str, Any]) -> dict[str, Any]:
    legacy_dream = record.get("dream") or {}
    legacy_daily = record.get("daily") or {}
    return {
        "phi": list(DEFAULT_PHI),
        "last_step_ts": float(record.get("born_at", 0.0) or 0.0),
        "circadian": {"mu_min": DEFAULT_MU_MIN, "kappa": 0.0, "n_obs": 0},
        "policy_name": "threshold",
        "policy_state": {},
        "dream": {
            "count": int(legacy_dream.get("count", 0) or 0),
            "night_of": legacy_dream.get("night_of") or None,
            "pending": bool(legacy_dream.get("pending", False)),
            "delivered_today": bool(legacy_daily.get("dream_delivered", False)),
            "residue": None,
        },
    }


def migrate_record(record: dict[str, Any]) -> bool:
    """单条 record 原地迁移;已迁移(有 `intrinsic_field`)返回 False(跳过)。"""
    if "intrinsic_field" in record:
        return False
    record["intrinsic_field"] = _neutral_intrinsic_field(record)
    return True


def migrate_bindings_file(path: str | Path) -> dict[str, int]:
    """迁移一个 bindings.json 文件;返回 {"total":n,"migrated":m,"skipped":k}。"""
    path = Path(path)
    if not path.exists():
        return {"total": 0, "migrated": 0, "skipped": 0}

    raw = path.read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: bindings.json 顶层应为 dict,实际 {type(data)!r}")

    backup = path.with_name(path.name + ".premigrate.bak")
    if not backup.exists():
        backup.write_text(raw, encoding="utf-8")

    migrated = 0
    skipped = 0
    for record in data.values():
        if not isinstance(record, dict):
            continue
        if migrate_record(record):
            migrated += 1
        else:
            skipped += 1

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)

    return {"total": migrated + skipped, "migrated": migrated, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="迁移 bindings.json:dream 散字段收编进 intrinsic_field.dream(X10)。"
    )
    parser.add_argument("bindings_path", help="bindings.json 的路径")
    args = parser.parse_args(argv)

    report = migrate_bindings_file(args.bindings_path)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["migrate_record", "migrate_bindings_file", "main"]
