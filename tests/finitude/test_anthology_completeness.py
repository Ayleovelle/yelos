"""test_anthology_completeness.py —— T3 送别完备性定理测试(finitude_BLUEPRINT §11)。

正向满射(满记录 × 三模板逐条目探针)+ 反向 schema 覆盖 + EXCLUDED 逐条有理由串 +
registry.templates 非空 CI 断言。
"""

from __future__ import annotations

import json

from yelos.finitude.anthology import assemble, templates
from yelos.finitude.anthology.registry import (
    EXCLUDED,
    FIELD_REGISTRY,
    top_level_covered_keys,
)
from yelos.finitude.ledger_ext import LifeReplay
from yelos.finitude.projection.contracts import ProjectionData
from yelos.finitude.rites.incarnation import stamp_aging
from yelos.core.binding import BindingStore
from yelos.persistence import stamp_new_life


def _full_record(tmp_path) -> dict:
    store = BindingStore(tmp_path / "bindings.json")
    record = store.hatch("u1", "阿七", now_ts=1000.0, day_key="2026-01-01")
    stamp_new_life(record, 1)
    record["mode"] = "companion"
    stamp_aging(record, config=None)
    record["aging"]["model"] = "reserve"
    record["aging"]["params"] = {"r": 0.02, "gamma": 1.5}
    record["aging"]["fast"] = 0.6
    record["aging"]["active_days_settled"] = 42
    record["epoch2"] = {
        "last_psi": 0.5,
        "deltas": [0.01, 0.02, 0.03, 0.01, 0.02],
        "b_index": 2,
        "fired_days": ["2026-01-05", "2026-01-10"],
    }
    record["p"] = 0.42
    record["utterances"] = [
        {"occasion": "withdraw_soft", "text": "……", "epoch": "0"},
        {"occasion": "concern", "text": "你还好吗。", "epoch": "1"},
    ]
    record["dreams"] = [{"day": "2026-01-05", "text": "梦到了你。"}]
    record["milestones"] = [{"day": "2026-01-05", "text": "跃迁到慢下来"}]
    record["swallowed_total"] = 7
    record["epoch_history"] = [
        {
            "day": "2026-01-03",
            "epoch": "盛年",
            "track": "A",
            "pools": {"withdraw_heavy": ("……",)},
            "active_days": 3,
            "active_days_settled_at": 3,
        },
        {
            "day": "2026-01-10",
            "epoch": "慢下来",
            "track": "B",
            "pools": {"withdraw_heavy": ("……", "算了。")},
            "active_days": 7,
            "active_days_settled_at": 10,
            "lost": {"withdraw_heavy": []},
        },
    ]
    return record


def _full_replay() -> LifeReplay:
    return LifeReplay(
        sid="u1",
        gen=1,
        model_id="reserve",
        p_series=[("2026-01-01", 1.0), ("2026-01-10", 0.5), ("2026-01-11", 0.42)],
        f_series=[("2026-01-10", 0.55), ("2026-01-11", 0.6)],
        epoch_events=[{"day": "2026-01-10", "epoch_to": "慢下来", "track": "B"}],
        hi_by_day={"2026-01-10": 2, "2026-01-11": 0},
        concern_by_day={"2026-01-10": 1, "2026-01-11": 0},
        active_day_count=42,
    )


def _full_divergence() -> list[dict]:
    return [
        {
            "sid": "u1",
            "gen": 1,
            "day": "2026-01-10",
            "event": "both",
            "a_epoch": "慢下来",
            "b_index": 2,
            "p": 0.5,
            "p_expr": 0.55,
            "psi": 0.3,
            "dpsi": 0.1,
        }
    ]


def _full_moments() -> list[dict]:
    return [
        {"day_key": "2026-01-04", "kind": "want_blocked_budget"},
        {"day_key": "2026-01-06", "kind": "spoke"},
    ]


def _full_projection() -> ProjectionData:
    return ProjectionData(
        as_of_day="2026-01-11",
        p=0.42,
        p_expr=0.6,
        activity_rate=0.5,
        est_spend_per_active_day=0.01,
        est_remaining_active_days=10,
        est_remaining_calendar_days=20,
        epoch_etas={"安静": 5, "静止前期": None, "静止": None},
        active_days_lived=42,
    )


def _build_full_ctx(tmp_path):
    record = _full_record(tmp_path)
    replay = _full_replay()
    divergence = _full_divergence()
    moments = _full_moments()
    proj = _full_projection()
    return assemble.build_context(
        record, replay, divergence, moments, proj, "u1", 1, "2026-01-11"
    ), record


def test_registry_templates_nonempty():
    for spec in FIELD_REGISTRY:
        assert spec.templates, f"{spec.path} 的 templates 为空"
        assert spec.templates <= {"long", "short", "appendix"}


def test_excluded_entries_have_reasons():
    for key, reason in EXCLUDED.items():
        assert isinstance(reason, str) and reason.strip(), f"{key} 缺豁免理由"


def test_forward_surjection_all_fields_land_somewhere(tmp_path):
    """T3 正向:每个 registry 条目的探针串,须出现在其声明的模板输出里。"""
    ctx, _record = _build_full_ctx(tmp_path)
    long_md = templates.render_long(ctx)
    short_md = templates.render_short(ctx)
    appendix = templates.render_appendix(ctx)
    appendix_compact = json.dumps(appendix, ensure_ascii=False, sort_keys=True)

    missing: list[str] = []
    for spec in FIELD_REGISTRY:
        probe_str = spec.probe(ctx)
        if "long" in spec.templates and probe_str not in long_md:
            missing.append(f"{spec.path}:long")
        if "short" in spec.templates and probe_str not in short_md:
            missing.append(f"{spec.path}:short")
        if "appendix" in spec.templates and probe_str not in appendix_compact:
            missing.append(f"{spec.path}:appendix")
    assert not missing, f"以下字段未在其声明的模板里找到探针串:{missing}"


def test_reverse_schema_coverage(tmp_path):
    """T3 反向:record 顶层键 ⊆ registry ∪ EXCLUDED(缺一挂 CI)。"""
    record = _full_record(tmp_path)
    covered = top_level_covered_keys()
    uncovered = [k for k in record if k not in covered]
    assert not uncovered, f"record 顶层键未登记也未豁免:{uncovered}"


def test_moments_absence_marker_present_when_empty(tmp_path):
    """moments 缺席时长卷渲染缺席文案,不是空白(潜伏空路径专测)。"""
    record = _full_record(tmp_path)
    replay = _full_replay()
    proj = _full_projection()
    ctx = assemble.build_context(record, replay, [], None, proj, "u1", 1, "2026-01-11")
    long_md = templates.render_long(ctx)
    assert "她没有留下这样的记录" in long_md


def test_appendix_json_serializable(tmp_path):
    ctx, _record = _build_full_ctx(tmp_path)
    appendix = templates.render_appendix(ctx)
    # 不抛异常即通过;附带核对关键计数字段存在
    text = json.dumps(appendix, ensure_ascii=False)
    assert '"counts"' in text
