"""stub golden:同键同输出、跨进程重放、key 键型已登记 determinism.py(→DA3);

rerank 两法各自确定。
"""

from __future__ import annotations

from yelos.distill.packaging.verify import LoadState
from yelos.distill.runtime.provider import SylannDistilledProvider
from yelos.distill.runtime.rerank import FidelityRerank, HashRerank
from yelos.primal import determinism

from .conftest import FakeGate, FakeLoader
from .stub_model import StubBackend


def _provider(loader, gate, reranker, clock, fixed_deps):
    return SylannDistilledProvider(
        loader=loader,
        gate=gate,
        reranker=reranker,
        clock=clock,
        budget_ms=50,
        k_candidates=4,
        **fixed_deps,
    )


def test_determinism_golden_same_key_same_output(virtual_clock, fixed_deps):
    backend = StubBackend(["候选甲。", "候选乙。", "候选丙。"])
    loader = FakeLoader(LoadState.READY, backend=backend)
    gate = FakeGate(allowed={"候选甲。", "候选乙。", "候选丙。"})
    provider = _provider(loader, gate, HashRerank(), virtual_clock, fixed_deps)

    out1 = provider.utter_canonical(
        {"seed": "x"},
        "sid1",
        "2026-07-11",
        "concern",
        p=0.5,
        epoch=0,
        lang="zh",
        context={"corpus": ()},
    )
    out2 = provider.utter_canonical(
        {"seed": "x"},
        "sid1",
        "2026-07-11",
        "concern",
        p=0.5,
        epoch=0,
        lang="zh",
        context={"corpus": ()},
    )
    assert out1 == out2


def test_determinism_cross_process_replay_same_key_format(virtual_clock, fixed_deps):
    """ "跨进程重放":新建全套对象(模拟另一进程),同键仍同输出。"""

    def _run():
        backend = StubBackend(["候选甲。", "候选乙。", "候选丙。"])
        loader = FakeLoader(LoadState.READY, backend=backend)
        gate = FakeGate(allowed={"候选甲。", "候选乙。", "候选丙。"})
        provider = _provider(loader, gate, HashRerank(), virtual_clock, fixed_deps)
        return provider.utter_canonical(
            {"seed": "x"},
            "sid1",
            "2026-07-11",
            "concern",
            p=0.5,
            epoch=0,
            lang="zh",
            context={"corpus": ()},
        )

    assert _run() == _run()


def test_rerank_key_format_registered_in_determinism_registry():
    assert "distill" in determinism.KEY_REGISTRY
    meta = determinism.KEY_REGISTRY["distill"]
    assert meta["format"] == "{sid}|{day_key}|distill|{occasion}"


def test_hash_rerank_deterministic():
    reranker = HashRerank()
    passed = ["a", "b", "c", "d"]
    key = "sid1|2026-07-11|distill|concern"
    assert reranker.pick(passed, key) == reranker.pick(passed, key)


def test_fidelity_rerank_deterministic():
    reranker = FidelityRerank(corpus=("你好呀。", "在的呢。"))
    passed = ["你好呀啊", "完全无关的文本"]
    key = "sid1|2026-07-11|distill|concern"
    assert reranker.pick(passed, key) == reranker.pick(passed, key)
