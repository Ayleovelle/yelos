"""越界率闸前测正确(stub 可控)/ fidelity JS 距离数值性质(自距离=0,对称)/

fallback_probe 三情形 / 报告 schema 往返。
"""

from __future__ import annotations

from yelos.distill.eval.fallback_probe import fallback_probe
from yelos.distill.eval.fidelity import fidelity_js, js_divergence
from yelos.distill.eval.report import EvalReport, distinct_n, write_report
from yelos.distill.eval.violation import violation_rate
from yelos.distill.packaging.verify import LoadState
from yelos.distill.runtime.provider import SylannDistilledProvider
from yelos.distill.runtime.rerank import HashRerank
from yelos.primal.lexicon.closure import enumerate_closure
from yelos.primal.whitelist_gate import WhitelistGate, load_forbidden_patterns

from .conftest import FakeGate, FakeLoader
from .stub_model import StubBackend


def _real_gate() -> WhitelistGate:
    return WhitelistGate(
        lambda occasion, lang, band, epoch: enumerate_closure(
            occasion, lang, band, epoch
        ),
        forbidden_patterns=load_forbidden_patterns("zh"),
    )


def test_violation_rate_stub_controllable():
    gate = _real_gate()
    candidates = [
        ("你必须马上休息", "concern", "zh", "B2", 0, ()),  # 违规
        ("这不是任何一个合法句子。", "concern", "zh", "B2", 0, ()),  # 违规
    ]
    result = violation_rate(candidates, gate)
    assert result.total == 2
    assert result.violations == 2
    assert result.rate == 1.0


def test_violation_rate_empty_is_zero():
    result = violation_rate([], _real_gate())
    assert result.rate == 0.0


def test_fidelity_js_self_distance_zero():
    corpus = ("你好呀今天怎么样。", "我在的别担心。")
    assert fidelity_js(corpus, corpus) == 0.0


def test_js_divergence_symmetric():
    p = {"a": 0.6, "b": 0.4}
    q = {"a": 0.2, "b": 0.8}
    assert abs(js_divergence(p, q) - js_divergence(q, p)) < 1e-12


def test_js_divergence_both_empty_is_zero():
    assert js_divergence({}, {}) == 0.0


def test_distinct_n_properties():
    assert distinct_n(()) == 0.0
    assert distinct_n(("aa",), n=2) == 1.0  # 单一 bigram,唯一


def test_fallback_probe_three_scenarios(virtual_clock, fixed_deps):
    def make(loader, gate):
        return SylannDistilledProvider(
            loader=loader,
            gate=gate,
            reranker=HashRerank(),
            clock=virtual_clock,
            budget_ms=50,
            k_candidates=2,
            **fixed_deps,
        )

    absent_provider = make(FakeLoader(LoadState.ABSENT), FakeGate())
    timeout_backend = StubBackend(["你好。"], clock=virtual_clock, delay_ms=1000.0)
    timeout_provider = make(
        FakeLoader(LoadState.READY, backend=timeout_backend),
        FakeGate(allowed={"你好。"}),
    )
    reject_backend = StubBackend(["越界"])
    rejected_provider = make(
        FakeLoader(LoadState.READY, backend=reject_backend), FakeGate()
    )

    def _call(provider):
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

    result = fallback_probe(
        {
            "absent": lambda: _call(absent_provider),
            "timeout": lambda: _call(timeout_provider),
            "rejected": lambda: _call(rejected_provider),
        }
    )
    assert result == {"absent": True, "timeout": True, "rejected": True}


def test_report_schema_round_trip(tmp_path):
    report = EvalReport(
        tier="ngram",
        corpus_hash="abc",
        model_hash="def",
        violation_rate_pregate=0.1,
        fidelity_js={"concern": 0.2},
        fallback_probe={"absent": True, "timeout": True, "rejected": True},
        distinct_n=0.8,
    )
    json_path, md_path = write_report(report, tmp_path)
    assert json_path.is_file() and md_path.is_file()

    import json

    raw = json.loads(json_path.read_text(encoding="utf-8"))
    round_tripped = EvalReport.from_dict(raw)
    assert round_tripped == report
