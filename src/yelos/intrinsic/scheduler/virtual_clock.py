"""scheduler/virtual_clock.py 在整个架构中的位置:X2 去重后的时钟复用点。

INTEGRATION_SPEC §3.2 裁定:`Clock` 协议归 `yelos.core.clock`,具体实现
(`RealClock`/`VirtualClock`)归 `yelos.bench.clock`——**本文件不重定义**
任何时钟类,只做薄重导出,供 intrinsic 内部统一从 `scheduler.virtual_clock`
引用而不必四处 import 两个不同的包路径。禁止在此新增第二套虚拟时钟实现
(X2 必修项,W2 验收硬闸)。
"""

from __future__ import annotations

from yelos.bench.clock import RealClock, VirtualClock
from yelos.core.clock import Clock

__all__ = ["Clock", "RealClock", "VirtualClock"]
