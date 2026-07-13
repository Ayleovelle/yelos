"""test_selection.py:T3 四行全枚举;主权违例一票否决;平手不动;online_weight=1.0 影响 verdict(消费断言)。"""

from __future__ import annotations

from yelos.evolution.selection.fitness import Fitness
from yelos.evolution.selection.judge import judge


def _f(bench=50.0, online=0.0, veto=0):
    return Fitness(
        bench_score=bench,
        online_score=online,
        sovereignty_violations=veto,
        report_path="",
    )


def test_sovereignty_violation_is_one_vote_veto():
    assert judge(_f(bench=999.0, veto=1), _f(bench=1.0)) == "reject"


def test_inferior_candidate_rejected():
    assert judge(_f(bench=10.0), _f(bench=20.0)) == "reject"


def test_tie_is_conservative_reject():
    assert judge(_f(bench=20.0), _f(bench=20.0)) == "reject"


def test_strictly_better_candidate_accepted():
    assert judge(_f(bench=21.0), _f(bench=20.0)) == "accept"


def test_online_weight_zero_ignores_online_score():
    candidate = _f(bench=20.0, online=100.0)
    incumbent = _f(bench=20.0, online=0.0)
    assert judge(candidate, incumbent, online_weight=0.0) == "reject"  # 仍是平手


def test_online_weight_one_makes_online_score_decisive():
    """消费断言(wiring manifest §5.1):篡改在线信号权重 -> verdict 翻转。"""
    candidate = _f(bench=20.0, online=1.0)
    incumbent = _f(bench=20.0, online=0.0)
    assert judge(candidate, incumbent, online_weight=0.0) == "reject"
    assert judge(candidate, incumbent, online_weight=1.0) == "accept"


def test_evaluate_reads_bench_report_contract(fake_harness):
    from yelos.evolution.selection.fitness import evaluate

    fitness = evaluate({"intrinsic_daily_cap": 4}, fake_harness, "scenario-a")
    assert fitness.bench_score == 100.0
    assert fitness.sovereignty_violations == 0
    assert fitness.report_path == "fake://report"


def test_evaluate_veto_from_tampered_bench_report():
    """消费断言:篡改 bench 报告分 -> verdict 变。"""
    from yelos.evolution.selection.fitness import evaluate

    class VetoHarness:
        def evaluate(self, candidate, scenario):
            return {"overall": 0.0, "vetoes": ["p0_violation"], "report_path": "x"}

    fitness = evaluate({"intrinsic_daily_cap": 4}, VetoHarness(), "scenario-a")
    incumbent = Fitness(
        bench_score=10.0, online_score=0.0, sovereignty_violations=0, report_path=""
    )
    assert judge(fitness, incumbent) == "reject"
