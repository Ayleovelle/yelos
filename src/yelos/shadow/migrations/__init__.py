"""migrations/ 在整个架构中的位置:binding v1→v2 迁移脚本的落点(蓝图 §3.3)。

蓝图原文写的路径是 `scripts/migrate_binding_v1_to_v2.py`;本实现改落
`src/yelos/shadow/migrations/`,与 intrinsic 波已建立的
`src/yelos/intrinsic/migrations/migrate_intrinsic_field.py` 同一约定——
两处迁移脚本都需要 import 本模块内部的默认值构造函数,放在包内比放在
仓库根 `scripts/` 更利于随包分发与单测 import,且避免与 W-UI/finitude
未来可能各自也要一个顶层 `scripts/` 目录产生命名冲突。此偏离已记入模块
交付说明供红队核对。
"""

from __future__ import annotations
