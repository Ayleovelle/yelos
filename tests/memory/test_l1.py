"""test_l1.py:L1 情景流水(单元 + 性质)。

锁 append-only(MEM-A3)、kind 白名单、段滚动、尾行截断恢复、世代键
(MEM-A10)、meta 禁自由文本 schema 校验。
"""

from __future__ import annotations

import json

import pytest

from yelos.memory.contracts import AffectStamp, EpisodeEvent
from yelos.memory.l1_episodic.reader import sid_hash
from yelos.memory.l1_episodic.store import EpisodeStore

from ._time_helpers import ts_for_index


def _ev(i: int, kind: str = "user_turn", **kw) -> EpisodeEvent:
    return EpisodeEvent(
        kind=kind, ts=ts_for_index(0) + i, day_key="2024-01-01", text=f"t{i}", **kw
    )


def test_kind_whitelist_rejects_unknown(tmp_path):
    with pytest.raises(ValueError):
        EpisodeEvent(kind="not_a_kind", ts=0.0, day_key="2024-01-01")


def test_meta_rejects_free_text(tmp_path):
    with pytest.raises(ValueError):
        EpisodeEvent(
            kind="user_turn",
            ts=0.0,
            day_key="2024-01-01",
            meta={"note": "x" * 40},
        )
    with pytest.raises(ValueError):
        EpisodeEvent(
            kind="user_turn",
            ts=0.0,
            day_key="2024-01-01",
            meta={"nested": {"a": 1}},
        )
    # 结构化小字段放行
    EpisodeEvent(
        kind="user_turn",
        ts=0.0,
        day_key="2024-01-01",
        meta={"verdict": "REPLACE", "intensity": 3},
    )


def test_append_only_and_count(tmp_path):
    store = EpisodeStore(tmp_path, "abc123", 0)
    for i in range(5):
        seq = store.append(_ev(i))
        assert seq == i
    assert store.count() == 5


def test_generation_keying_isolates_files(tmp_path):
    s0 = EpisodeStore(tmp_path, "abc123", 0)
    s1 = EpisodeStore(tmp_path, "abc123", 1)
    s0.append(_ev(0))
    s1.append(_ev(0))
    assert s0.count() == 1
    assert s1.count() == 1
    g0_path = tmp_path / "memory" / "l1" / "abc123.g0.jsonl"
    g1_path = tmp_path / "memory" / "l1" / "abc123.g1.jsonl"
    assert g0_path.is_file()
    assert g1_path.is_file()


def test_segment_rolling(tmp_path):
    store = EpisodeStore(tmp_path, "seg", 0, segment_max=3)
    for i in range(7):
        store.append(_ev(i))
    assert store.count() == 7
    archive0 = tmp_path / "memory" / "l1" / "seg.g0.0.arc.jsonl"
    archive1 = tmp_path / "memory" / "l1" / "seg.g0.1.arc.jsonl"
    active = tmp_path / "memory" / "l1" / "seg.g0.jsonl"
    assert archive0.is_file() and archive1.is_file() and active.is_file()
    assert len(archive0.read_text(encoding="utf-8").splitlines()) == 3
    assert len(archive1.read_text(encoding="utf-8").splitlines()) == 3
    assert len(active.read_text(encoding="utf-8").splitlines()) == 1

    # 重新加载应恢复完整计数与顺序
    reloaded = EpisodeStore(tmp_path, "seg", 0, segment_max=3)
    assert reloaded.count() == 7
    events = reloaded.read_span(0, 6)
    assert [e.text for e in events] == [f"t{i}" for i in range(7)]


def test_tail_truncation_recovery(tmp_path):
    store = EpisodeStore(tmp_path, "crash", 0)
    for i in range(3):
        store.append(_ev(i))
    active = tmp_path / "memory" / "l1" / "crash.g0.jsonl"
    with active.open("a", encoding="utf-8") as f:
        f.write('{"kind": "user_turn", "ts": 1.0, "day_key": "2024-01-01"')  # 半行

    reloaded = EpisodeStore(tmp_path, "crash", 0)
    assert reloaded.count() == 3
    # 磁盘上的半行应已被截尾清除
    lines = active.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for line in lines:
        json.loads(line)  # 不应再抛异常


def test_read_day_and_span(tmp_path):
    store = EpisodeStore(tmp_path, "days", 0)
    store.append(EpisodeEvent(kind="user_turn", ts=1.0, day_key="2024-01-01", text="a"))
    store.append(EpisodeEvent(kind="user_turn", ts=2.0, day_key="2024-01-02", text="b"))
    store.append(EpisodeEvent(kind="user_turn", ts=3.0, day_key="2024-01-01", text="c"))
    day1 = store.read_day("2024-01-01")
    assert {e.text for e in day1} == {"a", "c"}
    span = store.read_span(1, 2)
    assert [e.text for e in span] == ["b", "c"]


def test_affect_stamp_roundtrip(tmp_path):
    store = EpisodeStore(tmp_path, "affect", 0)
    stamp = AffectStamp(
        warmth=0.7, pressure=0.2, contact=0.5, quiet=0.1, pad_label="warm"
    )
    store.append(
        EpisodeEvent(kind="her_word", ts=1.0, day_key="2024-01-01", affect=stamp)
    )
    reloaded = EpisodeStore(tmp_path, "affect", 0)
    ev = reloaded.read_span(0, 0)[0]
    assert ev.affect is not None
    assert ev.affect.warmth == pytest.approx(0.7)
    assert ev.affect.pad_label == "warm"


def test_sid_hash_is_deterministic_and_stable_length():
    a = sid_hash("user:123")
    b = sid_hash("user:123")
    c = sid_hash("user:456")
    assert a == b
    assert a != c
    assert len(a) == 12
