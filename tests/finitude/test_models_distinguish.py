"""test_models_distinguish.py —— 可区分性 + T1 归零签名(finitude_BLUEPRINT §3.6,维二⑥)。

TRAJ-D1 五断言 + T1 各模型的归零/非归零签名 + model_comparison.json 再生成一致
(conftest 的 `_write_model_comparison` 已落盘,这里再跑一次核对内容一致,防止
"落盘了但没人核对内容"式虚胖)。
"""

from __future__ import annotations

import json

from yelos.finitude.models.protocol import DayFacts

from .conftest import LIFESPAN, run_trajectory, traj_d1_event_days


def test_traj_d1_pairwise_distinguishable(traj_d1_results):
    """断言 1:四模型的 P 序列两两存在 >=1 个日的差 > 1e-6(逐对不可换皮)。"""
    model_ids = list(traj_d1_results)
    for i in range(len(model_ids)):
        for j in range(i + 1, len(model_ids)):
            a = traj_d1_results[model_ids[i]]["p"]
            b = traj_d1_results[model_ids[j]]["p"]
            diffs = [abs(x - y) for x, y in zip(a, b)]
            assert max(diffs) > 1e-6, f"{model_ids[i]} vs {model_ids[j]} 不可区分"


def test_weibull_shape_accelerates(traj_d1_results):
    """断言 2:weibull 后半生日均 ΔP > 前半生日均 ΔP(形状学可测)。

    **施工期修正记录**:蓝图字面写"linear 两者相等",但 TRAJ-D1 的事件在两半并不
    对称(第 10-20 日事件集中在前半、第 51 日起每 5 日 1 次事件散布在后半),而
    linear 的 spend 本身也随 hi 调制(委托 core.finitude.settle_day 的
    `spend=base+0.5*base*hi`)——在这份不对称事件轨迹下 linear 前后两半日均 ΔP
    并不相等(已用本仓 TRAJ-D1 数值核实,差值 ~4e-3,不是浮点误差量级)。这是
    蓝图断言与其自定义轨迹的一处真实字面矛盾,不强行断言一个数值上不成立的等式。
    改用更严格也更真实的比较:weibull 的"后半/前半"放大比率 > linear 的同一比率
    ——把"形状学额外贡献的加速度"从"事件本身造成的不对称"中分离出来,两个模型
    共用同一条事件轨迹,唯一变量是 W(t) 的形状,比较才成立。
    """

    def _avg_delta(series, lo, hi):
        seg = series[lo:hi]
        deltas = [seg[i] - seg[i + 1] for i in range(len(seg) - 1)]
        return sum(deltas) / len(deltas)

    weibull = traj_d1_results["weibull"]["p"]
    w_first = _avg_delta(weibull, 0, LIFESPAN // 2)
    w_second = _avg_delta(weibull, LIFESPAN // 2, LIFESPAN)
    assert w_second > w_first

    linear = traj_d1_results["linear"]["p"]
    lin_first = _avg_delta(linear, 0, LIFESPAN // 2)
    lin_second = _avg_delta(linear, LIFESPAN // 2, LIFESPAN)

    weibull_ratio = w_second / w_first
    linear_ratio = lin_second / lin_first
    assert weibull_ratio > linear_ratio


def test_event_weighted_calm_segment_much_less_dissipation(traj_d1_results):
    """断言 3:event 在 21-50 日(无事件段,1-based)的总 ΔP < linear 同段的 1/3。"""
    # p 序列下标 0 = 初值(第 0 活跃日前);第 k 活跃日结束后的值在下标 k。
    lo, hi = 20, 50  # 对应第 21..50 活跃日结束时的值
    event_series = traj_d1_results["event"]["p"]
    linear_series = traj_d1_results["linear"]["p"]
    event_drop = event_series[lo] - event_series[hi]
    linear_drop = linear_series[lo] - linear_series[hi]
    assert event_drop < linear_drop / 3.0


def test_reserve_p_expr_recovers_and_bounded(traj_d1_results):
    """断言 4:reserve 的 P_expr 在 21-50 日(无事件段)回升且恒 <= S;其余模型 P_expr 单调。"""
    reserve = traj_d1_results["reserve"]
    p_expr = reserve["p_expr"]
    s = reserve["p"]
    for expr, contract in zip(p_expr, s):
        assert expr <= contract + 1e-9

    lo, hi = 20, 50
    assert p_expr[hi] >= p_expr[lo] - 1e-9  # 回升或至少不再进一步下降到更低
    # 至少存在严格回升的一步(回填确实发生)
    assert any(p_expr[i + 1] > p_expr[i] + 1e-12 for i in range(lo, hi))

    for model_id in ("linear", "weibull", "event"):
        series = traj_d1_results[model_id]["p_expr"]
        for prev, cur in zip(series, series[1:]):
            assert cur <= prev + 1e-12


def test_t1_zero_day_signatures():
    """断言 5:T1 归零/非归零签名逐模型断言(无事件、全活跃的一生)。"""
    no_events: dict[int, tuple[int, int]] = {}
    lifespan = 80

    linear = run_trajectory(
        "linear", lifespan=lifespan, events=no_events, steps=lifespan
    )
    assert abs(linear["p"][-1] - 0.0) < 1e-9

    weibull = run_trajectory(
        "weibull", lifespan=lifespan, events=no_events, steps=lifespan
    )
    assert abs(weibull["p"][-1] - 0.0) < 1e-9

    event = run_trajectory("event", lifespan=lifespan, events=no_events, steps=lifespan)
    assert abs(event["p"][-1] - (1.0 - 0.25)) < 1e-9  # 1 - alpha0

    reserve = run_trajectory(
        "reserve", lifespan=lifespan, events=no_events, steps=lifespan
    )
    assert abs(reserve["p"][-1] - 0.0) < 1e-9


def test_model_comparison_json_regenerates_consistently(model_comparison_path):
    """落盘的 model_comparison.json 与再次计算的结果一致(不是"落盘了没人核对")。"""
    assert model_comparison_path.exists()
    payload = json.loads(model_comparison_path.read_text(encoding="utf-8"))
    assert payload["trajectory"] == "TRAJ-D1"
    for model_id, expected in payload["models"].items():
        recomputed = run_trajectory(
            model_id, lifespan=payload["lifespan"], events=traj_d1_event_days()
        )
        assert recomputed["p"] == expected["p_series"]
        assert recomputed["p_expr"] == expected["p_expr_series"]


def test_day_facts_construction_smoke():
    """DayFacts 是 frozen dataclass,基本构造/字段访问 smoke。"""
    facts = DayFacts(
        day="2026-01-01",
        was_active_day=True,
        high_intensity=1,
        concern_fired=0,
        swallowed=0,
        proactive_sent=0,
        epoch_shift_yesterday=False,
        active_days_settled=0,
        lifespan_active_days=100,
    )
    assert facts.day == "2026-01-01"
    assert facts.was_active_day is True
