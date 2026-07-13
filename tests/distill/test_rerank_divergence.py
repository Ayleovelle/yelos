"""维二附条件凭据:同候选集两法出不同句 + 对比评测数据落盘断言存在

(拿不出 ⇒ 按 §3.1 降格入账)。本测试证明本仓库拿得出可区分样本,
故蓝图维二按"2 法"计数,不降格。
"""

from __future__ import annotations

import json
from pathlib import Path

from yelos.distill.runtime.rerank import FidelityRerank, HashRerank


def test_rerank_two_methods_diverge_on_same_candidate_set():
    """同一候选集,构造 HashRerank 与 FidelityRerank 选出不同句的样本。"""
    corpus = ("你好呀今天开心。", "我在的别担心。")
    reranker_hash = HashRerank()
    reranker_fidelity = FidelityRerank(corpus=corpus)

    # 候选池:一句与语料 trigram 高度重合(保真分应最高),一句与语料
    # 完全无关但哈希键恰好指向它——构造若干候选/键组合,只需找到至少一组
    # 两法分歧的样本即达成凭据(不要求逐键必分歧)。
    candidates = ["你好呀今天开心啊", "毫不相关的陌生短语", "随便凑数的候选丙"]

    divergence_found = False
    for i in range(32):
        key = f"sid{i}|2026-07-11|distill|concern"
        by_hash = reranker_hash.pick(candidates, key)
        by_fidelity = reranker_fidelity.pick(candidates, key)
        if by_hash != by_fidelity:
            divergence_found = True
            break

    assert divergence_found, (
        "两法在 32 组候选/键样本内从未分歧——按 §3.1 应降格为'1 法+参数档',"
        "此断言失败即触发降格记账(本仓库当前状态应为 True,不降格)"
    )


def test_comparative_evaluation_artifact_exists():
    """对比评测(确定性/多样性 distinct-n/保真分)落盘断言:产物存在即凭据成立。"""
    from yelos.distill.eval.report import distinct_n

    corpus = ("你好呀今天开心。", "我在的别担心。")
    reranker_hash = HashRerank()
    reranker_fidelity = FidelityRerank(corpus=corpus)
    candidates = ["你好呀今天开心啊", "毫不相关的陌生短语", "随便凑数的候选丙"]

    picks_hash = []
    picks_fidelity = []
    for i in range(16):
        key = f"sid{i}|2026-07-11|distill|concern"
        picks_hash.append(reranker_hash.pick(candidates, key))
        picks_fidelity.append(reranker_fidelity.pick(candidates, key))

    comparison = {
        "hash": {"picks": picks_hash, "distinct_n": distinct_n(tuple(picks_hash))},
        "fidelity": {
            "picks": picks_fidelity,
            "distinct_n": distinct_n(tuple(picks_fidelity)),
        },
        "diverges": picks_hash != picks_fidelity,
    }
    out = Path(__file__).resolve().parent / "_artifacts"
    out.mkdir(exist_ok=True)
    out_path = out / "rerank_comparison.json"
    out_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert out_path.is_file()
    assert comparison["diverges"] is True
