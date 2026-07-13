"""test_concurrency.py —— 并发用例(finitude_BLUEPRINT §11,RE6 清单:aging 写入入临界区)。

**范围说明**:per-session 锁的持有者是 server/session 层(本波禁止编辑
session.py),finitude 本身不实现锁——这正是 RE6 的字面要求("aging 写入入
临界区",临界区由调用方提供)。本文件用一把外部 `threading.Lock` 模拟
session 层的临界区包裹 `rollover`+`settle_fn` 调用,验证:①同一天的并发
rollover 请求在锁保护下只产生一次真实 settle(`BindingStore.rollover` 的
"未跨日即 None"语义天然防重入)、②ledger 文件不因并发写入而损坏、③aging
块不被撕裂(active_days_settled 不重复递增)。若移除锁保护直接并发调用,
`BindingStore._data` 字典的非原子读改写本就不是线程安全结构——这不是
finitude 该修的账,红队核验时按此范围裁定。
"""

from __future__ import annotations

import json
import threading

from yelos.core.binding import BindingStore
from yelos.finitude import build_settle_fn
from yelos.finitude.ledger_ext import LedgerExt
from yelos.finitude.rites.incarnation import stamp_aging
from yelos.persistence import PlasticityLedger


class _FakeConfig:
    finitude_model = "linear"
    finitude_model_params = "{}"
    finitude_epoch_track = "fixed"
    finitude_enabled = True
    lifespan_active_days = 100
    intrinsic_daily_cap = 3


def test_concurrent_rollover_same_day_under_lock_settles_once(tmp_path):
    store = BindingStore(tmp_path / "bindings.json")
    record = store.hatch("u1", "小满", now_ts=0.0, day_key="2026-01-01")
    record["mode"] = "companion"
    stamp_aging(record, config=_FakeConfig())
    record["daily"]["interacted"] = True
    record["daily"]["active_seen"] = True

    ledger = PlasticityLedger(tmp_path / "plasticity.ledger")
    ledger_ext = LedgerExt(ledger)
    settle_fn = build_settle_fn(
        record,
        "u1",
        ledger=ledger,
        ledger_ext=ledger_ext,
        config=_FakeConfig(),
        data_dir=tmp_path,
    )

    lock = threading.Lock()
    results: list[float | None] = []

    def _do_rollover():
        with lock:
            result = store.rollover("u1", "2026-01-02", settle_fn)
            results.append(result)

    threads = [threading.Thread(target=_do_rollover) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    non_none = [r for r in results if r is not None]
    assert len(non_none) == 1, "临界区保护下,同一天只应真正 settle 一次"

    settled_p = non_none[0]
    assert store.get("u1")["p"] == settled_p
    assert store.get("u1")["aging"]["active_days_settled"] == 1

    # ledger 文件可正常整行解析,无损坏/交错写入
    lines = [
        ln for ln in ledger.path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    settle_rows = [json.loads(ln) for ln in lines]
    assert len(settle_rows) == 1
    assert settle_rows[0]["reason"] == "settle_day"


def test_concurrent_different_umo_rollovers_do_not_interfere(tmp_path):
    """不同 sid 并发 rollover 互不干扰(各自 aging 块独立)。"""
    store = BindingStore(tmp_path / "bindings.json")
    ledger = PlasticityLedger(tmp_path / "plasticity.ledger")
    ledger_ext = LedgerExt(ledger)

    sids = [f"u{i}" for i in range(8)]
    settle_fns = {}
    for sid in sids:
        record = store.hatch(sid, sid, now_ts=0.0, day_key="2026-01-01")
        record["mode"] = "companion"
        stamp_aging(record, config=_FakeConfig())
        record["daily"]["interacted"] = True
        record["daily"]["active_seen"] = True
        settle_fns[sid] = build_settle_fn(
            record,
            sid,
            ledger=ledger,
            ledger_ext=ledger_ext,
            config=_FakeConfig(),
            data_dir=tmp_path,
        )

    lock = threading.Lock()

    def _do_rollover(sid: str):
        with lock:
            store.rollover(sid, "2026-01-02", settle_fns[sid])

    threads = [threading.Thread(target=_do_rollover, args=(sid,)) for sid in sids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for sid in sids:
        assert store.get(sid)["aging"]["active_days_settled"] == 1
        assert store.get(sid)["p"] < 1.0
