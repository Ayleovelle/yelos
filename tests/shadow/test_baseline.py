"""test_baseline.py:三窗分位 sketch 正确性 / EWMA 方差 / 首拍 legacy 退化 /
rollover 推进 / 重启无损(binding 往返)(蓝图 §11)。
"""

from __future__ import annotations

import json

import pytest

from yelos.shadow.baseline import drift, legacy, rolling
from yelos.shadow.binding_v2 import default_shadow_block


def test_first_three_ticks_use_legacy_anchor() -> None:
    ch = default_shadow_block()["baselines"]["warmth"]
    rolling.observe_tick(ch, 0.7)
    assert ch["day"] == 0.7
    rolling.observe_tick(ch, 0.5)
    assert ch["day"] == 0.7  # 仍是首拍锚点(day_ticks<=3)
    rolling.observe_tick(ch, 0.6)
    assert ch["day"] == 0.7
    rolling.observe_tick(ch, 0.9)
    assert ch["day"] != 0.7  # 第 4 拍起切换到 EWMA


def test_ewma_variance_increases_with_noisy_observations() -> None:
    calm = default_shadow_block()["baselines"]["pressure"]
    for _ in range(10):
        rolling.observe_tick(calm, 0.5)
    noisy = default_shadow_block()["baselines"]["pressure"]
    seq = [0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9]
    for v in seq:
        rolling.observe_tick(noisy, v)
    assert noisy["ewma_var"] > calm["ewma_var"]


def test_rollover_pushes_day_value_into_week_and_month() -> None:
    ch = default_shadow_block()["baselines"]["warmth"]
    rolling.observe_tick(ch, 0.8)
    rolling.rollover_day(ch, "2026-07-11", "warmth")
    assert ch["week"] is not None
    assert ch["month"] is not None
    assert ch["day"] is None  # 翻转后 day 重置,待下一天首拍重建


def test_rollover_is_idempotent_for_same_day_key() -> None:
    ch = default_shadow_block()["baselines"]["warmth"]
    rolling.observe_tick(ch, 0.8)
    rolling.rollover_day(ch, "2026-07-11", "warmth")
    week_after_first = ch["week"]
    rolling.rollover_day(ch, "2026-07-11", "warmth")  # 同 day_key 重复调用
    assert ch["week"] == week_after_first


def test_get_baseline_view_returns_dispersion_in_unit_interval() -> None:
    ch = default_shadow_block()["baselines"]["pressure"]
    rolling.observe_tick(ch, 0.9)
    rolling.rollover_day(ch, "d1", "pressure")
    rolling.observe_tick(ch, 0.1)
    view = rolling.get_baseline_view(ch, "pressure")
    assert 0.0 <= view.dispersion <= 1.0


def test_channel_drift_none_when_missing() -> None:
    assert drift.channel_drift(None, 0.5, 1.0) == 0.0
    assert drift.channel_drift(0.5, None, 1.0) == 0.0


def test_family_dispersion_needs_at_least_two_samples() -> None:
    assert drift.family_dispersion(0.5, None, None, 1.0) == 0.0
    assert drift.family_dispersion(0.2, 0.8, None, 1.0) == pytest.approx(0.6)


def test_legacy_single_point_prefers_anchor() -> None:
    ch = default_shadow_block()["baselines"]["warmth"]
    rolling.observe_tick(ch, 0.42)
    assert legacy.legacy_single_point(ch) == 0.42


def test_bootstrap_from_memory_only_applies_when_no_observation_yet() -> None:
    class FakeMemBaseline:
        typical_warmth = 0.77
        typical_pressure = 0.33
        familiarity = 0.5

    ch = default_shadow_block()["baselines"]["warmth"]
    legacy.bootstrap_from_memory(ch, "warmth", FakeMemBaseline())
    assert ch["day"] == 0.77

    rolling.observe_tick(ch, 0.1)  # 真实观测到达
    legacy.bootstrap_from_memory(ch, "warmth", FakeMemBaseline())  # 不应再覆盖
    assert ch["day"] == 0.1


def test_bootstrap_from_memory_none_is_noop() -> None:
    ch = default_shadow_block()["baselines"]["warmth"]
    legacy.bootstrap_from_memory(ch, "warmth", None)
    assert ch["day"] is None


def test_binding_roundtrip_survives_json(tmp_path) -> None:
    """重启无损:binding 结构可 json 往返,数值不变(不含 NaN/Infinity)。"""
    block = default_shadow_block()
    rolling.observe_tick(block["baselines"]["warmth"], 0.6)
    path = tmp_path / "b.json"
    path.write_text(json.dumps(block, ensure_ascii=False), encoding="utf-8")
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["baselines"]["warmth"]["day"] == block["baselines"]["warmth"]["day"]
    assert reloaded["schema"] == 2
