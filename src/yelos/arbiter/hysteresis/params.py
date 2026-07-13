"""hysteresis/params.py 在整个架构中的位置。

θ 的 schema、Box(硬界)、单事件步长表、MUTABLE_SET。这是 AX:A5.1/A4
铁域声明的结构性落点:``Theta`` dataclass **只有**这四个字段——
min_gap/P0/narrow_p/high_intensity 判据/哈希键型/白名单一个都不在这里,
不是运行时检查,是"没有被更新的路径"这件事本身。

AX:A5.1(信赖域):每个 θ_k 有硬界 [lo_k, hi_k],每次更新后投影回 Box。
AX:A5.2(步长有界):单事件更新 |Δθ_k| <= η0 * step_k。
"""

from __future__ import annotations

from dataclasses import dataclass

# AX:A5.1 —— Box(硬界),逐分量语义见 arbiter_BLUEPRINT §5.3 表
BOX: dict[str, tuple[float, float]] = {
    "d_sw": (-0.05, 0.05),
    "d_rp": (-0.05, 0.05),
    "d_ex": (-0.10, 0.10),
    "gamma_offset": (-0.20, 0.20),  # gamma = 1.0 + gamma_offset,clip 后再合成
}

# AX:A5.2 —— 单事件步长上限(step_k)
STEP: dict[str, float] = {
    "d_sw": 0.002,
    "d_rp": 0.002,
    "d_ex": 0.004,
    "gamma_offset": 0.008,
}

# 结构性穷尽的可变异集(A4 铁域声明:与 P0/min_gap/narrow_p/
# high_intensity 判据/哈希键型/白名单交集为空)。
MUTABLE_SET: frozenset[str] = frozenset(BOX.keys())


def _clip(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


@dataclass(frozen=True)
class Theta:
    """hysteresis 状态的可变异部分。gamma 对外呈现为 [0.8,1.2]
    (arbiter_BLUEPRINT §5.3 表的字面范围),内部按 ``gamma = 1.0 +
    gamma_offset`` 存储,便于 Box 投影用统一的"以 0 为中性点"的加法更新
    ——这是实现选择,不改变对外契约(``gamma`` property 与表面语义一致)。
    """

    d_sw: float = 0.0
    d_rp: float = 0.0
    d_ex: float = 0.0
    gamma_offset: float = 0.0

    @property
    def gamma(self) -> float:
        return 1.0 + self.gamma_offset

    def project(self) -> "Theta":
        """AX:A5.1 —— 逐坐标投影回 Box(T1(i) 的直接依据)。"""
        return Theta(
            d_sw=_clip(self.d_sw, *BOX["d_sw"]),
            d_rp=_clip(self.d_rp, *BOX["d_rp"]),
            d_ex=_clip(self.d_ex, *BOX["d_ex"]),
            gamma_offset=_clip(self.gamma_offset, *BOX["gamma_offset"]),
        )

    def in_box(self) -> bool:
        return (
            BOX["d_sw"][0] - 1e-12 <= self.d_sw <= BOX["d_sw"][1] + 1e-12
            and BOX["d_rp"][0] - 1e-12 <= self.d_rp <= BOX["d_rp"][1] + 1e-12
            and BOX["d_ex"][0] - 1e-12 <= self.d_ex <= BOX["d_ex"][1] + 1e-12
            and BOX["gamma_offset"][0] - 1e-12
            <= self.gamma_offset
            <= BOX["gamma_offset"][1] + 1e-12
        )

    def to_dict(self) -> dict:
        return {
            "d_sw": self.d_sw,
            "d_rp": self.d_rp,
            "d_ex": self.d_ex,
            "gamma": self.gamma,
        }

    @staticmethod
    def from_dict(d: dict) -> "Theta":
        gamma = d.get("gamma", 1.0)
        return Theta(
            d_sw=d.get("d_sw", 0.0),
            d_rp=d.get("d_rp", 0.0),
            d_ex=d.get("d_ex", 0.0),
            gamma_offset=gamma - 1.0,
        )


BOX_VERTICES: tuple[Theta, ...] = tuple(
    Theta(d_sw=a, d_rp=b, d_ex=c, gamma_offset=d)
    for a in BOX["d_sw"]
    for b in BOX["d_rp"]
    for c in BOX["d_ex"]
    for d in BOX["gamma_offset"]
)
