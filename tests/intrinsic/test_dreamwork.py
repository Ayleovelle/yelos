"""T-DRM-01..05:梦境生成子系统(intrinsic_BLUEPRINT §4/§8.2)。"""

from __future__ import annotations

import ast
from pathlib import Path

from yelos.intrinsic.dreamwork import dream_state as dream_state_mod
from yelos.intrinsic.dreamwork.dream_state import DreamState
from yelos.intrinsic.dreamwork.residue import ResidueAggregation, sanitize_theme_source
from yelos.intrinsic.dreamwork.wander import MarkovWander
from yelos.intrinsic.field.state import FieldState
from yelos.intrinsic.moments.taxonomy import MomentEntry, MomentKind

_DREAMWORK_DIR = Path(dream_state_mod.__file__).parent


def _night_trace(
    n: int = 60, longing: float = 0.6, afterglow: float = 0.1, languor: float = 0.3
):
    return [
        FieldState(
            drive=0.2,
            languor=languor,
            longing=longing,
            afterglow=afterglow,
            ts=float(i),
        )
        for i in range(n)
    ]


def _moments(kinds: list[MomentKind]) -> list[MomentEntry]:
    return [
        MomentEntry(
            ts=float(i),
            day_key="2026-07-11",
            kind=k,
            reason_code="seek",
            phi=(0.5, 0.2, 0.3, 0.1),
            trace_hash="abc",
        )
        for i, k in enumerate(kinds)
    ]


# --- T-DRM-01:状态机跨日 --------------------------------------------------


def test_drm01_state_machine_arms_after_two_ticks_and_delivers() -> None:
    state = DreamState()
    surface_hit = {"state": {"needs": {"expression": 0.8}}}

    state = dream_state_mod.tick(state, surface_hit, in_quiet_hours=True)
    assert state.count == 1
    state = dream_state_mod.tick(state, surface_hit, in_quiet_hours=True)
    assert state.count == 2

    trace = _night_trace()
    moments = _moments([MomentKind.CROSSED_BUT_GATED, MomentKind.WANT_BLOCKED_QUIET])
    state = dream_state_mod.arm(
        state,
        "2026-07-11",
        trace,
        moments,
        ("挂念", "夜"),
        ResidueAggregation(),
        "seed1",
    )
    assert state.count == 0
    assert state.pending is True
    assert state.residue is not None

    assert dream_state_mod.ready(state, p=0.5, enabled=True) is True
    assert dream_state_mod.ready(state, p=0.1, enabled=True) is False  # P<0.3

    delivered = dream_state_mod.deliver(state)
    assert delivered.pending is False
    assert delivered.delivered_today is True
    assert delivered.residue is None

    rolled = dream_state_mod.rollover_day(delivered)
    assert rolled.delivered_today is False


def test_drm01_below_threshold_resets_count_without_arming() -> None:
    state = DreamState(count=1)
    trace = _night_trace()
    state2 = dream_state_mod.arm(
        state, "2026-07-11", trace, [], (), ResidueAggregation(), "s"
    )
    assert state2.count == 0
    assert state2.pending is False
    assert state2.residue is None


def test_drm01_state_roundtrip_dict() -> None:
    state = DreamState(
        count=2, night_of="2026-07-11", pending=True, delivered_today=False
    )
    d = state.to_dict()
    back = DreamState.from_dict(d)
    assert back == state


# --- T-DRM-02/03:白名单三锁 + 对抗集 ---------------------------------------


def test_drm02_theme_keys_are_closed_set_only() -> None:
    moments = _moments([MomentKind.SPOKE, MomentKind.CROSSED_BUT_GATED])
    l2_keywords = ("挂念", "散步")
    trace = _night_trace()
    residue = ResidueAggregation().generate(trace, moments, l2_keywords, "seed")
    closed = {str(m.kind) for m in moments} | set(l2_keywords)
    assert set(residue.theme_keys) <= closed


def test_drm02_ast_lock_no_free_text_sentences_in_dreamwork() -> None:
    """AST 扫描锁:dreamwork/*.py 里(docstring 之外)不得出现含句末标点的字符串
    字面量(疑似硬编码用户可见句子;§4.2 三锁之一,静态锁)。
    """
    terminators = "。!?…"
    for path in _DREAMWORK_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        docstring_nodes = set()
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                body = getattr(node, "body", [])
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                ):
                    docstring_nodes.add(id(body[0].value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in docstring_nodes:
                    continue
                assert not any(t in node.value for t in terminators), (
                    path,
                    node.value,
                )


def test_drm03_adversarial_l2_keywords_are_filtered() -> None:
    """对抗集:构造含禁形片段的伪 L2 关键词,断言被拒收(不进 theme_keys)。"""
    adversarial = ("你必须开心一点", "正常关键词")
    filtered = sanitize_theme_source(adversarial)
    assert "你必须开心一点" not in filtered
    assert "正常关键词" in filtered

    moments = _moments([MomentKind.SPOKE])
    trace = _night_trace()
    residue = ResidueAggregation().generate(trace, moments, adversarial, "seed")
    assert "你必须开心一点" not in residue.theme_keys

    wander = MarkovWander(fallback=ResidueAggregation())
    residue_w = wander.generate(
        trace, moments, adversarial, "seed", utterance_corpus=("语料句子",)
    )
    assert "你必须开心一点" not in residue_w.theme_keys


# --- T-DRM-04:wander 回退链 -------------------------------------------------


def test_drm04_wander_falls_back_when_candidates_all_rejected() -> None:
    """候选池全部被禁形表拦下 → 干净回退到 ResidueAggregation,不产半成品。"""
    moments: list[MomentEntry] = []
    l2_keywords = ("你必须马上", "我保证陪你")  # 两条都命中禁形表
    trace = _night_trace()
    wander = MarkovWander(fallback=ResidueAggregation())
    fallback_expected = ResidueAggregation().generate(
        trace, moments, l2_keywords, "seed"
    )
    residue = wander.generate(
        trace, moments, l2_keywords, "seed", utterance_corpus=("语料",)
    )
    assert residue == fallback_expected


# --- T-DRM-05:空语料干净缺席 ------------------------------------------------


def test_drm05_empty_corpus_falls_back_cleanly() -> None:
    wander = MarkovWander(fallback=ResidueAggregation())
    assert wander.available(()) is False

    moments = _moments([MomentKind.SPOKE, MomentKind.DREAM_ARMED])
    l2_keywords = ("挂念",)
    trace = _night_trace()
    expected = ResidueAggregation().generate(trace, moments, l2_keywords, "seed")
    actual = wander.generate(trace, moments, l2_keywords, "seed", utterance_corpus=())
    assert actual == expected
