"""时钟协议(INTEGRATION_SPEC X2 裁定 / bench_BLUEPRINT §3.1)——全平台唯一时钟抽象。

跨模块接缝 X2 的收口:bench 与 intrinsic 曾各自定义一套虚拟时钟协议
(bench 5 法 vs intrinsic 3 法)。裁定采纳"推荐后者"选项——``Clock`` 协议
下沉到 ``yelos.core``(与 memory/primal 同批可用),**具体实现**
(``RealClock``/``VirtualClock``)归 ``yelos.bench.clock``。

本文件只放协议本体,不放实现:
- core/ 包禁 random、禁 sylanne_core、禁 astrbot(tests/test_structure.py
  的结构锁覆盖本文件所在目录);协议是纯类型声明,天然满足该禁令。
- ``RealClock`` 需要 ``time.time()``/``datetime``,``VirtualClock`` 是纯游标
  推进——两者都不需要 core 之外的任何借来符号,但按 §1.4"记账纪律"与
  bench 蓝图 §1.2 自著清单,实现体归 bench 自己的目录记账。
- memory/primal 两模块 W1 不依赖本协议(各自纯函数入参传时间戳/日期
  字符串,不持有 Clock 实例);本文件是 bench W1 骨架先行落地的一部分,
  为 W2 起 session.py 的侵入式注入(bench_BLUEPRINT §3.2)预留唯一协议面。

五法定义(bench_BLUEPRINT §3.1,逐字对齐 session.py 现有五个
``_now_ts/_day_key/_now_local_minutes/_day_end_ts/_next_quiet_start_ts``
staticmethod 的语义,便于未来"注入不改行为"的委托改造):
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """时间读取的唯一协议面。所有实现对同一虚拟/真实时刻给出相同导出值。"""

    def now_ts(self) -> float:
        """epoch 秒(浮点)。"""
        ...

    def local_minutes(self) -> int:
        """服务器本地时间的当日分钟数,0..1439。"""
        ...

    def day_key(self) -> str:
        """服务器本地日期键,格式 ``YYYY-MM-DD``。"""
        ...

    def day_end_ts(self) -> float:
        """当前本地日 23:59:59(含)对应的 epoch 秒上界。"""
        ...

    def next_quiet_start_ts(self, qstart_min: int) -> float:
        """下一次到达 ``qstart_min`` (0..1439,本地分钟)静默窗起点的 epoch 秒。

        若当前本地分钟已过 ``qstart_min``,顺延到次日同一分钟。
        """
        ...
