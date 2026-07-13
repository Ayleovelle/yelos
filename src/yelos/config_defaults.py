"""新建模块级默认值(施工纪律:不编辑 ``config.py``,增量默认值放本文件)。

``config.py`` 若要接入 ``guidance_profile`` 配置键(蓝图 §5.2 明示增量),
从本文件 import 默认值即可,不改动本文件之外的既有配置代码。当前没有任何
运行时代码依赖本文件——``build_guidance``/``build_compact_surface`` 的
``profile`` 入参自带默认值 ``"chat"``,不强制读取这里,保持 guidance 纯函数
零配置依赖(I4)。这里只是给 config.py 接线时用的稳定默认值来源。
"""

from __future__ import annotations

# guidance 模块 profile 选择的进程级默认值(蓝图 §5.2:config.py 新键
# ``guidance_profile``,默认 "chat" = 与 v0.1 行为一致)。
GUIDANCE_PROFILE_DEFAULT: str = "chat"

# guidance 模块 phrasebook 语言的进程级默认值(蓝图 §5.4:M1 未落地/未过
# RE8 审校时恒 "zh")。
GUIDANCE_LANG_DEFAULT: str = "zh"

__all__ = ["GUIDANCE_PROFILE_DEFAULT", "GUIDANCE_LANG_DEFAULT"]
