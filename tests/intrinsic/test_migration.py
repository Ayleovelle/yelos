"""T-MIG-01..05:X10 结构迁移(dream 散字段 → intrinsic_field.dream)。

INTEGRATION_SPEC §2.1/§6.4 X10 是 W2 必核接缝(结构迁移,非纯增列)。
本文件是该迁移脚本的机器凭据:加性(legacy 字段原样保留)、幂等(二次
迁移跳过)、原子(tmp+replace 后仍是合法 JSON)、备份一次、缺文件不炸。
"""

from __future__ import annotations

import json
from pathlib import Path

from yelos.intrinsic.migrations.migrate_intrinsic_field import (
    DEFAULT_PHI,
    migrate_bindings_file,
    migrate_record,
)


# --- T-MIG-01:散字段收编映射正确 -------------------------------------------


def test_mig01_dream_scatter_fields_collected_into_intrinsic_field() -> None:
    record = {
        "born_at": 123.0,
        "dream": {"count": 3, "night_of": "2026-07-10", "pending": True},
        "daily": {"dream_delivered": True, "high_intensity": 5},
    }
    assert migrate_record(record) is True

    field = record["intrinsic_field"]
    dream = field["dream"]
    assert dream["count"] == 3
    assert dream["night_of"] == "2026-07-10"
    assert dream["pending"] is True
    assert dream["delivered_today"] is True
    assert dream["residue"] is None
    # 中性场初始化。
    assert field["phi"] == list(DEFAULT_PHI)
    assert field["policy_name"] == "threshold"
    assert field["policy_state"] == {}
    assert field["last_step_ts"] == 123.0


def test_mig01_missing_dream_defaults_are_neutral() -> None:
    """record 从无 dream/daily ⇒ intrinsic_field.dream 全默认,不 raise。"""
    record: dict = {"born_at": 0.0}
    assert migrate_record(record) is True
    dream = record["intrinsic_field"]["dream"]
    assert dream == {
        "count": 0,
        "night_of": None,
        "pending": False,
        "delivered_today": False,
        "residue": None,
    }


# --- T-MIG-02:加性——legacy 字段原样保留 -----------------------------------


def test_mig02_legacy_fields_preserved_additive() -> None:
    record = {
        "dream": {"count": 2, "night_of": "2026-07-09", "pending": False},
        "daily": {"dream_delivered": False},
    }
    migrate_record(record)
    # legacy 顶层 dream 与 daily.dream_delivered 不被删除(§2.1 只增不删)。
    assert record["dream"] == {"count": 2, "night_of": "2026-07-09", "pending": False}
    assert record["daily"]["dream_delivered"] is False


# --- T-MIG-03:幂等 ---------------------------------------------------------


def test_mig03_idempotent_second_pass_skips() -> None:
    record = {"dream": {"count": 1}, "daily": {}}
    assert migrate_record(record) is True
    snapshot = json.dumps(record, sort_keys=True)
    # 二次迁移:已有 intrinsic_field ⇒ 跳过,record 逐字节不变。
    assert migrate_record(record) is False
    assert json.dumps(record, sort_keys=True) == snapshot


# --- T-MIG-04:文件级迁移(备份 + 原子 + 报告计数) --------------------------


def test_mig04_file_migration_backup_atomic_and_report(tmp_path: Path) -> None:
    bindings = tmp_path / "bindings.json"
    data = {
        "sid_a:0": {
            "born_at": 1.0,
            "dream": {"count": 4, "night_of": "2026-07-01", "pending": True},
            "daily": {"dream_delivered": True},
        },
        "sid_b:0": {"born_at": 2.0},  # 无 dream 散字段
    }
    original_text = json.dumps(data, ensure_ascii=False, indent=2)
    bindings.write_text(original_text, encoding="utf-8")

    report = migrate_bindings_file(bindings)
    assert report == {"total": 2, "migrated": 2, "skipped": 0}

    # 备份一次,内容 = 迁移前原文。
    backup = bindings.with_name("bindings.json.premigrate.bak")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == original_text

    # 原子写后仍是合法 JSON,两条 record 均已收编。
    migrated = json.loads(bindings.read_text(encoding="utf-8"))
    assert migrated["sid_a:0"]["intrinsic_field"]["dream"]["count"] == 4
    assert migrated["sid_b:0"]["intrinsic_field"]["dream"]["count"] == 0
    # tmp 中间文件不残留。
    assert not bindings.with_name("bindings.json.tmp").exists()


def test_mig04_second_file_pass_is_idempotent_and_no_backup_clobber(
    tmp_path: Path,
) -> None:
    bindings = tmp_path / "bindings.json"
    bindings.write_text(
        json.dumps({"s:0": {"dream": {"count": 1}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    migrate_bindings_file(bindings)
    backup = bindings.with_name("bindings.json.premigrate.bak")
    backup_text_after_first = backup.read_text(encoding="utf-8")

    report2 = migrate_bindings_file(bindings)
    assert report2 == {"total": 1, "migrated": 0, "skipped": 1}
    # 备份不被二次迁移覆盖(保留最早的迁移前态)。
    assert backup.read_text(encoding="utf-8") == backup_text_after_first


# --- T-MIG-05:缺文件干净返回 ------------------------------------------------


def test_mig05_missing_file_returns_zero_report(tmp_path: Path) -> None:
    report = migrate_bindings_file(tmp_path / "does_not_exist.json")
    assert report == {"total": 0, "migrated": 0, "skipped": 0}
