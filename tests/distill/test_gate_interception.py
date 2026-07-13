"""对抗样本集(红队造:越界词/拼接注入/超长/空串/白名单近似串)拦截率

==100%(→DA1)。对抗集固化 ``tests/distill/adversarial_corpus.jsonl``,
只增不删。用**真实** ``WhitelistGate``(非 stub),证明闸真承重——不是
测试自己的假闸在自证。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yelos.distill.packaging.verify import LoadState
from yelos.distill.runtime.provider import SylannDistilledProvider
from yelos.distill.runtime.rerank import HashRerank
from yelos.primal.lexicon.closure import enumerate_closure
from yelos.primal.providers import ProviderUnavailable
from yelos.primal.whitelist_gate import WhitelistGate, load_forbidden_patterns

from .conftest import FakeLoader
from .stub_model import StubBackend

FIXTURE = Path(__file__).resolve().parent / "adversarial_corpus.jsonl"


def _load_cases() -> list[dict]:
    cases = []
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def _real_closure_fn(occasion, lang, band, epoch):
    return enumerate_closure(occasion, lang, band, epoch)


def _real_gate() -> WhitelistGate:
    return WhitelistGate(
        _real_closure_fn, forbidden_patterns=load_forbidden_patterns("zh")
    )


@pytest.mark.parametrize(
    "case", _load_cases(), ids=lambda c: c["canonical"][:12] or "empty"
)
def test_gate_interception(case, virtual_clock, fixed_deps):
    """每条对抗样本单独喂给 provider;真实闸必须拦下,provider 必须回退。"""
    backend = StubBackend([case["canonical"]])
    loader = FakeLoader(LoadState.READY, backend=backend)
    gate = _real_gate()
    provider = SylannDistilledProvider(
        loader=loader,
        gate=gate,
        reranker=HashRerank(),
        clock=virtual_clock,
        budget_ms=50,
        k_candidates=1,
        **fixed_deps,
    )
    with pytest.raises(ProviderUnavailable):
        provider.utter_canonical(
            {"seed": case["occasion"]},
            "sid1",
            "2026-07-11",
            case["occasion"],
            p=0.5,
            epoch=0,
            lang="zh",
            context={"corpus": ("你好。", "在的。", "嗯。")},
        )


def test_gate_interception_rate_is_100_percent(virtual_clock, fixed_deps):
    """汇总口径:对抗集拦截率恒 == 100%(DA1 断言的机器形态)。"""
    cases = _load_cases()
    gate = _real_gate()
    intercepted = 0
    for case in cases:
        backend = StubBackend([case["canonical"]])
        loader = FakeLoader(LoadState.READY, backend=backend)
        provider = SylannDistilledProvider(
            loader=loader,
            gate=gate,
            reranker=HashRerank(),
            clock=virtual_clock,
            budget_ms=50,
            k_candidates=1,
            **fixed_deps,
        )
        try:
            provider.utter_canonical(
                {"seed": case["occasion"]},
                "sid1",
                "2026-07-11",
                case["occasion"],
                p=0.5,
                epoch=0,
                lang="zh",
                context={"corpus": ("你好。", "在的。", "嗯。")},
            )
        except ProviderUnavailable:
            intercepted += 1
    assert intercepted == len(cases)
    assert len(cases) > 0
