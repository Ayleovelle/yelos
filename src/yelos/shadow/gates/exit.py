"""exit.py 在整个架构中的位置:[SHTOM-A2] 一切影子可感输出的唯一出口(蓝图
§9)。全包任何其他函数返回值都不得被 session/server 直接转成用户可见
文本——只有本文件的 `apply_exit` 产出 `ConcernVerdict`,且其像空间有限可
枚举(SHTOM-T1):`ctype` 取自 `binding_v2.CTYPES` 闭包,`intensity`/`q` 量化到
3 位小数网格并钳到 `[0,1]`,`do_inject`/`do_enqueue` 是布尔。

字符串字面量全部 ASCII-only(中文说明一律 `#`/docstring 注释,不进 AST
字符串常量)——`test_whitelist.py` 的 AST 扫描锁死这条,呼应 `core/shadow.py`
的既有纪律(A2 的可执行验证面)。
"""

from __future__ import annotations

from ..binding_v2 import CTYPES
from ..contracts import ConcernVerdict

_NDIGITS = 3


def apply_exit(
    ctype: str,
    intensity: float,
    q: float,
    *,
    do_inject: bool,
    do_enqueue: bool,
    gate_trace: tuple[str, ...],
) -> ConcernVerdict:
    """[SHTOM-A2/T1] 唯一构造点。`ctype` 越界即 raise(编程错误,不是运行时
    数据问题——四检测器闭包在组合根固定,越界只可能是内部调用错误)。
    """
    if ctype not in CTYPES:
        raise ValueError(f"ctype not in enum: {ctype!r}")
    intensity_q = round(max(0.0, min(1.0, intensity)), _NDIGITS)
    q_q = round(max(0.0, min(1.0, q)), _NDIGITS)
    return ConcernVerdict(
        ctype=ctype,
        intensity=intensity_q,
        q=q_q,
        do_inject=bool(do_inject),
        do_enqueue=bool(do_enqueue),
        gate_trace=tuple(gate_trace),
    )


__all__ = ["apply_exit"]
