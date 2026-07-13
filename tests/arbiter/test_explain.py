"""T-X1:v0.1 reason 全集 -> taxonomy 映射穷举;Explain 不出现在工具返回
序列化中(N1/N7,arbiter_BLUEPRINT §6.3)。
"""

from __future__ import annotations

import itertools

from yelos.arbiter.explain import REASON_TAXONOMY, taxonomy_for_reason
from yelos.core.arbiter import ArbiterInput, arbitrate

# 穷举网格,收集冻结内核 arbitrate() 实际能产生的全部 reason 字面量。
_ACTIONS = [
    "withdraw",
    "hold",
    "guard",
    "recover",
    "reach_out",
    "explore",
    "express",
    "unknown_x",
]
_PRESSURES = [0.0, 0.3, 0.55, 0.56, 0.7, 0.75, 0.76, 1.0]
_EXPRS = [0.0, 0.29, 0.3, 0.69, 0.7, 0.71, 1.0]
_PS = [0.0, 0.1, 0.15, 0.16, 0.3, 0.49, 0.5, 1.0]


def _collect_all_reasons() -> set[str]:
    reasons: set[str] = set()
    guard_variants = [
        dict(bound=False),
        dict(enabled=False),
        dict(silenced=True),
        dict(is_self=True),
        dict(has_plain=False),
        dict(has_non_plain=True),
        dict(surface=None),
        {},
    ]
    for gv in guard_variants:
        kwargs = dict(
            session_id="s",
            day_key="2026-07-11",
            draft="今天天气不错。第二句。第三句。第四句。",
            surface={
                "decision": {"action": "hold"},
                "state": {"boundary": {"pressure": 0.5}, "needs": {"expression": 0.5}},
                "guard": {"allowed": True},
            },
            p=0.8,
            bound=True,
            enabled=True,
            silenced=False,
            is_self=False,
            has_plain=True,
            has_non_plain=False,
            now_ts=100000.0,
            last_intervention_ts=0.0,
            min_gap_seconds=180,
        )
        kwargs.update(gv)
        reasons.add(arbitrate(ArbiterInput(**kwargs)).reason)

    for action, pressure, expr, p in itertools.product(
        _ACTIONS, _PRESSURES, _EXPRS, _PS
    ):
        base = ArbiterInput(
            session_id="s",
            day_key="2026-07-11",
            draft="今天天气不错,我们出去走走吧。第二句在这。第三句在这。第四句在这。",
            surface={
                "decision": {"action": action},
                "state": {
                    "boundary": {"pressure": pressure},
                    "needs": {"expression": expr},
                },
                "guard": {"allowed": True},
            },
            p=p,
            bound=True,
            enabled=True,
            silenced=False,
            is_self=False,
            has_plain=True,
            has_non_plain=False,
            now_ts=100000.0,
            last_intervention_ts=0.0,
            min_gap_seconds=180,
        )
        reasons.add(arbitrate(base).reason)
    return reasons


def test_all_observed_reasons_have_taxonomy_entry():
    reasons = _collect_all_reasons()
    assert len(reasons) >= 10  # 至少覆盖大部分分支,回归探测网格是否萎缩
    missing = []
    for r in reasons:
        category, summary = taxonomy_for_reason(r)
        if category == "unknown":
            missing.append(r)
    assert missing == [], f"以下 reason 未登记 taxonomy:{missing}"


def test_reason_taxonomy_table_has_no_duplicate_categories_collision():
    # 纯完整性检查:每条都有非空 category/summary。
    for reason, (category, summary) in REASON_TAXONOMY.items():
        assert category
        assert summary


def test_mod_gate_downgrade_reason_prefix_resolved():
    category, summary = taxonomy_for_reason("mod_gate_downgrade:withdraw")
    assert category == "gate"


def test_unknown_action_reason_resolved():
    category, summary = taxonomy_for_reason("unknown_action:teleport")
    assert category == "decision"


def test_explain_not_in_verdict_public_fields():
    """N1/N7:Explain 是包裹层的溯源产物,不是 core.arbiter.Verdict 的字段
    ——本测试断言 Verdict(工具返回体唯一来源类型)的字段集里没有
    'explain'/'guard_trace'/'theta_digest' 字样,防止未来误接线把
    Explain 泄漏进工具返回。
    """
    from dataclasses import fields

    from yelos.core.arbiter import Verdict

    field_names = {f.name for f in fields(Verdict)}
    assert "explain" not in field_names
    assert "guard_trace" not in field_names
    assert "theta_digest" not in field_names
