"""tests/evolution/conftest.py:fake bench fixture(§5.2,仓内自带,不需真引擎)。"""

from __future__ import annotations

import pytest


class FakeBenchHarness:
    """固定适应度地形:``bench_score`` 是候选 ``intrinsic_daily_cap`` 的
    单峰函数(峰值在 4),``vetoes`` 恒空(不触发主权一票否决)——供
    ``test_selection``/``test_optin_smoke`` 用可预期的地形驱动 judge 分支。
    """

    def __init__(self, veto_below: float | None = None) -> None:
        self.veto_below = veto_below
        self.calls: list[dict] = []

    def evaluate(self, candidate, scenario):
        self.calls.append(dict(candidate))
        cap = float(candidate.get("intrinsic_daily_cap", 3))
        score = 100.0 - abs(cap - 4.0) * 10.0
        vetoes = []
        if self.veto_below is not None and score < self.veto_below:
            vetoes = ["sovereignty_violation"]
        return {"overall": score, "vetoes": vetoes, "report_path": "fake://report"}


@pytest.fixture
def fake_harness() -> FakeBenchHarness:
    return FakeBenchHarness()


@pytest.fixture
def base_config() -> dict:
    """一个通过 ``validate_registry`` 的最小 config 代理(dict 形态)。"""
    return {
        "evolution_enabled": True,
        "evolution_velocity_bound": 0.34,  # 使 intrinsic_daily_cap 每代恰能走 1 档(域宽5,0.2/档)
        "evolution_min_days": 7,
        "evolution_online_weight": 0.0,
        "evolution_strategy": "pattern_search",
        "intrinsic_daily_cap": 3,
        "arbiter_min_gap_seconds": 180,
        "quiet_hours": "01:00-08:00",
        "lifespan_active_days": 545,
        "farewell_token_ttl_seconds": 600,
        "default_mode": "steward",
        "finitude_model": "linear",
    }
