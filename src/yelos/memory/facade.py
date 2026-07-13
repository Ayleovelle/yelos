"""facade.py 在架构中的位置。

MemoryFacade 是 session/server 能触到的**唯一** memory 符号(§3.8)。组合根:
装配 L1/L2/L3/vocab 索引/retention 族/scorer/summarizer/privacy,全部依赖
注入,无全局态。子模块之间只经 contracts 类型耦合,facade 是唯一的编排点。

时间(now_ts/day_key/night_key)全部由调用方传入;facade 自身不触碰
time.time()/datetime.now()。day_key→epoch 边界的转换是纯字符串/日历算术
(_day_key_end_ts),不读系统时钟。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable, Iterator

from .contracts import (
    BaselineContext,
    ConsolidationReport,
    ContinuityFlags,
    EpisodeEvent,
    JobBudget,
    MemoryConfig,
    RecallQuery,
    RecallResult,
    ThemeDigest,
)
from .consolidation.jobs import NightJob
from .forgetting.retention import get_family
from .l1_episodic.reader import sid_hash
from .l1_episodic.store import EpisodeStore
from .l2_semantic.entries import L2Store, VocabIndexStore
from .l2_semantic.summarize import Summarizer, build_summarizer
from .l3_autobio.lifecycle import TopicStore
from .privacy.lifecycle import PrivacyLifecycle
from .recall.scorers import get_scorer
from .recall.service import (
    apply_rehearse,
    build_affect_recall_response,
    build_baseline_context,
    build_continuity_flags,
    build_theme_digest,
    recall_l2,
    similarity_backend_for,
)
from .viz.export import export_all

_EPOCH_ORDINAL = date(1970, 1, 1).toordinal()


def _day_key_end_ts(day_key: str) -> float:
    """day_key(``YYYY-MM-DD``)当日最后一秒的 epoch 秒;纯日历算术,零系统时钟。"""
    d = date.fromisoformat(day_key)
    return float((d.toordinal() + 1 - _EPOCH_ORDINAL) * 86400 - 1)


class MemoryFacade:
    def __init__(
        self,
        root: Path,
        cfg: MemoryConfig | None = None,
        *,
        assessor_call: Callable[[list[EpisodeEvent], list[str]], str] | None = None,
    ) -> None:
        self._root = Path(root)
        self._cfg = cfg or MemoryConfig()
        self._privacy = PrivacyLifecycle(self._root)
        self._summarizer: Summarizer = build_summarizer(
            "assessor" if self._cfg.memory_assessor_summary else "template",
            assessor_call=assessor_call,
        )
        self._l1_cache: dict[tuple[str, int], EpisodeStore] = {}
        self._l2_cache: dict[tuple[str, int], L2Store] = {}
        self._idx_cache: dict[tuple[str, int], VocabIndexStore] = {}
        self._l3_cache: dict[tuple[str, int], TopicStore] = {}

    # -- 内部缓存装配(懒加载,§2.2)-----------------------------------------

    def _key(self, sid: str, gen: int) -> tuple[str, int]:
        return (sid_hash(sid), gen)

    def _l1(self, sid: str, gen: int) -> EpisodeStore:
        key = self._key(sid, gen)
        store = self._l1_cache.get(key)
        if store is None:
            store = EpisodeStore(
                self._root, key[0], gen, segment_max=self._cfg.memory_l1_segment_max
            )
            self._l1_cache[key] = store
        return store

    def _l2(self, sid: str, gen: int) -> L2Store:
        key = self._key(sid, gen)
        store = self._l2_cache.get(key)
        if store is None:
            store = L2Store(self._root, key[0], gen)
            self._l2_cache[key] = store
        return store

    def _idx(self, sid: str, gen: int) -> VocabIndexStore:
        key = self._key(sid, gen)
        store = self._idx_cache.get(key)
        if store is None:
            store = VocabIndexStore(self._root, key[0], gen)
            self._idx_cache[key] = store
        return store

    def _l3(self, sid: str, gen: int) -> TopicStore:
        key = self._key(sid, gen)
        store = self._l3_cache.get(key)
        if store is None:
            store = TopicStore(self._root, key[0], gen)
            self._l3_cache[key] = store
        return store

    def _invalidate(self, sid: str, gen: int, *, drop_l1: bool = False) -> None:
        key = self._key(sid, gen)
        self._l2_cache.pop(key, None)
        self._idx_cache.pop(key, None)
        self._l3_cache.pop(key, None)
        if drop_l1:
            self._l1_cache.pop(key, None)

    # -- 写面(WM1-5,session 层 per-session lock 内调)------------------

    def observe(self, sid: str, gen: int, ev: EpisodeEvent) -> int:
        if not self._cfg.memory_enabled:
            return -1
        return self._l1(sid, gen).append(ev)

    # -- 读面(只读)---------------------------------------------------------

    def recall(
        self, sid: str, gen: int, q: RecallQuery, *, rehearse: bool = True
    ) -> RecallResult:
        if not self._cfg.memory_enabled:
            return RecallResult(hits=(), scorer="disabled", deterministic_key="")
        l2 = self._l2(sid, gen)
        idx = self._idx(sid, gen)
        entries = l2.all()
        scorer = get_scorer(self._cfg.memory_recall_scorer)
        backend = similarity_backend_for(entries, self._cfg.memory_similarity_fusion)
        fam = get_family(self._cfg.memory_decay_family)
        result = recall_l2(
            q,
            entries,
            scorer=scorer,
            backend=backend,
            fam=fam,
            word_vecs=idx.word_vecs,
            idf=idx.idf,
        )
        if rehearse and result.hits:
            by_id = {e.id: e for e in entries}
            apply_rehearse(result.hits, by_id, q.now_ts, fam)
            l2.save()
        return result

    def theme_digest(self, sid: str, gen: int, day_key: str) -> ThemeDigest:
        l1 = self._l1(sid, gen)
        l2 = self._l2(sid, gen)
        l3 = self._l3(sid, gen)
        entries_by_id = {e.id: e for e in l2.all()}
        day_events = l1.read_day(day_key)
        return build_theme_digest(day_key, l3.all(), entries_by_id, day_events)

    def baseline_context(self, sid: str, gen: int, day_key: str) -> BaselineContext:
        l1 = self._l1(sid, gen)
        l2 = self._l2(sid, gen)
        events = list(l1.iter_all())
        now_ts = _day_key_end_ts(day_key)
        return build_baseline_context(
            last_user_ts=l1.last_ts("user_turn"),
            active_day_count=len(l1.day_keys()),
            l2_count=l2.count(),
            now_ts=now_ts,
            week_events=events,
            month_events=events,
        )

    def continuity_flags(self, sid: str, gen: int, now_ts: float) -> ContinuityFlags:
        l1 = self._l1(sid, gen)
        l2 = self._l2(sid, gen)
        l3 = self._l3(sid, gen)
        events = list(l1.iter_all())
        baseline = build_baseline_context(
            last_user_ts=l1.last_ts("user_turn"),
            active_day_count=len(l1.day_keys()),
            l2_count=l2.count(),
            now_ts=now_ts,
            week_events=events,
            month_events=events,
        )
        return build_continuity_flags(
            baseline,
            l3.all(),
            reunion_days=self._cfg.memory_reunion_days,
            min_history_days=self._cfg.memory_min_history_days,
            long_bond_familiarity=self._cfg.memory_long_bond_familiarity,
        )

    def corpus_view(self, sid: str, gen: int) -> Iterator[dict]:
        l1 = self._l1(sid, gen)
        return self._privacy.corpus_view(l1)

    def stats(self, sid: str, gen: int) -> dict:
        l1 = self._l1(sid, gen)
        l2 = self._l2(sid, gen)
        l3 = self._l3(sid, gen)
        sid_h, _gen = self._key(sid, gen)
        journal_dir = self._root / "memory" / "journal"
        nights: list[str] = []
        if journal_dir.is_dir():
            prefix = f"{sid_h}.g{gen}."
            for p in journal_dir.glob(f"{prefix}*.json"):
                stem = p.name[len(prefix) : -len(".json")]
                if stem != "cursor":
                    nights.append(stem)
        return {
            "l1_count": l1.count(),
            "l2_count": l2.count(),
            "l3_count": l3.count(),
            "active_topics": len(l3.active_topics()),
            "last_consolidation_night": max(nights) if nights else "",
        }

    # -- 作业面(心跳夜窗调,WM6)--------------------------------------------

    def consolidate(
        self, sid: str, gen: int, *, night_key: str, now_ts: float, budget: JobBudget
    ) -> ConsolidationReport:
        l1 = self._l1(sid, gen)
        sid_h, _gen = self._key(sid, gen)
        job = NightJob(self._root, sid_h, gen, self._cfg, summarizer=self._summarizer)
        report = job.run(l1, night_key=night_key, now_ts=now_ts, budget=budget)
        # NightJob 直接读写磁盘上的 L2/L3/index,facade 缓存须失效(R5 教训)
        self._invalidate(sid, gen)
        return report

    def export_viz(self, sid: str, gen: int, *, now_ts: float | None = None) -> None:
        l1 = self._l1(sid, gen)
        l2 = self._l2(sid, gen)
        l3 = self._l3(sid, gen)
        fam = get_family(self._cfg.memory_decay_family)
        ts = now_ts if now_ts is not None else l1.latest_ts()
        sid_h, _gen = self._key(sid, gen)
        export_all(
            self._root,
            sid_h,
            gen,
            l2.all(),
            l3.all(),
            ts,
            fam,
            self._cfg.memory_decay_family,
        )

    # -- 生命周期面(主权动作转发,WM11)---------------------------------------

    def reset(self, sid: str, gen: int, *, keep_l1_archive: bool = True) -> None:
        sid_h, _gen = self._key(sid, gen)
        self._privacy.reset(sid_h, gen, keep_l1_archive=keep_l1_archive)
        self._invalidate(sid, gen, drop_l1=not keep_l1_archive)

    def seal_export(self, sid: str, gen: int, *, export_raw: bool = False) -> dict:
        sid_h, _gen = self._key(sid, gen)
        l1 = self._l1(sid, gen) if export_raw else None
        return self._privacy.seal_export(sid_h, gen, export_raw=export_raw, l1_store=l1)

    # -- affect_recall 工具面逻辑(§5.6;server.py 注册留给后续集成波)---------

    def affect_recall_view(
        self,
        sid: str,
        gen: int,
        *,
        query: str = "",
        k: int = 3,
        now_ts: float,
        day_key: str,
        mode: str = "steward",
        sealed: bool = False,
        bound: bool = True,
        paused: bool = False,
    ) -> dict:
        """§5.6 决策表的完整装配:memory_enabled 门控恒先行(工具集不随配置变)。"""
        if not self._cfg.memory_enabled:
            return {"disabled": True}
        if sealed:
            return {"sealed": True}
        if not bound:
            return build_affect_recall_response(
                memory_enabled=True,
                sealed=False,
                bound=False,
                paused=paused,
                mode=mode,
                hits=(),
                themes_active=(),
                continuity=ContinuityFlags(
                    reunion=False, long_bond=False, active_themes=0
                ),
                days_since_last_contact=0,
            )

        l3 = self._l3(sid, gen)
        effective_scorer = (
            "linear" if mode == "steward" else self._cfg.memory_recall_scorer
        )
        q = RecallQuery(
            text=query, now_ts=now_ts, day_key=day_key, k=max(0, min(10, k))
        )
        l2 = self._l2(sid, gen)
        idx = self._idx(sid, gen)
        entries = l2.all()
        scorer = get_scorer(effective_scorer)
        backend = similarity_backend_for(entries, self._cfg.memory_similarity_fusion)
        fam = get_family(self._cfg.memory_decay_family)
        result = recall_l2(
            q,
            entries,
            scorer=scorer,
            backend=backend,
            fam=fam,
            word_vecs=idx.word_vecs,
            idf=idx.idf,
        )
        by_id = {e.id: e for e in entries}
        apply_rehearse(result.hits, by_id, now_ts, fam)
        l2.save()

        baseline = self.baseline_context(sid, gen, day_key)
        continuity = build_continuity_flags(
            baseline,
            l3.all(),
            reunion_days=self._cfg.memory_reunion_days,
            min_history_days=self._cfg.memory_min_history_days,
            long_bond_familiarity=self._cfg.memory_long_bond_familiarity,
        )
        themes_active = tuple(
            "".join(t.label_kw[:2]) for t in l3.all() if t.state == "active"
        )
        topics_by_id = {t.id: t for t in l3.all()}
        return build_affect_recall_response(
            memory_enabled=True,
            sealed=False,
            bound=True,
            paused=paused,
            mode=mode,
            hits=result.hits,
            themes_active=themes_active,
            continuity=continuity,
            days_since_last_contact=baseline.days_since_last_contact,
            topics_by_id=topics_by_id,
        )
