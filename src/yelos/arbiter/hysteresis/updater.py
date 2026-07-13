"""hysteresis/updater.py 在整个架构中的位置。

θ 更新的唯一权威实现:η(P)·共识·符号映射·投影(A5/T1/T2 的代码锚点)。
本模块是纯函数:θ_{t+1} = f(θ_t, kind, r, consensus, P),无 random、
无时钟直读——T-H3/T-H6 的可回放性由此保证(A5.5)。

AX:A5.3(学习率-有限性耦合):η(P) = η0·P,η0=1.0,单调不减于 P;P=0 ⇒ η=0。
"""

from __future__ import annotations

from .params import STEP, Theta

# η0(学习率的 P=1 上限),arbiter_BLUEPRINT §5.3 字面值。
ETA0 = 1.0


def learning_rate(p: float) -> float:
    """AX:A5.3 / T2 锚点:η(P) = η0·P。P 单调不增 ⇒ η 单调不增;P=0 ⇒ η=0。"""
    return ETA0 * p


# --- §5.4 符号映射表(以函数形式实现,因方向依赖 r 的正负) -----------------
#
# | 触发 kind    | r<0(负反馈)        | r>0(正反馈)        |
# |--------------|---------------------|---------------------|
# | SWALLOW      | d_sw +              | d_sw -              |
# | REPLACE      | d_rp +, gamma -     | d_rp -, gamma +     |
# | TRIM_hold    | d_sw -(单侧,标★)   | 无操作              |
# | TRIM_express | d_ex +              | d_ex -              |
#
# ★ hold-TRIM 负反馈方向有歧义(嫌被截?嫌只剩半句?),保守地只动 d_sw
# 单侧;若红队否证其方向,降为"无操作"不伤架构(arbiter_BLUEPRINT §5.4)。


def _sign_for(kind: str, param: str, r: float) -> int:
    if r == 0.0:
        return 0
    negative = r < 0
    if kind == "SWALLOW":
        if param == "d_sw":
            return 1 if negative else -1
        return 0
    if kind == "REPLACE":
        if param == "d_rp":
            return 1 if negative else -1
        if param == "gamma_offset":
            return -1 if negative else 1
        return 0
    if kind == "TRIM_hold":
        if param == "d_sw" and negative:
            return -1
        return 0
    if kind == "TRIM_express":
        if param == "d_ex":
            return 1 if negative else -1
        return 0
    return 0


def apply_update(
    theta: Theta, *, kind: str, r: float, consensus: int, p: float
) -> Theta:
    """AX:A5.1/A5.2/A5.3/A5.4 的合流点;T1/T2 的直接实现。

    θ_k <- Π_Box(θ_k + η(P)·c·sign_map(kind,k)·|r|·step_k)

    - consensus==0 或 p<=0 或 kind 未识别 ⇒ 原样返回(T2:P=0 精确凝固)。
    - 否则逐分量按 sign_map 决定方向,幅度 <= η(P)·|r|·step_k <= step_k
      (T1(iii) 单步有界的直接依据,|r|<=1、η(P)<=η0=1)。
    """
    if consensus == 0 or p <= 0.0:
        return theta  # AX:A5.4 非共识寸步不动 / T2 P=0 精确凝固
    eta = learning_rate(p)
    mag = eta * abs(r)
    deltas: dict[str, float] = {}
    for k in ("d_sw", "d_rp", "d_ex", "gamma_offset"):
        s = _sign_for(kind, k, r)
        deltas[k] = s * mag * STEP[k]
    new = Theta(
        d_sw=theta.d_sw + deltas["d_sw"],
        d_rp=theta.d_rp + deltas["d_rp"],
        d_ex=theta.d_ex + deltas["d_ex"],
        gamma_offset=theta.gamma_offset + deltas["gamma_offset"],
    )
    return new.project()  # AX:A5.1 / T1(i)
