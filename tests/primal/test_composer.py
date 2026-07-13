"""回退全序/终止;链尾 lexicon 校验;单 provider raise 不失声;谱系记账

正确;markov 进非 Tier-R 场合的配置拒载。锁 A5/T4/§5.1。
"""

from __future__ import annotations

from yelos.primal import build_composer
from yelos.primal.composer import DEFAULT_ROUTES, normalize_routes
from yelos.primal.providers import ProviderUnavailable
from yelos.primal.providers.distilled import register_distilled, unregister_distilled


def test_chain_always_ends_lexicon_default_routes():
    for occasion, chain in DEFAULT_ROUTES.items():
        assert chain[-1] == "lexicon", occasion


def test_markov_only_appears_in_tier_r_default_routes():
    for occasion, chain in DEFAULT_ROUTES.items():
        if occasion not in ("dream_murmur", "trim_tail"):
            assert "markov" not in chain


def test_normalize_routes_drops_markov_outside_tier_r():
    bad = {"concern": ("markov", "lexicon")}
    fixed = normalize_routes(bad)
    assert "markov" not in fixed["concern"]
    assert fixed["concern"][-1] == "lexicon"


def test_normalize_routes_appends_lexicon_if_missing():
    bad = {"withdraw_heavy": ("template",)}
    fixed = normalize_routes(bad)
    assert fixed["withdraw_heavy"][-1] == "lexicon"


def test_compose_terminates_and_always_returns_utterance():
    composer = build_composer()
    for occasion in DEFAULT_ROUTES:
        u = composer.compose("sid", "2026-07-11", occasion, surface={}, now_ts=0.0)
        assert u.text
        assert u.chain
        assert u.chain[-1][1] in ("ok", "critical_fallback")


def test_single_provider_exception_does_not_crash_compose(monkeypatch):
    composer = build_composer()

    class Boom:
        provider_id = "template"

        def available(self, sid, lang):
            return True

        def utter_canonical(self, *a, **kw):
            raise RuntimeError("boom")

    composer._registry["template"] = Boom()
    u = composer.compose("sid", "2026-07-11", "concern", surface={}, now_ts=0.0)
    assert u.text
    outcomes = dict(u.chain)
    assert outcomes.get("template") == "error"


def test_provider_unavailable_is_clean_absence_not_error():
    composer = build_composer()

    class AlwaysUnavailable:
        provider_id = "template"

        def available(self, sid, lang):
            return False

        def utter_canonical(self, *a, **kw):
            raise ProviderUnavailable("nope")

    composer._registry["template"] = AlwaysUnavailable()
    u = composer.compose("sid", "2026-07-11", "concern", surface={}, now_ts=0.0)
    outcomes = dict(u.chain)
    assert outcomes.get("template") == "unavailable"


# --- provenance 记账正确 ---------------------------------------------------


def test_provenance_chain_records_every_attempted_provider():
    composer = build_composer()
    u = composer.compose("sid", "2026-07-11", "withdraw_soft", surface={}, now_ts=0.0)
    pids = [pid for pid, _ in u.chain]
    assert pids[-1] == u.provider
    assert u.chain[-1][1] in ("ok", "critical_fallback")
    assert len(pids) == len(set(pids))  # 路由表内每个 provider 只尝试一次


def test_utterance_has_band_and_transforms_fields():
    composer = build_composer()
    u = composer.compose("sid", "2026-07-11", "withdraw_heavy", surface={}, now_ts=0.0)
    assert u.p_band in ("B0", "B1", "B2", "B3", "B4")
    assert isinstance(u.transforms, tuple)


# --- distilled 挂点:干净缺席 + 注册生效 + 越界回退 --------------------------


def test_distilled_stub_absent_by_default():
    unregister_distilled()
    composer = build_composer()
    u = composer.compose("sid", "2026-07-11", "concern", surface={}, now_ts=0.0)
    outcomes = dict(u.chain)
    assert outcomes.get("distilled") == "unavailable"


def test_distilled_registration_takes_effect_after_composer_built():
    unregister_distilled()
    composer = build_composer()

    class FakeDistilled:
        provider_id = "distilled"

        def available(self, sid, lang):
            return True

        def utter_canonical(self, *a, **kw):
            return "我在的。"  # 是 concern Canon 的合法成员

    register_distilled(FakeDistilled())
    try:
        u = composer.compose("sid", "2026-07-11", "concern", surface={}, now_ts=0.0)
        assert u.provider == "distilled"
        assert u.canonical == "我在的。"
    finally:
        unregister_distilled()


def test_distilled_out_of_canon_output_rejected_and_falls_back():
    unregister_distilled()
    composer = build_composer()

    class RogueDistilled:
        provider_id = "distilled"

        def available(self, sid, lang):
            return True

        def utter_canonical(self, *a, **kw):
            return "这是一句不在任何白名单里的话。"

    register_distilled(RogueDistilled())
    try:
        u = composer.compose("sid", "2026-07-11", "concern", surface={}, now_ts=0.0)
        assert u.provider != "distilled"
        outcomes = dict(u.chain)
        assert outcomes.get("distilled", "").startswith("gate_reject")
    finally:
        unregister_distilled()
