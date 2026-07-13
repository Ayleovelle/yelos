"""稳定导入路径:``yelos.guidance._v01_compat``。

v0.1 逐字实现物理上住在 ``__init__.py``(见该文件顶部说明:AST 兼容闸的
``inspect.getfile`` 语义决定了它不能只是"重导出"的空壳)。本文件反向从
``__init__`` 取那两个冻结函数,给需要显式"我要的是 v0.1 冻结版"这条稳定
路径的消费者用(差分测试、未来 treegen 等),不重复定义逻辑。
"""

from __future__ import annotations

from . import _legacy_build_compact_surface as build_compact_surface
from . import _legacy_build_guidance as build_guidance

__all__ = ["build_guidance", "build_compact_surface"]
