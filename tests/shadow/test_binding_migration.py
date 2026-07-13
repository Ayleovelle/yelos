"""test_binding_migration.py:v1→v2 幂等 / 旧字段保留 / 迁移后 v0.1 golden
不变 / 世代清零(蓝图 §11)。
"""

from __future__ import annotations

import json
from pathlib import Path

from yelos.shadow.binding_v2 import SCHEMA_VERSION, reset_for_new_incarnation
from yelos.shadow.migrations.migrate_binding_v1_to_v2 import (
    migrate_bindings_file,
    migrate_record,
)


def _v1_record() -> dict:
    return {
        "name": "test",
        "born_at": 0.0,
        "p": 1.0,
        "sealed": False,
        "daily": {"day": "2026-07-10", "high_intensity": 0},
        "concern_state": {
            "armed": {"pressure": False, "warmth_drop": True, "damage": False},
            "injected_day": "2026-07-10",
            "injected_types": ["pressure", "damage"],
        },
        "shadow_baseline": {"day": "2026-07-10", "warmth": 0.65},
    }


def test_migrate_record_adds_shadow_block_and_keeps_legacy() -> None:
    record = _v1_record()
    changed = migrate_record(record)
    assert changed is True
    assert record["shadow"]["schema"] == SCHEMA_VERSION
    # 原地保留(不删除)。
    assert "concern_state" in record
    assert "shadow_baseline" in record


def test_migrate_record_idempotent() -> None:
    record = _v1_record()
    migrate_record(record)
    first = json.dumps(record, sort_keys=True)
    changed_again = migrate_record(record)
    assert changed_again is False
    assert json.dumps(record, sort_keys=True) == first


def test_migrate_maps_pressure_and_damage_into_pressure_spike() -> None:
    record = _v1_record()
    migrate_record(record)
    # pressure=False AND damage=False -> pressure_spike.armed 应为 False(AND 合并)。
    assert record["shadow"]["hysteresis"]["pressure_spike"]["armed"] is False
    assert record["shadow"]["hysteresis"]["warmth_drop"]["armed"] is True


def test_migrate_new_detectors_start_armed() -> None:
    record = _v1_record()
    migrate_record(record)
    assert record["shadow"]["hysteresis"]["rhythm_break"]["armed"] is True
    assert record["shadow"]["hysteresis"]["withdrawal"]["armed"] is True


def test_migrate_bootstraps_warmth_baseline_from_legacy() -> None:
    record = _v1_record()
    migrate_record(record)
    assert record["shadow"]["baselines"]["warmth"]["day"] == 0.65


def test_migrate_already_v2_record_skipped() -> None:
    record = _v1_record()
    migrate_record(record)
    changed = migrate_record(record)
    assert changed is False


def test_migrate_bindings_file_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "bindings.json"
    data = {"alice": _v1_record(), "bob": _v1_record()}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    report = migrate_bindings_file(path)
    assert report == {"total": 2, "migrated": 2, "skipped": 0}
    assert (tmp_path / "bindings.json.premigrate.bak").exists()

    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["alice"]["shadow"]["schema"] == SCHEMA_VERSION

    report2 = migrate_bindings_file(path)
    assert report2 == {"total": 2, "migrated": 0, "skipped": 2}


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    path = tmp_path / "bindings.json"
    data = {"alice": _v1_record()}
    original = json.dumps(data, ensure_ascii=False)
    path.write_text(original, encoding="utf-8")

    migrate_bindings_file(path, dry_run=True)
    assert path.read_text(encoding="utf-8") == original
    assert not (tmp_path / "bindings.json.premigrate.bak").exists()


def test_migrate_missing_file_returns_zero_report(tmp_path: Path) -> None:
    report = migrate_bindings_file(tmp_path / "does_not_exist.json")
    assert report == {"total": 0, "migrated": 0, "skipped": 0}


def test_reset_for_new_incarnation_is_neutral_default_block() -> None:
    from yelos.shadow.binding_v2 import default_shadow_block

    assert reset_for_new_incarnation() == default_shadow_block()
