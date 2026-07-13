"""test_gate.py —— MonotoneGate 单元测试(finitude_BLUEPRINT §11,[FIN-A1])。

闸短路条件表逐行;恶意模型(返回 p+0.1)被钳;assert 双保险;手改 params 域外的
对抗用例(§7.3/§11 对抗表)。
"""

from __future__ import annotations

from yelos.finitude.gate import settle_through_gate
from yelos.finitude.models import build_model
from yelos.finitude.models.protocol import DayFacts
from yelos.finitude.rites.incarnation import aging_of, stamp_aging, validate_params


def _facts(**overrides) -> DayFacts:
    base = dict(
        day="d1",
        was_active_day=True,
        high_intensity=0,
        concern_fired=0,
        swallowed=0,
        proactive_sent=0,
        epoch_shift_yesterday=False,
        active_days_settled=0,
        lifespan_active_days=100,
    )
    base.update(overrides)
    return DayFacts(**base)


def test_gate_short_circuit_lifespan_zero():
    model, _ = build_model("linear", {}, fast=1.0)
    out = settle_through_gate(
        model, 0.7, _facts(lifespan_active_days=0, high_intensity=9)
    )
    assert out.new_p == 0.7


def test_gate_short_circuit_inactive_day():
    model, _ = build_model("weibull", {}, fast=1.0)
    out = settle_through_gate(
        model, 0.7, _facts(was_active_day=False, high_intensity=9)
    )
    assert out.new_p == 0.7


def test_gate_normal_active_day_decreases():
    model, _ = build_model("linear", {}, fast=1.0)
    out = settle_through_gate(model, 0.7, _facts())
    assert out.new_p < 0.7


class _MaliciousModel:
    model_id = "malicious"

    def spend(self, p, facts):
        from yelos.finitude.models.protocol import SettleOutcome

        return SettleOutcome(new_p=p + 0.1, fast_pool=None, extras={})


def test_gate_clamps_malicious_model_returning_higher_p():
    """恶意模型返回 p+0.1,gate 结构性钳死为 <= p。"""
    out = settle_through_gate(_MaliciousModel(), 0.5, _facts())
    assert out.new_p <= 0.5


class _NegativeModel:
    model_id = "negative"

    def spend(self, p, facts):
        from yelos.finitude.models.protocol import SettleOutcome

        return SettleOutcome(new_p=-5.0, fast_pool=None, extras={})


def test_gate_clamps_negative_new_p_to_zero_floor():
    out = settle_through_gate(_NegativeModel(), 0.5, _facts())
    assert out.new_p == 0.0


# --- 对抗用例:params 域外 → 保守回退 linear + 标记(§11 对抗表)---------------


def test_tampered_params_fallback():
    record: dict = {}
    stamp_aging(record, config=None)  # 默认 linear
    record["aging"]["model"] = "weibull"
    record["aging"]["params"] = {"k": 999.0}  # 域外(K_MAX=4.0)

    spec = aging_of(record)
    assert spec.fell_back is True
    assert spec.model == "linear"


def test_unknown_model_id_falls_back():
    record: dict = {
        "aging": {
            "model": "does-not-exist",
            "params": {},
            "active_days_settled": 3,
            "fast": 1.0,
        }
    }
    spec = aging_of(record)
    assert spec.fell_back is True
    assert spec.model == "linear"
    assert spec.active_days_settled == 3  # 生命周期计数器不因回退而丢


def test_missing_aging_block_falls_back():
    record: dict = {}
    spec = aging_of(record)
    assert spec.fell_back is True
    assert spec.model == "linear"
    assert spec.active_days_settled == 0


def test_validate_params_domain():
    assert validate_params("linear", {}) is True
    assert validate_params("weibull", {"k": 1.6}) is True
    assert validate_params("weibull", {"k": 0.5}) is False
    assert validate_params("weibull", {"k": 5.0}) is False
    assert validate_params("weibull", {"k": "not-a-number"}) is False
    assert validate_params("event", {"w_hi": -1.0}) is False
    assert validate_params("event", {"w_hi": 0.5}) is True
    assert validate_params("reserve", {"r": -0.1}) is False
    assert validate_params("reserve", {"gamma": 2.0}) is True
    assert validate_params("no-such-model", {}) is False


def test_tampered_model_allowed_mid_life_when_params_valid():
    """手改 record.aging.model 于在世中途:params 域内则允许(数据是用户的,主权语义)。"""
    record: dict = {
        "aging": {
            "model": "linear",
            "params": {},
            "active_days_settled": 5,
            "fast": 1.0,
        }
    }
    record["aging"]["model"] = "weibull"
    record["aging"]["params"] = {"k": 2.0}
    spec = aging_of(record)
    assert spec.fell_back is False
    assert spec.model == "weibull"
