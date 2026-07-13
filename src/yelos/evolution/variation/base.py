"""variation/base.py 在整个架构中的位置:VariationStrategy 协议 + A3 唯一出口(蓝图 §2.1)。

``clamp_step`` 是全部策略提案的唯一出口(A3:漂移速度上界公理)。零真随机
(总纲 §2.7):伪随机源经 ``primal.determinism`` 的哈希族,新增 ``evo`` 键型
(§2.2),不在此文件重复定义 hashlib——``primal/determinism.py`` 是全平台
唯一 hashlib 落点(蓝图 §10 纪律),本包 AST 扫描零 ``import hashlib``。
"""

from __future__ import annotations

from typing import Protocol

from ..genome.spec import Genome, GeneSpec

EVO_KEY_FMT = "evo|{deployment_id}|{gen}|{strategy}|{key}"
EVO_TIE_KEY_FMT = "evo|{deployment_id}|{gen}|tie"


class VariationStrategy(Protocol):
    """确定性提案协议:同 ``parent``/``gen``/``seed`` 恒同提案。"""

    name: str

    def propose(self, parent: Genome, gen: int, seed: str) -> tuple[Genome, ...]:
        """提案已过 ``clamp_step``(A3)与域界裁剪(A1);候选只在可变异维上
        与亲代不同。"""
        ...


def evo_hash_unit(deployment_id: str, gen: int, strategy: str, key: str) -> float:
    """``evo`` 键型的确定性 [0,1) 单位值(§2.2 evo 变异键)。"""
    from ..genome.registry import spec_for  # noqa: PLC0415 避免循环
    from ...primal.determinism import h_byte  # noqa: PLC0415

    _ = spec_for  # 仅供未来扩展引用,占位不影响本函数纯度
    hkey = EVO_KEY_FMT.format(
        deployment_id=deployment_id, gen=gen, strategy=strategy, key=key
    )
    return h_byte(hkey) / 256.0


def evo_tie_hash_unit(deployment_id: str, gen: int) -> float:
    """``evo`` 平手键的确定性 [0,1) 单位值(§2.2)。"""
    from ...primal.determinism import h_byte  # noqa: PLC0415

    hkey = EVO_TIE_KEY_FMT.format(deployment_id=deployment_id, gen=gen)
    return h_byte(hkey) / 256.0


def clamp_step(  # EVO-A3
    spec: GeneSpec, old: object, new: object, velocity_bound: float
) -> object:
    """A3 的唯一实现出口。

    数值参数:``|new-old| <= step_cap`` 其中
    ``step_cap = velocity_bound * (hi - lo)``;超界裁到该上界方向的边界值,
    再交 ``spec.clip`` 做域界裁剪(A1)。枚举参数:每代至多变一档——不满足
    则拒(原样返回 ``old``,不是"取消变异"以外的任何插值)。
    """
    if spec.kind == "enum":
        if new == old:
            return old
        return new if new in spec.choices else old

    old_v = float(old) if isinstance(old, (int, float)) else float(spec.default)
    new_v = float(new) if isinstance(new, (int, float)) else old_v
    lo = spec.lo if spec.lo is not None else old_v
    hi = spec.hi if spec.hi is not None else old_v
    step_cap = velocity_bound * (hi - lo)
    delta = new_v - old_v
    if delta > step_cap:
        new_v = old_v + step_cap
    elif delta < -step_cap:
        new_v = old_v - step_cap
    return spec.clip(new_v)


__all__ = [
    "VariationStrategy",
    "clamp_step",
    "evo_hash_unit",
    "evo_tie_hash_unit",
    "EVO_KEY_FMT",
    "EVO_TIE_KEY_FMT",
]
