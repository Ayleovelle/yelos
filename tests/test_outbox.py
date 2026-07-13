"""test_outbox.py —— outbox 单一出队点 / 到期 / 过期 / P0 闸测试(蓝图 §3.1/§8.2)。

锁死项(对应 §8.2 test_outbox.py 一行):
- 入队/出队 due 过滤(due_ts<=now<expires_ts 才可取)
- expire 丢弃(now>=expires_ts 静默丢,不出队、不补发)
- **单一出队点无双送达**:同一到期时刻连续 drain 两次,第二次必空
- **P0 闸出队拦截**:``blocked=True``(静默/封存)时不出队,但过期项照常丢
- 持久化往返(serialize/load_sid/load_records,日翻转不清空)
- 延迟 90s(delayed_withdraw)与 recover 120s(recover)due 计算 + 各自 expire 宽限

纯逻辑测试:只 import ``yelos.outbox``,一切时间由用例显式传入(§3.1 模块内
禁 time.time()/random,契约由 test_structure.py 的 AST 扫描另行守护)。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from yelos import outbox as ob  # noqa: E402

INTERVAL = 60.0  # intrinsic_interval_seconds 默认


# --- 入队工厂:due/expire 计算 ---------------------------------------------


class TestFactoryDueExpire:
    def test_delayed_withdraw_due_90s(self):
        item = ob.make_delayed_withdraw(1000.0, INTERVAL)
        assert item.kind == ob.KIND_DELAYED_WITHDRAW
        assert item.occasion == ob.OCCASION_WITHDRAW_HEAVY
        assert item.due_ts == 1000.0 + 90.0
        # expires = due + interval*3(grace),避免"三天前想说的话今天才漫上来"。
        assert item.expires_ts == item.due_ts + INTERVAL * 3

    def test_recover_due_120s(self):
        item = ob.make_recover(2000.0, INTERVAL)
        assert item.kind == ob.KIND_RECOVER
        assert item.occasion == ob.OCCASION_RECOVER
        assert item.due_ts == 2000.0 + 120.0
        assert item.expires_ts == item.due_ts + INTERVAL * 3

    def test_proactive_due_now_expires_min_of_quiet_or_6h(self):
        now = 10_000.0
        # quiet 边界比 6h 更近 → 取 quiet 边界。
        near_quiet = now + 3600.0
        item = ob.make_proactive(now, ob.OCCASION_CONTACT_SEEK, near_quiet)
        assert item.due_ts == now
        assert item.expires_ts == near_quiet

        # quiet 边界比 6h 更远(或缺省)→ 取 6h 上界(晚安不该午后才送)。
        far_quiet = now + 100_000.0
        item2 = ob.make_proactive(now, ob.OCCASION_CONTACT_NIGHT, far_quiet)
        assert item2.expires_ts == now + ob.PROACTIVE_MAX_HORIZON_SECONDS

        item3 = ob.make_proactive(now, ob.OCCASION_CONTACT_SEEK, None)
        assert item3.expires_ts == now + ob.PROACTIVE_MAX_HORIZON_SECONDS

        # 已过去的 quiet 边界(<=now)不该被采用为更近的上界。
        stale_quiet = now - 10.0
        item4 = ob.make_proactive(now, ob.OCCASION_CONTACT_SEEK, stale_quiet)
        assert item4.expires_ts == now + ob.PROACTIVE_MAX_HORIZON_SECONDS

    def test_dream_and_concern_due_now_expire_day_end(self):
        now = 500.0
        day_end = 86400.0
        dream = ob.make_dream(now, day_end)
        assert dream.kind == ob.KIND_DREAM
        assert dream.due_ts == now
        assert dream.expires_ts == day_end

        concern = ob.make_concern(now, day_end)
        assert concern.kind == ob.KIND_CONCERN
        assert concern.due_ts == now
        assert concern.expires_ts == day_end

    def test_epoch_notice_fixed_text_due_now(self):
        item = ob.make_epoch_notice(100.0, "最近…话好像少了。", 86400.0)
        assert item.kind == ob.KIND_EPOCH_NOTICE
        assert item.text == "最近…话好像少了。"
        assert item.due_ts == 100.0
        assert item.expires_ts == 86400.0


# --- OutboxItem.is_due / is_expired 边界 -----------------------------------


class TestItemBoundaries:
    def test_is_due_half_open_interval(self):
        item = ob.OutboxItem(
            kind="x", occasion="y", created_ts=0.0, due_ts=100.0, expires_ts=200.0
        )
        assert not item.is_due(99.9)
        assert item.is_due(100.0)  # due_ts<=now
        assert item.is_due(199.9)
        assert not item.is_due(200.0)  # now<expires_ts,200.0 不算 due(已过期)
        assert item.is_expired(200.0)
        assert not item.is_expired(199.9)

    def test_roundtrip_dict(self):
        item = ob.make_delayed_withdraw(1.0, INTERVAL, text="漫上来的话")
        d = item.to_dict()
        back = ob.OutboxItem.from_dict(d)
        assert back == item


# --- Outbox 队列:入队/出队/pending/expire --------------------------------


class TestOutboxQueue:
    def test_enqueue_and_pending_count_due_filter(self):
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_dream(100.0, 86400.0))  # due=100,立即可取
        q.enqueue(sid, ob.make_delayed_withdraw(100.0, INTERVAL))  # due=190

        assert q.pending_count(sid, 100.0) == 1
        assert q.pending_count(sid, 150.0) == 1  # delayed 尚未到期
        assert q.pending_count(sid, 190.0) == 2  # 二者皆到期
        assert q.has_due(sid, 100.0) is True
        assert q.has_due("no-such-sid", 100.0) is False

    def test_pending_count_excludes_expired(self):
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_concern(0.0, 10.0))  # expires=10
        assert q.pending_count(sid, 5.0) == 1
        assert q.pending_count(sid, 10.0) == 0  # 已过期,不算待取

    def test_drain_due_returns_ordered_by_created_ts_and_removes(self):
        q = ob.Outbox()
        sid = "s1"
        later = ob.make_proactive(50.0, ob.OCCASION_CONTACT_SEEK, None)
        earlier = ob.make_dream(10.0, 86400.0)
        q.enqueue(sid, later)
        q.enqueue(sid, earlier)

        result = q.drain_due(sid, 100.0)
        assert [it.created_ts for it in result.items] == [10.0, 50.0]
        assert result.expired == 0
        # 出队后队列已清空(size 反映未到期/未清过期的原始长度)。
        assert q.size(sid) == 0
        assert q.pending_count(sid, 100.0) == 0

    def test_drain_due_leaves_not_yet_due_items(self):
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_dream(10.0, 86400.0))  # due=10,到期
        q.enqueue(sid, ob.make_delayed_withdraw(90.0, INTERVAL))  # due=180,未到期

        result = q.drain_due(sid, 100.0)
        assert len(result.items) == 1
        assert result.items[0].kind == ob.KIND_DREAM
        assert q.size(sid) == 1  # delayed_withdraw 项仍在队列里

    def test_expired_items_silently_dropped_not_delivered(self):
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_concern(0.0, 50.0))  # expires=50
        q.enqueue(sid, ob.make_dream(0.0, 200.0))  # 未过期

        result = q.drain_due(sid, 60.0)
        # 过期的 concern 不出现在 items 里(静默丢),但计入 expired。
        assert len(result.items) == 1
        assert result.items[0].kind == ob.KIND_DREAM
        assert result.expired == 1
        # dream(due=0)已到期出队,concern 已过期丢弃 → 队列清空。
        assert q.size(sid) == 0

    def test_single_dequeue_point_no_double_delivery(self):
        """同一到期时刻连续 drain 两次:第二次必空(单一出队点纪律,§3.1)。"""
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_dream(10.0, 86400.0))

        first = q.drain_due(sid, 100.0)
        assert len(first.items) == 1
        second = q.drain_due(sid, 100.0)
        assert second.items == []
        assert second.expired == 0

    def test_empty_sid_drain_is_noop(self):
        q = ob.Outbox()
        result = q.drain_due("ghost", 100.0)
        assert result.items == []
        assert result.expired == 0
        assert q.pending_count("ghost", 100.0) == 0
        assert q.has_due("ghost", 100.0) is False


# --- P0 主权闸:静默/封存时出队被拦下 --------------------------------------


class TestSovereigntyGate:
    def test_blocked_drain_returns_nothing_but_expires_still_drop(self):
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_dream(10.0, 86400.0))  # 到期未过期
        q.enqueue(sid, ob.make_concern(0.0, 50.0))  # 已过期(now=100)

        result = q.drain_due(sid, 100.0, blocked=True)
        # 她被叫停时,攒着的话不漫出来:到期项也不出队。
        assert result.items == []
        # 但过期照常丢(不是"话被存起来",是"过了时窗真咽下")。
        assert result.expired == 1
        # 未到期/到期未取的项都留在队列里。
        assert q.size(sid) == 1
        assert q.pending_count(sid, 100.0) == 1  # 仍待取,只是被 P0 挡在出队外

    def test_blocked_then_unblocked_can_still_drain_later(self):
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_delayed_withdraw(0.0, INTERVAL))  # due=90

        blocked = q.drain_due(sid, 95.0, blocked=True)
        assert blocked.items == []
        assert q.size(sid) == 1  # 未被静默吞掉,仍在队列

        unblocked = q.drain_due(sid, 96.0, blocked=False)
        assert len(unblocked.items) == 1
        assert unblocked.items[0].occasion == ob.OCCASION_WITHDRAW_HEAVY

    def test_purge_expired_without_draining(self):
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_concern(0.0, 10.0))  # 过期
        q.enqueue(sid, ob.make_dream(0.0, 200.0))  # 未过期

        dropped = q.purge_expired(sid, 50.0)
        assert dropped == 1
        assert q.size(sid) == 1


# --- 持久化往返:serialize / load_sid / load_records ----------------------


class TestPersistenceRoundtrip:
    def test_serialize_load_sid_roundtrip(self):
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_dream(10.0, 86400.0, text="昨晚梦到点什么。"))
        q.enqueue(sid, ob.make_delayed_withdraw(10.0, INTERVAL))

        raw = q.serialize(sid)
        assert len(raw) == 2
        assert all(isinstance(d, dict) for d in raw)

        q2 = ob.Outbox()
        q2.load_sid(sid, raw)
        assert q2.size(sid) == 2
        assert q2.serialize(sid) == raw

    def test_load_sid_none_or_empty_clears(self):
        q = ob.Outbox()
        sid = "s1"
        q.enqueue(sid, ob.make_dream(10.0, 86400.0))
        q.load_sid(sid, None)
        assert q.size(sid) == 0

        q.enqueue(sid, ob.make_dream(10.0, 86400.0))
        q.load_sid(sid, [])
        assert q.size(sid) == 0

    def test_load_records_hydrates_multiple_sids_day_rollover_keeps_outbox(self):
        """启动时从 binding 记录水合;日翻转不清 outbox——延迟/梦可跨日到期(§7.2)。"""
        q = ob.Outbox()
        sid_a = "a"
        sid_b = "b"
        q.enqueue(sid_a, ob.make_delayed_withdraw(10.0, INTERVAL))
        records = {
            sid_a: {"outbox": q.serialize(sid_a), "day": "2026-07-10"},
            sid_b: {"outbox": [], "day": "2026-07-11"},
            "c-no-outbox-key": {"day": "2026-07-11"},
        }

        q2 = ob.Outbox()
        q2.load_records(records)
        assert q2.size(sid_a) == 1
        assert q2.size(sid_b) == 0
        assert q2.size("c-no-outbox-key") == 0

        # 模拟"日翻转"仅仅是 day_key 变了——outbox 内容与日期无关联,水合后照样在。
        assert q2.pending_count(sid_a, 10.0 + 90.0) == 1

    def test_load_records_clears_previous_state(self):
        q = ob.Outbox()
        q.enqueue("stale", ob.make_dream(0.0, 100.0))
        q.load_records({})
        assert q.size("stale") == 0
