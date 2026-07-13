"""test_anthology_golden.py —— 三模板 golden(finitude_BLUEPRINT §11)。

本仓 golden 纪律与 tests/primal/test_viz.py 同款:golden = 同输入产同字节输出
(确定性自证),不额外维护一份手写基线文本文件(避免文案调整时的脆弱漂移)。
长卷/短笺/附录三模板对合成一生的字节级 golden;空生命(她始终没有开口)golden;
moments 缺席文案 golden(潜伏空路径专测)。
"""

from __future__ import annotations

import json

from yelos.core.binding import BindingStore
from yelos.finitude.anthology import assemble, templates
from yelos.finitude.ledger_ext import LifeReplay
from yelos.finitude.projection.contracts import ProjectionData
from yelos.finitude.rites.incarnation import stamp_aging
from yelos.persistence import stamp_new_life

from .test_anthology_completeness import _build_full_ctx, _full_moments


def test_long_short_appendix_golden_bytewise_full_life(tmp_path):
    ctx, _record = _build_full_ctx(tmp_path)
    assert templates.render_long(ctx) == templates.render_long(ctx)
    assert templates.render_short(ctx) == templates.render_short(ctx)
    assert templates.render_appendix(ctx) == templates.render_appendix(ctx)

    long_md = templates.render_long(ctx)
    assert long_md.startswith("# 阿七 的一生")
    assert "## 送别" in long_md


def _empty_life_record(tmp_path) -> dict:
    store = BindingStore(tmp_path / "bindings.json")
    record = store.hatch("empty1", "小空", now_ts=0.0, day_key="2026-02-01")
    stamp_new_life(record, 1)
    record["mode"] = "companion"
    stamp_aging(record, config=None)
    return record


def test_empty_life_golden_she_never_spoke(tmp_path):
    """空生命(她始终没有开口)golden:利用 core.finitude 既有短语,长卷章节里出现同款文案。"""
    record = _empty_life_record(tmp_path)
    replay = LifeReplay(
        sid="empty1",
        gen=1,
        model_id="linear",
        p_series=[("2026-02-01", 1.0)],
        f_series=[],
        epoch_events=[],
        hi_by_day={},
        concern_by_day={},
        active_day_count=0,
    )
    proj = ProjectionData(
        as_of_day="2026-02-01",
        p=1.0,
        p_expr=1.0,
        activity_rate=0.0,
        est_spend_per_active_day=0.0,
        est_remaining_active_days=1_000_000_000,
        est_remaining_calendar_days=None,
        epoch_etas={},
        active_days_lived=0,
    )
    ctx = assemble.build_context(
        record, replay, [], None, proj, "empty1", 1, "2026-02-01"
    )
    long_md = templates.render_long(ctx)
    short_md = templates.render_short(ctx)

    assert "她始终没有开口" in long_md
    assert "她没有留下这样的记录" in long_md
    assert "没能说出口" in short_md

    # 确定性自证
    assert templates.render_long(ctx) == long_md
    assert templates.render_short(ctx) == short_md


def test_moments_absence_golden(tmp_path):
    record = _empty_life_record(tmp_path)
    replay = LifeReplay(
        sid="empty1",
        gen=1,
        model_id="linear",
        p_series=[("2026-02-01", 1.0)],
        f_series=[],
        epoch_events=[],
        hi_by_day={},
        concern_by_day={},
        active_day_count=0,
    )
    proj = ProjectionData(
        as_of_day="2026-02-01",
        p=1.0,
        p_expr=1.0,
        activity_rate=0.0,
        est_spend_per_active_day=0.0,
        est_remaining_active_days=1_000_000_000,
        est_remaining_calendar_days=None,
        epoch_etas={},
        active_days_lived=0,
    )
    ctx_absent = assemble.build_context(
        record, replay, [], None, proj, "empty1", 1, "2026-02-01"
    )
    ctx_present = assemble.build_context(
        record, replay, [], _full_moments(), proj, "empty1", 1, "2026-02-01"
    )
    long_absent = templates.render_long(ctx_absent)
    long_present = templates.render_long(ctx_present)
    assert "她没有留下这样的记录" in long_absent
    assert "她没有留下这样的记录" not in long_present
    assert "want_blocked_budget" in long_present


def test_appendix_dict_deterministic_json(tmp_path):
    ctx, _record = _build_full_ctx(tmp_path)
    a = json.dumps(templates.render_appendix(ctx), ensure_ascii=False, sort_keys=True)
    b = json.dumps(templates.render_appendix(ctx), ensure_ascii=False, sort_keys=True)
    assert a == b
