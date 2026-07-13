"""在整个架构中的位置:路由 + 回退链 + 谱系记账(蓝图 §3/§5)。

composer.compose 是全平台唯一发声出口:route(occasion) 给出 provider
偏好序,逐级尝试,gate 是唯一出口(A1),链尾恒 lexicon(全函数,A5/T4)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import determinism
from .lexicon.closure import band_of
from .prosody import plan as prosody_plan
from .prosody.engine import prosody_key
from .providers import ProviderUnavailable, PrimalProviderV2
from .providers.distilled import get_distilled
from .whitelist_gate import WhitelistGate
from . import morphology
from .i18n import resolve_lang
from .viz.contracts import PoolSnapshot

_ALL_OCCASIONS: tuple[str, ...] = (
    "withdraw_heavy",
    "withdraw_soft",
    "hold_hesitant",
    "express_warm",
    "recover",
    "concern",
    "contact_seek",
    "contact_night",
    "dream_murmur",
    "trim_tail",
)

# §5.1 默认路由表(expanded profile);v01 profile 由 build_composer 整体覆写。
DEFAULT_ROUTES: dict[str, tuple[str, ...]] = {
    "withdraw_heavy": ("lexicon",),
    "hold_hesitant": ("lexicon",),
    "withdraw_soft": ("distilled", "template", "lexicon"),
    "recover": ("distilled", "template", "lexicon"),
    "express_warm": ("distilled", "template", "lexicon"),
    "concern": ("distilled", "template", "lexicon"),
    "contact_seek": ("distilled", "template", "lexicon"),
    "contact_night": ("distilled", "template", "lexicon"),
    "dream_murmur": ("distilled", "markov", "template", "lexicon"),
    "trim_tail": ("markov", "lexicon"),
}

_TIER_R = frozenset({"dream_murmur", "trim_tail"})


def normalize_routes(routes: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """§5.1 校验:每链尾必为 lexicon(违者追加修正);markov 只准出现在

    Tier-R 场合(违者删除该项)。配置错误不该让她失声。
    """
    fixed: dict[str, tuple[str, ...]] = {}
    for occasion in _ALL_OCCASIONS:
        chain = routes.get(occasion, DEFAULT_ROUTES.get(occasion, ("lexicon",)))
        chain = tuple(pid for pid in chain if pid != "markov" or occasion in _TIER_R)
        if not chain or chain[-1] != "lexicon":
            chain = chain + ("lexicon",)
        fixed[occasion] = chain
    return fixed


@dataclass(frozen=True)
class Utterance:
    text: str
    canonical: str
    occasion: str
    lang: str
    provider: str
    chain: tuple[tuple[str, str], ...]
    p_band: str
    transforms: tuple[str, ...]


class Composer:
    def __init__(
        self,
        *,
        routes: dict[str, tuple[str, ...]],
        registry: dict[str, PrimalProviderV2],
        gate: WhitelistGate,
        p_lookup: Callable[[str], float],
        epoch_lookup: Callable[[str], int],
        lang_lookup: Callable[[str], str],
        corpus_reader: Callable[[str, str], tuple[str, ...]],
        incarnation_lookup: Callable[[str], int] | None = None,
        closure_max: int = 4096,
    ) -> None:
        self._routes = routes
        self._registry = registry
        self._gate = gate
        self._p_lookup = p_lookup
        self._epoch_lookup = epoch_lookup
        self._lang_lookup = lang_lookup
        self._corpus_reader = corpus_reader
        self._incarnation_lookup = incarnation_lookup or (lambda sid: 0)
        self._closure_max = closure_max

    def _resolve(self, pid: str) -> PrimalProviderV2:
        if pid == "distilled":
            return get_distilled()
        return self._registry[pid]

    def route(self, occasion: str) -> tuple[str, ...]:
        return self._routes.get(occasion, ("lexicon",))

    def compose(
        self,
        sid: str,
        day_key: str,
        occasion: str,
        *,
        surface: dict,
        now_ts: float,  # noqa: ARG002  时间不入选词逻辑,只是签名对齐调用方语境
        context: dict | None = None,
    ) -> Utterance:
        lang = resolve_lang(self._lang_lookup(sid))
        p = self._p_lookup(sid)
        epoch = self._epoch_lookup(sid)
        incarnation = self._incarnation_lookup(sid)
        band = band_of(p)
        corpus = self._corpus_reader(sid, lang)
        call_context = dict(context or {})
        call_context["corpus"] = corpus

        chain: list[tuple[str, str]] = []
        canonical: str | None = None
        used_provider: str | None = None

        for pid in self.route(occasion):
            try:
                prov = self._resolve(pid)
            except KeyError:
                chain.append((pid, "unavailable"))
                continue
            try:
                if not prov.available(sid, lang):
                    chain.append((pid, "unavailable"))
                    continue
            except Exception:  # noqa: BLE001  单 provider 异常不拖垮发声
                chain.append((pid, "error"))
                continue
            try:
                canonical_candidate = prov.utter_canonical(
                    surface,
                    sid,
                    day_key,
                    occasion,
                    p=p,
                    epoch=epoch,
                    lang=lang,
                    context=call_context,
                )
            except ProviderUnavailable:
                chain.append((pid, "unavailable"))
                continue
            except Exception:  # noqa: BLE001
                chain.append((pid, "error"))
                continue
            g = self._gate.check(
                canonical_candidate, occasion, lang, band, epoch, corpus
            )
            if not g.ok:
                chain.append((pid, f"gate_reject:{g.reason}"))
                continue
            chain.append((pid, "ok"))
            canonical = canonical_candidate
            used_provider = pid
            break

        if canonical is None or used_provider is None:
            # T4 防御性兜底:理论上链尾 lexicon 全函数必命中;若词库/闭包
            # 失同步导致连 lexicon 都被拒(§6.1 critical 路径),此处仍
            # 保证不失声,并把该次异常计入谱系供可视化/bench 盯梢。
            canonical = "……"
            chain.append(("lexicon", "critical_fallback"))
            used_provider = "lexicon"

        pkey = prosody_key(sid, day_key, occasion, canonical)
        pplan = prosody_plan(canonical, band, occasion, key=pkey)
        final_text, particle_tags = morphology.apply(
            pplan.text,
            surface,
            occasion,
            epoch,
            sid,
            incarnation,
            lang,
            source_provider=used_provider,
        )
        transforms = pplan.tags + particle_tags

        return Utterance(
            text=final_text,
            canonical=canonical,
            occasion=occasion,
            lang=lang,
            provider=used_provider,
            chain=tuple(chain),
            p_band=band,
            transforms=transforms,
        )

    def snapshot_pools(self, sid: str, day_key: str) -> PoolSnapshot:  # noqa: ARG002
        """§12.1 契约一:词池状态计数(给热图);sid_hash 用 determinism 摘要,

        不落 sid 原文(隐私纪律)。
        """
        from . import lexicon as lexicon_data
        from .lexicon.closure import enumerate_closure

        lang = resolve_lang(self._lang_lookup(sid))
        p = self._p_lookup(sid)
        epoch = self._epoch_lookup(sid)
        band = band_of(p)
        per_occasion: dict[str, dict] = {}
        for occasion in _ALL_OCCASIONS:
            base = lexicon_data.base_pool(occasion, lang)
            reachable = lexicon_data.query(occasion, lang, epoch)
            try:
                canon = enumerate_closure(
                    occasion, lang, band, epoch, closure_max=self._closure_max
                )
            except ValueError:
                canon = frozenset()
            per_occasion[occasion] = {
                "total": len(base),
                "reachable": len(reachable),
                "canon_size": len(canon),
                "transformed_size": min(len(canon) * 4, self._closure_max * 4),
            }
        sid_hash = determinism.text_digest(sid)
        return PoolSnapshot(
            day_key=day_key,
            sid_hash=sid_hash,
            lang=lang,
            epoch=epoch,
            p=p,
            band=band,
            per_occasion=per_occasion,
        )


__all__ = [
    "Utterance",
    "Composer",
    "DEFAULT_ROUTES",
    "normalize_routes",
]
