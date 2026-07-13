"""T-G3:ArbiterPipeline 性质测试 —— 后置滤波只降不升;守卫只产 PASS;
组合根装配校验 fail-fast。
"""

from __future__ import annotations

import random

import pytest

from yelos.arbiter import assemble_checks, build_pipeline
from yelos.arbiter.core_probe import build_neutral_probe
from yelos.arbiter.guards import GUARD_CHAIN, POST_FILTERS, assert_guards_pass_only
from yelos.arbiter.inputs import PolicyParams
from yelos.arbiter.lattice import sigma_of
from yelos.core.arbiter import Verdict


def test_assemble_checks_idempotent():
    # 已在 import 时跑过一次;显式重跑不应报错(装配自检是纯校验,无副作用)。
    assemble_checks()


def test_guard_only_pass():
    assert_guards_pass_only(GUARD_CHAIN)


def test_postfilter_downgrade_only_property():
    rng = random.Random(20260711)
    kinds = ["PASS", "TRIM", "REPLACE", "SWALLOW"]
    for _ in range(500):
        kind = rng.choice(kinds)
        v = Verdict(kind, reason="prop")
        p = rng.choice([0.1, 0.3, 0.49, 0.5, 0.8, 1.0])
        gate_scale = rng.choice([0.8, 1.0, 1.2])
        params = PolicyParams(0.75, 0.55, 0.70, gate_scale)
        pin = build_neutral_probe(p=p, params=params)
        for f in POST_FILTERS:
            out = f(v, pin)
            assert sigma_of(out) <= sigma_of(v)


def test_table_policy_skips_guards_and_filters():
    pipe = build_pipeline("table")
    assert pipe._guards == ()  # noqa: SLF001 -- 白盒断言管线语义表 §2.1
    assert pipe._post_filters == ()  # noqa: SLF001


def test_nontable_policy_has_full_chain():
    for pid in ("smooth", "conservative", "duel"):
        pipe = build_pipeline(pid)
        assert pipe._guards == GUARD_CHAIN  # noqa: SLF001
        assert pipe._post_filters == POST_FILTERS  # noqa: SLF001


def test_unknown_policy_id_raises():
    with pytest.raises(ValueError):
        build_pipeline("does-not-exist")


def test_run_returns_verdict_and_explain():
    pipe = build_pipeline("smooth")
    pin = build_neutral_probe(action="withdraw", pressure=0.9, expr=0.9)
    verdict, explain = pipe.run(pin)
    assert verdict.kind in ("PASS", "TRIM", "REPLACE", "SWALLOW")
    assert explain.policy_id == "smooth"
    assert len(explain.theta_digest) == 8


def test_p0_guard_short_circuits_and_produces_pass_only():
    pipe = build_pipeline("smooth")
    pin = build_neutral_probe(pressure=0.9, expr=0.9)
    base = pin.base
    silenced_base = base.__class__(**{**base.__dict__, "silenced": True})
    from yelos.arbiter.inputs import PolicyInput

    pin2 = PolicyInput(
        base=silenced_base, surface_age_s=0.0, daily_interventions=0, params=pin.params
    )
    verdict, explain = pipe.run(pin2)
    assert verdict.kind == "PASS"
    assert explain.guard_trace[0].guard_id == "p0_sovereignty"
    assert explain.guard_trace[0].fired is True
