"""distill 深化接线集成测试(wave A 诊断收尾:distill WIRED via registration

side-effect,但只有 ``primal_composer_enabled`` 也开时才真被 composer 查询
消费——只开 ``distill_enabled`` 不开 composer = 静默 no-op)。

覆盖:

- co-enable ``primal_composer_enabled`` + ``distill_enabled``:端到端冒烟,
  用 spy 断言 ``SylannDistilledProvider`` 真被 composer 查询(``available``
  被调用),不是注册了就没人再碰的死籍。
- 模型缺席(测试环境无模型文件,tier=ngram 亦缺 manifest)时探针给
  ``ABSENT``,composer 链自动回退 template/lexicon,不崩、仍出字。
- 只开 ``distill_enabled`` 不开 ``primal_composer_enabled``:provider 确实
  注册进 ``_registry``(副作用发生),但 session 层发声走的是 core
  ``LexiconProvider``(``_ComposerProvider`` 都没建),composer 根本不存在,
  distilled 槽自然不会被查询——静默 no-op 场景实证。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from yelos.config import YelosConfig  # noqa: E402
from yelos.engine_bridge import EngineBridge  # noqa: E402
from yelos.primal.providers.distilled import (  # noqa: E402
    get_distilled,
    unregister_distilled,
)
from yelos.session import SessionManager, _ComposerProvider  # noqa: E402


def make_manager(tmp_path: Path, **overrides) -> SessionManager:
    cfg = YelosConfig(
        data_dir=str(tmp_path / "data"),
        heartbeat_enabled=False,
        arbiter_min_gap_seconds=0,
        **overrides,
    )
    return SessionManager(cfg, EngineBridge(llm_fn=None))


class _AvailableSpy:
    """包一层记账壳,委托真身,不改任何返回值/异常语义。"""

    provider_id = "distilled"

    def __init__(self, inner) -> None:
        self._inner = inner
        self.available_calls = 0
        self.utter_calls = 0

    def available(self, sid: str, lang: str) -> bool:
        self.available_calls += 1
        return self._inner.available(sid, lang)

    def utter_canonical(self, *a, **kw):
        self.utter_calls += 1
        return self._inner.utter_canonical(*a, **kw)


@pytest.fixture(autouse=True)
def _clean_distilled_registry():
    """每个用例前后都撤回注册,不让 process-global _registry 跨测试泄漏。"""
    unregister_distilled()
    yield
    unregister_distilled()


def test_distill_co_enabled_provider_is_queried_by_composer(tmp_path: Path) -> None:
    """co-enable 冒烟:distilled 槽真被 composer 查询,不是静默注册了没人碰。"""
    sm = make_manager(
        tmp_path,
        primal_composer_enabled=True,
        distill_enabled=True,
        distill_model_dir=str(tmp_path / "no_model_here"),
    )
    assert isinstance(sm._provider, _ComposerProvider)

    real_provider = get_distilled()
    assert real_provider is not None
    assert getattr(real_provider, "provider_id", None) == "distilled"
    # 桩(DistilledSlotStub)不该出现——真身必须已经注册生效。
    assert type(real_provider).__name__ != "DistilledSlotStub"

    spy = _AvailableSpy(real_provider)
    from yelos.primal.providers.distilled import register_distilled

    register_distilled(spy)

    text = sm._provider.utter({}, "sid-distill-co", "2026-07-11", "concern")

    assert spy.available_calls >= 1, (
        "composer co-enable 时必须真的查询 distilled 槽(available()),"
        "而不是注册了从不被消费的静默 no-op"
    )
    # 测试环境无真模型文件 -> probe 给 ABSENT -> available() 恒 False ->
    # composer 链自动回退 template/lexicon,永不失声。
    assert text


def test_distill_model_absent_falls_back_without_crash(tmp_path: Path) -> None:
    """模型缺席场景显式断言:回落 template/lexicon,不崩、不失声。"""
    sm = make_manager(
        tmp_path,
        primal_composer_enabled=True,
        distill_enabled=True,
        distill_model_dir=str(tmp_path / "still_no_model"),
    )
    composer = sm._provider._composer
    u = composer.compose(
        "sid-distill-absent", "2026-07-11", "concern", surface={}, now_ts=0.0
    )
    outcomes = dict(u.chain)
    assert outcomes.get("distilled") == "unavailable"
    assert u.provider in ("template", "lexicon")
    assert u.text


def test_distill_enabled_without_composer_is_silent_noop(tmp_path: Path) -> None:
    """只开 distill_enabled、composer 关:注册确实发生,但从不被查询。"""
    sm = make_manager(
        tmp_path,
        primal_composer_enabled=False,
        distill_enabled=True,
        distill_model_dir=str(tmp_path / "irrelevant_model_dir"),
    )
    # 不是 _ComposerProvider -> composer 根本没建 -> distilled 槽不可能被查询。
    assert not isinstance(sm._provider, _ComposerProvider)

    real_provider = get_distilled()
    assert type(real_provider).__name__ != "DistilledSlotStub"  # 副作用确实发生

    spy = _AvailableSpy(real_provider)
    from yelos.primal.providers.distilled import register_distilled

    register_distilled(spy)

    text = sm._provider.utter({}, "sid-distill-noop", "2026-07-11", "concern")

    assert spy.available_calls == 0, "composer 未建时 distilled 槽不该被任何人查询"
    assert text  # core LexiconProvider 仍然正常发声


def test_distill_without_composer_emits_warning(tmp_path, caplog) -> None:
    """防呆:distill_enabled 开、primal_composer_enabled 关时构造期发一条

    warning(不改行为、不报错)。
    """
    with caplog.at_level("WARNING", logger="yelos.session"):
        make_manager(
            tmp_path,
            primal_composer_enabled=False,
            distill_enabled=True,
            distill_model_dir=str(tmp_path / "warn_probe_model_dir"),
        )
    assert any(
        "primal_composer_enabled" in rec.message and "静默 no-op" in rec.message
        for rec in caplog.records
    )


def test_distill_co_enabled_emits_no_mismatch_warning(tmp_path, caplog) -> None:
    """co-enable 时不该发这条防呆 warning(行为不变的对照组)。"""
    with caplog.at_level("WARNING", logger="yelos.session"):
        make_manager(
            tmp_path,
            primal_composer_enabled=True,
            distill_enabled=True,
            distill_model_dir=str(tmp_path / "co_enabled_model_dir"),
        )
    assert not any("静默 no-op" in rec.message for rec in caplog.records)
