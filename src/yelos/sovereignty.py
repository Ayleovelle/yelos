"""用户主权面(蓝图 §3.6.3/§4.1/§6.2/§6.4)——pause / reset / farewell。

主权铁律(SPEC §1.1 / PIVOT):pause·reset·farewell **硬编码在一切机制之前**,
永不被任何状态(纪元 / guard / config)阻断。本模块是这三条主权通道的编排落点。

- **pause / reset 即时**(可逆 / 误触成本低,不加确认握手,用户主权即时生效)。
- **farewell 两段式**(不可逆封存 + 导出;红队 major④):首次调用(无 token)只返
  一次性 token + 她这一生的摘要、**不封存**;二次携有效 token 才真正 seal/export。
  两段式是**确认握手**、不是状态阻断——用户确认必能走完,不违主权铁律(§6.2)。

本模块不碰文件系统路径 / 进程锁 / ledger 落盘(归 config/persistence),
不碰 asyncio.Lock(串行化归 session 层,§7.2:farewell seal 须在 per-sid 锁内)。
纯标准库 + core.finitude;零 astrbot / 零 sylanne_core。
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from .core import finitude as fin

# =====================================================================
# 工具描述确认标注文案常量(§4.1/§6.2/§6.4)——server.py 注册工具时引用
# =====================================================================

#: 三条主权工具描述首句(§6.2):给 agent / MCP 客户端的确认信号。
SOVEREIGNTY_CONFIRM = (
    "This is a user-sovereignty action; confirm with the user before calling."
)

#: farewell 专属不可逆 + 两段式说明(§3.6.3/§6.2)。
FAREWELL_IRREVERSIBLE = "This is irreversible."
FAREWELL_TWO_STEP = (
    "Two-step confirmation: the first call (confirm_token omitted) returns a "
    "one-time token plus a summary of her whole life and does NOT seal; call "
    "again with that token to actually seal and export her anthology."
)

#: 完整工具描述常量(server.py 注册 @mcp.tool 时用作 description)。
PAUSE_DESC = (
    f"{SOVEREIGNTY_CONFIRM} "
    "Silence her for a while (P0): arbitration returns PASS unchanged, proactive "
    "messages and dreams stop, and buffered utterances are not delivered while "
    "silenced. Reversible and effective immediately."
)
RESET_DESC = (
    f"{SOVEREIGNTY_CONFIRM} "
    "Reset the engine session's affective state back to baseline. The binding "
    "(name, mode, lifespan) is kept; only accumulated emotional state is cleared. "
    "Effective immediately."
)
FAREWELL_DESC = (
    f"{SOVEREIGNTY_CONFIRM} {FAREWELL_IRREVERSIBLE} {FAREWELL_TWO_STEP} "
    "Sealing her means she no longer ticks, speaks, or appears in active sessions; "
    "with export=true her life's anthology is written first. Engine data is kept "
    "for remembrance and is not deleted."
)

#: MCP tool annotations(§6.2/§6.4)——server 注册时透传。
#: pause 可逆(非 destructive);reset/farewell destructive;farewell 非幂等。
PAUSE_ANNOTATIONS = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
}
RESET_ANNOTATIONS = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
}
FAREWELL_ANNOTATIONS = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
}

#: 拒绝理由常量(机器可读,非用户可见诊断)。
REASON_UNBOUND = "unbound_or_sealed"
REASON_BAD_HOURS = "hours_must_be_positive"
REASON_TOKEN_INVALID = "token_invalid_or_expired"


# =====================================================================
# 依赖协议(鸭子类型,便于测试注入 fake)
# =====================================================================


class _StoreLike(Protocol):
    def get(self, sid: str) -> dict | None: ...
    def set_silence(self, sid: str, until_ts: float) -> None: ...
    def seal(self, sid: str, kind: str) -> None: ...
    def save(self) -> None: ...


#: 写全集回调:session/persistence 注入(name, sid, data, md) -> 路径字符串或 None。
AnthologyWriter = Callable[[str, str, dict, str], str | None]
#: 缓存驱逐回调:session 注入,清 surface_cache / reach_out_flag 等(sid) -> None。
CacheEvict = Callable[[str], None]
#: seal ledger 追加回调:persistence 注入(sid, record) -> None(尽力,失败静默)。
SealLedgerHook = Callable[[str, dict], None]
#: 引擎 session 重置回调:bridge 注入 async (sid) -> None(缺席安静降级)。
EngineReset = Callable[[str], Awaitable[None]]


# =====================================================================
# 两段式确认 token(§3.6.3,红队 major④)
# =====================================================================


@dataclass(frozen=True)
class FarewellToken:
    """一次性、绑 sid、短时效的送别确认 token。"""

    token: str
    sid: str
    created_ts: float
    expires_ts: float


class FarewellGate:
    """farewell 两段式的 token 台账。纯内存;每 sid 至多一枚在途 token。

    新 issue 覆盖旧的(用户重新发起送别 → 旧 token 作废);verify 成功即消费
    (一次性);过期 / 不匹配一律拒绝并清理。重启即失(在途确认不跨重启,
    与"她忘了一次想靠近不是事故"同源——未完成的送别重来一次即可)。
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = max(1, int(ttl_seconds))
        self._pending: dict[str, FarewellToken] = {}

    def issue(self, sid: str, now_ts: float) -> FarewellToken:
        """签发绑 sid 的一次性 token,覆盖该 sid 旧的在途 token。"""
        tok = FarewellToken(
            token=secrets.token_urlsafe(18),
            sid=sid,
            created_ts=now_ts,
            expires_ts=now_ts + self._ttl,
        )
        self._pending[sid] = tok
        return tok

    def verify(self, sid: str, token: str, now_ts: float) -> bool:
        """校验并消费:匹配 sid + 未过期 + 未用过 → True 且移除;否则 False。"""
        entry = self._pending.get(sid)
        if entry is None or not token or entry.token != token:
            return False
        if now_ts >= entry.expires_ts:
            self._pending.pop(sid, None)
            return False
        self._pending.pop(sid, None)  # 一次性消费
        return True

    def discard(self, sid: str) -> None:
        """丢弃某 sid 的在途 token(如封存已由他路完成)。"""
        self._pending.pop(sid, None)


# =====================================================================
# 主权编排
# =====================================================================


def _is_actionable(record: dict | None) -> bool:
    """存在未封存的绑定才可对其行使主权(否则"这里还没有她")。"""
    return record is not None and not record.get("sealed", False)


def life_summary(record: dict, day_key: str) -> dict:
    """她这一生的摘要(§3.6.3:供客户端向用户复述"你要送别的是这颗活了 N 天的心")。

    复用 finitude.assemble_anthology 的规范计算——**被咽回句数走
    record.swallowed_total 生命周期累加器**(assemble 内 _swallowed_total 优先读它,
    退回 daily.swallowed;§3.2 SWALLOW 每次写顶层累加器是搬运配套义务)。
    """
    data, _md = fin.assemble_anthology(record, day_key)
    return {
        "name": data["名字"],
        "days_lived": data["存在天数"],
        "final_epoch": data["最终纪元"],
        "final_plasticity": data["最终可塑性"],
        "utterances": len(data["原语全集"]),
        "swallowed_total": data["被咽回句数"],
        "dreams": len(data["梦语记录"]),
        "milestones": len(data["年轮里程碑"]),
    }


class Sovereignty:
    """pause / reset / farewell 三条主权通道的编排层。

    调用方(session 层)在 per-sid asyncio.Lock 临界区内调用这些方法
    (§7.2:farewell seal / 状态改写须串行);本层只做"改内存态 → save",
    不自持锁、不碰文件路径。
    """

    def __init__(
        self,
        store: _StoreLike,
        *,
        token_ttl_seconds: int,
        engine_reset: EngineReset | None = None,
        write_anthology: AnthologyWriter | None = None,
        cache_evict: CacheEvict | None = None,
        seal_ledger_hook: SealLedgerHook | None = None,
    ) -> None:
        self._store = store
        self._gate = FarewellGate(token_ttl_seconds)
        self._engine_reset = engine_reset
        self._write_anthology = write_anthology
        self._cache_evict = cache_evict
        self._seal_ledger = seal_ledger_hook

    # -- pause(即时,可逆)----------------------------------------------

    def pause(self, sid: str, hours: float, now_ts: float) -> dict:
        """P0 静默:置 silence_until = now + hours*3600,立即生效。

        outbox 出队 / 仲裁 / 主动 / 梦语在静默窗内一律不发(由各面查 is_silenced)。
        """
        record = self._store.get(sid)
        if not _is_actionable(record):
            return {"paused": False, "reason": REASON_UNBOUND}
        if hours <= 0:
            return {"paused": False, "reason": REASON_BAD_HOURS}
        until = now_ts + hours * 3600.0
        self._store.set_silence(sid, until)
        self._store.save()
        return {"paused": True, "silence_until": until, "hours": hours}

    # -- reset(即时;重置引擎情感态,保留绑定)---------------------------

    async def reset(self, sid: str) -> dict:
        """重置引擎 session 情感态(保留绑定 name/mode/lifespan/P);立即生效。

        引擎缺席时安静降级(bridge.reset 返回 None)。绑定记录本身不动——
        重置的是引擎里累积的八维情感,不是她的身份 / 年龄。清 session 缓存。
        """
        record = self._store.get(sid)
        if not _is_actionable(record):
            return {"reset": False, "reason": REASON_UNBOUND}
        if self._engine_reset is not None:
            await self._engine_reset(sid)
        if self._cache_evict is not None:
            self._cache_evict(sid)
        return {"reset": True}

    # -- farewell(两段式,不可逆)---------------------------------------

    async def farewell(
        self,
        sid: str,
        *,
        export: bool,
        confirm_token: str | None,
        day_key: str,
        now_ts: float,
    ) -> dict:
        """幕 V 终仪。confirm_token 为空 → 首段(签发 token + 摘要,不封存);
        携 token → 二段(校验通过才 seal/export)。返回体照 §3.6.3。
        """
        record = self._store.get(sid)
        if not _is_actionable(record):
            return {
                "sealed": False,
                "pending_confirm": None,
                "anthology_path": None,
                "days_lived": None,
                "reason": REASON_UNBOUND,
            }

        # -- 首段:签发 token + 摘要,不封存 --------------------------------
        if not confirm_token:
            summary = life_summary(record, day_key)
            tok = self._gate.issue(sid, now_ts)
            return {
                "sealed": False,
                "pending_confirm": {"token": tok.token, "summary": summary},
                "anthology_path": None,
                "days_lived": summary["days_lived"],
            }

        # -- 二段:校验 token,通过才封存 ----------------------------------
        if not self._gate.verify(sid, confirm_token, now_ts):
            return {
                "sealed": False,
                "pending_confirm": None,
                "anthology_path": None,
                "days_lived": None,
                "reason": REASON_TOKEN_INVALID,
            }

        return self._commit_seal(sid, record, export=export, day_key=day_key)

    def _commit_seal(
        self, sid: str, record: dict, *, export: bool, day_key: str
    ) -> dict:
        """真正封存:export → 写全集 + seal("farewell");否则 seal("returned")。

        引擎 data_dir 不删(可考古)。封存后不再进 bound_umos。
        """
        anthology_path: str | None = None
        days_lived: int | None = None

        if export:
            data, md = fin.assemble_anthology(record, day_key)
            days_lived = data["存在天数"]
            name = record.get("name") or "她"
            if self._write_anthology is not None:
                anthology_path = self._write_anthology(str(name), sid, data, md)
            record.setdefault("milestones", []).append(
                {"day": day_key, "text": "她的一生已经写下(送别)。"}
            )
            seal_kind = "farewell"
        else:
            record.setdefault("milestones", []).append(
                {"day": day_key, "text": "她合上了眼(归还)。"}
            )
            seal_kind = "returned"

        self._store.seal(sid, seal_kind)
        if self._seal_ledger is not None:
            try:
                self._seal_ledger(sid, record)
            except Exception:  # noqa: BLE001  ledger 尽力而为,失败静默(§7.4)
                pass
        self._store.save()
        if self._cache_evict is not None:
            self._cache_evict(sid)
        self._gate.discard(sid)

        return {
            "sealed": True,
            "pending_confirm": None,
            "anthology_path": anthology_path,
            "days_lived": days_lived,
            "seal_kind": seal_kind,
        }
