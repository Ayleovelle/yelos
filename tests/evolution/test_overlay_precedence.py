"""test_overlay_precedence.py:T1/D-E2/D-E3——opt-in 门控 + overlay schema 弃用不 raise。"""

from __future__ import annotations

import json

from yelos.evolution import build_evolution
from yelos.evolution.overlay import apply_overlay, load_overlay, save_overlay


def test_disabled_by_default_returns_none(base_config, tmp_path):
    cfg = dict(base_config)
    cfg["evolution_enabled"] = False
    assert build_evolution(cfg, data_dir=tmp_path) is None


def test_disabled_does_not_touch_filesystem(base_config, tmp_path):
    """D-E3:enabled=false 不读 overlay 文件——以文件系统探针证:即便 overlay
    文件存在且内容合法,disabled 装配也不建对象、不产生任何新文件。"""
    overlay_path = tmp_path / "evolution.overlay.json"
    save_overlay(
        overlay_path, deployment_id="dep", gen=1, values={"intrinsic_daily_cap": 4}
    )
    before = set(tmp_path.rglob("*"))

    cfg = dict(base_config)
    cfg["evolution_enabled"] = False
    result = build_evolution(cfg, data_dir=tmp_path)

    after = set(tmp_path.rglob("*"))
    assert result is None
    assert before == after  # 未新增任何文件/目录(evolution/ 子目录也不建)


def test_enabled_builds_object_and_creates_dirs(base_config, tmp_path):
    evo = build_evolution(base_config, data_dir=tmp_path)
    assert evo is not None
    assert evo.overlay_path.parent.exists()


def test_corrupt_overlay_falls_back_to_hatch_default_no_raise(tmp_path):
    overlay_path = tmp_path / "evolution.overlay.json"
    overlay_path.write_text("{not json", encoding="utf-8")
    assert load_overlay(overlay_path) is None
    genome = apply_overlay(None)  # 调用方看到 None 后回退 hatch 默认
    from yelos.evolution.genome.registry import hatch_genome

    assert genome == hatch_genome()


def test_overlay_schema_mismatch_treated_as_absent(tmp_path):
    overlay_path = tmp_path / "evolution.overlay.json"
    overlay_path.write_text(json.dumps({"schema": 999, "values": {}}), encoding="utf-8")
    assert load_overlay(overlay_path) is None


def test_overlay_ignores_iron_and_ghost_keys_even_if_present():
    """损坏的 overlay(手工篡改)不能撬动铁域——apply_overlay 第二道防线。"""
    genome = apply_overlay(
        {"arbiter_min_gap_seconds": 1, "ghost_key": 1, "intrinsic_daily_cap": 4}
    )
    assert genome["arbiter_min_gap_seconds"] == 180
    assert "ghost_key" not in genome
    assert genome["intrinsic_daily_cap"] == 4


def test_overlay_values_only_store_delta_from_hatch_default():
    from yelos.evolution.genome.registry import hatch_genome

    genome = hatch_genome()
    assert apply_overlay({}) == genome
