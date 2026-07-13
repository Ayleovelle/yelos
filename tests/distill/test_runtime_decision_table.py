"""4.1 决策表 R1–R6 全行(→DA1/DA2);R1–R5 断言"调用方可观测 ≡ 无 distill"

(干净缺席专测,契约点名项);超时用假时钟不真睡。
"""

from __future__ import annotations

import pytest

from yelos.distill.packaging.verify import LoadState
from yelos.distill.runtime.provider import SylannDistilledProvider
from yelos.distill.runtime.rerank import HashRerank
from yelos.primal.providers import ProviderUnavailable

from .conftest import FakeGate, FakeLoader
from .stub_model import StubBackend, StubLoadError


def _make_provider(loader, gate, clock, fixed_deps, *, budget_ms=50, k_candidates=8):
    return SylannDistilledProvider(
        loader=loader,
        gate=gate,
        reranker=HashRerank(),
        clock=clock,
        budget_ms=budget_ms,
        k_candidates=k_candidates,
        **fixed_deps,
    )


def _call(provider):
    return provider.utter_canonical(
        {"seed": "concern"},
        "sid1",
        "2026-07-11",
        "concern",
        p=0.5,
        epoch=0,
        lang="zh",
        context={"corpus": ("你好。",)},
    )


# R1 ------------------------------------------------------------------------


def test_r1_absent_raises_provider_unavailable(virtual_clock, fixed_deps):
    loader = FakeLoader(LoadState.ABSENT)
    gate = FakeGate()
    provider = _make_provider(loader, gate, virtual_clock, fixed_deps)
    assert provider.available("sid1", "zh") is False
    with pytest.raises(ProviderUnavailable):
        _call(provider)
    assert gate.calls == []  # 推理不发生,闸不被调用


# R2 ------------------------------------------------------------------------


def test_r2_hash_mismatch_raises_provider_unavailable(virtual_clock, fixed_deps):
    loader = FakeLoader(LoadState.HASH_MISMATCH)
    gate = FakeGate()
    provider = _make_provider(loader, gate, virtual_clock, fixed_deps)
    assert provider.available("sid1", "zh") is False
    with pytest.raises(ProviderUnavailable):
        _call(provider)
    assert gate.calls == []


# R3 ------------------------------------------------------------------------


def test_r3_deps_missing_raises_provider_unavailable(virtual_clock, fixed_deps):
    loader = FakeLoader(LoadState.DEPS_MISSING)
    gate = FakeGate()
    provider = _make_provider(loader, gate, virtual_clock, fixed_deps)
    assert provider.available("sid1", "zh") is False
    with pytest.raises(ProviderUnavailable):
        _call(provider)
    assert gate.calls == []


# R4:超时(假时钟推进,不真睡)------------------------------------------------


def test_r4_timeout_raises_provider_unavailable(virtual_clock, fixed_deps):
    backend = StubBackend(
        ["你好。"],
        clock=virtual_clock,
        delay_ms=1000.0,  # 远超 budget_ms=50
    )
    loader = FakeLoader(LoadState.READY, backend=backend)
    gate = FakeGate(allowed={"你好。"})
    provider = _make_provider(loader, gate, virtual_clock, fixed_deps, budget_ms=50)
    with pytest.raises(ProviderUnavailable):
        _call(provider)
    assert gate.calls == []  # 超时先于闸判定


# R5:全候选被拦 --------------------------------------------------------------


def test_r5_all_candidates_rejected(virtual_clock, fixed_deps):
    backend = StubBackend(["越界句子甲", "越界句子乙"])
    loader = FakeLoader(LoadState.READY, backend=backend)
    gate = FakeGate(allowed=set())  # 全拒
    provider = _make_provider(loader, gate, virtual_clock, fixed_deps)
    with pytest.raises(ProviderUnavailable):
        _call(provider)
    assert len(gate.calls) == 2


# R6:至少一个过闸 -------------------------------------------------------------


def test_r6_at_least_one_passes(virtual_clock, fixed_deps):
    backend = StubBackend(["越界句子", "合法句子。"])
    loader = FakeLoader(LoadState.READY, backend=backend)
    gate = FakeGate(allowed={"合法句子。"})
    provider = _make_provider(loader, gate, virtual_clock, fixed_deps)
    result = _call(provider)
    assert result == "合法句子。"


# 加载期异常同样走 DA2 回退,不抛到调用方 ---------------------------------------


def test_loader_get_exception_is_swallowed_into_unavailable(virtual_clock, fixed_deps):
    class ExplodingLoader(FakeLoader):
        def get(self):
            raise StubLoadError("坏权重")

    loader = ExplodingLoader(LoadState.READY)
    gate = FakeGate()
    provider = _make_provider(loader, gate, virtual_clock, fixed_deps)
    with pytest.raises(ProviderUnavailable):
        _call(provider)


def test_fallback_totality_four_scenarios_never_raise_other_exceptions(
    virtual_clock, fixed_deps
):
    """DA2:四情形(缺席/加载失败/超时/全拦)× utter 恒返回 ProviderUnavailable,

    零异常上抛调用方(composer 只需捕获这一种异常即可安全跳席)。
    """
    scenarios = []

    scenarios.append(
        _make_provider(
            FakeLoader(LoadState.ABSENT), FakeGate(), virtual_clock, fixed_deps
        )
    )

    class ExplodingLoader(FakeLoader):
        def get(self):
            raise StubLoadError("坏权重")

    scenarios.append(
        _make_provider(
            ExplodingLoader(LoadState.READY), FakeGate(), virtual_clock, fixed_deps
        )
    )

    timeout_backend = StubBackend(["你好。"], clock=virtual_clock, delay_ms=1000.0)
    scenarios.append(
        _make_provider(
            FakeLoader(LoadState.READY, backend=timeout_backend),
            FakeGate(allowed={"你好。"}),
            virtual_clock,
            fixed_deps,
        )
    )

    reject_backend = StubBackend(["越界"])
    scenarios.append(
        _make_provider(
            FakeLoader(LoadState.READY, backend=reject_backend),
            FakeGate(allowed=set()),
            virtual_clock,
            fixed_deps,
        )
    )

    for provider in scenarios:
        with pytest.raises(ProviderUnavailable):
            _call(provider)
