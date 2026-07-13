"""hysteresis/ema.py 在整个架构中的位置。

双 EMA 共识门。思想承自一代 personality.py(TraitMemory)的双 EMA 结构,
**实现自著**——差异见 arbiter_BLUEPRINT §5.2:一代按特质各持双 EMA、
共识时全量漂移 + 恒稳态回拉;Yelos 版按介入种类归因、共识门是 0/1
硬门(非共识寸步不动)、且学习率与幕 V 可塑性 P 耦合(一代无此耦合)。

AX:A5.4(共识门):参数仅在快慢 EMA 同号(共识)时移动;非共识 ⇒ Δθ=0。
τ≈8(快)/τ≈64(慢):τ 与 α 的关系 α = 2/(τ+1),四舍五入到题面给定的
2/9、2/65(对应 τ=8、τ=64.5≈64,沿用蓝图字面常量,不重新导出)。
"""

from __future__ import annotations

from dataclasses import dataclass

ALPHA_FAST = 2.0 / 9.0  # τ≈8
ALPHA_SLOW = 2.0 / 65.0  # τ≈64


@dataclass(frozen=True)
class EmaState:
    fast: float = 0.0
    slow: float = 0.0

    def update(self, r: float) -> "EmaState":
        return EmaState(
            fast=(1 - ALPHA_FAST) * self.fast + ALPHA_FAST * r,
            slow=(1 - ALPHA_SLOW) * self.slow + ALPHA_SLOW * r,
        )

    def consensus(self) -> int:
        """AX:A5.4 —— fast*slow > 0 时为共识(同号),否则 0。"""
        return 1 if self.fast * self.slow > 0 else 0

    def to_dict(self) -> dict:
        return {"fast": self.fast, "slow": self.slow}

    @staticmethod
    def from_dict(d: dict) -> "EmaState":
        return EmaState(fast=d.get("fast", 0.0), slow=d.get("slow", 0.0))
