"""privacy 子包在架构中的位置。

隐私公理 MEM-A5 的执行面:界定函数 is_verbatim_leak()(全输出面的闸)+
PrivacyLifecycle(reset/seal_export/corpus_view,主权动作的转发目标)。
redact.py 零依赖(只做字符串扫描),lifecycle.py 依赖 contracts 与文件路径。
"""

from __future__ import annotations

from .lifecycle import PrivacyLifecycle
from .redact import is_verbatim_leak

__all__ = ["PrivacyLifecycle", "is_verbatim_leak"]
