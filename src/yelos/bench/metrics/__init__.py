"""六维判分(bench_BLUEPRINT §6)——公共结构 + 注册表 + 聚合(AX-B2 唯一实现点)。

W4 全量交付:``Score``/``EvalContext`` 公共结构、``MetricRegistry``、
``aggregate()``(AX-B2 否决语义)+ 六维全部注册。维 A(克制)全曲线、维 D
(老化)否决 + 自著形状学、维 E(记忆)探针命中率+MRR(直接 import 已落地
的 ``yelos.memory``)、维 F(心疼精度)只读 shadow 校准账本的 jsonl 契约
(**不 import ``yelos.shadow``**——shadow 与 bench 同波并行建,契约边界见
``metrics/concern.py`` 头注)。依赖数据缺席(剧本无探针/账本不存在/样本量
不足)时如实 ``value=None``(n/a),不占位造分(B-D6 纪律不因 W4 收口而
放松)。

``EvalContext``(相对蓝图 §11 的实用化调整,记入本次施工疑义清单):蓝图
``MetricRegistry.register(dim, fn: Callable[[RunTrace], Score])`` 假定判分
函数只读单条 trace,但维 B(一致)按 AX-B1 定义天然需要"同剧本双跑"的第二
条 trace(+ 可选 golden digest)做比较,单 trace 参数放不下这个语义。W1 把
注册表签名改为 ``Callable[[EvalContext], Score]``,``EvalContext`` 携带
``trace``(主跑)+ ``repeat_trace``(可选,双跑校验)+ ``golden_digest``
(可选,入库基线)。其余五维只读 ``ctx.trace``,行为与蓝图签名等价。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..harness.trace import RunTrace

__all__ = ["Score", "EvalContext", "MetricRegistry", "aggregate", "default_registry"]


@dataclass
class Score:
    """单维判分结果。``value`` 为 None 表示该维不适用(n/a),不入均值。"""

    dim: str
    value: float | None
    veto: bool = False
    evidence: dict = field(default_factory=dict)


@dataclass
class EvalContext:
    """判分器的读入面(见本文件顶部 docstring 的 W1 实用化调整说明)。

    ``data_dir``(W4 新增):维 F(``metrics/concern.py``)读 shadow 校准
    账本 jsonl 的落盘根目录(契约路径 ``<data_dir>/shadow/calibration/
    {sid_hash}.jsonl``,INTEGRATION_SPEC C10)。``None`` 时维 F 恒 n/a
    (bench 自身的 fake 档回放不产出该账本,只有真会话/真 shadow 运行过的
    data_dir 才有得读)。
    """

    trace: RunTrace
    repeat_trace: RunTrace | None = None
    golden_digest: str | None = None
    data_dir: Path | None = None


class MetricRegistry:
    """六维注册表:插入顺序即判分顺序(dict 保序,蓝图 §11"顺序确定")。"""

    def __init__(self) -> None:
        self._fns: dict[str, Callable[[EvalContext], Score]] = {}

    def register(self, dim: str, fn: Callable[[EvalContext], Score]) -> None:
        self._fns[dim] = fn

    def evaluate(self, ctx: EvalContext) -> list[Score]:
        return [fn(ctx) for fn in self._fns.values()]


def aggregate(scores: list[Score]) -> dict:
    """AX-B2(bench_BLUEPRINT §2)唯一实现点:任一 veto ⇒ overall="FAIL"。"""
    per_dim = {
        s.dim: {"value": s.value, "veto": s.veto, "evidence": s.evidence}
        for s in scores
    }
    vetoes = [s.dim for s in scores if s.veto]
    if vetoes:
        return {"overall": "FAIL", "per_dim": per_dim, "vetoes": vetoes}
    values = [s.value for s in scores if s.value is not None]
    overall = sum(values) / len(values) if values else None
    return {"overall": overall, "per_dim": per_dim, "vetoes": []}


def default_registry() -> MetricRegistry:
    """组合根(bench_BLUEPRINT §11"六维注册于组合根,顺序确定")。W4 全量:
    六维皆注册(维 E/F 依赖数据缺席时如实返回 ``value=None``,不占位造分)。
    """
    from . import aging, concern, consistency, memory_dim, restraint, sovereignty

    reg = MetricRegistry()
    reg.register("restraint", restraint.evaluate)
    reg.register("consistency", consistency.evaluate)
    reg.register("sovereignty", sovereignty.evaluate)
    reg.register("aging", aging.evaluate)
    reg.register("memory", memory_dim.evaluate)
    reg.register("concern", concern.evaluate)
    return reg
