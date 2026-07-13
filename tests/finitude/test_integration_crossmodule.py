"""test_integration_crossmodule.py —— 跨模块集成测试(finitude_BLUEPRINT §11/§6.4/§6.5)。

年轮快照管道(§6.4 端到端,primal.pool_snapshot 独立复算全等)+ moments 管道
(§6.5,含空缺席 + 真实 intrinsic.moments.MomentEntry 鸭子类型)+
rollover→settle→ledger→dualtrack→notice 全链(用 core.binding.BindingStore 作
"fake bridge",不碰 session.py)+ farewell 全链落盘全模板。
"""

from __future__ import annotations

from pathlib import Path

from yelos import primal as primal_pkg
from yelos.core.binding import BindingStore
from yelos.finitude import build_settle_fn
from yelos.finitude.anthology.assemble import assemble_anthology_v2
from yelos.finitude.epochs.dualtrack import read_divergence
from yelos.finitude.ledger_ext import LedgerExt
from yelos.finitude.projection.estimate import project
from yelos.finitude.rites.incarnation import stamp_aging
from yelos.persistence import PlasticityLedger


class _FakeConfig:
    finitude_model = "linear"
    finitude_model_params = "{}"
    finitude_epoch_track = "fixed"
    finitude_enabled = True
    lifespan_active_days = 10
    intrinsic_daily_cap = 3


def test_rollover_settle_ledger_dualtrack_notice_full_chain(tmp_path):
    store = BindingStore(tmp_path / "bindings.json")
    record = store.hatch("u1", "小满", now_ts=0.0, day_key="2026-01-01")
    record["mode"] = "companion"
    stamp_aging(record, config=_FakeConfig())

    ledger = PlasticityLedger(tmp_path / "plasticity.ledger")
    ledger_ext = LedgerExt(ledger)
    ledger_ext.append_hatch("u1", 1, 0.0, 1.0, day="2026-01-01", model="linear")

    settle_fn = build_settle_fn(
        record,
        "u1",
        ledger=ledger,
        ledger_ext=ledger_ext,
        config=_FakeConfig(),
        data_dir=tmp_path,
    )

    days = [f"2026-01-{d:02d}" for d in range(2, 9)]  # 7 次 rollover
    for day in days:
        daily = store.get("u1")["daily"]
        daily["interacted"] = True
        daily["active_seen"] = True
        daily["high_intensity"] = 0
        new_p = store.rollover("u1", day, settle_fn)
        assert new_p is not None

    record = store.get("u1")
    # lifespan=10,7 个活跃日后 p ~= 1.0 - 7*0.1 = 0.3(浮点累计误差下实际值略高于
    # 精确 0.3,导致"慢下来→安静"这一步边界判定因浮点漂移未必跨档——这是
    # core.finitude 既有 settle_day/epoch 公式在重复减法下的系统性浮点特征,
    # 不是本模块引入的缺陷,断言只依赖"至少发生过一次跃迁",不假设精确档数)。
    assert abs(record["p"] - 0.3) < 1e-6
    assert record["epoch_history"], "应至少记录一次纪元跃迁"
    assert record["pending_epoch_notice"] is not None
    assert record["aging"]["active_days_settled"] == 7

    # ledger 侧应含 settle_day 与至少一条 epoch_shift 行
    ledger_text = ledger.path.read_text(encoding="utf-8")
    assert '"reason": "settle_day"' in ledger_text
    assert '"reason": "epoch_shift"' in ledger_text

    # --- 年轮快照管道端到端(§6.4)---------------------------------------
    for entry in record["epoch_history"]:
        assert "pools" in entry
    # 用最后一条 epoch_history 条目独立复算 pool_snapshot,断言逐场合全等
    # (用该条目自带的 p_expr 值复算,不用 record["p"]——record["p"] 可能已经过了
    # 该条目记录之后的更多活跃日,与该条目落笔当时的 p 不是同一个时刻)
    last_entry = record["epoch_history"][-1]
    recomputed = primal_pkg.pool_snapshot(last_entry["p_expr"])
    for occ, words in recomputed.items():
        assert tuple(last_entry["pools"].get(occ, ())) == tuple(words)

    # --- farewell 全链落盘全模板 ------------------------------------------
    replay = ledger_ext.replay("u1", 1)
    assert replay.active_day_count == 7
    divergence_rows = read_divergence(tmp_path)
    proj = project(replay, record, days[-1], lifespan_active_days=10)

    result = assemble_anthology_v2(
        record,
        replay,
        divergence_rows,
        None,
        proj,
        "u1",
        1,
        days[-1],
        data_dir=tmp_path,
    )
    assert result["anthology_path"] is not None
    assert Path(result["anthology_path"]).is_file()
    assert Path(result["json_path"]).is_file()
    assert Path(result["short_path"]).is_file()
    assert Path(result["p_curve_svg_path"]).is_file()
    assert Path(result["rings_svg_path"]).is_file()
    assert Path(result["hourglass_svg_path"]).is_file()


def test_moments_pipeline_with_real_moment_entry():
    """moments 管道用真实 `intrinsic.moments.taxonomy.MomentEntry`(非 dict 鸭子类型)。"""
    from yelos.finitude.anthology.assemble import build_context
    from yelos.finitude.ledger_ext import LifeReplay
    from yelos.finitude.projection.contracts import ProjectionData
    from yelos.intrinsic.moments.taxonomy import MomentEntry, MomentKind

    record = {
        "p": 0.5,
        "aging": {
            "model": "linear",
            "params": {},
            "active_days_settled": 3,
            "fast": 1.0,
        },
    }
    replay = LifeReplay(sid="u1", gen=1, model_id="linear")
    proj = ProjectionData(
        as_of_day="2026-01-10",
        p=0.5,
        p_expr=0.5,
        activity_rate=0.5,
        est_spend_per_active_day=0.01,
        est_remaining_active_days=50,
        est_remaining_calendar_days=100,
        epoch_etas={},
        active_days_lived=3,
    )
    entries = [
        MomentEntry(
            ts=1.0,
            day_key="2026-01-05",
            kind=MomentKind.WANT_BLOCKED_BUDGET,
            reason_code="daily_cap",
            phi=(0.1, 0.2, 0.3, 0.4),
            trace_hash="abc123",
        ),
        MomentEntry(
            ts=2.0,
            day_key="2026-01-06",
            kind=MomentKind.SPOKE,
            reason_code="ok",
            phi=(0.5, 0.5, 0.5, 0.5),
            trace_hash="def456",
        ),
    ]
    ctx = build_context(record, replay, [], entries, proj, "u1", 1, "2026-01-10")
    assert ctx["moments_marker"] != "她没有留下这样的记录"
    assert "want_blocked_budget" in ctx["moments_marker"]


def test_moments_pipeline_empty_gives_absence_marker():
    from yelos.finitude.anthology.assemble import build_context
    from yelos.finitude.ledger_ext import LifeReplay
    from yelos.finitude.projection.contracts import ProjectionData

    record = {
        "p": 0.5,
        "aging": {
            "model": "linear",
            "params": {},
            "active_days_settled": 0,
            "fast": 1.0,
        },
    }
    replay = LifeReplay(sid="u1", gen=1, model_id="linear")
    proj = ProjectionData(
        as_of_day="2026-01-10",
        p=0.5,
        p_expr=0.5,
        activity_rate=0.0,
        est_spend_per_active_day=0.0,
        est_remaining_active_days=50,
        est_remaining_calendar_days=None,
        epoch_etas={},
        active_days_lived=0,
    )
    ctx = build_context(record, replay, [], None, proj, "u1", 1, "2026-01-10")
    assert ctx["moments_marker"] == "她没有留下这样的记录"

    ctx_empty_list = build_context(record, replay, [], [], proj, "u1", 1, "2026-01-10")
    assert ctx_empty_list["moments_marker"] == "她没有留下这样的记录"
