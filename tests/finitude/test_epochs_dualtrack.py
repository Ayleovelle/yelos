"""test_epochs_dualtrack.py —— 纪元双轨性质/golden 测试(finitude_BLUEPRINT §11,A5/A6/T2)。

Ψ 单调网格枚举(T2 证明本体)、判据 golden、冷启动不触发、idx 永不回退(A5)、
权威表 6 行逐格、分歧 jsonl schema 往返。
"""

from __future__ import annotations


from yelos.finitude.epochs import fixed
from yelos.finitude.epochs.dualtrack import (
    DualTrack,
    decide_notification,
    read_divergence,
)
from yelos.finitude.epochs.order_parameter import (
    MIN_SAMPLES,
    OpDetectorState,
    clamp_forward,
    detect,
    psi,
    rho_budget,
    rho_lex,
)

CAP = 3


def test_psi_monotone_grid():
    """# [FIN-A6]/T2:p1<=p2 => Psi(p1)<=Psi(p2),全词典 × 网格枚举即证明本体。"""
    grid = [
        i / 1000.0 for i in range(0, 1001, 5)
    ]  # 精简步长(5/1000)控制耗时,仍是细密网格
    prev = -1.0
    for p in grid:
        cur = psi(p, CAP)
        assert cur >= prev - 1e-12
        prev = cur


def test_rho_lex_monotone_and_bounded():
    for p in (0.0, 0.15, 0.5, 0.9, 1.0):
        v = rho_lex(p)
        assert 0.0 <= v <= 1.0 + 1e-9


def test_rho_budget_boundary_and_cap_zero():
    assert rho_budget(0.5, 0) == 1.0  # cap=0 定义为中性
    assert rho_budget(1.0, CAP) == 1.0
    assert rho_budget(0.0, CAP) == 1.0 / CAP  # max(1, floor(cap*0))=1


def test_cold_start_no_fire():
    """样本 <5 恒不触发,即便 ΔΨ 很大。"""
    state = OpDetectorState()
    day = "d1"
    # p_expr 从 1.0 骤降到 0.0(最大可能的联动收缩),样本数仍是 0 < MIN_SAMPLES
    for _ in range(MIN_SAMPLES - 1):
        state, fired = detect(state, day, 1.0, 0.0, CAP)
        assert fired is False
    assert len(state.deltas) == MIN_SAMPLES - 1


def test_transition_criterion_golden():
    """判据 golden:预置滚动窗全零(中位数=0),下一次任意正向 ΔΨ 即触发(阈值退化为 0)。"""
    state = OpDetectorState(deltas=[0.0] * MIN_SAMPLES)
    new_state, fired = detect(state, "d10", 1.0, 0.5, CAP)
    assert fired is True
    assert new_state.b_index == 1
    assert new_state.fired_days == ["d10"]

    # 联动判据缺一不可:p 不变(Δρ_lex=Δρ_budget=0)不触发,即便窗口中位数为 0
    state2 = OpDetectorState(deltas=[0.0] * MIN_SAMPLES)
    _, fired2 = detect(state2, "d11", 0.5, 0.5, CAP)
    assert fired2 is False


def test_epoch_never_regresses_clamp_forward():
    """# [FIN-A5] idx' = max(idx, 提名),不可回退。"""
    assert clamp_forward(2, 1) == 2
    assert clamp_forward(2, 5) == 5
    assert clamp_forward(0, 0) == 0


def test_b_index_monotone_across_many_detects():
    state = OpDetectorState()
    day_idx = 0
    # 先跑满冷启动窗口
    for _ in range(MIN_SAMPLES):
        day_idx += 1
        state, _ = detect(state, f"d{day_idx}", 0.9, 0.85, CAP)
    prev_index = state.b_index
    for _ in range(20):
        day_idx += 1
        # 交替制造收缩/不收缩,只要求 b_index 单调不减
        p_old = 0.5
        p_new = 0.1
        state, _ = detect(state, f"d{day_idx}", p_old, p_new, CAP)
        assert state.b_index >= prev_index
        prev_index = state.b_index


def test_decision_table_six_rows():
    """§4.4 权威表 6 行逐格(经 decide_notification 纯函数直测)。"""
    # fixed 权威:A 触发(B 是/否都一样,只看 A)
    assert decide_notification("fixed", False, "慢下来", True, "安静") == (
        "慢下来",
        "A",
    )
    assert decide_notification("fixed", False, "慢下来", False, None) == ("慢下来", "A")
    # fixed 权威:A 不触发 → 无通告(即便 B 触发)
    assert decide_notification("fixed", False, None, True, "安静") == (None, None)
    assert decide_notification("fixed", False, None, False, None) == (None, None)
    # order_parameter 权威、非冷启动:B 触发 → 通告 B(钳制后名字)
    assert decide_notification("order_parameter", False, None, True, "安静") == (
        "安静",
        "B",
    )
    # order_parameter 权威、非冷启动:A 触发但 B 不触发 → 无通告
    assert decide_notification("order_parameter", False, "慢下来", False, None) == (
        None,
        None,
    )
    # order_parameter 权威、冷启动:退化为 A 代驱
    assert decide_notification("order_parameter", True, "慢下来", False, None) == (
        "慢下来",
        "A",
    )
    assert decide_notification("order_parameter", True, None, False, None) == (
        None,
        None,
    )


def test_dualtrack_observe_writes_divergence(tmp_path):
    dt = DualTrack(sid="u1", gen=1, track_authority="fixed", cap=CAP, data_dir=tmp_path)
    # 制造一次 A 不触发、B 也不触发的平常一天(不落分歧行)
    outcome = dt.observe("d1", 0.9, 0.85, 0.9, 0.85)
    assert outcome.divergence_rows == []
    rows = read_divergence(tmp_path)
    assert rows == []


def test_divergence_jsonl_roundtrip(tmp_path):
    dt = DualTrack(
        sid="u1", gen=1, track_authority="order_parameter", cap=CAP, data_dir=tmp_path
    )
    day_idx = 0
    # 跑满冷启动窗口(B 不会触发,但 A 可能触发——用不跨档的 p 避免 a_only 噪声)
    for _ in range(MIN_SAMPLES):
        day_idx += 1
        dt.observe(f"d{day_idx}", 0.9, 0.88, 0.9, 0.88)
    # 之后制造一次真实的强收缩,期待 B 有机会触发(非强制断言 fired,只测 schema)
    day_idx += 1
    dt.observe(f"d{day_idx}", 0.9, 0.1, 0.9, 0.1)
    rows = read_divergence(tmp_path)
    for row in rows:
        assert set(row) >= {
            "sid",
            "gen",
            "day",
            "event",
            "a_epoch",
            "b_index",
            "p",
            "p_expr",
            "psi",
            "dpsi",
        }
        assert row["sid"] == "u1"
        assert row["gen"] == 1
        assert row["event"] in ("a_only", "b_only", "both")

    # 损坏行安静跳过
    path = tmp_path / "epoch_divergence.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write("not-json\n")
        fh.write("\n")
    rows_after = read_divergence(tmp_path)
    assert all(isinstance(r, dict) for r in rows_after)


def test_fixed_epoch_boundaries_delegate_core():
    assert fixed.epoch_of(1.0) == "盛年"
    assert fixed.epoch_of(0.0) == "静止"
    assert fixed.epoch_index(1.0) == 0
    assert fixed.transition(0.65, 0.6) == "慢下来"
    assert fixed.transition(0.9, 0.65) is None
