"""维四差分闸:v01 profile 下 composer(occ).canonical 与

core.primal.pick 逐字节一致(全场合 × P 网格),锁蓝图 A3/§11.2/0.1。
"""

from __future__ import annotations

from yelos.core.primal import LEXICON, pick as core_pick
from yelos.primal import build_composer

P_GRID = (0.0, -0.5, 0.05, 0.1, 0.15, 0.16, 0.3, 0.5, 0.65, 0.8, 1.0)


def _composer_for_p(p: float):
    return build_composer(
        {"primal_lexicon_profile": "v01"},
        p_lookup=lambda sid: p,
    )


def test_v01_profile_matches_core_pick_byte_for_byte():
    for p in P_GRID:
        composer = _composer_for_p(p)
        for occasion in LEXICON:
            for sid in ("s1", "session-B", "totally-different"):
                u = composer.compose(
                    sid, "2026-07-11", occasion, surface={}, now_ts=0.0
                )
                expected = core_pick(sid, "2026-07-11", occasion, p)
                assert u.canonical == expected
                assert u.provider == "lexicon"


def test_v01_profile_routes_are_lexicon_only():
    composer = _composer_for_p(1.0)
    for occasion in LEXICON:
        assert composer.route(occasion) == ("lexicon",)


def test_v01_profile_unknown_occasion_falls_back_like_core():
    composer = _composer_for_p(1.0)
    u = composer.compose(
        "s", "2026-07-11", "not_a_real_occasion", surface={}, now_ts=0.0
    )
    assert u.canonical == core_pick("s", "2026-07-11", "not_a_real_occasion", 1.0)
