"""在整个架构中的位置:primal 包组合根(蓝图 §2)。

build_composer(...) 显式装配路由表 / provider 实例 / gate / 变换器,
返回一个 Composer。core/primal.py(v0.1)零改动保留在原位,是本包 v01
profile 的兼容内核(经 LexiconProviderV2(profile="v01") 直接复用其
pick/shrink_pool,不重实现)。

**config 读取纪律**:config.py 尚未加 primal_* 键(施工纪律禁止本波编辑
config.py),故这里一律用 getattr(config, key, default) 防御式读取——
config 可以是尚未扩表的 YelosConfig 实例,也可以是任意带同名属性的
对象或 dict(经 _cfg_get 统一处理);缺键时全部退到蓝图 §13 表列默认值。
"""

from __future__ import annotations

import json
from typing import Any, Callable

from yelos.core.primal import shrink_pool

from . import lexicon as lexicon_data
from .composer import Composer, DEFAULT_ROUTES, Utterance, normalize_routes
from .lexicon.closure import DEFAULT_CLOSURE_MAX, enumerate_closure
from .providers.lexicon import LexiconProviderV2
from .providers.markov import MarkovSurfaceProvider
from .providers.template import TemplateGrammarProvider
from .whitelist_gate import WhitelistGate, load_forbidden_patterns

_DEFAULTS = {
    "primal_lexicon_profile": "expanded",
    "primal_template_enabled": True,
    "primal_markov_enabled": True,
    "primal_markov_min_corpus": 50,
    "primal_closure_max": DEFAULT_CLOSURE_MAX,
    "primal_routes": "",
    "default_lang": "zh",
}


def _cfg_get(config: Any, key: str) -> Any:
    default = _DEFAULTS[key]
    if config is None:
        return default
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def _default_corpus_reader(sid: str, lang: str) -> tuple[str, ...]:  # noqa: ARG001
    """占位 corpus_reader:build_composer 调用方(session 层)应注入真实

    实现,读 record["utterances"] 中 lang 匹配的历史发声(蓝图 §1.1)。
    """
    return ()


def build_composer(
    config: Any = None,
    *,
    p_lookup: Callable[[str], float] | None = None,
    epoch_lookup: Callable[[str], int] | None = None,
    corpus_reader: Callable[[str, str], tuple[str, ...]] | None = None,
    lang_lookup: Callable[[str], str] | None = None,
    incarnation_lookup: Callable[[str], int] | None = None,
) -> Composer:
    profile = _cfg_get(config, "primal_lexicon_profile")
    if profile not in ("v01", "expanded"):
        profile = "expanded"
    template_enabled = bool(_cfg_get(config, "primal_template_enabled"))
    markov_enabled = bool(_cfg_get(config, "primal_markov_enabled"))
    markov_min_corpus = int(_cfg_get(config, "primal_markov_min_corpus"))
    closure_max = int(_cfg_get(config, "primal_closure_max"))
    routes_raw = _cfg_get(config, "primal_routes")

    if profile == "v01":
        routes = {occ: ("lexicon",) for occ in DEFAULT_ROUTES}
    else:
        routes = dict(DEFAULT_ROUTES)
        if routes_raw:
            try:
                override = json.loads(routes_raw)
                if isinstance(override, dict):
                    routes.update({k: tuple(v) for k, v in override.items()})
            except (ValueError, TypeError):
                pass
        if not template_enabled:
            routes = {
                occ: tuple(p for p in chain if p != "template")
                for occ, chain in routes.items()
            }
        if not markov_enabled:
            routes = {
                occ: tuple(p for p in chain if p != "markov")
                for occ, chain in routes.items()
            }
        routes = normalize_routes(routes)

    registry = {
        "lexicon": LexiconProviderV2(profile=profile),
        "template": TemplateGrammarProvider(enabled=template_enabled),
        "markov": MarkovSurfaceProvider(
            enabled=markov_enabled, min_corpus=markov_min_corpus
        ),
    }

    def closure_fn(occasion: str, lang: str, band: str, epoch: int) -> frozenset[str]:
        return enumerate_closure(
            occasion, lang, band, epoch, profile=profile, closure_max=closure_max
        )

    gate = WhitelistGate(closure_fn, forbidden_patterns=load_forbidden_patterns("zh"))

    return Composer(
        routes=routes,
        registry=registry,
        gate=gate,
        p_lookup=p_lookup or (lambda sid: 1.0),
        epoch_lookup=epoch_lookup or (lambda sid: 0),
        lang_lookup=lang_lookup or (lambda sid: _cfg_get(config, "default_lang")),
        corpus_reader=corpus_reader or _default_corpus_reader,
        incarnation_lookup=incarnation_lookup,
        closure_max=closure_max,
    )


def pool_snapshot(p: float) -> dict[str, tuple[str, ...]]:
    """接缝 X5:纯函数、无状态,供 finitude 词汇年轮消费

    (INTEGRATION_SPEC §3.5 裁定)。与 Composer.snapshot_pools(计数版,
    primal 自用热图)是两个不同形态的接口,不合并。

    对同一个 p,本函数与 Composer.snapshot_pools 报告的 reachable 计数
    须保持一致(test_integration_crossmodule::test_rings_snapshot_pipeline
    的断言点;本包侧对应测试见 tests/primal/test_integration_primal.py)。
    """
    return {
        occasion: shrink_pool(pool, p)
        for occasion, pool in lexicon_data.all_base_pools("zh").items()
    }


__all__ = [
    "build_composer",
    "pool_snapshot",
    "Composer",
    "Utterance",
    "DEFAULT_ROUTES",
]
