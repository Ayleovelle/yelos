"""finitude 深接线集成测试(session.py W-5 _settle_fn_for 单缝 + _do_rollover 账本
让位 + heartbeat 纪元通告消费点 schema 收口;finitude_BLUEPRINT §7/§10.1 对应的
"接线波" 验收)。

覆盖(诊断书冲突点 A/B/C + 铁律 1-6):

- ``finitude_settle_enabled`` 默认关 -> 深 `yelos.finitude.build_settle_fn` 从不被
  import/调用,ledger 仍是 v0.1 七字段行,纪元通告仍是 str(铁律 4,逐字节兼容)。
- flag 开时深路径**真执行**(spy 证明 `build_settle_fn` 真被调用,产出的 ledger 行
  带 v2 字段 hi/concern,`record["aging"]["active_days_settled"]` 真被推进——非仅
  "没崩"就默认判定为已接通)。
- 账本单写主:深路径开时 settle_day 恰好一行,不与 `_do_rollover` 的旧 append 双写。
- P 单调(SPEC P5):reserve 模型下多日 rollover,权威 P(`record["p"]`)只降不升;
  "休息回暖" 只抬 `record["aging"]["fast"]`(P_expr),从不抬 P。
- epoch 通知 schema 收口:深路径写 dict(`EpochNoticePayload.to_dict()`),heartbeat
  消费点统一取 `epoch_to` 做映射键,不因 `str(dict)` 变 repr 而 miss 掉映射落到
  默认文案。
- 深 settle_fn 构造期/调用期抛异常均退化 core `fin.settle_day`,不崩 rollover,且
  当天结算 P/ledger 仍完整落地(非"退化=丢一天")。
- P0 主权(`sealed`)在 rollover 之前的既有优先判定不被深路径接线扰动。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from yelos import finitude as fin_deep  # noqa: E402
from yelos.config import YelosConfig  # noqa: E402
from yelos.engine_bridge import EngineBridge  # noqa: E402
from yelos.session import SessionManager  # noqa: E402

pytestmark = pytest.mark.asyncio


def make_manager(tmp_path: Path, **overrides) -> SessionManager:
    cfg = YelosConfig(
        data_dir=str(tmp_path),
        heartbeat_enabled=False,
        arbiter_min_gap_seconds=0,
        # 跨零点闭区间会命中真实时钟的"安静时段",qs==qe 恒 False,消除 flaky。
        quiet_hours="00:00-00:00",
        **overrides,
    )
    return SessionManager(cfg, EngineBridge(llm_fn=None))


def _ledger_rows(sm: SessionManager) -> list[dict]:
    path = sm._ledger.path
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


async def _seed_active_yesterday(sm: SessionManager, sid: str, *, p: float | None = None) -> dict:
    """把 daily 伪装成"昨天已跨日"的活跃日快照,供下一次 rollover 结算。"""
    await sm.bind(sid, "阿澜", mode="companion")
    record = sm._store.get(sid)
    record["daily"]["day"] = "2000-01-01"
    record["daily"]["interacted"] = True
    record["daily"]["active_seen"] = True
    if p is not None:
        record["p"] = p
    return record


# =====================================================================
# 铁律 4:flag 默认关 -> 深路径从不 import/调用,字节等价 v0.1
# =====================================================================


async def test_flag_off_never_imports_deep_build_settle_fn(tmp_path, monkeypatch):
    sm = make_manager(tmp_path, lifespan_active_days=5)
    assert sm._cfg.finitude_settle_enabled is False

    def _boom(*_a, **_kw):
        raise AssertionError("深路径不该在 flag 关时被调用")

    monkeypatch.setattr(fin_deep, "build_settle_fn", _boom)

    sid = "s-off"
    await _seed_active_yesterday(sm, sid, p=0.8)
    sm._do_rollover(sid, sm._day_key())

    record = sm._store.get(sid)
    assert record["p"] == pytest.approx(0.6)  # lifespan=5 → base=0.2,0.8-0.2=0.6
    # deep 从未写过 aging 块(legacy 路径根本不碰它)。
    assert "aging" not in record

    rows = _ledger_rows(sm)
    settle_rows = [r for r in rows if r.get("reason") == "settle_day"]
    assert len(settle_rows) == 1
    # v0.1 七字段行:无 hi/concern 等 v2 增量字段。
    assert set(settle_rows[0].keys()) == {"sid", "gen", "born_at", "p", "ts", "day", "reason"}


async def test_flag_off_epoch_notice_is_plain_str(tmp_path):
    # p=0.75, lifespan=2 → base=0.5 → new_p=0.25(离 0.3/0.15 两条边界都留足余量,
    # 不碰浮点边界)。epoch(0.75)=盛年 → epoch(0.25)=安静,确定发生跨档。
    sm = make_manager(tmp_path, lifespan_active_days=2)
    sid = "s-off-epoch"
    await _seed_active_yesterday(sm, sid, p=0.75)
    sm._do_rollover(sid, sm._day_key())
    record = sm._store.get(sid)
    assert record["p"] == pytest.approx(0.25)
    assert record["pending_epoch_notice"] == "安静"  # v0.1 浅路径:纯字符串纪元名


# =====================================================================
# flag 开:深路径真执行(spy 证明真调用,非静默回落)
# =====================================================================


async def test_flag_on_deep_path_really_executes(tmp_path, monkeypatch):
    sm = make_manager(tmp_path, finitude_settle_enabled=True, lifespan_active_days=5)
    calls: list[tuple] = []
    real_build = fin_deep.build_settle_fn

    def spy_build(*a, **kw):
        calls.append((a, kw))
        return real_build(*a, **kw)

    monkeypatch.setattr(fin_deep, "build_settle_fn", spy_build)

    sid = "s-on"
    await _seed_active_yesterday(sm, sid, p=0.8)
    sm._do_rollover(sid, sm._day_key())

    assert len(calls) == 1, "深 build_settle_fn 必须被真实调用一次"
    args, kwargs = calls[0]
    assert args[1] == sid  # (record, sid, ...)

    record = sm._store.get(sid)
    assert record["p"] == pytest.approx(0.6)
    # 只有深路径会推进 aging 块 —— 证明真走了深 settle,不是构造完就静默回落。
    assert record["aging"]["active_days_settled"] == 1

    rows = _ledger_rows(sm)
    settle_rows = [r for r in rows if r.get("reason") == "settle_day"]
    assert len(settle_rows) == 1
    # v2 增量字段(finitude_BLUEPRINT §5.1)证明这行是 LedgerExt 写的,非旧 append。
    assert "hi" in settle_rows[0]
    assert "concern" in settle_rows[0]


async def test_flag_on_ledger_settle_day_written_exactly_once(tmp_path, monkeypatch):
    """账本单写主(铁律 2):深路径开时,_do_rollover 的旧 append 必须让位,不双写。"""
    sm = make_manager(tmp_path, finitude_settle_enabled=True, lifespan_active_days=5)

    sid = "s-once"
    await _seed_active_yesterday(sm, sid, p=0.8)
    sm._do_rollover(sid, sm._day_key())

    rows = _ledger_rows(sm)
    settle_rows = [r for r in rows if r.get("sid") == sid and r.get("reason") == "settle_day"]
    assert len(settle_rows) == 1, "深路径 + 旧路径双写了 settle_day 行"


async def test_flag_on_epoch_shift_ledger_row_also_written_once(tmp_path):
    """跨纪元当天:深路径应写 settle_day + epoch_shift 各一行,旧路径完全让位。"""
    sm = make_manager(tmp_path, finitude_settle_enabled=True, lifespan_active_days=2)
    sid = "s-epoch-once"
    await _seed_active_yesterday(sm, sid, p=0.8)
    sm._do_rollover(sid, sm._day_key())

    rows = _ledger_rows(sm)
    sid_rows = [r for r in rows if r.get("sid") == sid]
    reasons = [r.get("reason") for r in sid_rows]
    assert reasons.count("settle_day") == 1
    assert reasons.count("epoch_shift") == 1

    record = sm._store.get(sid)
    # 深路径自己维护 epoch_history/milestones,旧路径没有再追加一条重复项。
    assert len(record["epoch_history"]) == 1
    epoch_milestones = [m for m in record["milestones"] if "跃迁" in m.get("text", "")]
    assert len(epoch_milestones) == 1


# =====================================================================
# 铁律 1:P 单调 —— reserve 模型下"休息回暖"只抬 P_expr,不抬权威 P
# =====================================================================


async def test_p_monotone_non_increasing_across_days_reserve_model(tmp_path):
    sm = make_manager(
        tmp_path,
        finitude_settle_enabled=True,
        finitude_model="reserve",
        lifespan_active_days=20,
    )
    sid = "s-reserve"
    await sm.bind(sid, "阿澜", mode="companion")
    record = sm._store.get(sid)

    p_series: list[float] = []
    fast_series: list[float] = []

    # day1:高压事件日,快池大幅消耗。
    record["daily"]["day"] = "2000-01-01"
    record["daily"]["interacted"] = True
    record["daily"]["active_seen"] = True
    record["daily"]["high_intensity"] = 3
    sm._do_rollover(sid, "2000-01-02")
    record = sm._store.get(sid)
    p_series.append(record["p"])
    fast_series.append(record["aging"]["fast"])

    # day2/day3:无事件活跃日(休息),快池理应回暖。
    for day, next_day in (("2000-01-02", "2000-01-03"), ("2000-01-03", "2000-01-04")):
        record["daily"]["day"] = day
        record["daily"]["interacted"] = True
        record["daily"]["active_seen"] = True
        record["daily"]["high_intensity"] = 0
        sm._do_rollover(sid, next_day)
        record = sm._store.get(sid)
        p_series.append(record["p"])
        fast_series.append(record["aging"]["fast"])

    # 权威 P(慢池 S)严格单调非增,休息日也照样按 base 扣,不因回暖被抬高。
    for a, b in zip(p_series, p_series[1:]):
        assert b <= a
    assert p_series[-1] < p_series[0]

    # 表达面 F(fast pool)在休息日应回暖抬升,但永不超过同期权威 P。
    assert fast_series[1] > fast_series[0], "休息日快池应回暖,P_expr 应上抬"
    for p, f in zip(p_series, fast_series):
        assert f <= p + 1e-9, "P_expr 永不允许超过权威 P 的单调天花板"


# =====================================================================
# 点 B:epoch 通知 schema 收口 —— dict/str 消费端统一取 epoch_to
# =====================================================================


async def test_epoch_notice_dict_schema_maps_to_correct_text_end_to_end(tmp_path):
    """深路径写 dict pending_epoch_notice,heartbeat 消费点须映射到正确文案,
    不能因 str(dict) 变 repr 落到默认文案(诊断书冲突点 B)。
    """
    sm = make_manager(tmp_path, finitude_settle_enabled=True, lifespan_active_days=2)
    sid = "s-notice"
    # p=0.75,lifespan=2 → base=0.5 → new_p=0.25,离 0.6/0.3/0.15 三条边界都留足
    # 余量(>=0.1),避免浮点精度在边界抖动导致误判纪元名。
    await _seed_active_yesterday(sm, sid, p=0.75)

    record = sm._store.get(sid)
    # 深路径产出前置断言:build_settle_fn 确实写 dict 形态(非 str)。
    out = await sm.impulse(sid)  # heartbeat_enabled=False → impulse 内联走 _heartbeat_step
    record = sm._store.get(sid)

    # p: 0.75 -> 0.25,epoch(0.75)=盛年, epoch(0.25)=安静 → 该文案与默认文案不同,
    # 若消费端误吞 dict 会落到 _EPOCH_NOTICE_DEFAULT(与"慢下来"同文案)而非本句。
    epoch_notices = [u for u in out["utterances"] if u["kind"] == "epoch_notice"]
    assert len(epoch_notices) == 1
    assert epoch_notices[0]["text"] == "我好像越来越安静了。"
    # 消费后 pending_epoch_notice 清空(与 v0.1 契约一致)。
    assert record["pending_epoch_notice"] is None


# =====================================================================
# 铁律 3:深 settle_fn 构造期 / 调用期异常均退化 core,不崩 rollover
# =====================================================================


async def test_deep_construction_exception_falls_back_to_core(tmp_path, monkeypatch):
    sm = make_manager(tmp_path, finitude_settle_enabled=True, lifespan_active_days=5)

    def _boom(*_a, **_kw):
        raise RuntimeError("深路径构造炸了")

    monkeypatch.setattr(fin_deep, "build_settle_fn", _boom)

    sid = "s-boom-build"
    await _seed_active_yesterday(sm, sid, p=0.8)
    sm._do_rollover(sid, sm._day_key())  # 不应抛异常

    record = sm._store.get(sid)
    assert record["p"] == pytest.approx(0.6)  # 退化 core 公式,当天结算完整落地
    rows = _ledger_rows(sm)
    settle_rows = [r for r in rows if r.get("reason") == "settle_day"]
    assert len(settle_rows) == 1
    assert "hi" not in settle_rows[0]  # 退化路径写的是 v0.1 旧行


async def test_deep_call_time_exception_falls_back_to_core(tmp_path, monkeypatch):
    sm = make_manager(tmp_path, finitude_settle_enabled=True, lifespan_active_days=5)

    def _boom_fn(*_a, **_kw):
        def fn(_p, _daily):
            raise RuntimeError("深 settle_fn 调用期炸了")

        return fn

    monkeypatch.setattr(fin_deep, "build_settle_fn", _boom_fn)

    sid = "s-boom-call"
    await _seed_active_yesterday(sm, sid, p=0.8)
    sm._do_rollover(sid, sm._day_key())  # 不应抛异常

    record = sm._store.get(sid)
    assert record["p"] == pytest.approx(0.6)
    rows = _ledger_rows(sm)
    settle_rows = [r for r in rows if r.get("reason") == "settle_day"]
    assert len(settle_rows) == 1
    assert "hi" not in settle_rows[0]


# =====================================================================
# P0 主权:sealed 在 rollover 之前的既有优先判定不被深路径接线扰动
# =====================================================================


async def test_sealed_short_circuits_before_rollover_deep_enabled(tmp_path, monkeypatch):
    sm = make_manager(tmp_path, finitude_settle_enabled=True, lifespan_active_days=5)

    def _boom(*_a, **_kw):
        raise AssertionError("sealed 会话不该走到深路径构造")

    monkeypatch.setattr(fin_deep, "build_settle_fn", _boom)

    sid = "s-sealed"
    record = await _seed_active_yesterday(sm, sid, p=0.8)
    record["sealed"] = True

    await sm._heartbeat_step(sid)  # P0:sealed 早退,rollover 不应被触碰

    record = sm._store.get(sid)
    assert record["p"] == 0.8  # 完全未结算
    assert record["daily"]["day"] == "2000-01-01"  # daily 也未被跨日重置
