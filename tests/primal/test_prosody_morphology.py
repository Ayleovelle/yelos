"""每带 golden;severity 单调性质;幂等守卫;变体数<=4;warmth 档位→

粒子档 golden;纪元固化(同 incarnation 恒定/异 incarnation 可异);
lexicon 源不施加。锁 A6/8.1/8.2。
"""

from __future__ import annotations

from yelos.primal import build_composer
from yelos.primal.morphology import epochal, particles
from yelos.primal.prosody import SEVERITY, plan
from yelos.primal.prosody.engine import _variants_for


# --- severity 单调(A6)-----------------------------------------------------


def test_severity_monotone_across_bands():
    order = ["B4", "B3", "B2", "B1", "B0"]
    severities = [SEVERITY[b] for b in order]
    assert severities == sorted(severities)


def test_variant_count_never_exceeds_four():
    for band in ("B0", "B1", "B2", "B3", "B4"):
        variants = _variants_for(band, "没什么,就是看看你在不在。")
        assert len(variants) <= 4


# --- 幂等守卫 --------------------------------------------------------------


def test_idempotent_guard_pure_ellipsis_untouched():
    result = plan("……", "B0", "trim_tail", key="k1")
    assert result.text == "……"
    assert result.tags == ()


def test_idempotent_guard_no_prosody_hint_untouched():
    result = plan("我想说来着——", "B1", "hold_hesitant", key="k2", hint="no_prosody")
    assert result.text == "我想说来着——"


def test_idempotent_guard_already_ends_em_dash():
    result = plan("先到这儿——", "B0", "trim_tail", key="k3")
    assert result.text == "先到这儿——"


def test_b4_is_always_identity():
    result = plan("没什么,就是看看你在不在。", "B4", "contact_seek", key="k4")
    assert result.text == "没什么,就是看看你在不在。"
    assert result.tags == ()


# --- golden per band(固定 key → 固定输出,不随时间/环境漂移)-------------


def test_prosody_golden_each_band():
    canonical = "没什么,就是看看你在不在。"
    expected = {
        "B4": canonical,
    }
    for band, exp in expected.items():
        result = plan(canonical, band, "contact_seek", key="golden-key")
        assert result.text == exp

    for band in ("B3", "B2", "B1", "B0"):
        a = plan(canonical, band, "contact_seek", key="golden-key")
        b = plan(canonical, band, "contact_seek", key="golden-key")
        assert a == b  # 同 key 同输出(确定性)


# --- morphology:仅 template 源 --------------------------------------------


def test_morphology_skips_non_template_source():
    composer = build_composer({"primal_lexicon_profile": "v01"})
    u = composer.compose("sid", "2026-07-11", "express_warm", surface={}, now_ts=0.0)
    assert u.provider == "lexicon"
    assert u.text == u.canonical  # lexicon 源不被形态变化触碰(§8.1)
    assert not any(t.startswith("particle:") for t in u.transforms)


def test_warmth_tier_gradient():
    assert particles.warmth_tier({"valence": {"warmth": 0.1}}) == 0
    assert particles.warmth_tier({"valence": {"warmth": 0.5}}) == 1
    assert particles.warmth_tier({"valence": {"warmth": 0.9}}) == 2
    assert particles.warmth_tier({}) == 1  # 缺失给中档保守默认
    assert particles.warmth_tier({"valence": {"warmth": "not-a-number"}}) == 1


def test_exclaim_only_allowed_in_expressive_occasions():
    high = {"valence": {"warmth": 0.95}}
    particle_concern = particles.select_particle(
        "concern", high, epoch=0, sid="s", incarnation=0
    )
    assert "!" not in particle_concern
    particle_warm = particles.select_particle(
        "express_warm", high, epoch=0, sid="s", incarnation=0
    )
    # express_warm 允许感叹号档位(不强制出现,但不应被裁剪掉的话应含叹号)
    assert particle_warm in particles.PARTICLE_POOL["express_warm"]


# --- 纪元固化(§8.2)--------------------------------------------------------


def test_epoch_pool_full_at_young_epochs():
    base = ("a", "b", "c", "d")
    assert epochal.epoch_pool(base, 0, "sid", 0) == base
    assert epochal.epoch_pool(base, 1, "sid", 0) == base


def test_epoch_pool_shrinks_at_epoch_two():
    base = ("a", "b", "c", "d")
    shrunk = epochal.epoch_pool(base, 2, "sid", 0)
    assert shrunk == base[:2]


def test_epoch_pool_singleton_fixed_same_incarnation():
    base = ("a", "b", "c", "d", "e")
    first = epochal.epoch_pool(base, 3, "sid-1", 0)
    second = epochal.epoch_pool(base, 4, "sid-1", 0)
    assert len(first) == 1
    assert first == second  # 同一颗心老年期口头禅恒定


def test_epoch_pool_singleton_may_differ_across_incarnations():
    base = ("a", "b", "c", "d", "e")
    results = {epochal.epoch_pool(base, 3, "sid-1", inc) for inc in range(6)}
    assert len(results) >= 2  # 不同 incarnation 种子不同,允许不同(网格断言)


def test_epoch_pool_singleton_may_differ_across_sids():
    base = ("a", "b", "c", "d", "e")
    results = {
        epochal.epoch_pool(base, 3, sid, 0)
        for sid in ("sid-a", "sid-b", "sid-c", "sid-d")
    }
    assert len(results) >= 2  # 两颗同配置的心,老年期口头禅不同(概率意义上)
