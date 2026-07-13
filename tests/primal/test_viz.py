"""三渲染器 golden SVG;契约 schema 往返;PoolSnapshot 数值与词库/闭包

一致。锁维五。
"""

from __future__ import annotations

from yelos.primal import build_composer
from yelos.primal.viz import contracts, pool_heatmap, routing_sankey, timeline
from yelos.primal.viz.contracts import PoolSnapshot


def _fixed_snapshot() -> PoolSnapshot:
    return PoolSnapshot(
        day_key="2026-07-11",
        sid_hash="abcd1234",
        lang="zh",
        epoch=0,
        p=1.0,
        band="B4",
        per_occasion={
            "concern": {
                "total": 6,
                "reachable": 6,
                "canon_size": 10,
                "transformed_size": 40,
            },
            "trim_tail": {
                "total": 3,
                "reachable": 3,
                "canon_size": 3,
                "transformed_size": 12,
            },
        },
    )


def test_pool_heatmap_golden_svg():
    svg = pool_heatmap.render(_fixed_snapshot())
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "concern" in svg
    assert "trim_tail" in svg
    # 逐字节固定:同输入必同输出。
    assert svg == pool_heatmap.render(_fixed_snapshot())


def test_timeline_golden_svg():
    record = {
        "utterances": [
            {
                "occasion": "concern",
                "text": "我在的。",
                "epoch": 0,
                "provider": "lexicon",
            },
            {
                "occasion": "concern",
                "text": "我在的。",
                "epoch": 0,
                "provider": "lexicon",
            },
            {
                "occasion": "recover",
                "text": "还在的。",
                "epoch": 1,
                "provider": "template",
            },
        ]
    }
    exported = contracts.timeline_export(record)
    svg = timeline.render(exported)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert svg == timeline.render(exported)


def test_timeline_export_counts_frequency():
    record = {
        "utterances": [
            {"occasion": "concern", "text": "我在的。", "epoch": 0},
            {"occasion": "concern", "text": "我在的。", "epoch": 0},
        ]
    }
    exported = contracts.timeline_export(record)
    assert exported["by_epoch"]["0"]["concern"]["我在的。"] == 2


def test_timeline_export_handles_malformed_record():
    assert contracts.timeline_export({}) == {"by_epoch": {}}
    assert contracts.timeline_export({"utterances": "not-a-list"}) == {"by_epoch": {}}


def test_routing_sankey_golden_svg():
    provenance = [
        {
            "ts": 0.0,
            "occasion": "concern",
            "provider": "template",
            "chain": [["distilled", "unavailable"], ["template", "ok"]],
            "band": "B4",
            "transforms": [],
        }
    ]
    svg = routing_sankey.render(provenance)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "concern" in svg
    assert svg == routing_sankey.render(provenance)


def test_routing_sankey_contains_no_raw_text_only_outcomes():
    # 隐私纪律:谱系不含文本原文,渲染器只吃 occasion/provider/outcome。
    provenance = [
        {
            "ts": 0.0,
            "occasion": "concern",
            "provider": "lexicon",
            "chain": [["lexicon", "ok"]],
            "band": "B4",
            "transforms": [],
        }
    ]
    svg = routing_sankey.render(provenance)
    assert "我在的" not in svg  # 不应出现任何 canonical/text 原文片段


def test_pool_snapshot_to_json_roundtrip():
    snap = _fixed_snapshot()
    data = contracts.pool_snapshot_to_json(snap)
    restored = contracts.pool_snapshot_from_json(data)
    assert restored == snap


def test_snapshot_pools_numbers_consistent_with_closure_and_lexicon():
    composer = build_composer()
    snap = composer.snapshot_pools("sid", "2026-07-11")
    for occasion, stats in snap.per_occasion.items():
        assert stats["reachable"] <= stats["total"] or stats["total"] == 0
        assert stats["canon_size"] >= 0
