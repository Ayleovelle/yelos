"""migrate_binding_v1_to_v2.py 在整个架构中的位置:X3/X9 结构迁移执行体
(蓝图 §3.3,INTEGRATION_SPEC §2.1 第 5 行 / §6 X9)。

v0.1 record 现有 `shadow_baseline: {day, warmth}` 与
`concern_state: {armed, injected_day, injected_types}` 原地保留(不删除,
供 v0.1 兼容与回滚);本迁移只**新增** `shadow` 顶层块(`binding_v2.
default_shadow_block()`),并把旧 `concern_state.armed` 映射进
`shadow.hysteresis`:

- `concern_state.armed["pressure"]` 与 `concern_state.armed["damage"]` →
  `shadow.hysteresis.pressure_spike.armed`(damage 触发归 pressure_spike
  家族,蓝图 §6.2 明文"v0.1 的 damage 触发并入 pressure_spike 家族");
  两路取 AND(任一为 False 视为已 disarm,保守方向——旧数据里只要有一路
  记录着"已经 fire 过还没 re-arm",迁移后就不该让新系统立刻又 fire 一次)。
- `concern_state.armed["warmth_drop"]` → `shadow.hysteresis.warmth_drop.armed`
  (同名直迁)。
- `rhythm_break`/`withdrawal` 是 v2 新增检测器,v0.1 没有对应态,一律
  `armed=True`(冷启动,允许迁移当天即可正常判定,不视为"欠了历史")。
- `concern_state.injected_day`/`injected_types` 只读不迁移进
  `shadow.hysteresis.*.injected_day`(v0.1 的"当日已注入"语义与 v2
  per-ctype 语义不是同一件事:v0.1 只要任一类型今天注入过就整体记一个
  `injected_day`;v2 是每类型独立记账)。为避免"迁移当天全部类型误判为
  已注入过"这种比 v0.1 更保守都不对的行为,迁移后 `injected_day` 一律置
  空——迁移当天所有检测器都可以正常评估一次(不欠账、不超发:即使 v0.1
  当天已经 inject 过,v2 的迟滞状态机会在真正再次越阈时才 fire,不会无
  中生有触发)。

幂等:已有 `shadow` 块(`schema==2`)的 record 直接跳过。原子写:tmp +
os.replace;迁移前若无 `.premigrate.bak` 备份则先备份一次。`--dry-run`
模式先行(只打印报告,不落盘)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from ..binding_v2 import SCHEMA_VERSION, default_shadow_block

# concern_state.armed 键 -> shadow.hysteresis 归属检测器类型的映射表
# (蓝图 §3.3 迁移脚本条款 + §6.2 "damage 并入 pressure_spike 家族")。
_ARMED_KEY_TO_CTYPE: dict[str, str] = {
    "warmth_drop": "warmth_drop",
    "pressure": "pressure_spike",
    "damage": "pressure_spike",
}


def _migrated_hysteresis(legacy_concern_state: dict[str, Any]) -> dict[str, dict]:
    block = default_shadow_block()["hysteresis"]
    legacy_armed = legacy_concern_state.get("armed") or {}
    # pressure_spike 由 pressure/damage 两路 AND 合并(保守:任一 disarm 就 disarm)。
    ps_armed = True
    saw_ps_key = False
    for legacy_key in ("pressure", "damage"):
        if legacy_key in legacy_armed:
            saw_ps_key = True
            ps_armed = ps_armed and bool(legacy_armed[legacy_key])
    if saw_ps_key:
        block["pressure_spike"]["armed"] = ps_armed
    if "warmth_drop" in legacy_armed:
        block["warmth_drop"]["armed"] = bool(legacy_armed["warmth_drop"])
    # rhythm_break / withdrawal 保持默认 armed=True(冷启动,无 v0.1 对应态)。
    return block


def migrate_record(record: dict[str, Any]) -> bool:
    """单条 record 原地迁移;已迁移(`shadow.schema==2`)返回 False(跳过)。"""
    existing = record.get("shadow")
    if isinstance(existing, dict) and existing.get("schema") == SCHEMA_VERSION:
        return False

    block = default_shadow_block()
    legacy_concern_state = record.get("concern_state")
    if isinstance(legacy_concern_state, dict):
        block["hysteresis"] = _migrated_hysteresis(legacy_concern_state)

    # legacy shadow_baseline.warmth 可作 warmth 通道 day 值的迁移起点
    # (X6 冷启动兜底同精神:不让已有的一点观测白白作废)。
    legacy_baseline = record.get("shadow_baseline")
    if isinstance(legacy_baseline, dict) and legacy_baseline.get("warmth") is not None:
        try:
            warmth0 = float(legacy_baseline["warmth"])
        except (TypeError, ValueError):
            warmth0 = None
        if warmth0 is not None:
            block["baselines"]["warmth"]["day"] = warmth0
            block["baselines"]["warmth"]["ewma_mean"] = warmth0

    record["shadow"] = block
    return True


def migrate_bindings_file(path: str | Path, *, dry_run: bool = False) -> dict[str, int]:
    """迁移一个 bindings.json 文件;返回 {"total":n,"migrated":m,"skipped":k}。"""
    path = Path(path)
    if not path.exists():
        return {"total": 0, "migrated": 0, "skipped": 0}

    raw = path.read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: bindings.json top-level must be dict, got {type(data)!r}"
        )

    migrated = 0
    skipped = 0
    for record in data.values():
        if not isinstance(record, dict):
            continue
        if migrate_record(record):
            migrated += 1
        else:
            skipped += 1

    if dry_run:
        return {"total": migrated + skipped, "migrated": migrated, "skipped": skipped}

    backup = path.with_name(path.name + ".premigrate.bak")
    if not backup.exists():
        backup.write_text(raw, encoding="utf-8")

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)

    return {"total": migrated + skipped, "migrated": migrated, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate bindings.json: add shadow v2 block (concern_state kept in place)."
    )
    parser.add_argument("bindings_path", help="path to bindings.json")
    parser.add_argument(
        "--dry-run", action="store_true", help="report only, do not write"
    )
    args = parser.parse_args(argv)

    report = migrate_bindings_file(args.bindings_path, dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["migrate_record", "migrate_bindings_file", "main"]
