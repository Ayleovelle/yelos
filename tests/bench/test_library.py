"""剧本库入库(bench_BLUEPRINT §9 W4 交付)——语料表 + 入库 ``.yel`` 文本。"""

from __future__ import annotations

import asyncio

import pytest

from yelos.bench import run_bench
from yelos.bench.scenarios import list_library
from yelos.bench.scenarios.corpus import CORPUS_ZH_PATH, load_corpus
from yelos.bench.scenarios.dsl import load_file


def _run(coro):
    return asyncio.run(coro)


def test_corpus_zh_loads_and_covers_all_tiers():
    corpus = load_corpus(CORPUS_ZH_PATH)
    assert corpus, "语料表不应为空"
    for tier in ("calm", "intimate", "pressure", "withdraw"):
        keys = [k for k in corpus if k.startswith(f"{tier}_")]
        assert len(keys) >= 5, f"{tier} 档语料条目不足:{keys}"
    for k, v in corpus.items():
        assert v, f"{k} 语料值不得为空"


def test_library_lists_only_yel_files_excluding_corpus():
    files = list_library()
    assert files, "剧本库不应为空"
    names = {p.name for p in files}
    assert "corpus_zh.yel" not in names
    assert all(p.suffix == ".yel" for p in files)


def test_library_files_parse_without_error():
    for path in list_library():
        scenario = load_file(path)
        assert scenario.scenario_id
        assert scenario.days or scenario.scenario_id  # 至少能解析成 Scenario


@pytest.mark.parametrize("path", list_library(), ids=lambda p: p.name)
def test_library_scenario_runs_without_veto(path):
    scenario = load_file(path)
    report = _run(run_bench(scenario))
    assert report.vetoes == [], f"{path.name} 出现否决:{report.vetoes}"


def test_library_contains_both_origins():
    """§9 交付面:入库剧本须含 synth(统计形态)与 dsl(手写对抗/示范)两种
    出身——策略族可观测差异的机器凭据(§4.3)。
    """
    origins = {load_file(p).origin for p in list_library()}
    assert origins == {"dsl"}, (
        "入库文件本身走 dsl.parse 落地(origin 恒 dsl);synth 来源体现在"
        "生成时的 scenario_id 前缀(synth-*),origin 字段是解析器落的元数据"
    )
    synth_named = [
        p
        for p in list_library()
        if p.stem.split("_")[0]
        in ("honeymoon", "fatigue", "reunion", "pressure", "silence")
        and "adversarial" not in p.stem
        and "probe" not in p.stem
    ]
    assert len(synth_named) >= 5, "应含 synth 原型批量落库的剧本"
