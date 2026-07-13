"""consolidation 子包在架构中的位置。

夜窗巩固管线:把新 L1 区间压成 L2 摘要、更新词表/语义向量基、驱动 L3
生命周期、遗忘强度重算、容量护栏、可视化契约刷新——全部幂等/可续跑
(MEM-A8,journal 守卫)。schedule.py 是决策表常量,jobs.py 是编排正身。
"""

from __future__ import annotations

from .jobs import NightJob
from .schedule import NIGHT_STEPS, should_refit

__all__ = ["NightJob", "NIGHT_STEPS", "should_refit"]
