"""migrations/ 在整个架构中的位置:intrinsic 侧 bindings.json 结构迁移脚本(X10)。

只新增文件,不改 `core/binding.py`/`persistence.py`。迁移脚本独立可运行,
幂等(已迁移的 record 直接跳过),原子写(tmp+os.replace),迁移前备份
原文件一次(`.premigrate.bak`,已存在则不覆盖备份)。
"""

from __future__ import annotations
