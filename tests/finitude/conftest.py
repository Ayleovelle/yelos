"""tests/finitude/conftest.py 在整个架构中的位置:公共夹具(finitude_BLUEPRINT §3.6/§11)。

`TRAJ_D1` 是固化轨迹(维二⑥ 机器凭据):100 活跃日,L=100;第 10-20 日每日
hi=3、concern=1;第 21-50 日无事件;第 51 日起每 5 日 hi=1。`run_trajectory`
把一个模型沿该轨迹跑一遍,产出契约 P 序列与 P_expr 序列(reserve 用 fast,
其余等于契约 P),供 `test_models_distinguish.py` 断言与
`experiments/finitude/model_comparison.json` 落盘复用。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yelos.finitude.gate import settle_through_gate
from yelos.finitude.models import MODEL_REGISTRY, build_model
from yelos.finitude.models.protocol import DayFacts

LIFESPAN = 100


def traj_d1_event_days() -> dict[int, tuple[int, int]]:
    """活跃日序号(1-based)→ (hi, concern)。未列出的日子 = (0, 0)。"""
    events: dict[int, tuple[int, int]] = {}
    for day in range(10, 21):
        events[day] = (3, 1)
    for day in range(51, 101):
        if (day - 51) % 5 == 0:
            events[day] = (1, 0)
    return events


def make_day_facts(
    day_index: int,
    hi: int,
    concern: int,
    active_days_settled: int,
    lifespan: int = LIFESPAN,
) -> DayFacts:
    return DayFacts(
        day=f"day-{day_index}",
        was_active_day=True,
        high_intensity=hi,
        concern_fired=concern,
        swallowed=0,
        proactive_sent=0,
        epoch_shift_yesterday=False,
        active_days_settled=active_days_settled,
        lifespan_active_days=lifespan,
    )


def run_trajectory(
    model_id: str,
    lifespan: int = LIFESPAN,
    params: dict | None = None,
    events: dict[int, tuple[int, int]] | None = None,
    steps: int | None = None,
) -> dict:
    """沿事件轨迹跑一个模型;返回 {"p": [...], "p_expr": [...]}(含初值,长度 steps+1)。"""
    events = events if events is not None else traj_d1_event_days()
    steps = steps if steps is not None else lifespan
    model, _ = build_model(model_id, params or {}, fast=1.0)

    p = 1.0
    p_series = [p]
    p_expr_series = [p]
    active_days_settled = 0
    for day_index in range(1, steps + 1):
        hi, concern = events.get(day_index, (0, 0))
        facts = make_day_facts(day_index, hi, concern, active_days_settled, lifespan)
        outcome = settle_through_gate(model, p, facts)
        p = outcome.new_p
        active_days_settled += 1
        if hasattr(model, "fast") and outcome.fast_pool is not None:
            model.fast = outcome.fast_pool
        if model_id == "reserve" and outcome.fast_pool is not None:
            p_expr_series.append(outcome.fast_pool)
        else:
            p_expr_series.append(p)
        p_series.append(p)
    return {"p": p_series, "p_expr": p_expr_series}


@pytest.fixture(scope="session")
def traj_d1_results() -> dict:
    return {model_id: run_trajectory(model_id) for model_id in MODEL_REGISTRY}


@pytest.fixture(scope="session")
def model_comparison_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "finitude"
        / "model_comparison.json"
    )


@pytest.fixture(scope="session", autouse=True)
def _write_model_comparison(traj_d1_results, model_comparison_path):
    """性质测试收口时把四模型 × TRAJ-D1 的对比评测落盘(维二⑥,§3.6)。"""
    model_comparison_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trajectory": "TRAJ-D1",
        "lifespan": LIFESPAN,
        "models": {
            model_id: {
                "p_final": series["p"][-1],
                "p_series": series["p"],
                "p_expr_series": series["p_expr"],
            }
            for model_id, series in traj_d1_results.items()
        },
    }
    model_comparison_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    yield
