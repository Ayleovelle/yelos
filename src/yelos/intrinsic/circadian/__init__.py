"""circadian/ 在整个架构中的位置:昼夜强迫曲线与用户相位在线学习(维一)。

`forcing.py` 提供 C(τ) 分段余弦强迫(quiet_hours 硬窗语义不在此——硬窗在
impulses/gates.py);`phase_learn.py` 是纯统计的圆均值/集中度学习,禁 ToM
越界(总纲 §2.3 明文边界:不建模内容/情绪/状态,输入面只收分钟整数)。
"""

from __future__ import annotations
