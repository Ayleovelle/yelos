"""test_dayfacts_concern_source.py —— 接缝 X3 finitude 落笔侧读取断言
(INTEGRATION_SPEC §3.3)。

shadow 侧供数(`shadow.daily.concern_count`)由 `tests/shadow/
test_ledger_concern_field.py` 覆盖;本文件覆盖 finitude 侧的**读取来源切换**:
`dayfacts.extract_dayfacts` 必须以 `record["shadow"]["daily"]["concern_count"]`
为权威源,仅在该块缺失时回退 legacy `record["concern_state"]["injected_types"]`
——即"确实读 shadow,不读 legacy"。这正是 §3.3 裁定要求共享测试断言的那一条,
也是 dayfacts.py 模块 docstring 承诺存在的来源核对。
"""

from __future__ import annotations

from yelos.finitude.dayfacts import extract_dayfacts

_DAY = "2026-07-11"


def _daily(**over) -> dict:
    base = {"day": _DAY, "interacted": True, "high_intensity": 0}
    base.update(over)
    return base


def test_reads_shadow_concern_count_as_authority() -> None:
    """shadow.daily.concern_count 存在即取它(四检测器语义)。"""
    record = {
        "shadow": {"daily": {"day": _DAY, "concern_count": 3}},
        # legacy 故意给一个不同的值,证明没有被读到。
        "concern_state": {"injected_day": _DAY, "injected_types": ["a"]},
    }
    facts = extract_dayfacts(record, _daily(), lifespan_active_days=100)
    assert facts.concern_fired == 3  # shadow 的 3,不是 legacy 的 1


def test_prefers_shadow_over_legacy_when_both_present() -> None:
    """两源皆在且值不同:必须取 shadow,不取 legacy(mutation 式消费断言)。"""
    record = {
        "shadow": {"daily": {"day": _DAY, "concern_count": 0}},
        "concern_state": {"injected_day": _DAY, "injected_types": ["a", "b", "c"]},
    }
    facts = extract_dayfacts(record, _daily(), lifespan_active_days=100)
    # 若错读 legacy,会得到 3;权威源 shadow 是 0。
    assert facts.concern_fired == 0


def test_falls_back_to_legacy_when_shadow_block_absent() -> None:
    """shadow 块整体缺失(冷启动/未接线):回退 legacy concern_state。"""
    record = {
        "concern_state": {"injected_day": _DAY, "injected_types": ["a", "b"]},
    }
    facts = extract_dayfacts(record, _daily(), lifespan_active_days=100)
    assert facts.concern_fired == 2


def test_falls_back_when_shadow_daily_missing_concern_count() -> None:
    """shadow 块在但 daily 无 concern_count:视同缺失,回退 legacy。"""
    record = {
        "shadow": {"daily": {"day": _DAY}},
        "concern_state": {"injected_day": _DAY, "injected_types": ["x"]},
    }
    facts = extract_dayfacts(record, _daily(), lifespan_active_days=100)
    assert facts.concern_fired == 1


def test_legacy_ignored_when_injected_day_mismatch() -> None:
    """回退路径仍守 legacy 语义:injected_day 非当日则不计。"""
    record = {
        "concern_state": {"injected_day": "2026-07-10", "injected_types": ["x", "y"]},
    }
    facts = extract_dayfacts(record, _daily(), lifespan_active_days=100)
    assert facts.concern_fired == 0


def test_shadow_zero_is_authoritative_not_missing() -> None:
    """concern_count==0 是"今天没触发"的真实权威值,不该被当成缺失而回退 legacy。"""
    record = {
        "shadow": {"daily": {"day": _DAY, "concern_count": 0}},
        "concern_state": {"injected_day": _DAY, "injected_types": ["a", "b"]},
    }
    facts = extract_dayfacts(record, _daily(), lifespan_active_days=100)
    assert facts.concern_fired == 0


def test_shadow_bool_or_negative_treated_as_invalid() -> None:
    """脏态防御:concern_count 为 bool/负数时不采信,回退 legacy。"""
    record_bool = {
        "shadow": {"daily": {"day": _DAY, "concern_count": True}},
        "concern_state": {"injected_day": _DAY, "injected_types": ["a"]},
    }
    facts_bool = extract_dayfacts(record_bool, _daily(), lifespan_active_days=100)
    assert facts_bool.concern_fired == 1

    record_neg = {
        "shadow": {"daily": {"day": _DAY, "concern_count": -5}},
        "concern_state": {"injected_day": _DAY, "injected_types": ["a"]},
    }
    facts_neg = extract_dayfacts(record_neg, _daily(), lifespan_active_days=100)
    assert facts_neg.concern_fired == 1
