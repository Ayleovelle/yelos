"""打包哈希往返 / verify 改一字节即 HASH_MISMATCH / 模型卡字段完备。"""

from __future__ import annotations

import json

from yelos.distill.packaging.model_card import ModelCard
from yelos.distill.packaging.pack import pack
from yelos.distill.packaging.verify import LoadState, verify


def test_pack_verify_round_trip(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.ngram.json.gz").write_bytes(b"\x1f\x8bfake-gzip-bytes")

    card = ModelCard(tier="ngram", corpus_hash="abc123", model_hash="def456")
    out = tmp_path / "bundle"
    manifest = pack(model_dir, card, out)

    assert manifest.files
    manifest_path = out.with_suffix(".manifest.json")
    assert manifest_path.is_file()
    assert (out.with_name(out.name + ".MODEL_CARD.md")).is_file()

    state = verify(model_dir, manifest_path)
    assert state == LoadState.READY


def test_verify_tamper_one_byte_triggers_hash_mismatch(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    target = model_dir / "model.ngram.json.gz"
    target.write_bytes(b"\x1f\x8boriginal-bytes")

    card = ModelCard(tier="ngram", corpus_hash="abc", model_hash="def")
    out = tmp_path / "bundle"
    pack(model_dir, card, out)
    manifest_path = out.with_suffix(".manifest.json")

    # 改一字节
    tampered = bytearray(target.read_bytes())
    tampered[-1] ^= 0xFF
    target.write_bytes(bytes(tampered))

    state = verify(model_dir, manifest_path)
    assert state == LoadState.HASH_MISMATCH


def test_verify_absent_when_no_manifest(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    assert verify(model_dir, None) == LoadState.ABSENT
    assert verify(model_dir, tmp_path / "nope.json") == LoadState.ABSENT


def test_model_card_fields_complete_after_pack(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.ngram.json.gz").write_bytes(b"x" * 128)

    card = ModelCard(
        tier="ngram",
        corpus_hash="abc",
        model_hash="def",
        train_config={"order": 3},
        determinism_note="贪心解码,零真随机",
    )
    out = tmp_path / "bundle"
    pack(model_dir, card, out)
    card_text = (out.with_name(out.name + ".MODEL_CARD.md")).read_text(encoding="utf-8")
    for expected in ("tier: ngram", "corpus_hash: abc", "model_hash: def", "license:"):
        assert expected in card_text

    manifest_json = json.loads(
        out.with_suffix(".manifest.json").read_text(encoding="utf-8")
    )
    assert manifest_json["total_size_bytes"] == 128
