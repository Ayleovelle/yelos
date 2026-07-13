"""test_intensity.py:[SHTOM-A4] 两套函数网格 golden / conf 折减单调 / 量化
位数;A/B 差异数据落盘断言存在(蓝图 §11)。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yelos.shadow.signals.intensity import (
    compute_intensity,
    intensity_ab_grid,
    linear_intensity,
    saturating_intensity,
)

EXPERIMENTS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "experiments" / "shadow"
)


def test_linear_floor_and_ceiling() -> None:
    assert compute_intensity(0.0, 1.0, "linear") == pytest.approx(0.3)
    assert compute_intensity(1.0, 1.0, "linear") == pytest.approx(1.0)


def test_saturating_floor_and_near_ceiling() -> None:
    assert compute_intensity(0.0, 1.0, "saturating") == pytest.approx(0.3)
    # saturating 在 strength=1 时接近但小于 linear 的 1.0(1-exp(-2.2)<1)。
    assert compute_intensity(1.0, 1.0, "saturating") < 1.0


def test_confidence_discount_monotone() -> None:
    # [SHTOM-A4] conf 越低,同一 strength 下 intensity 越低(不绕过折减)。
    high_conf = compute_intensity(0.8, 1.0, "linear")
    mid_conf = compute_intensity(0.8, 0.5, "linear")
    zero_conf = compute_intensity(0.8, 0.0, "linear")
    assert high_conf > mid_conf > zero_conf
    assert zero_conf == pytest.approx(0.3)  # conf=0 仍有 floor,不归零(诚实但不过度悲观)


def test_intensity_quantized_to_three_digits() -> None:
    val = compute_intensity(0.333333, 0.777777, "linear")
    assert round(val, 3) == val


def test_unknown_fn_name_raises() -> None:
    with pytest.raises(ValueError):
        compute_intensity(0.5, 0.5, "not_a_real_fn")


def test_intensity_ab_grid_shape() -> None:
    grid = intensity_ab_grid()
    assert grid["grid"]
    for row in grid["grid"]:
        assert set(row) == {"strength", "conf", "linear", "saturating", "delta"}


def test_ab_grid_can_be_written_to_experiments_artifact(tmp_path: Path) -> None:
    """维二对比评测凭据(蓝图 §6.4):生成并落盘,断言产物存在且可回读。"""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPERIMENTS_DIR / "intensity_ab.json"
    grid = intensity_ab_grid()
    out_path.write_text(
        json.dumps(grid, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert out_path.exists()
    reloaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert reloaded == grid


def test_linear_and_saturating_differ_at_low_strength() -> None:
    lo_lin = linear_intensity(0.1, 1.0)
    lo_sat = saturating_intensity(0.1, 1.0)
    assert lo_sat != pytest.approx(lo_lin)
