"""test_sensitization.py:[SHTOM-A7/T2] 千次随机 (y) 序列回放 β 有界 / hit
降 miss 升 / 安全域断言(蓝图 §11)。
"""

from __future__ import annotations

import hashlib

import pytest

from yelos.shadow.sensitization.scar import (
    BETA_HI,
    BETA_LO,
    update_beta,
    th_eff_for,
)
from yelos.shadow.signals.protocol import TH_BASE


def _pseudo_random_bits(seed: str, n: int) -> list[int]:
    """确定性伪随机(不用 random 模块——测试也走哈希族,守全局纪律)。"""
    out = []
    for i in range(n):
        digest = hashlib.sha256(f"{seed}#{i}".encode()).digest()
        out.append(digest[0] % 2)
    return out


def test_hit_lowers_beta() -> None:
    state = {"beta": 0.05, "hits": 0, "misses": 0}
    update_beta(state, 1)
    assert state["beta"] == pytest.approx(0.04)
    assert state["hits"] == 1


def test_miss_raises_beta() -> None:
    state = {"beta": 0.05, "hits": 0, "misses": 0}
    update_beta(state, 0)
    assert state["beta"] == pytest.approx(0.07)
    assert state["misses"] == 1


def test_beta_monotone_bounded_property() -> None:
    """性质测试:千次随机 y 序列回放,beta 恒在 [BETA_LO, BETA_HI]。"""
    for ctype in TH_BASE:
        state = {"beta": 0.0, "hits": 0, "misses": 0}
        bits = _pseudo_random_bits(f"scar-{ctype}", 1000)
        for y in bits:
            update_beta(state, y)
            assert BETA_LO - 1e-9 <= state["beta"] <= BETA_HI + 1e-9


def test_th_eff_safety_margin_holds_for_all_ctypes() -> None:
    """安全域断言:th_eff 恒 >= th_base * 0.5,即使 beta 触底(BETA_LO)。"""
    for ctype, th_base in TH_BASE.items():
        th_eff = th_eff_for(th_base, BETA_LO)
        assert th_eff >= th_base * 0.5 - 1e-9


def test_th_eff_increases_with_beta() -> None:
    lo = th_eff_for(0.25, -0.05)
    hi = th_eff_for(0.25, 0.10)
    assert hi > lo


def test_seal_resets_to_neutral() -> None:
    from yelos.shadow.binding_v2 import reset_for_new_incarnation

    block = reset_for_new_incarnation()
    for ctype, entry in block["sensitization"].items():
        assert entry["beta"] == 0.0
        assert entry["hits"] == 0
        assert entry["misses"] == 0
