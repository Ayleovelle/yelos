"""T-P5:DuelPolicy 单元 + 隐私测试(arbiter_BLUEPRINT §3.4/§6.2)。

- 取保守者(σ min);
- 分歧样本字段白名单(无 draft/text);
- 语料 schema 校验读取器往返(写入 -> 读取 -> 校验)。
"""

from __future__ import annotations

import json

from yelos.arbiter.accounting.duel_corpus import (
    FIELD_WHITELIST,
    DuelCorpusWriter,
    build_row,
    read_corpus,
)
from yelos.arbiter.core_probe import build_neutral_probe
from yelos.arbiter.inputs import PolicyParams
from yelos.arbiter.lattice import sigma_of
from yelos.arbiter.policies.duel import DUEL_POLICY


def test_duel_takes_conservative_verdict_on_divergence():
    pin = build_neutral_probe(
        action="withdraw",
        pressure=0.74,
        expr=0.8,
        p=0.8,
        params=PolicyParams(0.75, 0.55, 0.70, 1.0),
    )
    result = DUEL_POLICY.evaluate(pin)
    assert result.diverged is True
    assert result.chosen is (
        result.verdict_a
        if sigma_of(result.verdict_a) <= sigma_of(result.verdict_b)
        else result.verdict_b
    )
    assert sigma_of(result.chosen) == min(
        sigma_of(result.verdict_a), sigma_of(result.verdict_b)
    )


def test_duel_no_divergence_no_write(tmp_path):
    pin = build_neutral_probe(action="explore", pressure=0.1, expr=0.1)
    result = DUEL_POLICY.evaluate(pin)
    assert result.diverged is False
    writer = DuelCorpusWriter(tmp_path)
    writer.write(pin, result, ts=1000.0, day_key="2026-07-11", theta_digest="deadbeef")
    assert not (tmp_path / "bench_corpus" / "arbiter_duel" / "2026-07.jsonl").exists()


def test_duel_corpus_field_whitelist_no_draft_or_text():
    pin = build_neutral_probe(
        action="withdraw",
        pressure=0.74,
        expr=0.8,
        p=0.8,
        params=PolicyParams(0.75, 0.55, 0.70, 1.0),
    )
    result = DUEL_POLICY.evaluate(pin)
    row = build_row(pin, result, ts=123.0, theta_digest="cafebabe")
    assert set(row.keys()) == FIELD_WHITELIST
    for key in row:
        low = key.lower()
        assert "draft" not in low
        assert "text" not in low
    assert "draft" not in json.dumps(
        row
    )  # 双保险:序列化后的字符串里也不含该字面量之外的原文泄漏字段名


def test_duel_corpus_writer_roundtrip(tmp_path):
    pin = build_neutral_probe(
        action="withdraw",
        pressure=0.74,
        expr=0.8,
        p=0.8,
        params=PolicyParams(0.75, 0.55, 0.70, 1.0),
    )
    result = DUEL_POLICY.evaluate(pin)
    assert result.diverged
    writer = DuelCorpusWriter(tmp_path)
    writer.write(
        pin, result, ts=1_700_000_000.0, day_key="2026-07-11", theta_digest="0123abcd"
    )
    writer.write(
        pin, result, ts=1_700_000_100.0, day_key="2026-07-15", theta_digest="0123abcd"
    )
    rows = read_corpus(tmp_path, "2026-07")
    assert len(rows) == 2
    for r in rows:
        assert r["verdict_a"] == "REPLACE"
        assert r["verdict_b"] == "SWALLOW"
        assert r["chosen"] == "REPLACE"


def test_duel_corpus_path_is_data_dir_bench_corpus_arbiter_duel(tmp_path):
    """INTEGRATION_SPEC X1 裁定的唯一路径:<data_dir>/bench_corpus/arbiter_duel/YYYY-MM.jsonl。"""
    writer = DuelCorpusWriter(tmp_path)
    p = writer.path_for("2026-07-11")
    assert p == tmp_path / "bench_corpus" / "arbiter_duel" / "2026-07.jsonl"


def test_readcorpus_rejects_bad_field(tmp_path):
    d = tmp_path / "bench_corpus" / "arbiter_duel"
    d.mkdir(parents=True)
    bad_row = {
        "ts": 1.0,
        "draft": "泄漏原文",
        "sid_digest": "x",
        "features": {},
        "verdict_a": "PASS",
        "verdict_b": "PASS",
        "chosen": "PASS",
        "theta_digest": "x",
    }
    (d / "2026-08.jsonl").write_text(
        json.dumps(bad_row, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    import pytest

    with pytest.raises(AssertionError):
        read_corpus(tmp_path, "2026-08")
