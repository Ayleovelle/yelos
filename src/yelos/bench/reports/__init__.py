"""报告层(bench_BLUEPRINT §7.1)——JSON 报告装配 + 自著零依赖 SVG 渲染
(仓内消费者①,golden 锁)。regression 门禁挂 CI 见 ``..regression``。
"""

from __future__ import annotations

from .report import build
from .svg import render_report_svg

__all__ = ["build", "render_report_svg"]
