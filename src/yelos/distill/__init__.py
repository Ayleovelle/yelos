"""distill/ 在整个架构中的位置:opt-in 薄嗓音候选模块(distill_BLUEPRINT v1.0)。

组合根:``build_distill_provider(config, **deps) -> SylannDistilledProvider
| None``。``enabled=false`` 或 probe≠READY ⇒ 返回 ``None``,调用方(未来
波次的 composer/session 接线)零挂载、零 import ``distill.runtime`` 之外
的东西——这是"干净缺席"的定义(蓝图 §4.3)。

**施工纪律留白(疑义记录)**:蓝图 §4.2 设想的"session.py 过渡两席路由"与
composer 路由表注册(``primal.providers.distilled.register_distilled``)
不在本文件完成——施工纪律明令本波不得编辑 ``session.py``/``server.py``/
``__main__.py``/``persistence.py``/``config.py``,而 composer 的真实挂点
需要的 ``p_lookup``/``epoch_lookup``/``lang_lookup``/``corpus_reader`` 等
依赖目前只存在于 ``SessionManager`` 内部。本文件把组合根建完整、可独立
装配自测(见 ``tests/distill/test_optin_smoke.py``),真正把
``build_distill_provider(...)`` 的返回值喂给
``primal.providers.distilled.register_distilled`` 是另一任务(session.py
接线波)的编码前置义务,与 finitude/intrinsic 侧 ``config_defaults.py``
同款"留白待接"模式。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from yelos.core.clock import Clock
from yelos.primal.whitelist_gate import WhitelistGate

from . import config_defaults as cfgd
from .runtime.loader import ModelLoader
from .runtime.provider import SylannDistilledProvider
from .runtime.rerank import build_reranker
from .trainer.protocol import DistillExtrasMissing

__all__ = [
    "DistillExtrasMissing",
    "build_distill_provider",
]


def build_distill_provider(
    config: object,
    *,
    gate: WhitelistGate,
    p_lookup: Callable[[str], float],
    epoch_lookup: Callable[[str], int],
    lang_lookup: Callable[[str], str],
    corpus_reader: Callable[[str, str], tuple[str, ...]],
    clock: Clock,
    trace_sink: Callable[[dict], None] | None = None,
    fidelity_corpus: tuple[str, ...] = (),
) -> SylannDistilledProvider | None:
    """组合根:opt-in 总闸在此裁决,defensive config 读全走 ``config_defaults``。

    返回 ``None`` 的两种情形:``[distill].enabled = false``,或 tier 非法
    (回落默认后仍走完整装配——非法 tier 已在 ``config_defaults`` 内被
    纠正为 ``ngram``,故这里不会因非法值返回 None,只有显式关闭才 None)。
    """
    if not cfgd.distill_enabled(config):
        return None

    model_dir = Path(cfgd.distill_model_dir(config)).expanduser()
    tier = cfgd.distill_tier(config)
    budget_ms = cfgd.distill_budget_ms(config)
    k_candidates = cfgd.distill_k_candidates(config)
    reranker_kind = cfgd.distill_reranker(config)

    loader = ModelLoader(model_dir, tier)
    reranker = build_reranker(reranker_kind, fidelity_corpus)

    return SylannDistilledProvider(
        loader=loader,
        gate=gate,
        reranker=reranker,
        p_lookup=p_lookup,
        epoch_lookup=epoch_lookup,
        lang_lookup=lang_lookup,
        corpus_reader=corpus_reader,
        clock=clock,
        budget_ms=budget_ms,
        k_candidates=k_candidates,
        trace_sink=trace_sink,
    )
