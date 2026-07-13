"""锁 core/finitude.py(幕 V 有限性)与 core/binding.py 里日结/重生相关行为。

蓝图 §7 / §8、§13 测试映射表 test_finitude.py 一行:
    性质测试:任意事件序列回放 P 单调不增 / 封顶 2×base / Legacy 不动 /
    epoch 边界 / 双写同世代 min 合并 / 重生不继承旧 P(世代键,红队 F4)。

世代键(p:{umo}:{int(born_at)})的读取/合并逻辑落在 main.py,不在本测试范围内
(main 依赖 W1,W3 不依赖 main)。本文件改为在 core 层面锁死两件能独立验证的事:
    1. settle_day 本身的结构性单调 / 封顶 / Legacy 行为(性质测试,随机事件序列回放)。
    2. BindingStore.hatch() 产生全新记录(p=1.0,daily/utterances 等清零)——
       "重新孵化是新的存在"在 binding 层的体现是:hatch 对已封存 umo 会整体
       换成 _new_binding,不残留旧 daily/旧 milestones,更不会用旧 p 初始化。
       同时 lower_p 只降不升的钳制语义在此一并锁死。

被测 core 模块内禁止 random;本测试文件是"壳",允许用 random 生成确定性种子下的
伪随机事件序列——真正被回放验证的是 finitude.settle_day 这个纯函数本身。
"""

from __future__ import annotations

import random

from yelos.core import binding as binding_mod
from yelos.core import finitude


# --- 性质测试:任意事件序列回放,P 单调不增 --------------------------------


def _run_settle_sequence(seed: int, lifespan: int, steps: int) -> list[float]:
    """用固定种子的确定性伪随机序列跑 settle_day,返回逐日 P 轨迹(含初值)。

    被测函数 finitude.settle_day 本身不碰 random/now;random 只用于测试侧
    生成"某天是否活跃"“当日多少次高强度事件”的事件序列。
    """
    rng = random.Random(seed)
    p = 1.0
    trace = [p]
    for _ in range(steps):
        was_active = rng.random() < 0.7
        high_intensity_events = rng.randint(0, 4)
        p = finitude.settle_day(
            p,
            was_active_day=was_active,
            high_intensity_events=high_intensity_events,
            lifespan_active_days=lifespan,
        )
        trace.append(p)
    return trace


def test_settle_day_monotonic_nonincreasing_property_many_seeds():
    """任意事件序列回放:P 轨迹逐点单调不增,且恒落在 [0,1]。"""
    for seed in range(50):
        trace = _run_settle_sequence(seed, lifespan=30, steps=200)
        for prev, cur in zip(trace, trace[1:]):
            assert cur <= prev
            assert 0.0 <= cur <= 1.0
        # 最终必然落到与初值同或更低,不可能反弹回 1.0 以上
        assert trace[-1] <= trace[0]


def test_settle_day_monotonic_with_extreme_lifespans():
    """极端 lifespan(1、超大)下同样单调不增,不因 base 极端值破坏结构。"""
    for lifespan in (1, 2, 3650, 10_000_000):
        trace = _run_settle_sequence(seed=lifespan, lifespan=lifespan, steps=60)
        for prev, cur in zip(trace, trace[1:]):
            assert cur <= prev


def test_settle_day_never_increases_even_with_negative_events_input():
    """high_intensity_events 负值被钳到 0,不会产出负 spend 导致 P 上升。"""
    p = 0.5
    new_p = finitude.settle_day(
        p, was_active_day=True, high_intensity_events=-5, lifespan_active_days=10
    )
    assert new_p <= p


# --- 封顶 2×base ----------------------------------------------------------


def test_settle_day_spend_caps_at_two_times_base():
    """high_intensity_events 很大时 spend 封顶 2*base,不再无限增大扣减。"""
    lifespan = 20
    base = 1.0 / lifespan
    p = 1.0
    # events=100 应与 events=2(达到封顶所需的最小值附近)产生相同扣减
    new_p_huge = finitude.settle_day(
        p, was_active_day=True, high_intensity_events=100, lifespan_active_days=lifespan
    )
    new_p_at_cap = finitude.settle_day(
        p, was_active_day=True, high_intensity_events=2, lifespan_active_days=lifespan
    )
    assert new_p_huge == new_p_at_cap
    assert p - new_p_huge <= 2.0 * base + 1e-12


def test_settle_day_spend_formula_below_cap():
    """封顶之前 spend = base + 0.5*base*events,逐字对照蓝图公式。"""
    lifespan = 10
    base = 1.0 / lifespan
    p = 1.0
    for events in (0, 1, 2):
        expected_spend = min(base + 0.5 * base * events, 2.0 * base)
        new_p = finitude.settle_day(
            p,
            was_active_day=True,
            high_intensity_events=events,
            lifespan_active_days=lifespan,
        )
        assert abs((p - new_p) - expected_spend) < 1e-12


def test_settle_day_never_goes_below_zero():
    """长期消耗下 P 触底为 0,不会变负。"""
    p = 0.05
    new_p = finitude.settle_day(
        p, was_active_day=True, high_intensity_events=4, lifespan_active_days=2
    )
    assert new_p == 0.0


# --- Legacy:lifespan<=0 或非活跃日 → 不变 ---------------------------------


def test_settle_day_legacy_lifespan_zero_untouched():
    p = 0.73
    new_p = finitude.settle_day(
        p, was_active_day=True, high_intensity_events=3, lifespan_active_days=0
    )
    assert new_p == p


def test_settle_day_legacy_lifespan_negative_untouched():
    p = 0.4
    new_p = finitude.settle_day(
        p, was_active_day=True, high_intensity_events=9, lifespan_active_days=-5
    )
    assert new_p == p


def test_settle_day_inactive_day_untouched():
    """当日非活跃(was_active_day=False)→ 原样返回,即便 lifespan 正常。"""
    p = 0.6
    new_p = finitude.settle_day(
        p, was_active_day=False, high_intensity_events=5, lifespan_active_days=30
    )
    assert new_p == p


# --- epoch 边界(蓝图 §7.2 逐字)--------------------------------------------


def test_epoch_boundaries_exact():
    assert finitude.epoch(1.0) == "盛年"
    assert finitude.epoch(0.6001) == "盛年"
    assert finitude.epoch(0.6) == "慢下来"
    assert finitude.epoch(0.3001) == "慢下来"
    assert finitude.epoch(0.3) == "安静"
    assert finitude.epoch(0.15001) == "安静"
    assert finitude.epoch(0.15) == "静止前期"
    assert finitude.epoch(0.0001) == "静止前期"
    assert finitude.epoch(0.0) == "静止"


def test_epoch_transition_reports_only_on_crossing():
    assert finitude.epoch_transition(0.9, 0.65) is None  # 同档:盛年
    assert finitude.epoch_transition(0.65, 0.6) == "慢下来"
    assert finitude.epoch_transition(0.3, 0.3) is None  # 未变
    assert finitude.epoch_transition(0.3, 0.15) == "静止前期"
    assert finitude.epoch_transition(0.15, 0.0) == "静止"


def test_epoch_transition_property_along_monotonic_trace():
    """沿单调递减轨迹逐步核对 epoch_transition:纪元只可能不变或"更老"一档。

    用蓝图给定的档位顺序核验:一旦跨档,新纪元必然在"更老"的方向上,
    不会出现从"静止"跳回"盛年"这类不可能的跃迁(单调性在纪元层的推论)。
    """
    order = ["盛年", "慢下来", "安静", "静止前期", "静止"]
    for seed in range(20):
        trace = _run_settle_sequence(seed, lifespan=15, steps=100)
        last_rank = 0
        for prev, cur in zip(trace, trace[1:]):
            new_epoch = finitude.epoch_transition(prev, cur)
            if new_epoch is not None:
                rank = order.index(new_epoch)
                assert rank >= last_rank
                last_rank = rank


# --- BindingStore.rollover:settle 的唯一入口 + lower_p 只降不升 -----------


def test_rollover_uses_settle_fn_and_is_monotonic(tmp_path):
    path = tmp_path / "bindings.json"
    store = binding_mod.BindingStore(path)
    store.hatch("u1", "阿七", now_ts=1000.0, day_key="2026-07-01")
    b = store.get("u1")
    assert b["p"] == 1.0

    b["daily"]["interacted"] = True
    b["daily"]["active_seen"] = True
    b["daily"]["high_intensity"] = 3

    def settle_fn(p: float, daily: dict) -> float:
        was_active = daily.get("interacted", False) and daily.get("active_seen", False)
        return finitude.settle_day(
            p,
            was_active_day=was_active,
            high_intensity_events=daily.get("high_intensity", 0),
            lifespan_active_days=30,
        )

    new_p = store.rollover("u1", "2026-07-02", settle_fn)
    assert new_p is not None
    assert new_p <= 1.0
    assert store.get("u1")["p"] == new_p
    # daily 已重置为新的一天
    assert store.get("u1")["daily"]["day"] == "2026-07-02"
    assert store.get("u1")["daily"]["high_intensity"] == 0

    # 同一天再次 rollover 不重复结算(未跨日返回 None,P 不变)
    again = store.rollover("u1", "2026-07-02", settle_fn)
    assert again is None
    assert store.get("u1")["p"] == new_p


def test_rollover_property_sequence_monotonic(tmp_path):
    """连续多天 rollover(含 settle_fn 内部随机化的 daily 输入)P 轨迹单调不增。"""
    path = tmp_path / "bindings.json"
    store = binding_mod.BindingStore(path)
    store.hatch("u1", "阿七", now_ts=0.0, day_key="2026-01-01")

    rng = random.Random(42)
    days = [f"2026-01-{d:02d}" for d in range(2, 40) if d <= 31]
    prev_p = store.get("u1")["p"]
    for day in days:
        daily = store.get("u1")["daily"]
        daily["interacted"] = rng.random() < 0.8
        daily["active_seen"] = rng.random() < 0.8
        daily["high_intensity"] = rng.randint(0, 5)

        def settle_fn(p: float, d: dict) -> float:
            return finitude.settle_day(
                p,
                was_active_day=bool(d.get("interacted") and d.get("active_seen")),
                high_intensity_events=d.get("high_intensity", 0),
                lifespan_active_days=20,
            )

        new_p = store.rollover("u1", day, settle_fn)
        assert new_p is not None
        assert new_p <= prev_p
        prev_p = new_p


def test_rollover_settle_fn_cannot_raise_p_even_if_misbehaving(tmp_path):
    """即便 settle_fn(调用方传入)违规返回更高的 P,rollover 也钳制为只降不升。

    这是 binding.rollover 里"双保险"注释对应的行为:
    `if new_p > cur: new_p = cur`。
    """
    path = tmp_path / "bindings.json"
    store = binding_mod.BindingStore(path)
    store.hatch("u1", "阿七", now_ts=0.0, day_key="2026-02-01")
    store.get("u1")["p"] = 0.4

    def buggy_settle_fn(p: float, daily: dict) -> float:
        return 0.9  # 违规:比当前 p 更高

    new_p = store.rollover("u1", "2026-02-02", buggy_settle_fn)
    assert new_p == 0.4
    assert store.get("u1")["p"] == 0.4


def test_lower_p_only_decreases_never_increases(tmp_path):
    path = tmp_path / "bindings.json"
    store = binding_mod.BindingStore(path)
    store.hatch("u1", "阿七", now_ts=0.0, day_key="2026-03-01")
    assert store.get("u1")["p"] == 1.0

    store.lower_p("u1", 0.6)
    assert store.get("u1")["p"] == 0.6

    # 试图升高:被钳制为当前值,不生效
    store.lower_p("u1", 0.9)
    assert store.get("u1")["p"] == 0.6

    # 更低的值仍然生效
    store.lower_p("u1", 0.2)
    assert store.get("u1")["p"] == 0.2

    # 对不存在的 umo 调用:静默无操作,不抛
    store.lower_p("no-such-umo", 0.1)
    assert store.get("no-such-umo") is None


def test_lower_p_property_monotonic_under_random_writes(tmp_path):
    """任意一串 lower_p 调用序列(含试图升高的值)后,P 轨迹逐点单调不增。"""
    path = tmp_path / "bindings.json"
    store = binding_mod.BindingStore(path)
    store.hatch("u1", "阿七", now_ts=0.0, day_key="2026-04-01")

    rng = random.Random(7)
    prev = store.get("u1")["p"]
    for _ in range(100):
        candidate = rng.random()
        store.lower_p("u1", candidate)
        cur = store.get("u1")["p"]
        assert cur <= prev
        prev = cur


# --- 重生不继承旧 P(世代键逻辑在 main;这里锁 binding 层能验证的部分)------


def test_hatch_after_seal_produces_fresh_record_not_inheriting_old_p(tmp_path):
    """已封存后重新 hatch:新记录 p=1.0,不带旧记录的 daily/utterances/里程碑。

    真正的"跨世代 P 不继承"防线是 main.py 里的 KV 世代键(p:{umo}:{int(born_at)})
    只在同世代内做 min 合并;本用例锁住 binding 层能独立验证的那一半——
    hatch() 产出的记录本身与旧记录彻底切断(哪怕旧记录 p 很低,新记录也是 1.0,
    born_at 也变了,天然落入新的世代键)。
    """
    path = tmp_path / "bindings.json"
    store = binding_mod.BindingStore(path)
    store.hatch("u1", "阿七", now_ts=1000.0, day_key="2026-01-01")

    old = store.get("u1")
    old["p"] = 0.05  # 模拟老去到静止前期
    old["daily"]["high_intensity"] = 9
    old["utterances"].append({"ts": 1.0, "occasion": "withdraw_soft", "text": "……"})
    old["milestones"].append({"day": "2026-01-01", "text": "她睁开了眼"})
    old_born_at = old["born_at"]

    store.seal("u1", "farewell")
    assert store.get("u1")["sealed"] is True

    new_born_at = 5000.0
    new_record = store.hatch("u1", "小满", now_ts=new_born_at, day_key="2026-02-01")

    assert new_record["p"] == 1.0
    assert new_record["born_at"] == new_born_at
    assert new_record["born_at"] != old_born_at
    assert new_record["utterances"] == []
    assert new_record["milestones"] == []
    assert new_record["daily"]["high_intensity"] == 0
    assert new_record["sealed"] is False
    assert new_record["seal_kind"] is None

    # store 里当前记录也确实是新的这份,不是旧记录被就地改回 1.0
    assert store.get("u1") is new_record
    assert store.get("u1")["name"] == "小满"


def test_hatch_rejects_when_existing_and_not_sealed(tmp_path):
    """未封存时重复 hatch 拒绝(ValueError),不会用新调用覆盖/继承旧记录的 P。"""
    path = tmp_path / "bindings.json"
    store = binding_mod.BindingStore(path)
    store.hatch("u1", "阿七", now_ts=0.0, day_key="2026-01-01")
    store.get("u1")["p"] = 0.3

    try:
        store.hatch("u1", "阿七二号", now_ts=999.0, day_key="2026-01-02")
        assert False, "expected ValueError"
    except ValueError:
        pass

    # 原记录未被覆盖
    assert store.get("u1")["p"] == 0.3
    assert store.get("u1")["name"] == "阿七"
