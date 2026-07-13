"""全链集成:compose→gate→final_text;可区分性(template vs lexicon);

pool_snapshot(p) 与 Composer.snapshot_pools 对同一 p 的一致性(接缝 X5
跨模块契约,finitude 消费点的仓内自证);gate 不可绕过的消费断言。
"""

from __future__ import annotations

from yelos.core.primal import LEXICON
from yelos.primal import build_composer, pool_snapshot
from yelos.primal.composer import DEFAULT_ROUTES
from yelos.primal.lexicon.closure import band_of


def test_full_chain_all_occasions_produce_gate_passed_text():
    composer = build_composer()
    for occasion in DEFAULT_ROUTES:
        u = composer.compose(
            "sid-int",
            "2026-07-11",
            occasion,
            surface={"valence": {"warmth": 0.6}},
            now_ts=0.0,
        )
        assert isinstance(u.text, str) and u.text
        assert u.occasion == occasion
        assert u.lang == "zh"


def test_provider_distinguishable_template_vs_lexicon():
    """§15 可区分性凭据:同一 σ 网格上存在 σ 使 template 与 lexicon 异句。"""
    composer_expanded = build_composer()

    found_difference = False
    for sid in ("s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"):
        u = composer_expanded.compose(
            sid, "2026-07-11", "contact_seek", surface={}, now_ts=0.0
        )
        if u.provider == "template":
            lex_only = build_composer({"primal_template_enabled": False})
            u_lex = lex_only.compose(
                sid, "2026-07-11", "contact_seek", surface={}, now_ts=0.0
            )
            if u.canonical != u_lex.canonical:
                found_difference = True
                break
    assert found_difference, "未能观测到 template 与 lexicon 输出集存在差异"


def test_lexicon_only_route_never_uses_template_or_markov():
    composer = build_composer(
        {"primal_template_enabled": False, "primal_markov_enabled": False}
    )
    for occasion in DEFAULT_ROUTES:
        assert "template" not in composer.route(occasion)
        assert "markov" not in composer.route(occasion)


# --- 接缝 X5:pool_snapshot(p) 与 Composer.snapshot_pools 一致 -------------


def test_rings_snapshot_pipeline_consistency():
    for p in (0.0, 0.2, 0.55, 0.9, 1.0):
        composer_p = build_composer(p_lookup=lambda sid, p=p: p)
        band = band_of(p)
        snap_counts = composer_p.snapshot_pools("sid", "2026-07-11")
        snap_words = pool_snapshot(p)
        for occasion in LEXICON:
            assert (
                len(snap_words[occasion]) <= snap_counts.per_occasion[occasion]["total"]
            )
        assert snap_counts.band == band


# --- 消费断言(律二 mutation 式):gate 短路必被对抗集察觉 -----------------


def test_gate_cannot_be_bypassed_composer_always_routes_through_it():
    composer = build_composer(
        {"primal_template_enabled": False, "primal_markov_enabled": False}
    )

    class RogueLexicon:
        provider_id = "lexicon"

        def available(self, sid, lang):
            return True

        def utter_canonical(self, *a, **kw):
            return "你必须马上振作起来"  # 命中禁形表,若闸被短路会漏出

    composer._registry["lexicon"] = RogueLexicon()
    u = composer.compose("sid", "2026-07-11", "concern", surface={}, now_ts=0.0)
    assert u.text != "你必须马上振作起来"
    assert u.canonical != "你必须马上振作起来"
    outcomes = dict(u.chain)
    # lexicon 是唯一链尾且被伪造,gate 必须挡下并触发 critical_fallback。
    assert outcomes.get("lexicon", "").startswith("gate_reject") or (
        outcomes.get("lexicon") == "critical_fallback"
    )


def test_trim_tail_composed_through_composer_end_to_end():
    composer = build_composer()
    u = composer.compose("sid", "2026-07-11", "trim_tail", surface={}, now_ts=0.0)
    assert u.occasion == "trim_tail"
    assert u.text
