"""test_determinism_registry_coverage.py:evo 键型登记进 primal/determinism.py(§2.2/§3.9,X12)。"""

from __future__ import annotations

from yelos.primal.determinism import KEY_REGISTRY, h_byte


def test_evo_key_type_registered():
    assert "evo" in KEY_REGISTRY
    entry = KEY_REGISTRY["evo"]
    assert "deployment_id" in entry["format"]
    assert "gen" in entry["format"]


def test_evo_hash_unit_uses_registered_key_format():
    from yelos.evolution.variation.base import evo_hash_unit, evo_tie_hash_unit

    unit = evo_hash_unit("dep-1", 3, "pattern_search", "intrinsic_daily_cap")
    assert 0.0 <= unit < 1.0
    # 与手工按注册格式拼 key 调 h_byte 的结果一致(接线可证)。
    expected = h_byte("evo|dep-1|3|pattern_search|intrinsic_daily_cap") / 256.0
    assert unit == expected

    tie = evo_tie_hash_unit("dep-1", 3)
    assert tie == h_byte("evo|dep-1|3|tie") / 256.0
