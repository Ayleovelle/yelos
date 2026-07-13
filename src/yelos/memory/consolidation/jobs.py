"""jobs.py 在架构中的位置。

夜窗巩固管线的编排正身(NightJob):l1_day_seal → l2_summarize →
vocab_update → vec_refit → l3_lifecycle → forgetting_sweep → l2_capacity →
viz_export。journal 守卫幂等/续跑(MEM-A8);零 LLM 红线(assessor 显式开启
才外呼,本文件本身零外呼)。

facade.py 是本文件的唯一调用方;NightJob 不知道 session/server 的存在。
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Callable

from ..contracts import (
    ConsolidationReport,
    EpisodeEvent,
    JobBudget,
    MemoryConfig,
    SemanticEntry,
)
from ..forgetting.retention import RetentionFamily, get_family
from ..l1_episodic.store import EpisodeStore
from ..l2_semantic.entries import (
    L2Store,
    VocabIndexStore,
    build_semantic_entry,
    extract_keywords,
)
from ..l2_semantic.linalg_lite import embed_doc, rsvd
from ..l2_semantic.ppmi import cooccurrence, ppmi_weight, row_totals
from ..l2_semantic.summarize import Summarizer
from ..l2_semantic.tokenizer import tokenize
from ..l3_autobio.cluster import (
    assign_topic,
    compute_centroid,
    connected_components,
    merge_candidates,
    split_candidates,
)
from ..l3_autobio.lifecycle import (
    TopicStore,
    apply_death,
    apply_dormancy,
    born_topic,
    days_between,
    grow,
    merge,
    split,
)
from ..viz.export import export_all
from .schedule import NIGHT_STEPS, should_refit

_CONVO_KINDS = frozenset({"user_turn", "agent_turn", "her_word", "swallowed"})


def _bucket(kind: str) -> str:
    return "convo" if kind in _CONVO_KINDS else kind


# --- 续跑凭据:journal(每夜一份)+ cursor(跨夜持久)-----------------------


class JournalStore:
    """夜窗作业日志:done 步列表 + 跨步传值(MEM-A8 幂等/续跑凭据)。"""

    def __init__(self, root: Path, sid_hash: str, gen: int, night_key: str) -> None:
        self._path = (
            Path(root) / "memory" / "journal" / f"{sid_hash}.g{gen}.{night_key}.json"
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.done: list[str] = []
        self.elapsed: dict[str, float] = {}
        self.data: dict = {}
        self.load()

    def load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.done = list(raw.get("done", []))
        self.elapsed = dict(raw.get("elapsed", {}))
        self.data = dict(raw.get("data", {}))

    def save(self) -> None:
        tmp = self._path.with_name(self._path.name + ".tmp")
        payload = {"done": self.done, "elapsed": self.elapsed, "data": self.data}
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, self._path)

    def is_done(self, step: str) -> bool:
        return step in self.done

    def mark_done(self, step: str, elapsed_s: float, extra: dict | None = None) -> None:
        if step not in self.done:
            self.done.append(step)
        self.elapsed[step] = elapsed_s
        if extra:
            self.data.update(extra)
        self.save()

    def mark_skipped(self, step: str) -> None:
        self.data.setdefault("skipped", [])
        if step not in self.data["skipped"]:
            self.data["skipped"].append(step)
        self.save()

    def skipped_steps(self) -> tuple[str, ...]:
        return tuple(self.data.get("skipped", []))


class CursorStore:
    """跨夜持久的 L1 处理进度(processed_upto,不属于任何单夜 journal)。"""

    def __init__(self, root: Path, sid_hash: str, gen: int) -> None:
        self._path = (
            Path(root) / "memory" / "journal" / f"{sid_hash}.g{gen}.cursor.json"
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.processed_upto: int = -1
        self.load()

    def load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.processed_upto = int(raw.get("processed_upto", -1))

    def save(self) -> None:
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(
            json.dumps({"processed_upto": self.processed_upto}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)


# --- l2_summarize:同日相邻 8 事件或跨 kind 边界切窗(§3.6)------------------


def segment_events(
    events: list[tuple[int, EpisodeEvent]], max_window: int = 8
) -> list[list[tuple[int, EpisodeEvent]]]:
    windows: list[list[tuple[int, EpisodeEvent]]] = []
    cur: list[tuple[int, EpisodeEvent]] = []
    cur_day: str | None = None
    cur_bucket: str | None = None
    for seq, ev in events:
        b = _bucket(ev.kind)
        if cur and (ev.day_key != cur_day or b != cur_bucket or len(cur) >= max_window):
            windows.append(cur)
            cur = []
        cur.append((seq, ev))
        cur_day = ev.day_key
        cur_bucket = b
    if cur:
        windows.append(cur)
    return windows


def _label_from_members(members: list[SemanticEntry]) -> list[str]:
    all_kw = [kw for e in members for kw in e.keywords]
    return extract_keywords(all_kw, top_n=4)


def _tokens_for_span(l1: EpisodeStore, span: tuple[int, int]) -> list[str]:
    events = l1.read_span(span[0], span[1])
    tokens: list[str] = []
    for ev in events:
        text = ev.text or ev.occasion
        if text:
            tokens.extend(tokenize(text, lang="zh"))
    return tokens


class NightJob:
    """夜窗巩固管线;facade.consolidate 的唯一转发目标。"""

    def __init__(
        self,
        root: Path,
        sid_hash: str,
        gen: int,
        cfg: MemoryConfig,
        *,
        summarizer: Summarizer,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._root = Path(root)
        self._sid_hash = sid_hash
        self._gen = gen
        self._cfg = cfg
        self._summarizer = summarizer
        self._clock = clock

    def run(
        self,
        l1: EpisodeStore,
        *,
        night_key: str,
        now_ts: float,
        budget: JobBudget,
    ) -> ConsolidationReport:
        journal = JournalStore(self._root, self._sid_hash, self._gen, night_key)
        cursor = CursorStore(self._root, self._sid_hash, self._gen)
        l2 = L2Store(self._root, self._sid_hash, self._gen)
        idx = VocabIndexStore(self._root, self._sid_hash, self._gen)
        topics = TopicStore(self._root, self._sid_hash, self._gen)
        fam = get_family(self._cfg.memory_decay_family)

        resumed = bool(journal.done)
        elapsed_by_step: dict[str, float] = dict(journal.elapsed)
        steps_skipped: list[str] = list(journal.skipped_steps())

        for step in NIGHT_STEPS:
            if journal.is_done(step):
                continue
            t0 = self._clock()
            if step == "l1_day_seal":
                seal_upto = l1.count() - 1
                journal.mark_done(step, self._clock() - t0, {"seal_upto": seal_upto})
            elif step == "l2_summarize":
                self._step_l2_summarize(l1, l2, journal, cursor, night_key, now_ts)
                journal.mark_done(step, self._clock() - t0)
            elif step == "vocab_update":
                self._step_vocab_update(l1, l2, idx)
                journal.mark_done(step, self._clock() - t0)
            elif step == "vec_refit":
                decision = self._step_vec_refit(l1, l2, idx, night_key, budget, t0)
                if decision == "budget_exceeded":
                    steps_skipped.append(step)
                    journal.mark_skipped(step)
                else:
                    journal.mark_done(
                        step, self._clock() - t0, {"refit_decision": decision}
                    )
            elif step == "l3_lifecycle":
                self._step_l3_lifecycle(l2, topics, night_key)
                journal.mark_done(step, self._clock() - t0)
            elif step == "forgetting_sweep":
                self._step_forgetting_sweep(l2, topics, fam, now_ts)
                journal.mark_done(step, self._clock() - t0)
            elif step == "l2_capacity":
                self._step_l2_capacity(l2, topics, fam, now_ts)
                journal.mark_done(step, self._clock() - t0)
            elif step == "viz_export":
                export_all(
                    self._root,
                    self._sid_hash,
                    self._gen,
                    l2.all(),
                    topics.all(),
                    now_ts,
                    fam,
                    self._cfg.memory_decay_family,
                )
                journal.mark_done(step, self._clock() - t0)
            elapsed_by_step[step] = journal.elapsed.get(step, self._clock() - t0)

        return ConsolidationReport(
            night_key=night_key,
            steps_done=tuple(journal.done),
            steps_skipped=tuple(dict.fromkeys(steps_skipped)),
            resumed=resumed,
            elapsed_by_step=elapsed_by_step,
        )

    # -- l2_summarize --------------------------------------------------

    def _step_l2_summarize(
        self,
        l1: EpisodeStore,
        l2: L2Store,
        journal: JournalStore,
        cursor: CursorStore,
        night_key: str,
        now_ts: float,
    ) -> None:
        seal_upto = int(journal.data.get("seal_upto", l1.count() - 1))
        start = cursor.processed_upto + 1
        if start > seal_upto:
            return
        events = [(s, e) for s, e in l1.iter_all() if start <= s <= seal_upto]
        windows = segment_events(events)
        for window in windows:
            span = (window[0][0], window[-1][0])
            evs = [e for _s, e in window]
            entry = build_semantic_entry(
                self._sid_hash,
                self._gen,
                span,
                evs,
                summarizer=self._summarizer,
                now_ts=now_ts,
            )
            if entry is not None:
                l2.add(entry)
        l2.save()
        cursor.processed_upto = seal_upto
        cursor.save()

    # -- vocab_update ----------------------------------------------------

    def _step_vocab_update(
        self, l1: EpisodeStore, l2: L2Store, idx: VocabIndexStore
    ) -> None:
        entries = l2.all()
        docs = [_tokens_for_span(l1, e.span) for e in entries]
        idx.vocab.fit_update(docs)
        idx.save()

    # -- vec_refit ---------------------------------------------------------

    def _step_vec_refit(
        self,
        l1: EpisodeStore,
        l2: L2Store,
        idx: VocabIndexStore,
        night_key: str,
        budget: JobBudget,
        t0: float,
    ) -> str:
        entries = l2.all()
        if len(entries) < 30:
            return "skip"
        docs_by_id = {e.id: _tokens_for_span(l1, e.span) for e in entries}
        prev_tokens = idx.vocab.current_tokens()
        new_ratio = idx.vocab.new_token_ratio(prev_tokens) if prev_tokens else 1.0
        nights_since = (
            days_between(idx.last_refit_night, night_key)
            if idx.last_refit_night
            else 9999
        )
        decision = should_refit(
            has_basis=idx.has_basis(),
            l2_count=len(entries),
            new_token_ratio=new_ratio,
            nights_since_refit=nights_since,
        )
        if decision == "skip":
            return "skip"

        if decision == "refit":
            if self._clock() - t0 > budget.per_step_seconds:
                return "budget_exceeded"
            docs_encoded = [idx.vocab.encode(toks) for toks in docs_by_id.values()]
            vocab_size = idx.vocab.size()
            cooc = cooccurrence(docs_encoded, vocab_size, window=4)
            row_tot, total = row_totals(cooc)
            ppmi = ppmi_weight(cooc, row_tot, total)
            if self._clock() - t0 > budget.per_step_seconds:
                return "budget_exceeded"
            seed_key = f"{self._sid_hash}|{self._gen}|vec"
            u, sigma = rsvd(
                ppmi,
                (vocab_size, vocab_size),
                self._cfg.memory_vec_dim,
                seed_key=seed_key,
            )
            word_vecs: dict[str, list[float]] = {}
            for tid in range(vocab_size):
                tok = idx.vocab.token(tid)
                row = u[tid] if tid < len(u) else []
                if row and sigma:
                    word_vecs[tok] = [
                        row[c] * (sigma[c] ** 0.5) for c in range(len(sigma))
                    ]
            idx.word_vecs = word_vecs
            n_docs = max(1, len(docs_by_id))
            df: dict[str, int] = {}
            for toks in docs_by_id.values():
                for t in set(toks):
                    df[t] = df.get(t, 0) + 1
            idx.idf = {t: math.log((n_docs + 1) / (c + 1)) + 1.0 for t, c in df.items()}
            idx.last_refit_night = night_key
            idx.refit_count += 1

        for e in entries:
            toks = docs_by_id.get(e.id, [])
            e.vec = embed_doc(toks, idx.word_vecs, idx.idf) if idx.word_vecs else []
            l2.add(e)
        l2.save()
        idx.save()
        return decision

    # -- l3_lifecycle --------------------------------------------------

    def _step_l3_lifecycle(
        self, l2: L2Store, topics: TopicStore, night_key: str
    ) -> None:
        cfg = self._cfg
        entries = l2.all()
        entries_by_id = {e.id: e for e in entries}
        all_topics = topics.all()

        unassigned: list[SemanticEntry] = []
        for e in entries:
            if e.topic_id and topics.get(e.topic_id) is not None:
                continue
            if not e.vec:
                continue
            tid = assign_topic(e, all_topics, cfg.memory_theta_assign)
            if tid:
                t = topics.get(tid)
                member_entries = [
                    entries_by_id[m] for m in t.members if m in entries_by_id
                ] + [e]
                new_centroid = compute_centroid(
                    [m.vec for m in member_entries if m.vec]
                )
                label_kw = _label_from_members(member_entries)
                grow(t, e.id, night_key, new_centroid, label_kw)
                e.topic_id = t.id
                topics.add(t)
            else:
                unassigned.append(e)

        if unassigned:
            for group in connected_components(unassigned, cfg.memory_theta_assign):
                seq = topics.next_seq()
                centroid = compute_centroid([e.vec for e in group if e.vec])
                label_kw = _label_from_members(group)
                node = born_topic(
                    seq,
                    self._sid_hash,
                    self._gen,
                    night_key,
                    label_kw,
                    centroid,
                    [e.id for e in group],
                )
                topics.add(node)
                for e in group:
                    e.topic_id = node.id

        fires, new_streak = merge_candidates(
            topics.all(), cfg.memory_theta_merge, topics.merge_streak
        )
        topics.merge_streak = new_streak
        for elder_id, younger_id in fires:
            elder = topics.get(elder_id)
            younger = topics.get(younger_id)
            if elder is None or younger is None:
                continue
            merge(elder, younger, night_key)
            for eid, entry in entries_by_id.items():
                if entry.topic_id == younger_id:
                    entry.topic_id = elder_id
            topics.add(elder)
            topics.add(younger)

        for t in list(topics.all()):
            if t.state != "active":
                continue
            member_entries = [entries_by_id[m] for m in t.members if m in entries_by_id]
            blocks = split_candidates(
                t, member_entries, cfg.memory_theta_split, cfg.memory_theta_assign
            )
            if not blocks:
                continue
            for block in blocks[1:]:
                seq = topics.next_seq()
                child_centroid = compute_centroid(
                    [entries_by_id[eid].vec for eid in block if eid in entries_by_id]
                )
                child_label = _label_from_members(
                    [entries_by_id[eid] for eid in block if eid in entries_by_id]
                )
                child = split(
                    t,
                    block,
                    seq,
                    self._sid_hash,
                    self._gen,
                    night_key,
                    child_label,
                    child_centroid,
                )
                topics.add(child)
                for eid in block:
                    if eid in entries_by_id:
                        entries_by_id[eid].topic_id = child.id
            topics.add(t)

        for t in topics.all():
            apply_dormancy(t, night_key)
            apply_death(t, night_key)
            topics.add(t)

        topics.save()
        for e in entries:
            l2.add(e)
        l2.save()

    # -- forgetting_sweep --------------------------------------------------

    def _step_forgetting_sweep(
        self, l2: L2Store, topics: TopicStore, fam: RetentionFamily, now_ts: float
    ) -> None:
        entries_by_id = {e.id: e for e in l2.all()}
        for t in topics.all():
            total = 0.0
            for m in t.members:
                e = entries_by_id.get(m)
                if e is None:
                    continue
                total += fam.R(max(0.0, now_ts - e.created_ts), e.S)
            t.strength = total
            topics.add(t)
        topics.save()

    # -- l2_capacity(护栏 §2.3)--------------------------------------------

    def _step_l2_capacity(
        self, l2: L2Store, topics: TopicStore, fam: RetentionFamily, now_ts: float
    ) -> None:
        cap = self._cfg.memory_l2_cap
        count = l2.count()
        if count <= cap:
            return
        excess = count - cap
        ranked = sorted(
            l2.all(), key=lambda e: fam.R(max(0.0, now_ts - e.created_ts), e.S)
        )
        for e in ranked[:excess]:
            if e.topic_id:
                t = topics.get(e.topic_id)
                if t is not None and e.id in t.members:
                    t.members.remove(e.id)
                    topics.add(t)
            l2.remove(e.id)
        l2.save()
        topics.save()
