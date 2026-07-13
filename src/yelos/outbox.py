"""Outbox——统一的服务端自发言语通道(蓝图 §3.1 / D1 / D12)。

MCP 无 server→agent 推送:她的一切主动/延迟言语无法自己送达。方案是每
session 一个 due/expire 队列(outbox)。心跳(§3.4)与 ``affect_arbitrate``
(延迟补句,§3.2)负责*入队*;``affect_impulse``(§3.4)是*唯一出队点*(drain)。
其余工具只在返回里报 ``pending: N`` 不出队——单一出队点,杜绝跨工具双送达。

五(六)类入队协议全部归一到这一个队列(D12):

    delayed_withdraw  SWALLOW 高压咽回,90s 后漫上来(§3.2.1)
    proactive         幕 III 主动(在吗 / 晚安,§3.4 步7)
    dream             梦语(昨晚梦到点什么,§3.4 步4)
    concern           影子心疼原语(你还好吗,§3.5)
    epoch_notice      纪元跃迁提示(话好像少了,§3.4 步6)
    recover           缓过来的延迟原语(§3.2 步5)

本模块是*纯逻辑*:一切时间(now / due / expires)由调用方(session 层)算好
传入,模块内禁 ``time.time()`` / ``datetime.now()`` / ``random``。P0 主权闸
(静默 / 封存)在出队时由 ``blocked`` 入参落地——被拦下时到期项照常丢、待取项
不出队(她的嘴被静默时,攒着的话也不漫出来,§3.1)。

持久化:队列项随 ``bindings.json`` 存(binding 记录顶层 ``outbox`` 块),日
翻转不清 outbox——延迟 / 梦可跨日到期(§7.2)。序列化 / 反序列化由本模块提供,
落盘由 session 层在 ``binding.save()`` 前写入记录。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

# --- 常量:kind / occasion / 时窗策略 -----------------------------------

# 队列项类别(kind)
KIND_DELAYED_WITHDRAW = "delayed_withdraw"
KIND_PROACTIVE = "proactive"
KIND_DREAM = "dream"
KIND_CONCERN = "concern"
KIND_EPOCH_NOTICE = "epoch_notice"
KIND_RECOVER = "recover"

# 交 primal 的词组名(occasion);epoch_notice 文本固定、不走 primal
OCCASION_WITHDRAW_HEAVY = "withdraw_heavy"
OCCASION_CONTACT_SEEK = "contact_seek"
OCCASION_CONTACT_NIGHT = "contact_night"
OCCASION_DREAM_MURMUR = "dream_murmur"
OCCASION_CONCERN = "concern"
OCCASION_RECOVER = "recover"
OCCASION_EPOCH_NOTICE = "epoch_notice"

# 时窗策略常量(§3.1)
DELAYED_DUE_DELAY_SECONDS = 90.0  # SWALLOW 高压:90s 后漫上来
RECOVER_DUE_DELAY_SECONDS = 120.0  # recover 原语:120s 后
PROACTIVE_MAX_HORIZON_SECONDS = 6 * 3600.0  # 主动言语最长 6h 时窗


def _grace(intrinsic_interval_seconds: float) -> float:
    """过期宽限 = intrinsic_interval_seconds*3(§3.1)。

    避免"她三天前想说的话今天才漫上来":延迟 / recover 类过了这个时窗就真咽下。
    """
    return float(intrinsic_interval_seconds) * 3.0


# --- 队列项 -------------------------------------------------------------


@dataclass
class OutboxItem:
    """一条待取的自发言语(§3.1)。

    ``text`` 入队时可由 primal 定文本(确定性,同日同态同句);为 ``None`` 则出队
    时再定(delayed / proactive / dream / concern 多走此路,epoch_notice 文本固定)。
    """

    kind: str
    occasion: str
    created_ts: float
    due_ts: float  # now >= due_ts 才可取
    expires_ts: float  # now >= expires_ts 则弃(过期不补发)
    text: str | None = None

    def is_due(self, now: float) -> bool:
        return self.due_ts <= now < self.expires_ts

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_ts

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "occasion": self.occasion,
            "created_ts": self.created_ts,
            "due_ts": self.due_ts,
            "expires_ts": self.expires_ts,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, d: Mapping) -> "OutboxItem":
        return cls(
            kind=str(d.get("kind", "")),
            occasion=str(d.get("occasion", "")),
            created_ts=float(d.get("created_ts", 0.0)),
            due_ts=float(d.get("due_ts", 0.0)),
            expires_ts=float(d.get("expires_ts", 0.0)),
            text=d.get("text"),
        )


@dataclass
class DrainResult:
    """一次出队结果:到期取走的项 + 静默丢弃的过期项计数(供 debug,不含全文)。"""

    items: list[OutboxItem] = field(default_factory=list)
    expired: int = 0


# --- 入队协议工厂(五 / 六类) ------------------------------------------
#
# 一切时间入参传入。delayed / recover 的过期宽限自足(由 interval 算);
# proactive / dream / concern / epoch_notice 的时窗上界(quiet 边界 / 当日结束)
# 由 session 层算好传入——这些依赖 quiet_hours 与本地日期,不属纯逻辑面。


def make_delayed_withdraw(
    now: float, intrinsic_interval_seconds: float, text: str | None = None
) -> OutboxItem:
    """SWALLOW 高压咽回 → 90s 后漫上来(§3.2.1)。

    due=now+90;expires=now+90+grace(grace=interval*3)。
    """
    due = now + DELAYED_DUE_DELAY_SECONDS
    return OutboxItem(
        kind=KIND_DELAYED_WITHDRAW,
        occasion=OCCASION_WITHDRAW_HEAVY,
        created_ts=now,
        due_ts=due,
        expires_ts=due + _grace(intrinsic_interval_seconds),
        text=text,
    )


def make_recover(
    now: float, intrinsic_interval_seconds: float, text: str | None = None
) -> OutboxItem:
    """recover 允许延迟原语 → 120s 后(§3.2 步5)。

    due=now+120;expires=due+grace。
    """
    due = now + RECOVER_DUE_DELAY_SECONDS
    return OutboxItem(
        kind=KIND_RECOVER,
        occasion=OCCASION_RECOVER,
        created_ts=now,
        due_ts=due,
        expires_ts=due + _grace(intrinsic_interval_seconds),
        text=text,
    )


def make_proactive(
    now: float,
    occasion: str,
    quiet_boundary_ts: float | None = None,
    text: str | None = None,
) -> OutboxItem:
    """幕 III 主动(§3.4 步7)。

    occasion 为 ``contact_seek`` | ``contact_night``。due=now;
    expires = min(下一个 quiet 边界, now+6h),取近者(晚安不该午后才送)。
    ``quiet_boundary_ts`` 为 None 或已过 now → 只用 6h 上界。
    """
    horizon = now + PROACTIVE_MAX_HORIZON_SECONDS
    if quiet_boundary_ts is not None and quiet_boundary_ts > now:
        expires = min(quiet_boundary_ts, horizon)
    else:
        expires = horizon
    return OutboxItem(
        kind=KIND_PROACTIVE,
        occasion=occasion,
        created_ts=now,
        due_ts=now,
        expires_ts=expires,
        text=text,
    )


def make_dream(now: float, day_end_ts: float, text: str | None = None) -> OutboxItem:
    """梦语(§3.4 步4)。

    "首次被动回复前投"→ 由 agent 下次交互前 poll 取走;expires = 当日结束。
    """
    return OutboxItem(
        kind=KIND_DREAM,
        occasion=OCCASION_DREAM_MURMUR,
        created_ts=now,
        due_ts=now,
        expires_ts=day_end_ts,
        text=text,
    )


def make_concern(now: float, day_end_ts: float, text: str | None = None) -> OutboxItem:
    """影子 concern 原语(§3.5)。

    过幕 III 全部闸门后经 outbox 送达。due=now;expires = 当日结束
    (心疼是当下状态,隔日即陈旧)。
    """
    return OutboxItem(
        kind=KIND_CONCERN,
        occasion=OCCASION_CONCERN,
        created_ts=now,
        due_ts=now,
        expires_ts=day_end_ts,
        text=text,
    )


def make_epoch_notice(now: float, text: str, day_end_ts: float) -> OutboxItem:
    """纪元跃迁提示(§3.4 步6)。

    text 为固定纪元句(如"最近…话好像少了。"),不走 primal;占 self_words 记账。
    due=now;expires = 当日结束。
    """
    return OutboxItem(
        kind=KIND_EPOCH_NOTICE,
        occasion=OCCASION_EPOCH_NOTICE,
        created_ts=now,
        due_ts=now,
        expires_ts=day_end_ts,
        text=text,
    )


# --- Outbox 队列 --------------------------------------------------------


class Outbox:
    """每 session 一个待取言语队列(§3.1)。

    内存态 ``dict[sid, list[OutboxItem]]``,随 bindings.json 持久化。入队由心跳
    与 arbitrate 调用;出队由 ``affect_impulse`` 经 ``drain_due`` 唯一入口做,并发
    安全由 session 层的 per-sid ``asyncio.Lock`` 保证(§7.2 daemon 并发模型),本
    模块不含锁——只做同步内存操作。
    """

    def __init__(self) -> None:
        self._q: dict[str, list[OutboxItem]] = {}

    # -- 入队 ------------------------------------------------------------

    def enqueue(self, sid: str, item: OutboxItem) -> None:
        """把一条自发言语挂入该 sid 队列(§3.1 入队规则)。"""
        self._q.setdefault(sid, []).append(item)

    # -- 出队(唯一 drain 点由 affect_impulse 调用) --------------------

    def drain_due(self, sid: str, now: float, blocked: bool = False) -> DrainResult:
        """出队所有到期项(due<=now<expires),按 created_ts 排序返回;并静默丢弃
        过期项(now>=expires)。

        P0 主权闸(§3.1 / §6.2):``blocked=True``(session 静默中 / 已封存)时
        *不出队、不返回任何项*,但过期项照常丢(她被叫停时,攒着的话也不漫出来,
        过了时窗的照样真咽下)。留在队里的未到期项保持不动。

        返回 ``DrainResult(items, expired)``——``expired`` 供调用方记一条 debug
        (不记全文),``items`` 为本次取走(已从队列移除)的到期项。
        """
        items = self._q.get(sid)
        if not items:
            return DrainResult()

        survivors: list[OutboxItem] = []
        expired = 0
        for it in items:
            if it.is_expired(now):
                expired += 1
            else:
                survivors.append(it)

        if blocked:
            # 被静默 / 封存:过期照丢,到期不出队(未到期 + 到期未取的都留下)
            self._q[sid] = survivors
            return DrainResult(items=[], expired=expired)

        due: list[OutboxItem] = []
        remaining: list[OutboxItem] = []
        for it in survivors:
            if it.due_ts <= now:  # survivors 已排除过期 → 此处即 due
                due.append(it)
            else:
                remaining.append(it)

        self._q[sid] = remaining
        due.sort(key=lambda it: it.created_ts)
        return DrainResult(items=due, expired=expired)

    def purge_expired(self, sid: str, now: float) -> int:
        """只清过期项、不出队,返回丢弃计数(供 P0/静默态下也能定期陈旧回收)。"""
        items = self._q.get(sid)
        if not items:
            return 0
        survivors = [it for it in items if not it.is_expired(now)]
        dropped = len(items) - len(survivors)
        if dropped:
            self._q[sid] = survivors
        return dropped

    # -- 只读查询(pending 冒泡,不出队、不改状态) ---------------------

    def pending_count(self, sid: str, now: float) -> int:
        """当前待取数(due<=now<expires)——各工具返回里的 ``pending: N``(§3.2)。

        只读:不出队、不清过期。过期项不计入(已过时窗不算待取)。
        """
        items = self._q.get(sid)
        if not items:
            return 0
        return sum(1 for it in items if it.is_due(now))

    def has_due(self, sid: str, now: float) -> bool:
        items = self._q.get(sid)
        if not items:
            return False
        return any(it.is_due(now) for it in items)

    def size(self, sid: str) -> int:
        """队列原始长度(含未到期 / 已过期未清),供测试 / 调试。"""
        return len(self._q.get(sid, ()))

    # -- 生命周期 --------------------------------------------------------

    def clear(self, sid: str) -> None:
        """清空该 sid 队列(封存 / reset 时由 session 层调用)。"""
        self._q.pop(sid, None)

    # -- 持久化(随 bindings.json;由 session 层在 save 前后接线) ------

    def serialize(self, sid: str) -> list[dict]:
        """该 sid 队列 → 可 JSON 化的 list(写入 binding 记录 ``outbox`` 块)。"""
        return [it.to_dict() for it in self._q.get(sid, ())]

    def load_sid(self, sid: str, raw: Iterable[Mapping] | None) -> None:
        """从记录的 ``outbox`` 块反序列化到内存(单 sid)。"""
        if not raw:
            self._q.pop(sid, None)
            return
        self._q[sid] = [OutboxItem.from_dict(d) for d in raw]

    def load_records(self, records: Mapping[str, Mapping]) -> None:
        """启动时从全部 binding 记录水合(record.get("outbox", []))。

        日翻转不清 outbox → 记录里跨日残留的延迟 / 梦项照常载回(§7.2)。
        """
        self._q.clear()
        for sid, record in records.items():
            raw = record.get("outbox") if isinstance(record, Mapping) else None
            if raw:
                self._q[sid] = [OutboxItem.from_dict(d) for d in raw]
