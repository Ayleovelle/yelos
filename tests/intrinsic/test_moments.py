"""moments/ 测试:schema 无原文、滚动归档、T-MOM-04 主题 mutation、T-MOM-05 过期记账。"""

from __future__ import annotations

import gzip
import json

from yelos.intrinsic.dreamwork.residue import ResidueAggregation
from yelos.intrinsic.field.state import FieldState
from yelos.intrinsic.moments.ledger import (
    MomentsLedger,
    compute_trace_hash,
    read_moments,
    sid_hash,
)
from yelos.intrinsic.moments.taxonomy import (
    MomentEntry,
    MomentKind,
    moment_kind_for_decision,
)
from yelos.core.intrinsic import IntrinsicDecision


def test_schema_no_free_text_fields() -> None:
    """MomentEntry 只放 reason code / 封闭键 / 数值,没有自由文本字段。"""
    field_names = {f for f in MomentEntry.__dataclass_fields__}
    assert field_names == {
        "ts",
        "day_key",
        "kind",
        "reason_code",
        "phi",
        "trace_hash",
        "occasion_hint",
    }
    entry = MomentEntry(
        ts=1.0,
        day_key="2026-07-11",
        kind=MomentKind.SPOKE,
        reason_code="seek",
        phi=(0.1, 0.2, 0.3, 0.4),
        trace_hash=compute_trace_hash({"a": 1}),
        occasion_hint="contact_seek",
    )
    d = entry.to_dict()
    assert isinstance(d["reason_code"], str) and len(d["reason_code"]) < 32
    assert MomentEntry.from_dict(d) == entry


def test_moment_kind_for_decision_matches_table() -> None:
    assert (
        moment_kind_for_decision(IntrinsicDecision(True, "contact_seek", "seek"))
        == MomentKind.SPOKE
    )
    assert moment_kind_for_decision(IntrinsicDecision(False, reason="p0")) is None
    assert (
        moment_kind_for_decision(IntrinsicDecision(False, reason="no_trigger")) is None
    )
    assert (
        moment_kind_for_decision(IntrinsicDecision(False, reason="pressure"))
        == MomentKind.CROSSED_BUT_GATED
    )
    assert (
        moment_kind_for_decision(IntrinsicDecision(False, reason="daily_cap"))
        == MomentKind.WANT_BLOCKED_BUDGET
    )
    assert (
        moment_kind_for_decision(IntrinsicDecision(False, reason="min_gap"))
        == MomentKind.WANT_BLOCKED_GAP
    )
    assert (
        moment_kind_for_decision(IntrinsicDecision(False, reason="unanswered"))
        == MomentKind.WANT_BLOCKED_RESPECT
    )
    assert (
        moment_kind_for_decision(IntrinsicDecision(False, reason="quiet_hours"))
        == MomentKind.WANT_BLOCKED_QUIET
    )


def test_ledger_append_and_read(tmp_path) -> None:
    ledger = MomentsLedger(tmp_path, sid_hash("user-1"))
    e1 = MomentEntry(
        1.0, "2026-07-01", MomentKind.SPOKE, "seek", (0.1, 0.2, 0.3, 0.0), "h1"
    )
    e2 = MomentEntry(
        2.0,
        "2026-07-11",
        MomentKind.WANT_EXPIRED,
        "expired",
        (0.1, 0.2, 0.3, 0.0),
        "h2",
    )
    ledger.append(e1)
    ledger.append(e2)

    all_entries = ledger.read_all()
    assert all_entries == [e1, e2]
    assert ledger.read_day("2026-07-11") == [e2]

    read_back = read_moments(tmp_path, "user-1")
    assert read_back == [e1, e2]


def test_ledger_rolling_archive_never_deletes(tmp_path) -> None:
    ledger = MomentsLedger(tmp_path, "abc123")
    old = MomentEntry(
        1.0, "2026-05-01", MomentKind.SPOKE, "seek", (0.0, 0.0, 0.0, 0.0), "h1"
    )
    new = MomentEntry(
        2.0, "2026-07-11", MomentKind.SPOKE, "seek", (0.0, 0.0, 0.0, 0.0), "h2"
    )
    ledger.append(old)
    ledger.append(new)

    moved = ledger.archive_before("2026-07-01")
    assert moved == 1
    assert ledger.read_all() == [new]  # 本体只剩 cutoff 之后的行

    archive_path = ledger.path.parent / "abc123" / "202605.jsonl.gz"
    assert archive_path.exists()
    with gzip.open(archive_path, "rt", encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    assert len(lines) == 1
    assert lines[0]["kind"] == "spoke"

    # 再次归档同月份不覆盖(追加式,永不删)。
    ledger.append(
        MomentEntry(3.0, "2026-05-02", MomentKind.SPOKE, "seek", (0.0,) * 4, "h3")
    )
    ledger.archive_before("2026-07-01")
    with gzip.open(archive_path, "rt", encoding="utf-8") as fh:
        lines2 = [json.loads(line) for line in fh if line.strip()]
    assert len(lines2) == 2


def test_mom04_moments_mutation_changes_dream_theme_keys() -> None:
    """[T-MOM-04] 改某日 moments 的 kind 分布 ⇒ 当晚 residue.theme_keys 变。"""
    trace = [
        FieldState(drive=0.2, languor=0.3, longing=0.6, afterglow=0.1, ts=float(i))
        for i in range(30)
    ]
    l2_keywords = ("挂念",)
    gen = ResidueAggregation()

    moments_a = [
        MomentEntry(float(i), "d", MomentKind.SPOKE, "seek", (0.1,) * 4, "h")
        for i in range(3)
    ]
    moments_b = [
        MomentEntry(
            float(i), "d", MomentKind.WANT_BLOCKED_QUIET, "quiet_hours", (0.1,) * 4, "h"
        )
        for i in range(3)
    ]

    residue_a = gen.generate(trace, moments_a, l2_keywords, "seed")
    residue_b = gen.generate(trace, moments_b, l2_keywords, "seed")
    assert residue_a.theme_keys != residue_b.theme_keys


def test_mom05_want_expired_is_a_recordable_kind() -> None:
    """[T-MOM-05] WANT_EXPIRED 是可记账的 MomentKind(outbox 过期回调钩,W-6)。

    本波 outbox 接线不在 intrinsic 包内(不改 session.py);此处只锁 schema
    契约:MomentKind.WANT_EXPIRED 存在且可落盘/读回。
    """
    assert MomentKind.WANT_EXPIRED == "want_expired"
    entry = MomentEntry(
        1.0, "2026-07-11", MomentKind.WANT_EXPIRED, "expired", (0.0,) * 4, "h"
    )
    assert MomentEntry.from_dict(entry.to_dict()) == entry
