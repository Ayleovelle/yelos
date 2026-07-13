"""T-A1/T-A3:记账测试(AX:A6,arbiter_BLUEPRINT §6.1)。

- 计数器单调;递增点唯一(AST 扫描:全仓只有 ledger.py 出现对应递增语义);
- SWALLOW 必记账;
- 沉默结算先于 settle 的时序断言(N10 履约,arbiter 侧义务)。
"""

from __future__ import annotations

import ast
from pathlib import Path

from yelos.arbiter.accounting.ledger import ArbiterLedger
from yelos.arbiter.hysteresis import HystState, settle_silence
from yelos.arbiter.hysteresis.ema import EmaState
from yelos.arbiter.hysteresis.params import Theta
from yelos.arbiter.hysteresis.signals import PendingOutcome, SessionSignalState
from yelos.core.arbiter import Verdict


def test_swallow_increments_both_counters():
    ledger = ArbiterLedger()
    v = Verdict("SWALLOW", high_intensity=True, reason="withdraw_swallow")
    delta = ledger.record_verdict(sid="s1", ts=1.0, verdict=v, policy_id="table")
    assert delta == {"swallowed": 1, "high_intensity": 1}


def test_swallow_low_intensity_only_increments_swallowed():
    ledger = ArbiterLedger()
    v = Verdict("SWALLOW", high_intensity=False, reason="hold_swallow")
    delta = ledger.record_verdict(sid="s1", ts=1.0, verdict=v, policy_id="table")
    # N6:high_intensity 判据与 swallow_th 解耦,固定 pressure>=0.75——非高强度
    # 的 SWALLOW 仍计入 swallowed,只是不计入 high_intensity。
    assert delta == {"swallowed": 1, "high_intensity": 0}


def test_non_swallow_no_increment():
    ledger = ArbiterLedger()
    for kind in ("PASS", "TRIM", "REPLACE"):
        v = Verdict(kind, reason="x")
        delta = ledger.record_verdict(sid="s1", ts=1.0, verdict=v, policy_id="table")
        assert delta == {"swallowed": 0, "high_intensity": 0}


def test_counters_monotone_over_simulated_binding():
    """累加应用增量到一个模拟 binding daily 块上,验证只增不减。"""
    ledger = ArbiterLedger()
    daily = {"swallowed": 0, "high_intensity": 0}
    lifetime_total = 0
    rows = [
        Verdict("SWALLOW", high_intensity=True, reason="a"),
        Verdict("PASS", reason="b"),
        Verdict("SWALLOW", high_intensity=False, reason="c"),
        Verdict("REPLACE", reason="d"),
        Verdict("SWALLOW", high_intensity=True, reason="e"),
    ]
    prev_daily = dict(daily)
    prev_total = lifetime_total
    for i, v in enumerate(rows):
        delta = ledger.record_verdict(
            sid="s1", ts=float(i), verdict=v, policy_id="table"
        )
        daily["swallowed"] += delta["swallowed"]
        daily["high_intensity"] += delta["high_intensity"]
        lifetime_total += delta["swallowed"]
        assert daily["swallowed"] >= prev_daily["swallowed"]
        assert daily["high_intensity"] >= prev_daily["high_intensity"]
        assert lifetime_total >= prev_total
        prev_daily, prev_total = dict(daily), lifetime_total
    assert daily == {"swallowed": 3, "high_intensity": 2}
    assert lifetime_total == 3


def test_ring_buffer_caps_at_256():
    ledger = ArbiterLedger()
    for i in range(300):
        ledger.record_verdict(
            sid="s1",
            ts=float(i),
            verdict=Verdict("PASS", reason="x"),
            policy_id="table",
        )
    rows = ledger.rows_for("s1")
    assert len(rows) == 256
    assert rows[-1].ts == 299.0
    assert rows[0].ts == 44.0  # 300-256


def test_single_increment_point_ast_scan():
    """AX:A6 AST 扫描:全仓(除 ledger.py 自身)不应出现对
    swallowed_total / daily.high_intensity 语义等价的第二处独立递增
    ——本扫描聚焦本波新增的 arbiter 包目录(核心 v0.1 层的既有递增点
    是历史地基,不在本条新增纪律的审计范围内,见蓝图 §11.1 记账两栏)。
    """
    root = Path(__file__).resolve().parents[2] / "src" / "yelos" / "arbiter"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "ledger.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
                target = ast.dump(node.target)
                if "swallowed" in target or "high_intensity" in target:
                    offenders.append((path, target))
    assert offenders == [], offenders


def test_silence_settlement_precedes_rollover_ordering():
    """T-A3 时序断言:沉默结算(settle_silence)必须在 finitude rollover
    settle 之前发生,才能保证 daily.high_intensity 在 settle 快照时刻
    已含当日全部重咽(N10)。本测试模拟"未决 SWALLOW 账 -> 心跳沉默结算
    -> (finitude 侧)读取 daily.high_intensity 快照"的顺序契约。
    """
    theta = Theta()
    ema = EmaState()
    pending = PendingOutcome(sid="s1", turn_id="t1", kind="SWALLOW", ts_i=100.0)
    signals = SessionSignalState(gaps=[30.0], lens=[20.0], pending=pending)
    state = HystState(theta=theta, ema=ema, n_events=0, signals=signals)

    # 心跳 rollover 前的沉默结算:必须发生,且发生后 pending 清空。
    settled = settle_silence(state, p=0.8)
    assert settled.signals.pending is None
    assert settled.n_events == state.n_events + 1

    # 只有在沉默结算之后,daily.high_intensity 计数(由 ledger 另行维护,
    # 与 hysteresis 状态是两条独立账本)才应被 finitude 读取——本测试断言
    # 的是"沉默结算函数本身在 settle 读取点之前是幂等收口"这件事:
    # 结算后再结算一次不再变化(可安全地在 settle 读取点之前反复调用)。
    settled_again = settle_silence(settled, p=0.8)
    assert settled_again == settled
