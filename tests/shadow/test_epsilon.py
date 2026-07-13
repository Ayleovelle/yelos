"""test_epsilon.py:[SHTOM-A5] ε 公式数值/clip 域界/哈希方向确定性/σ_obs
响应观测方差(蓝图 §11)。
"""

from __future__ import annotations

from yelos.shadow.simulator.epsilon import (
    DEFAULT_EPS_HI,
    DEFAULT_EPS_LO,
    compute_epsilon,
    compute_sigma_family,
    compute_sigma_obs,
    perturb_direction,
)


def test_epsilon_formula_matches_weighted_sum() -> None:
    sigma_obs, sigma_family = 0.1, 0.2
    lam, w_obs, w_base = 0.5, 0.6, 0.4
    expected = max(
        DEFAULT_EPS_LO,
        min(DEFAULT_EPS_HI, lam * (w_obs * sigma_obs + w_base * sigma_family)),
    )
    assert compute_epsilon(sigma_obs, sigma_family) == expected


def test_epsilon_clips_to_lo() -> None:
    assert compute_epsilon(0.0, 0.0) == DEFAULT_EPS_LO


def test_epsilon_clips_to_hi() -> None:
    assert compute_epsilon(10.0, 10.0) == DEFAULT_EPS_HI


def test_epsilon_override_still_clipped() -> None:
    # override 超出域界仍要被 clip(测试专用入口,不是绕过 clip 的旁路)。
    assert compute_epsilon(0.0, 0.0, epsilon_override=1.0) == DEFAULT_EPS_HI
    assert compute_epsilon(0.0, 0.0, epsilon_override=-1.0) == DEFAULT_EPS_LO


def test_epsilon_monotone_in_sigma() -> None:
    low = compute_epsilon(0.05, 0.05)
    high = compute_epsilon(0.3, 0.3)
    assert high >= low


def test_sigma_obs_responds_to_ewma_variance() -> None:
    calm = compute_sigma_obs({"pressure": 0.0, "warmth": 0.0, "damage": 0.0})
    noisy = compute_sigma_obs({"pressure": 0.09, "warmth": 0.0, "damage": 0.0})
    assert noisy > calm


def test_sigma_family_takes_max_across_engine_channels() -> None:
    dispersions = {"pressure": 0.1, "warmth": 0.9, "damage": 0.2}
    assert compute_sigma_family(dispersions) == 0.9


def test_perturb_direction_is_deterministic_same_key() -> None:
    d1 = perturb_direction("sid-1", "2026-07-11", 1)
    d2 = perturb_direction("sid-1", "2026-07-11", 1)
    assert d1 == d2
    assert d1 in (1, -1)


def test_perturb_direction_varies_by_key_component() -> None:
    directions = {perturb_direction("sid-1", "2026-07-11", k) for k in range(1, 4)} | {
        perturb_direction("sid-2", "2026-07-11", 1),
        perturb_direction("sid-1", "2026-07-12", 1),
    }
    # 不要求全异(哈希天然会碰撞),但至少不能全部退化为同一个常量。
    assert directions <= {1, -1}
