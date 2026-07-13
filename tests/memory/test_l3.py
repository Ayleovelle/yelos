"""test_l3.py:L3 主题生命周期状态机(性质 + 集成)。

锁:状态机全转移枚举;事件重放重建(MEM-A6);成员守恒(MEM-T3);合成
跨月剧本(90 日跨多次 dormant/wake 仍同 id);merge 保长者 id;split moved
正确。
"""

from __future__ import annotations

from yelos.memory.l3_autobio.cluster import compute_centroid
from yelos.memory.l3_autobio.lifecycle import (
    TopicStore,
    apply_death,
    apply_dormancy,
    born_topic,
    days_between,
    grow,
    merge,
    replay_members,
    split,
)


def test_days_between_basic():
    assert days_between("2024-01-01", "2024-01-01") == 0
    assert days_between("2024-01-01", "2024-01-31") == 30
    assert days_between("2024-01-31", "2024-02-01") == 1


def test_nascent_to_active_requires_members_and_days():
    t = born_topic(1, "sid", 0, "2024-01-01", ["猫"], [1.0, 0.0], ["e0"])
    assert t.state == "nascent"
    grow(t, "e1", "2024-01-01", [1.0, 0.0], ["猫"])
    assert t.state == "nascent"  # 只 2 个成员,未满足 >=3
    grow(t, "e2", "2024-01-02", [1.0, 0.0], ["猫"])  # 第 3 个成员且跨第 2 日
    assert t.state == "active"


def test_active_to_dormant_after_21_days_no_grow():
    t = born_topic(1, "sid", 0, "2024-01-01", ["猫"], [1.0, 0.0], ["e0", "e1", "e2"])
    t.state = "active"
    t.last_active_day = "2024-01-01"
    apply_dormancy(t, "2024-01-10")  # 未满 21 天
    assert t.state == "active"
    apply_dormancy(t, "2024-01-22")  # 满 21 天
    assert t.state == "dormant"
    kinds = [e.kind for e in t.events]
    assert "dormant" in kinds


def test_dormant_to_active_via_grow_emits_wake():
    t = born_topic(1, "sid", 0, "2024-01-01", ["猫"], [1.0, 0.0], ["e0", "e1", "e2"])
    t.state = "dormant"
    t.last_active_day = "2024-01-01"
    grow(t, "e3", "2024-03-01", [1.0, 0.0], ["猫"])
    assert t.state == "active"
    assert any(e.kind == "wake" for e in t.events)


def test_dormant_to_dead_after_60_days_no_wake_and_low_strength():
    t = born_topic(1, "sid", 0, "2024-01-01", ["猫"], [1.0, 0.0], ["e0", "e1", "e2"])
    t.state = "dormant"
    t.last_active_day = "2024-01-01"
    t.strength = 0.01
    apply_death(t, "2024-02-01")  # 未满 60 天
    assert t.state == "dormant"
    apply_death(t, "2024-03-15")  # 满 60 天 + strength 低
    assert t.state == "dead"


def test_dead_not_triggered_if_strength_high():
    t = born_topic(1, "sid", 0, "2024-01-01", ["猫"], [1.0, 0.0], ["e0", "e1", "e2"])
    t.state = "dormant"
    t.last_active_day = "2024-01-01"
    t.strength = 0.5  # 仍有余温
    apply_death(t, "2024-06-01")
    assert t.state == "dormant"  # strength 不够低,不死


def test_event_replay_reconstructs_members_after_grow():
    t = born_topic(1, "sid", 0, "2024-01-01", ["猫"], [1.0, 0.0], ["e0"])
    grow(t, "e1", "2024-01-02", [1.0, 0.0], ["猫"])
    grow(t, "e2", "2024-01-03", [1.0, 0.0], ["猫"])
    replayed = replay_members(t.events)
    assert set(replayed) == set(t.members)


def test_merge_keeps_elder_id_and_conserves_members():
    elder = born_topic(1, "sid", 0, "2024-01-01", ["猫"], [1.0, 0.0], ["e0", "e1"])
    younger = born_topic(2, "sid", 0, "2024-01-05", ["猫"], [1.0, 0.0], ["e2", "e3"])
    union_before = set(elder.members) | set(younger.members)

    merged_elder = merge(elder, younger, "2024-01-10")

    assert merged_elder.id == elder.id  # elder id 不变(M12)
    assert younger.state == "dead"  # 幼者墓碑
    assert set(merged_elder.members) == union_before  # 成员并集守恒(MEM-T3)
    # 事件重放也应能独立重建出并集(MEM-A6)
    assert set(replay_members(merged_elder.events)) == union_before


def test_split_moved_members_correct_and_conserves_union():
    parent = born_topic(
        1,
        "sid",
        0,
        "2024-01-01",
        ["猫"],
        [1.0, 0.0],
        ["e0", "e1", "e2", "e3", "e4", "e5"],
    )
    original_members = set(parent.members)
    moved = ["e3", "e4", "e5"]

    child = split(parent, moved, 2, "sid", 0, "2024-02-01", ["猫崽"], [0.0, 1.0])

    assert set(child.members) == set(moved)
    assert set(parent.members) == original_members - set(moved)
    # 并集守恒(MEM-T3):split 前后成员并集不变
    assert set(parent.members) | set(child.members) == original_members
    # child 自身事件流可独立重放出其初始成员(MEM-A6)
    assert set(replay_members(child.events)) == set(moved)


def test_synthetic_90_day_cross_dormant_wake_keeps_same_id():
    """合成跨月剧本:90 日跨 3 次 dormant/wake 循环,topic_id 全程不变(MEM-A6)。"""
    t = born_topic(1, "sid", 0, "2024-01-01", ["猫"], [1.0, 0.0], ["e0", "e1", "e2"])
    t.state = "active"
    original_id = t.id

    # 第一轮:day1 活跃 -> day1+25 dormant -> day1+30 wake(grow)
    apply_dormancy(t, "2024-01-26")
    assert t.state == "dormant"
    grow(t, "e3", "2024-01-31", [1.0, 0.0], ["猫"])
    assert t.state == "active"
    assert t.id == original_id

    # 第二轮:再次 dormant -> 再次 wake(day ~60)
    apply_dormancy(t, "2024-02-25")
    assert t.state == "dormant"
    grow(t, "e4", "2024-03-05", [1.0, 0.0], ["猫"])
    assert t.state == "active"
    assert t.id == original_id

    # 第三轮:再次 dormant,直到第 90 天仍未死(strength 由外部维护,这里手动设高)
    t.strength = 0.5
    apply_dormancy(t, "2024-03-30")
    assert t.state == "dormant"
    apply_death(t, "2024-04-01")  # 远不足 60 天
    assert t.state == "dormant"
    assert t.id == original_id

    wake_events = [e for e in t.events if e.kind == "wake"]
    assert len(wake_events) == 2
    replayed = replay_members(t.events)
    assert set(replayed) == set(t.members)


def test_compute_centroid_mean_and_normalize():
    c = compute_centroid([[1.0, 0.0], [0.0, 1.0]])
    assert abs(sum(x * x for x in c) - 1.0) < 1e-9

    assert compute_centroid([]) == []


def test_topic_store_roundtrip_atomic_write(tmp_path):
    store = TopicStore(tmp_path, "sidz", 0)
    t = born_topic(1, "sidz", 0, "2024-01-01", ["猫"], [1.0, 0.0], ["e0"])
    store.add(t)
    store.merge_streak["a|b"] = 2
    store.save()

    reloaded = TopicStore(tmp_path, "sidz", 0)
    assert reloaded.count() == 1
    assert reloaded.get(t.id) is not None
    assert reloaded.merge_streak.get("a|b") == 2
