"""lattice.py 在整个架构中的位置。

arbiter 包的最底层原子:verdict 强度全序 σ。被 pipeline/guards/policies/
hysteresis 全部依赖(依赖方向表 §2 的叶子节点),自身不依赖包内任何其它模块。

AX:A1 介入强度全序公理(arbiter_BLUEPRINT §1.1)。verdict 集合
V = {PASS, TRIM, REPLACE, SWALLOW},强度函数 σ: V -> {0,1,2,3},
PASS ⊑ TRIM ⊑ REPLACE ⊑ SWALLOW。σ 值仅用于比较,不参与任何算术加权
——不以"格"自夸形式化(总纲红队裁决 3),承重用途只有两个:
(i) 后置滤波单调性(A2)的比较基准;(ii) DuelPolicy 取保守者的 min() 依据。
"""

from __future__ import annotations

from typing import Protocol

# AX:A1 —— 强度全序表,唯一权威定义处
SIGMA: dict[str, int] = {"PASS": 0, "TRIM": 1, "REPLACE": 2, "SWALLOW": 3}


class _HasKind(Protocol):
    kind: str


def sigma(kind: str) -> int:
    """verdict kind 字符串 -> 强度序数。未知 kind 视为编程错误,直接 KeyError。"""
    return SIGMA[kind]


def sigma_of(verdict: _HasKind) -> int:
    """verdict 对象(duck-typed,含 .kind)-> 强度序数。"""
    return SIGMA[verdict.kind]


def min_sigma_verdict(a: _HasKind, b: _HasKind):
    """A1 承重用途 (ii):取"更保守"的一枚(σ 更小者)。

    σ 相同时返回 a(约定优先序,调用方按需自行决定谁传 a);A1 声明
    "σ 相同不同 verdict 不可能"(σ 单射于 kind),但本函数不假设这一点,
    只做纯粹的 σ 比较,容错。
    """
    return a if sigma_of(a) <= sigma_of(b) else b


def is_downgrade_or_equal(before: _HasKind, after: _HasKind) -> bool:
    """A2 后置滤波单调性判据:σ(after) <= σ(before)。"""
    return sigma_of(after) <= sigma_of(before)
