"""剧本层(bench_BLUEPRINT §4)——维二的真策略族:DSL 手写 / 程序化合成。

W4 全量交付面:``Scenario``/``ScenarioDay``/``ScenarioEvent`` 规范形
(schema.py)+ DSL 全文法解析器(dsl.py)+ 合成器五原型全量(synth.py)+
语料表(corpus.py + ``library/corpus_zh.yel``)+ 入库剧本文本
(``library/*.yel``:5 原型 × 30 日、3 原型 × 90 日、1 原型 × 365 日、
2 份手写对抗/记忆探针示范剧本)。``list_library()`` 是仓内消费者③的
最小读取器(§8.1#6 邻近纪律:契约与读取器归 bench,内容是数据)。
"""

from __future__ import annotations

from pathlib import Path

from .schema import Scenario, ScenarioDay, ScenarioEvent

__all__ = ["Scenario", "ScenarioDay", "ScenarioEvent", "LIBRARY_DIR", "list_library"]

LIBRARY_DIR = Path(__file__).resolve().parent / "library"


def list_library(library_dir: Path | None = None) -> list[Path]:
    """入库剧本文件路径清单(``.yel``,按文件名排序,确定性)。"""
    d = Path(library_dir) if library_dir is not None else LIBRARY_DIR
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.yel") if p.name != "corpus_zh.yel")
