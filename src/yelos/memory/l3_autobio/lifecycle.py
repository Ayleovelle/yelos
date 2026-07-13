"""lifecycle.py 在架构中的位置。

L3 主题生命周期状态机(全确定性,时间以 day_key 字符串入参,MEM-A6):

    nascent --(成员>=3 且跨>=2 日)--> active
    active --(连续 dormant_days 夜无 grow)--> dormant
    dormant --(新成员归入)--> active [事件 wake]
    dormant --(再 dead_days 夜无 wake 且 strength<dead_strength)--> dead
    任意态 --(merge 判定)--> 幼者 dead(墓碑),长者收编
    active --(split 判定)--> 母题保 id,子题 born

事件溯源(MEM-A6):任何现存主题的成员集可由 events 从 born 重放重建
(``replay_members``),与 lifecycle 维护的 ``members`` 字段独立可核对
(MEM-T3 成员守恒的测试锚点)。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path

from ..contracts import TopicEvent, TopicNode

DEFAULT_DORMANT_DAYS = 21
DEFAULT_DEAD_DAYS = 60
DEFAULT_DEAD_STRENGTH = 0.05
DEFAULT_NASCENT_MIN_MEMBERS = 3
DEFAULT_NASCENT_MIN_DAYS = 2


def days_between(day_a: str, day_b: str) -> int:
    """两个 ``YYYY-MM-DD`` day_key 的天数差(纯字符串解析,零 time.time())。"""
    return (date.fromisoformat(day_b) - date.fromisoformat(day_a)).days


def topic_id(sid_hash: str, gen: int, born_day: str, seq: int) -> str:
    raw = f"{sid_hash}|{gen}|{born_day}|{seq}"
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=6).hexdigest()


def born_topic(
    seq: int,
    sid_hash: str,
    gen: int,
    day_key: str,
    label_kw: list[str],
    centroid: list[float],
    member_ids: list[str],
) -> TopicNode:
    tid = topic_id(sid_hash, gen, day_key, seq)
    return TopicNode(
        id=tid,
        label_kw=label_kw[:4],
        centroid=centroid,
        born_day=day_key,
        last_active_day=day_key,
        state="nascent",
        strength=0.0,
        members=list(member_ids),
        events=[
            TopicEvent(
                kind="born", day_key=day_key, payload={"moved": list(member_ids)}
            )
        ],
    )


def grow(
    topic: TopicNode,
    entry_id: str,
    day_key: str,
    new_centroid: list[float],
    label_kw: list[str],
    *,
    min_members: int = DEFAULT_NASCENT_MIN_MEMBERS,
    min_days: int = DEFAULT_NASCENT_MIN_DAYS,
) -> TopicNode:
    """新成员归入既有主题;可能触发 nascent->active 或 dormant->active(wake)。"""
    if entry_id not in topic.members:
        topic.members.append(entry_id)
    topic.centroid = new_centroid
    topic.label_kw = label_kw[:4]
    topic.last_active_day = day_key
    topic.events.append(
        TopicEvent(kind="grow", day_key=day_key, payload={"entry_id": entry_id})
    )
    if topic.state == "dormant":
        topic.events.append(TopicEvent(kind="wake", day_key=day_key, payload={}))
        topic.state = "active"
    elif topic.state == "nascent":
        distinct_days = {
            ev.day_key for ev in topic.events if ev.kind in ("born", "grow")
        }
        if len(topic.members) >= min_members and len(distinct_days) >= min_days:
            topic.state = "active"
    return topic


def apply_dormancy(
    topic: TopicNode, today: str, *, dormant_days: int = DEFAULT_DORMANT_DAYS
) -> TopicNode:
    if topic.state == "active":
        d = days_between(topic.last_active_day, today)
        if d >= dormant_days:
            topic.events.append(TopicEvent(kind="dormant", day_key=today, payload={}))
            topic.state = "dormant"
    return topic


def apply_death(
    topic: TopicNode,
    today: str,
    *,
    dead_days: int = DEFAULT_DEAD_DAYS,
    dead_strength: float = DEFAULT_DEAD_STRENGTH,
) -> TopicNode:
    if topic.state == "dormant":
        d = days_between(topic.last_active_day, today)
        if d >= dead_days and topic.strength < dead_strength:
            topic.events.append(TopicEvent(kind="dead", day_key=today, payload={}))
            topic.state = "dead"
    return topic


def merge(elder: TopicNode, younger: TopicNode, today: str) -> TopicNode:
    """长者收编幼者(M12):elder id 不变,younger 墓碑 dead(可考古)。"""
    absorbed_members = list(younger.members)
    elder.events.append(
        TopicEvent(
            kind="merge_in",
            day_key=today,
            payload={"absorbed_id": younger.id, "absorbed_members": absorbed_members},
        )
    )
    for m in absorbed_members:
        if m not in elder.members:
            elder.members.append(m)
    if elder.state == "dormant":
        elder.events.append(TopicEvent(kind="wake", day_key=today, payload={}))
        elder.state = "active"
    younger.events.append(
        TopicEvent(kind="merge_out", day_key=today, payload={"absorbed_by": elder.id})
    )
    younger.state = "dead"
    return elder


def split(
    parent: TopicNode,
    moved_members: list[str],
    seq: int,
    sid_hash: str,
    gen: int,
    today: str,
    child_label_kw: list[str],
    child_centroid: list[float],
) -> TopicNode:
    """母题保 id(members 移除 moved),子题 born(携带 moved 供自身重放)。"""
    for m in moved_members:
        if m in parent.members:
            parent.members.remove(m)
    child_id = topic_id(sid_hash, gen, today, seq)
    child = TopicNode(
        id=child_id,
        label_kw=child_label_kw[:4],
        centroid=child_centroid,
        born_day=today,
        last_active_day=today,
        state="nascent",
        strength=0.0,
        members=list(moved_members),
        events=[
            TopicEvent(
                kind="born",
                day_key=today,
                payload={"split_from": parent.id, "moved": list(moved_members)},
            )
        ],
    )
    parent.events.append(
        TopicEvent(
            kind="split",
            day_key=today,
            payload={"child_id": child_id, "moved": list(moved_members)},
        )
    )
    return child


def replay_members(events: list[TopicEvent]) -> list[str]:
    """由事件流从 born 重放重建成员集(MEM-A6/T3 的测试锚点)。"""
    members: list[str] = []
    for ev in events:
        if ev.kind == "born":
            for m in ev.payload.get("moved", []):
                if m not in members:
                    members.append(m)
            eid = ev.payload.get("entry_id")
            if eid and eid not in members:
                members.append(eid)
        elif ev.kind == "grow":
            eid = ev.payload.get("entry_id")
            if eid and eid not in members:
                members.append(eid)
        elif ev.kind == "merge_in":
            for m in ev.payload.get("absorbed_members", []):
                if m not in members:
                    members.append(m)
        elif ev.kind == "split":
            for m in ev.payload.get("moved", []):
                if m in members:
                    members.remove(m)
    return members


# --- TopicStore:L3 全量持久化(原子写)------------------------------------


class TopicStore:
    def __init__(self, root: Path, sid_hash: str, gen: int) -> None:
        self._path = Path(root) / "memory" / "l3" / f"{sid_hash}.g{gen}.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._topics: dict[str, TopicNode] = {}
        self._order: list[str] = []
        self._seq = 0
        self.merge_streak: dict[str, int] = {}
        self.load()

    def load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self._topics = {}
        self._order = []
        for raw in data.get("topics", []):
            t = TopicNode.from_dict(raw)
            self._topics[t.id] = t
            self._order.append(t.id)
        self._seq = int(data.get("seq", 0))
        self.merge_streak = {
            str(k): int(v) for k, v in (data.get("merge_streak") or {}).items()
        }

    def save(self) -> None:
        tmp = self._path.with_name(self._path.name + ".tmp")
        payload = {
            "topics": [self._topics[i].to_dict() for i in self._order],
            "seq": self._seq,
            "merge_streak": self.merge_streak,
        }
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, self._path)

    def all(self) -> list[TopicNode]:
        return [self._topics[i] for i in self._order]

    def get(self, tid: str) -> TopicNode | None:
        return self._topics.get(tid)

    def add(self, topic: TopicNode) -> None:
        if topic.id not in self._topics:
            self._order.append(topic.id)
        self._topics[topic.id] = topic

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def active_topics(self) -> list[TopicNode]:
        return [t for t in self.all() if t.state in ("active", "nascent")]

    def count(self) -> int:
        return len(self._order)
