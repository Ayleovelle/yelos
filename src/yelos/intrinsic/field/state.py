"""field/state.py 在整个架构中的位置:场状态与参数的数据类(维一 §1.1)。

四通道内在场 φ ∈ [0,1]^4 = (drive, languor, longing, afterglow)。
本文件只定义状态/参数的数据结构与 [AX-1] 有界性算子;演化方程在
dynamics.py,积分器在 integrators.py——本文件不含任何步进逻辑。

零 random / 零 time.time()(AX-7);ts 字段由调用方传入(AX-8)。
"""

from __future__ import annotations

from dataclasses import dataclass

Vec4 = tuple[float, float, float, float]

CHANNEL_NAMES: tuple[str, str, str, str] = ("drive", "languor", "longing", "afterglow")


def _clip01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


@dataclass(frozen=True)
class FieldState:
    """内在场瞬时状态;四通道 + 上次步进时刻(入参化,AX-8)。"""

    drive: float
    languor: float
    longing: float
    afterglow: float
    ts: float

    def vec(self) -> Vec4:
        return (self.drive, self.languor, self.longing, self.afterglow)

    def clipped(self) -> "FieldState":
        """[AX-1] 有界性:clip 是最后一步,任何项组合不可越界。"""
        return FieldState(
            drive=_clip01(self.drive),
            languor=_clip01(self.languor),
            longing=_clip01(self.longing),
            afterglow=_clip01(self.afterglow),
            ts=self.ts,
        )

    @classmethod
    def from_vec(cls, v: Vec4, ts: float) -> "FieldState":
        return cls(
            drive=v[0], languor=v[1], longing=v[2], afterglow=v[3], ts=ts
        ).clipped()

    @classmethod
    def neutral(cls, ts: float = 0.0) -> "FieldState":
        """中性初始化(binding schema 缺省态,INTEGRATION_SPEC §2.1)。"""
        return cls(drive=0.2, languor=0.2, longing=0.2, afterglow=0.0, ts=ts)

    def to_dict(self) -> dict:
        return {
            "drive": self.drive,
            "languor": self.languor,
            "longing": self.longing,
            "afterglow": self.afterglow,
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, d: dict | None, *, default_ts: float = 0.0) -> "FieldState":
        if not d:
            return cls.neutral(default_ts)
        return cls(
            drive=float(d.get("drive", 0.2)),
            languor=float(d.get("languor", 0.2)),
            longing=float(d.get("longing", 0.2)),
            afterglow=float(d.get("afterglow", 0.0)),
            ts=float(d.get("ts", default_ts)),
        ).clipped()


@dataclass(frozen=True)
class FieldParams:
    """通道演化参数;域界由 build_intrinsic 组合根校验(§6.4 config schema)。"""

    lam: Vec4 = (0.35, 0.2, 0.05, 0.9)
    """Λ 对角,全正[AX-2]。默认:afterglow 快衰减,longing 慢通道。"""

    eq: Vec4 = (0.2, 0.2, 0.2, 0.0)
    """φ_eq 均衡点(中性态)。"""

    i_max: float = 0.6
    """冲击向量单类范数上限[AX-4]。"""

    def validate(self) -> None:
        if any(v <= 0.0 for v in self.lam):
            raise ValueError("FieldParams.lam 全部通道必须为正 [AX-2]")
        if any(not (0.0 <= v <= 1.0) for v in self.eq):
            raise ValueError("FieldParams.eq 必须落在 [0,1]")
        if self.i_max <= 0.0:
            raise ValueError("FieldParams.i_max 必须为正 [AX-4]")

    def to_dict(self) -> dict:
        return {"lam": list(self.lam), "eq": list(self.eq), "i_max": self.i_max}

    @classmethod
    def from_dict(cls, d: dict | None) -> "FieldParams":
        if not d:
            return cls()
        lam = d.get("lam")
        eq = d.get("eq")
        p = cls(
            lam=tuple(float(x) for x in lam) if lam else cls().lam,
            eq=tuple(float(x) for x in eq) if eq else cls().eq,
            i_max=float(d.get("i_max", cls().i_max)),
        )
        p.validate()
        return p


__all__ = ["Vec4", "CHANNEL_NAMES", "FieldState", "FieldParams"]
