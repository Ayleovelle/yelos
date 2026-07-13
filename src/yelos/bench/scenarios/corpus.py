"""语料表加载器(bench_BLUEPRINT §4.1"剧本不含自由用户文本")——``.yel``
文本(数据不是代码)映 ``text_key -> 中文示例句``,自著零依赖极简格式:

    calm_00: "今天很平静，想和你说说话。"
    # 注释行,井号起
    intimate_02: "靠近一点点也好呀。"

一行一条,``key: "value"``(值必须双引号包裹,不支持嵌套/多行——比 DSL
的映射语法更窄,专为"扁平语料表"这一种形状收敛,不复用 ``scenarios/dsl.py``
的完整解析器,避免为一个平铺 key-value 表拖一整套缩进块文法)。

**本表只供人审 / 评审可读性**(§4.1"保证 trace 与报告永不携带类自由原文"
的旁证:runner/FakeBridge 只消费 ``text_key`` 的 tier 前缀,从不读这份
语料表的句子本体);程序化路径不依赖本文件存在与否。
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["parse_corpus", "load_corpus", "CORPUS_ZH_PATH"]

CORPUS_ZH_PATH = Path(__file__).resolve().parent / "library" / "corpus_zh.yel"


def parse_corpus(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        idx = raw.find("#")
        line = (raw if idx == -1 else raw[:idx]).strip()
        if not line:
            continue
        sep = line.find(": ")
        if sep == -1:
            raise ValueError(f"corpus_zh.yel 第 {lineno} 行:缺少 ': ' 分隔:{raw!r}")
        key = line[:sep].strip()
        val = line[sep + 2 :].strip()
        if len(val) < 2 or val[0] != '"' or val[-1] != '"':
            raise ValueError(f"corpus_zh.yel 第 {lineno} 行:值须双引号包裹:{raw!r}")
        out[key] = val[1:-1]
    return out


def load_corpus(path: Path | None = None) -> dict[str, str]:
    p = Path(path) if path is not None else CORPUS_ZH_PATH
    if not p.is_file():
        return {}
    return parse_corpus(p.read_text(encoding="utf-8"))
