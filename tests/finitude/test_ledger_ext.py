"""test_ledger_ext.py —— 账本深化单元/兼容测试(finitude_BLUEPRINT §11/§5.2)。

v2 字段写入;v0.1 reader 穿透未知字段/reason;epoch_shift 行 min 合并无害;
replay 往返;损坏行跳过。接缝 X3(concern 权威源)共享测试见 test_dayfacts 相关用例。
"""

from __future__ import annotations

import json

from yelos.finitude.ledger_ext import LedgerExt
from yelos.persistence import PlasticityLedger


def _make_ledger_ext(tmp_path):
    ledger = PlasticityLedger(tmp_path / "plasticity.ledger")
    return ledger, LedgerExt(ledger)


def test_v2_fields_written_and_readable_raw(tmp_path):
    ledger, ext = _make_ledger_ext(tmp_path)
    ext.append_hatch("u1", 1, 1000.0, 1.0, day="2026-01-01", model="weibull")
    ext.append_settle(
        "u1",
        1,
        1000.0,
        0.98,
        day="2026-01-02",
        hi=2,
        concern=1,
        f=None,
        model_fallback=False,
    )
    ext.append_epoch_shift(
        "u1", 1, 1000.0, 0.98, day="2026-01-02", epoch_to="慢下来", track="A"
    )

    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    assert rows[0]["reason"] == "hatch"
    assert rows[0]["model"] == "weibull"
    assert rows[1]["reason"] == "settle_day"
    assert rows[1]["hi"] == 2
    assert rows[1]["concern"] == 1
    assert "f" not in rows[1]
    assert rows[2]["reason"] == "epoch_shift"
    assert rows[2]["epoch_to"] == "慢下来"
    assert rows[2]["track"] == "A"


def test_reserve_settle_row_includes_f(tmp_path):
    ledger, ext = _make_ledger_ext(tmp_path)
    ext.append_settle("u1", 1, 0.0, 0.9, day="d1", hi=0, concern=0, f=0.712345678)
    row = json.loads(ledger.path.read_text(encoding="utf-8").splitlines()[0])
    assert row["f"] == 0.712346 or abs(row["f"] - 0.712345678) < 1e-6


def test_model_fallback_flag_written(tmp_path):
    ledger, ext = _make_ledger_ext(tmp_path)
    ext.append_settle("u1", 1, 0.0, 0.9, day="d1", hi=0, concern=0, model_fallback=True)
    row = json.loads(ledger.path.read_text(encoding="utf-8").splitlines()[0])
    assert row["model_fallback"] is True


def test_v01_reader_ignores_v2_fields(tmp_path):
    """PlasticityLedger._iter_entries 只要求 sid/gen/p 三键;v2 字段/reason 穿透。"""
    ledger, ext = _make_ledger_ext(tmp_path)
    ext.append_hatch("u1", 1, 1000.0, 1.0, day="2026-01-01", model="event")
    ext.append_settle("u1", 1, 1000.0, 0.95, day="2026-01-02", hi=1, concern=0)
    ext.append_epoch_shift(
        "u1", 1, 1000.0, 0.95, day="2026-01-02", epoch_to="慢下来", track="A"
    )

    assert ledger.last_p("u1", 1) == 0.95
    assert ledger.effective_p("u1", 1, bindings_p=1.0) == 0.95


def test_epoch_shift_min_merge_safe(tmp_path):
    """epoch_shift 行的 p = 当时契约 P,不引入更低值,min 合并语义不破坏。"""
    ledger, ext = _make_ledger_ext(tmp_path)
    ext.append_hatch("u1", 1, 0.0, 1.0, day="d0", model="linear")
    ext.append_settle("u1", 1, 0.0, 0.7, day="d1", hi=0, concern=0)
    ext.append_epoch_shift("u1", 1, 0.0, 0.7, day="d1", epoch_to="慢下来", track="A")
    ext.append_settle("u1", 1, 0.0, 0.65, day="d2", hi=0, concern=0)

    # 末条 P 应是最后一次 settle_day 的 0.65(epoch_shift 行的 0.7 不覆盖成"回升")
    assert ledger.last_p("u1", 1) == 0.65
    assert ledger.effective_p("u1", 1, bindings_p=0.65) == 0.65
    # 即便 bindings_p 意外更高,合并仍取更低值
    assert ledger.effective_p("u1", 1, bindings_p=0.9) == 0.65


def test_replay_roundtrip(tmp_path):
    ledger, ext = _make_ledger_ext(tmp_path)
    ext.append_hatch("u1", 1, 0.0, 1.0, day="d0", model="reserve")
    ext.append_settle("u1", 1, 0.0, 0.99, day="d1", hi=1, concern=0, f=0.98)
    ext.append_epoch_shift("u1", 1, 0.0, 0.99, day="d1", epoch_to="盛年", track="A")
    ext.append_settle("u1", 1, 0.0, 0.98, day="d2", hi=0, concern=1, f=0.97)

    replay = ext.replay("u1", 1)
    assert replay.model_id == "reserve"
    assert replay.active_day_count == 2
    assert replay.hi_by_day == {"d1": 1, "d2": 0}
    assert replay.concern_by_day == {"d1": 0, "d2": 1}
    assert replay.f_series == [("d1", 0.98), ("d2", 0.97)]
    assert replay.epoch_events == [{"day": "d1", "epoch_to": "盛年", "track": "A"}]
    assert replay.final_p() == 0.98


def test_replay_ignores_other_sid_and_gen(tmp_path):
    ledger, ext = _make_ledger_ext(tmp_path)
    ext.append_hatch("u1", 1, 0.0, 1.0, day="d0", model="linear")
    ext.append_settle("u1", 1, 0.0, 0.9, day="d1", hi=0, concern=0)
    ext.append_hatch("u2", 1, 0.0, 1.0, day="d0", model="linear")
    ext.append_settle(
        "u1", 2, 0.0, 0.5, day="d1", hi=9, concern=9
    )  # 前世/别的世代,不该混入

    replay = ext.replay("u1", 1)
    assert replay.active_day_count == 1
    assert replay.final_p() == 0.9


def test_corrupt_lines_skipped_silently(tmp_path):
    ledger, ext = _make_ledger_ext(tmp_path)
    ext.append_hatch("u1", 1, 0.0, 1.0, day="d0", model="linear")
    with ledger.path.open("a", encoding="utf-8") as fh:
        fh.write("not-json-at-all\n")
        fh.write("\n")
        fh.write("[1,2,3]\n")  # 合法 json 但非 dict
    ext.append_settle("u1", 1, 0.0, 0.9, day="d1", hi=0, concern=0)

    replay = ext.replay("u1", 1)
    assert replay.active_day_count == 1
    assert replay.final_p() == 0.9
