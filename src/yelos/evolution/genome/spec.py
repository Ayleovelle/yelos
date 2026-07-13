"""genome/spec.py 在整个架构中的位置:GeneSpec / Genome 数据结构(蓝图 §2.1)。

``GeneSpec`` 是注册表一行的 schema;``Genome`` 是"键 -> 当前值"的只读映射
——只含 ``REGISTRY`` 内的键,不带任何未注册的幽灵键。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

Genome = Mapping[str, object]


@dataclass(frozen=True)
class GeneSpec:
    """一个可注册参数的完整声明(§2.1)。

    ``mutable=False`` 即铁域(A2):静态守卫对该键的任何变异请求结构性拒绝,
    与运行时检查无关——它是"没有被更新的路径"这件事本身的文档化声明。
    """

    key: str
    module: str
    kind: str  # "float" | "int" | "enum"
    lo: float | None
    hi: float | None
    choices: tuple[str, ...]
    default: object
    mutable: bool
    semantics: str

    def in_domain(self, value: object) -> bool:
        """域界判定(A1 裁剪的判据面)。"""
        if self.kind == "enum":
            return value in self.choices
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        lo = self.lo if self.lo is not None else float("-inf")
        hi = self.hi if self.hi is not None else float("inf")
        return lo <= float(value) <= hi

    def clip(self, value: object) -> object:
        """域界裁剪(A1);enum 域界外原样返回(由调用方拒绝,不猜插值)。"""
        if self.kind == "enum":
            return value
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return self.default
        lo = self.lo if self.lo is not None else float("-inf")
        hi = self.hi if self.hi is not None else float("inf")
        clipped = min(max(float(value), lo), hi)
        return int(round(clipped)) if self.kind == "int" else clipped


__all__ = ["GeneSpec", "Genome"]
