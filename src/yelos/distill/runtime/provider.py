"""在整个架构中的位置:PrimalProvider 家族第 4 席,composer 路由表末席前

(兜底恒为 lexicon)。封版例外挂点的兑现:模型只提候选,闸决定出口
(DA1/DA2/DA3,蓝图 §3.1)。

协议对齐真实代码(``primal.providers.PrimalProviderV2``),不是蓝图草稿
里设想的 ``utter(surface, session_id, day_key, occasion)`` 简化签名——
composer 的真实挂点在 ``primal/providers/distilled.py::register_distilled``,
本文件的 ``SylannDistilledProvider`` 就是那个"真身"(疑义已记入交付报告)。
"""

from __future__ import annotations

from typing import Callable

from yelos.core.clock import Clock
from yelos.primal.lexicon.closure import band_of
from yelos.primal.providers import ProviderUnavailable
from yelos.primal.whitelist_gate import WhitelistGate

from ..packaging.verify import LoadState
from .budget import BudgetExceeded, run_with_budget
from .loader import ModelLoader
from .rerank import Reranker

# --- distill.trace.jsonl 记账(§5 数据契约)outcome 枚举 -------------------

OUTCOME_ABSENT = "skip:absent"
OUTCOME_HASH_MISMATCH = "skip:hash_mismatch"
OUTCOME_DEPS_MISSING = "skip:deps_missing"
OUTCOME_TIMEOUT = "skip:timeout"
OUTCOME_REJECTED_ALL = "rejected_all"
OUTCOME_OK = "ok"


class SylannDistilledProvider:
    """封版例外挂点的兑现:模型只提候选,闸决定出口(DA1/DA2/DA3)。"""

    provider_id = "distilled"

    def __init__(
        self,
        loader: ModelLoader,
        gate: WhitelistGate,
        reranker: Reranker,
        p_lookup: Callable[[str], float],
        epoch_lookup: Callable[[str], int],
        lang_lookup: Callable[[str], str],
        corpus_reader: Callable[[str, str], tuple[str, ...]],
        clock: Clock,
        *,
        budget_ms: int = 50,
        k_candidates: int = 8,
        trace_sink: Callable[[dict], None] | None = None,
    ) -> None:
        self._loader = loader
        self._gate = gate
        self._reranker = reranker
        self._p_lookup = p_lookup
        self._epoch_lookup = epoch_lookup
        self._lang_lookup = lang_lookup
        self._corpus_reader = corpus_reader
        self._clock = clock
        self._budget_ms = budget_ms
        self._k_candidates = k_candidates
        self._trace_sink = trace_sink or (lambda _row: None)
        self._logged_skip: set[str] = set()  # 每进程一次的缺席日志去重

    def _trace(self, occasion: str, outcome: str, **extra: object) -> None:
        row = {
            "ts": self._clock.now_ts(),
            "occasion": occasion,
            "outcome": outcome,
            **extra,
        }
        self._trace_sink(row)

    def _log_once(self, tag: str) -> None:
        if tag not in self._logged_skip:
            self._logged_skip.add(tag)
            # 干净缺席专测消费:composer 路由前一次 info,不重复噪音(§3.1)。

    def available(self, sid: str, lang: str) -> bool:  # noqa: ARG002
        """干净缺席探针:模型文件在 ∧ 哈希对 ∧(torch 档时)extras 可 import。"""
        state = self._loader.probe()
        if state != LoadState.READY:
            self._log_once(f"probe:{state.value}")
        return state == LoadState.READY

    def utter_canonical(
        self,
        surface: dict,
        sid: str,
        day_key: str,
        occasion: str,
        *,
        p: float,
        epoch: int,
        lang: str,
        context: dict | None = None,
    ) -> str:
        """PrimalProviderV2 协议(冻结,零改动实现)。内部流水见 4.1 决策表。"""
        state = self._loader.probe()
        if state == LoadState.ABSENT:  # R1
            self._trace(occasion, OUTCOME_ABSENT)
            raise ProviderUnavailable("distill: 模型缺席")
        if state == LoadState.HASH_MISMATCH:  # R2
            self._trace(occasion, OUTCOME_HASH_MISMATCH)
            raise ProviderUnavailable("distill: 模型哈希校验失败,拒载")
        if state == LoadState.DEPS_MISSING:  # R3
            self._trace(occasion, OUTCOME_DEPS_MISSING)
            raise ProviderUnavailable("distill: torch extras 未安装")

        try:
            backend = self._loader.get()
        except Exception as exc:  # noqa: BLE001  加载期失败一律回退(DA2)
            self._trace(occasion, OUTCOME_ABSENT)
            raise ProviderUnavailable(f"distill: 加载失败:{exc}") from exc

        context = context or {}
        corpus = context.get("corpus") or self._corpus_reader(sid, lang)
        seed = str(surface.get("seed", occasion))

        try:
            candidates, _elapsed_ms = run_with_budget(
                lambda: backend.generate(seed, self._k_candidates, self._budget_ms),
                self._clock,
                self._budget_ms,
            )
        except BudgetExceeded:  # R4
            self._trace(occasion, OUTCOME_TIMEOUT)
            raise ProviderUnavailable("distill: 推理超时")

        band = band_of(p)
        passed = [
            c
            for c in candidates
            if self._gate.check(c, occasion, lang, band, epoch, tuple(corpus)).ok
        ]
        if not passed:  # R5
            self._trace(occasion, OUTCOME_REJECTED_ALL, k=len(candidates), passed=0)
            raise ProviderUnavailable("distill: 全候选被闸拦截")

        rerank_key = f"{sid}|{day_key}|distill|{occasion}"  # DA3
        chosen = self._reranker.pick(passed, rerank_key)  # R6
        self._trace(occasion, OUTCOME_OK, k=len(candidates), passed=len(passed))
        return chosen


__all__ = ["SylannDistilledProvider"]
