"""T-CIR-01, T-CIR-02, T-CIR-03(intrinsic_BLUEPRINT §8.2)。"""

from __future__ import annotations


from yelos.intrinsic.circadian import phase_learn
from yelos.intrinsic.circadian.forcing import MINUTES_PER_DAY, forcing


def test_cir01_forcing_periodic_and_deterministic() -> None:
    for t in (0, 100, 700, 1439):
        assert forcing(t) == forcing(t + MINUTES_PER_DAY)
        assert forcing(t) == forcing(t)  # 确定性:同 τ 同值


def test_cir01_forcing_offset_shifts_phase() -> None:
    base = forcing(600, 0.0)
    shifted = forcing(600, 60.0)
    assert base != shifted


def test_cir02_phase_learning_converges_on_synthetic_schedule() -> None:
    """合成作息:每次交互都在 22:00(1320 分钟)附近 ± 抖动,收敛到该邻域。"""
    state = phase_learn.PhaseLearnerState()
    true_minute = 1320
    jitter_seq = [0, 5, -5, 3, -3, 2, -2, 1, -1, 0, 4, -4, 2, -2, 0, 3, -3, 1, -1, 0]
    for j in jitter_seq:
        state = phase_learn.update(state, (true_minute + j) % MINUTES_PER_DAY)
    assert state.n_obs == len(jitter_seq)
    # 圆均值应落在真相位 15 分钟邻域内(处理跨零点的环形距离)。
    delta = (state.mu_min - true_minute) % MINUTES_PER_DAY
    if delta > MINUTES_PER_DAY / 2:
        delta -= MINUTES_PER_DAY
    assert abs(delta) <= 15
    assert state.kappa > 0.7  # 抖动很小,集中度应该高


def test_cir02_cold_start_offset_disabled() -> None:
    state = phase_learn.PhaseLearnerState()
    for _ in range(phase_learn.MIN_OBS_FOR_OFFSET - 1):
        state = phase_learn.update(state, 600)
    assert phase_learn.phase_offset_minutes(state) == 0.0


def test_cir02_input_surface_is_minutes_only() -> None:
    """边界:输入面签名只收 minutes(总纲 §2.3 明文,不建模内容/情绪/状态)。"""
    import inspect

    sig = inspect.signature(phase_learn.update)
    params = list(sig.parameters)
    assert params == ["state", "interaction_minute"]
    ann = sig.parameters["interaction_minute"].annotation
    assert ann in (int, "int")


def test_cir03_stop_feeding_freezes_offset() -> None:
    """停喂时刻:相位状态不再变化(golden 不再漂的最小可测替身)。"""
    state = phase_learn.PhaseLearnerState()
    for m in (600, 610, 605, 615, 595):
        state = phase_learn.update(state, m)
    frozen = state
    # 不再调用 update,反复读 phase_offset_minutes 恒定。
    a = phase_learn.phase_offset_minutes(frozen)
    b = phase_learn.phase_offset_minutes(frozen)
    assert a == b


def test_forcing_bounded_small_amplitude() -> None:
    """强迫项量级远小于衰减项(软调制,不该反客为主)。"""
    for t in range(0, 1440, 37):
        c = forcing(t)
        assert all(abs(x) <= 0.05 for x in c)
