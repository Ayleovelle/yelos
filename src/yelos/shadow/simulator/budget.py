"""budget.py 在整个架构中的位置:心跳引擎调用预算与降档(蓝图 §4.4,RE11)。

`shadow_engine_calls_per_beat`(默认 4)= `tick_state`(主心跳自己的 1 次,
不归 shadow 管,但占同一预算)+ `shadow_state` 读取次数(K 条轨迹各 1 次,
K≤3)。超配判定用**滚动窗口**(默认最近 5 拍)的平均实际调用数与配额比较,
超了就本拍降档 `K→1`(只读 h0),降档事件必须可观测(`EnsembleReading.
degraded=True`),不静默。次日重评(`reset_window` 由 orchestrator 在日翻转
时调用)。

**有意的持久化边界**:滚动窗口状态是纯运行时软探测(进程内存,不写
binding)——它衡量的是"这个进程这段时间实际调用引擎的频率",不是这段关系
的历史事实,重启后回到未降档起点是合理默认(不属于蓝图 §3.3 schema v2 列出
的持久化字段,记入交付说明供红队核对)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULT_WINDOW = 5


def calls_for_k(k: int) -> int:
    """本拍预计引擎调用数:tick_state(1)+ shadow_state 读取(k 条轨迹各 1 次)。"""
    return 1 + max(1, k)


@dataclass
class BudgetTracker:
    """每 sid 一份的滚动调用历史(进程内存,见模块 docstring 持久化边界说明)。"""

    history: list[int] = field(default_factory=list)
    window: int = _DEFAULT_WINDOW

    def record(self, calls_this_beat: int) -> None:
        self.history.append(calls_this_beat)
        if len(self.history) > self.window:
            self.history = self.history[-self.window :]

    def reset(self) -> None:
        self.history = []

    def decide_k(self, requested_k: int, quota: int) -> tuple[int, bool]:
        """返回 `(effective_k, degraded)`。滚动窗口平均超配额 → 降档 K=1。"""
        if requested_k <= 1:
            return requested_k, False
        if not self.history:
            return requested_k, False
        avg = sum(self.history) / len(self.history)
        if avg > quota:
            return 1, True
        return requested_k, False


__all__ = ["calls_for_k", "BudgetTracker"]
