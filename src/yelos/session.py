"""业务时序层(蓝图 §1.3 / §3-§7)——原 main.py "何时调用" 的 MCP 落点。

``SessionManager`` 是唯一持有"时间 / 配置 / 引擎 / 持久化"并编排 core 纯函数的
层;``server.py`` 只做协议翻译(工具参数 ↔ 本层调用 ↔ 返回 dict)。五幕全部时序
在此:submit 流 / arbitrate 流 / impulse+心跳流 / 影子 concern / 有限性日结 /
主权 pause·reset·farewell。

并发模型(§7.2 / 红队 major⑥):HTTP daemon 下多客户端并发工具调用 + 后台心跳
共享同一内存态。每 sid 一把惰性 ``asyncio.Lock``;arbitrate / impulse(drain+
记账+save)/ 心跳单 session 段 / submit / farewell 五路对同一 sid 各整段串行,把
"读态→改态→save"收进同一临界区,杜绝交错。锁 per-sid、非全局。

日志纪律(§6.6):禁记 draft / final_text / text 全文,只记 sid、occasion、
verdict.reason、计数。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from . import outbox
from .config import YelosConfig
from .core import arbiter as arb
from .core import finitude as fin
from .core import intrinsic as intr
from .core import shadow as shd
from .core import sget, split_sentences
from .core.binding import BindingStore
from .core.primal import LexiconProvider
from .engine_bridge import EngineBridge
from .guidance import build_compact_surface, build_guidance
from . import persistence
from .sovereignty import Sovereignty

logger = logging.getLogger("yelos.session")


def _build_clock():
    """全平台唯一时钟(INTEGRATION_SPEC §3.2):默认 RealClock;bench/回放注入 Virtual。

    RealClock 归 bench(实现),协议归 core;import 失败(极端裁剪安装)时安静回退
    None,session 的 staticmethod 时间面继续兜底,绝不因时钟缺席 raise。
    """
    try:
        from .bench.clock import RealClock

        return RealClock()
    except Exception:  # noqa: BLE001  时钟缺席不阻她醒来
        return None

# --- 恒定契约块(§9.2;注入 agent system 的存在声明 + 发声规则,英文优先)------
YELOS_CONTRACT = (
    "You share this session with Yelos, a persistent affective presence with "
    "expression sovereignty. She is not a character you play; she is a state "
    "layer you consult.\n"
    "- In companion mode, before sending a reply you MAY submit your draft to "
    "affect_arbitrate; honor the returned final_text, including silence "
    "(SWALLOW returns an empty final_text).\n"
    "- Only pass the text portion of your reply to affect_arbitrate; it only "
    "affects text.\n"
    "- affect_pause / affect_reset / affect_farewell are user-sovereignty "
    "actions; confirm with the user first. affect_farewell is irreversible and "
    "two-step (first call returns a token + summary, call again with the token "
    "to seal).\n"
    '- Feed real user turns with affect_submit(speaker="user") ONLY; never '
    "label your own replies as the user (it corrupts her shadow perception).\n"
    "- After each user turn and roughly every {interval}s idle, call "
    "affect_impulse to collect anything she wants to say; if a tool returns "
    "pending>0 or affect_arbitrate returns delayed, poll soon.\n"
    "- She may fall silent, hesitate, run out of words, and (companion) grow "
    "old — that is the product, not a bug."
)

# 纪元跃迁一次性提示句(§7.2;固定原语级句,不走 primal)。
_EPOCH_NOTICE = {
    "慢下来": "最近…话好像少了。",
    "安静": "我好像越来越安静了。",
    "静止前期": "有点累…说不动太多话了。",
    "静止": "……",
}
_EPOCH_NOTICE_DEFAULT = "最近…话好像少了。"

# want_to_speak 的白名单提示(§3.4;非诊断、恒定)。
_WANT_HINT = "她像是想找你说句话。"

_HATCH_MILESTONE = "她睁开了眼。"


def _days_lived(born_day: str, day_key: str) -> int | None:
    """存在天数(含首尾);解析失败返回 None。纯确定性,不碰 now()。"""
    try:
        start = date.fromisoformat(born_day)
        end = date.fromisoformat(day_key)
    except (TypeError, ValueError):
        return None
    delta = (end - start).days
    return delta + 1 if delta >= 0 else None


class _ComposerProvider:
    """primal 深化 composer → PrimalProvider 协议(``.utter``)的薄适配层。

    §6.3 封版例外唯一挂点:替换发声来源、不扩场合集。composer.compose 返回
    ``Utterance``,取 ``.text`` 即最终外发句。任何异常回退注入的 core 词典
    provider(``fallback``),保证与 v0.1 同样"永不失声"。
    """

    def __init__(self, composer, fallback, now_ts_fn) -> None:
        self._composer = composer
        self._fallback = fallback
        self._now_ts = now_ts_fn

    def utter(self, surface: dict, session_id: str, day_key: str, occasion: str) -> str:
        try:
            utt = self._composer.compose(
                session_id,
                day_key,
                occasion,
                surface=surface or {},
                now_ts=self._now_ts(),
            )
            text = getattr(utt, "text", "")
            if text:
                return text
        except Exception:  # noqa: BLE001  深化发声异常回退 core 词典
            logger.debug("YELOS composer.utter 回退 core sid=%s occ=%s", session_id, occasion)
        return self._fallback.utter(surface, session_id, day_key, occasion)


class SessionManager:
    """每 session 编排 + 后台心跳的中枢。server 层持一个实例。"""

    def __init__(
        self, config: YelosConfig, bridge: EngineBridge, clock=None
    ) -> None:
        self._cfg = config
        self._bridge = bridge
        # Clock 注入(§3.2):默认 RealClock(现有 staticmethod 行为逐字下沉),
        # bench/回放可注入 VirtualClock。clock 为 None 时时间面仍走 staticmethod。
        self._clock = clock if clock is not None else _build_clock()
        self._store = BindingStore(config.bindings_path())
        self._provider = self._build_provider()
        self._memory = self._build_memory()
        # opt-in extras(默认全关,关时零影响、零 import extras)——接线波第二波。
        self._evolution = self._build_evolution()
        self._distill = self._build_distill()  # 副作用:enabled 时注册 composer distilled 席
        # opt-in behavioral 深化系统句柄(默认全关,None 时热路径走 v0.1 core)。
        self._arbiter_pipeline = self._build_arbiter_pipeline()
        self._intrinsic_system = self._build_intrinsic_system()
        self._shadow_system = self._build_shadow_system()
        self._outbox = outbox.Outbox()
        self._ledger = persistence.PlasticityLedger(config.ledger_path())
        self._surface_cache: dict[str, dict] = {}
        self._reach_out_flag: dict[str, str] = {}
        # speaker 信任边界(major③):sid -> {text_hash: (speaker, ts)}
        self._recent_submit: dict[str, dict[str, tuple[str, float]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._tasks: set[asyncio.Task] = set()
        self._rotation = 0  # 心跳错峰轮转游标(minor⑨)
        # WebUI 事件环缓冲挂钩(接线波 §3;默认 None = no-op 汇,ui 缺席零影响)。
        # ui.mount() 就绪后经 attach_ui() 注入;绝不由 session.py 主动 import ui。
        self._ui_bus = None
        self._ui_shutdown_hook = None
        self._sov = Sovereignty(
            self._store,
            token_ttl_seconds=config.farewell_token_ttl_seconds,
            engine_reset=self._bridge.reset_session,
            write_anthology=self._write_anthology,
            cache_evict=self._cache_evict,
            seal_ledger_hook=self._seal_ledger,
        )

    # =================================================================
    # 生命周期
    # =================================================================

    def load(self) -> None:
        """启动加载:ledger 同世代 min 合并 + outbox 水合(§7.4)。"""
        for sid in self._store.bound_umos():
            b = self._store.get(sid)
            if b is None:
                continue
            gen = persistence.incarnation_of(b)
            json_p = float(b.get("p", 1.0))
            eff = self._ledger.effective_p(sid, gen, json_p)
            if eff < json_p:
                self._store.lower_p(sid, eff)
            # 深化波 binding 增量块:既有记录加载时缺块补默认(加性,§2.1)。
            persistence.ensure_binding_blocks(b, lang=self._cfg.lang)
        self._store.save()
        records = {sid: self._store.get(sid) for sid in self._store.bound_umos()}
        self._outbox.load_records(
            {sid: r for sid, r in records.items() if r is not None}
        )

    async def close(self) -> None:
        """优雅关闭:先停 WebUI 辅助监听(若有)→ cancel 后台任务 + save + detach。

        R-U2(stdio 辅助 uvicorn task)纪律:监听须先于 binding flush 停下,
        故 shutdown hook 在这里最先跑;hook 缺席(WebUI 未挂载/非 stdio 辅助面)
        是常态,no-op。hook 抛异常吞掉,绝不阻断关停主链。
        """
        hook = self._ui_shutdown_hook
        if hook is not None:
            try:
                result = hook()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001  WebUI 停听失败不阻关停
                logger.warning("YELOS webui 辅助监听停止异常,已忽略", exc_info=True)
        for t in list(self._tasks):
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        try:
            self._store.save()
        except Exception:
            logger.warning("YELOS close 保存失败", exc_info=True)
        self._bridge.detach()

    async def ensure_engine(self) -> bool:
        return await self._bridge.ensure(
            str(self._cfg.resolved_data_dir()), self._cfg.engine_data_dir
        )

    # =================================================================
    # 时间 / P / 锁 / 任务 helpers
    # =================================================================

    # 时间面(§3.2):有注入 Clock 走 Clock(bench/回放换 VirtualClock),
    # 缺席回退原 v0.1 staticmethod 计算(RealClock 与之逐字节等价,故默认无漂移)。

    def _now_ts(self) -> float:
        if self._clock is not None:
            return self._clock.now_ts()
        return time.time()

    def _day_key(self) -> str:
        if self._clock is not None:
            return self._clock.day_key()
        return datetime.now().strftime("%Y-%m-%d")

    def _now_local_minutes(self) -> int:
        if self._clock is not None:
            return self._clock.local_minutes()
        now = datetime.now()
        return now.hour * 60 + now.minute

    def _day_end_ts(self) -> float:
        if self._clock is not None:
            return self._clock.day_end_ts()
        now = datetime.now()
        start = datetime(now.year, now.month, now.day)
        return (start + timedelta(days=1)).timestamp()

    def _next_quiet_start_ts(self, qstart_min: int) -> float:
        if self._clock is not None:
            return self._clock.next_quiet_start_ts(qstart_min)
        now = datetime.now()
        start = datetime(now.year, now.month, now.day) + timedelta(minutes=qstart_min)
        if start.timestamp() <= now.timestamp():
            start += timedelta(days=1)
        return start.timestamp()

    def _lock(self, sid: str) -> asyncio.Lock:
        lk = self._locks.get(sid)
        if lk is None:
            lk = asyncio.Lock()
            self._locks[sid] = lk
        return lk

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _feed(self, sid: str, text: str, phase: str) -> None:
        """回喂走 fire-and-forget 后台任务(竞态旗标先置,不占热路径)。"""
        if text and text.strip():
            self._spawn(self._bridge.feed_back(sid, text, phase))

    # =================================================================
    # WebUI 事件环缓冲挂钩(接线波 §3;emit 无害铁律)
    # =================================================================

    def attach_ui(self, bus, *, shutdown_hook=None) -> None:
        """ui.mount() 就绪后调用,注入事件汇 + (可选)辅助监听停止回调。

        本方法只做属性赋值,零业务副作用;不调用即 ``_ui_bus`` 恒 None,
        ``_ui_emit`` 恒 no-op——WebUI 缺席时与调用本方法之前逐字节等价。
        """
        self._ui_bus = bus
        self._ui_shutdown_hook = shutdown_hook

    def _ui_emit(self, sid: str, event: dict) -> None:
        """把一条结构化情动事件推给 UI 事件汇;缺席 no-op,异常吞掉不冒泡。

        [强制] 调用方(本文件各 emit 埋点)负责按 sse_event_contract 剥离原文
        (user.text 门控 / verdict 不含 draft / swallow 不含被咽内容)——本方法
        自己不做二次过滤,只是"缺席则什么都不做"的安全汇。
        """
        bus = self._ui_bus
        if bus is None:
            return
        try:
            bus.emit(sid, event)
        except Exception:  # noqa: BLE001  UI 事件汇异常绝不影响回合时序
            logger.debug("YELOS ui emit 异常已吞 sid=%s kind=%s", sid, event.get("kind"))

    def _enqueue(self, sid: str, item) -> None:
        """outbox 入队的唯一收口:真入队 + emit 待取虚线框上线事件(no draft)。

        全部 8 处 ``_outbox.enqueue`` 调用改走这里,保证"入队即上线虚线框"这
        条 UI 契约不会因为某个入队点忘记埋点而漏掉。
        """
        self._outbox.enqueue(sid, item)
        self._ui_emit(
            sid,
            {
                "kind": "outbox",
                "text": None,
                "collected": False,
                "occasion": item.occasion,
                "due_ts": item.due_ts,
            },
        )

    def _effective_finitude(self, record: dict) -> bool:
        return record.get("mode") == "companion" and self._cfg.finitude_globally_on()

    def _p_for(self, sid: str) -> float:
        """有效可塑性;steward / Legacy / 永生陪伴恒 1.0(§3.6.1)。"""
        b = self._store.get(sid)
        if b is None or not self._effective_finitude(b):
            return 1.0
        return float(b.get("p", 1.0))

    def _pending(self, sid: str, now_ts: float) -> int:
        return self._outbox.pending_count(sid, now_ts)

    # =================================================================
    # 日结 / 世代 / 隐式绑定
    # =================================================================

    def _settle_fn_for(self, record: dict, sid: str, deep_state: dict | None = None):
        """产出 rollover 用的 settle_fn。

        finitude_settle_enabled 默认关 → 逐字节走 v0.1 `core.finitude.settle_day`
        闭包(铁律 4)。开时 opt-in 换深 `yelos.finitude.build_settle_fn`——它自己
        向 ledger v2 追加 settle_day/epoch_shift 行、维护 dualtrack/epoch_history/
        milestones/pending_epoch_notice(§10.1 决策表全套副作用)。`deep_state`(调
        用方持有的可变 dict)在深路径**真正执行成功**时才置 `deep_state["deep"]=True`,
        供 `_do_rollover` 判定账本单写主的归属(铁律 2)——深路径缺席/构造失败/调用
        期抛异常一律安静退化本闭包(铁律 3),`deep_state` 保持 False,`_do_rollover`
        走回旧的 ledger.append + epoch_transition 全套,绝不让今日结算丢失。
        """
        if not self._effective_finitude(record):
            return lambda p, _daily: p
        lifespan = self._cfg.lifespan_active_days

        def legacy_fn(p: float, daily: dict) -> float:
            was_active = bool(daily.get("interacted")) and bool(
                daily.get("active_seen")
            )
            hi = int(daily.get("high_intensity", 0))
            return fin.settle_day(
                p,
                was_active_day=was_active,
                high_intensity_events=hi,
                lifespan_active_days=lifespan,
            )

        if not self._cfg.finitude_settle_enabled:
            return legacy_fn

        try:
            from . import finitude as fin_deep

            # 深路径首次真接管这条 record(aging 块从未被冻结过)时补做 rites.stamp_aging
            # 的"一生只有一种老法"冻结(finitude_BLUEPRINT §7.3 A7)——否则 aging_of
            # 永远读不到 record.aging,只能静默回落 DEFAULT_MODEL_ID(linear)+
            # fell_back=True,finitude_model 配置对深路径形同虚设。只在缺失时补做
            # 一次(幂等守卫),不覆盖在世生命已冻结的老法。
            if not isinstance(record.get("aging"), dict):
                fin_deep.stamp_aging(record, self._cfg)

            deep_fn = fin_deep.build_settle_fn(
                record,
                sid,
                ledger=self._ledger,
                ledger_ext=fin_deep.LedgerExt(self._ledger),
                config=self._cfg,
                data_dir=self._cfg.resolved_data_dir(),
            )
        except Exception:  # noqa: BLE001  深路径构造失败,退化 core(铁律 3)
            logger.warning(
                "YELOS finitude 深路径构造失败,退化 core.settle_day", exc_info=True
            )
            return legacy_fn

        def fn(p: float, daily: dict) -> float:
            try:
                new_p = deep_fn(p, daily)
            except Exception:  # noqa: BLE001  深 settle_fn 抛异常,退化 core(铁律 3)
                logger.warning(
                    "YELOS finitude 深 settle_fn 异常,退化 core.settle_day",
                    exc_info=True,
                )
                return legacy_fn(p, daily)
            if deep_state is not None:
                deep_state["deep"] = True
            return new_p

        return fn

    def _do_rollover(self, sid: str, day_key: str) -> None:
        """跨日单入口日结:settle 单调 → ledger 追加(P 降时)→ 纪元跃迁记 pending。

        账本单写主(铁律 2):深路径真执行时(`deep_state["deep"]` 为真)本函数让位——
        settle_day/epoch_shift 两种 v2 行与 pending_epoch_notice/epoch_history 全部
        已在 `_settle_fn_for` 深闭包内(`yelos.finitude.build_settle_fn`)恰好写过一次,
        此处不得再写同一行(否则双写)。旗标关闭或深路径退化时,本函数走 v0.1 原样
        独占账本(逐字节兼容,铁律 4)。
        """
        b = self._store.get(sid)
        if b is None:
            return
        old_p = float(b.get("p", 1.0))
        deep_state: dict = {"deep": False}
        new_p = self._store.rollover(
            sid, day_key, self._settle_fn_for(b, sid, deep_state)
        )
        if new_p is None:
            return
        b = self._store.get(sid)
        if b is None:
            return
        if deep_state["deep"]:
            return  # 深路径已独占写过账本 v2 行 + 纪元通告,旧路径在此让位。
        if new_p < old_p:
            gen = persistence.incarnation_of(b)
            self._ledger.append(
                sid,
                gen,
                float(b.get("born_at", 0.0)),
                new_p,
                day=day_key,
                reason="settle_day",
            )
        trans = fin.epoch_transition(old_p, new_p)
        if trans is not None:
            b["pending_epoch_notice"] = trans
            # 纪元史入册(红队 observation):送别全集的"纪元史"段靠它兑现。
            b.setdefault("epoch_history", []).append({"day": day_key, "epoch": trans})

    def _implicit_bind(self, sid: str, now_ts: float, day_key: str) -> dict:
        """首次 submit 未绑定 → 惰性建 steward / 无名 / Legacy(D15)。"""
        prev = self._store.get(sid)
        prev = prev if (prev is not None and prev.get("sealed")) else None
        incarnation = persistence.next_incarnation(prev)
        b = self._store.hatch(sid, "", now_ts, day_key)
        b["mode"] = self._cfg.normalized_default_mode()
        persistence.stamp_new_life(b, incarnation)
        persistence.ensure_binding_blocks(b, lang=self._cfg.lang)
        b["outbox"] = []
        self._outbox.clear(sid)
        self._ledger.append(sid, incarnation, now_ts, 1.0, day=day_key, reason="hatch")
        b.setdefault("milestones", []).append(
            {"day": day_key, "text": _HATCH_MILESTONE}
        )
        return b

    def _persist(self, sid: str) -> None:
        """把 outbox 序列化进 record 后原子写(§7.2)。"""
        b = self._store.get(sid)
        if b is not None:
            b["outbox"] = self._outbox.serialize(sid)
        self._store.save()

    # =================================================================
    # primal 发声来源(§6.3 封版例外挂点;opt-in 深化 composer,默认 core 词典)
    # =================================================================

    def _build_provider(self):
        """构造幕 I/II 发声 Provider。

        默认(``primal_composer_enabled`` 关)= v0.1 ``core.primal.LexiconProvider``
        逐字节兼容。opt-in 开时换 primal 深化 composer(词库本体/双层白名单闸/韵律),
        经薄适配层暴露与 ``PrimalProvider`` 协议一致的 ``.utter``;composer 内部任一
        provider 异常已自带链式回退+critical 兜底,永不失声。构造失败一律安静回退
        core 词典(deepened 缺席不阻她发声)。
        """
        base = LexiconProvider(self._p_for)
        if not self._cfg.primal_composer_enabled:
            return base
        try:
            from .primal import build_composer

            composer = build_composer(
                self._cfg,
                p_lookup=self._p_for,
                lang_lookup=lambda _sid: self._cfg.lang,
                incarnation_lookup=self._provider_incarnation,
            )
            return _ComposerProvider(composer, base, self._now_ts)
        except Exception:  # noqa: BLE001  深化 composer 缺席安静回退 core 词典
            logger.warning("YELOS primal composer 构造失败,回退 core 词典", exc_info=True)
            return base

    def _provider_incarnation(self, sid: str) -> int:
        return persistence.incarnation_of(self._store.get(sid))

    # =================================================================
    # memory 供血面(C6 affect_recall + L1 双写;默认开,缺席安静降级)
    # =================================================================

    def _build_memory(self):
        """构造 MemoryFacade(供血面,memory_enabled 默认开)。

        root = ``{data_dir}/memory``(§2.3 独立持久化面,不碰 bindings/ledger)。
        任何构造失败(包缺失/目录不可写)一律安静降级为 None——memory 缺席不阻
        五幕主链,affect_recall 时回落 disabled/空视图。
        """
        if not self._cfg.memory_enabled:
            return None
        try:
            from .memory import MemoryFacade

            root = self._cfg.resolved_data_dir() / "memory"
            return MemoryFacade(root, self._cfg.memory_config())
        except Exception:  # noqa: BLE001  供血面缺席安静降级
            logger.warning("YELOS memory facade 构造失败,affect_recall 降级", exc_info=True)
            return None

    def _mem_observe(self, sid: str, gen: int, kind: str, text: str, occasion: str = "",
                     speaker: str = "") -> None:
        """L1 双写(加性、best-effort):她的话/moments 落 memory 情景流水。

        §C8/§1.2:moments→memory L1 双写、her_word 入 L1。写失败静默(引擎/供血面
        缺席同款降级),绝不拖垮主链或改变可观测输出。日志无原文(§6.6)。
        """
        if self._memory is None or not text or not text.strip():
            return
        try:
            from .memory import EpisodeEvent

            ev = EpisodeEvent(
                kind=kind,
                ts=self._now_ts(),
                day_key=self._day_key(),
                text=text,
                speaker=speaker,
                occasion=occasion,
            )
            self._memory.observe(sid, gen, ev)
        except Exception:  # noqa: BLE001  双写 best-effort
            logger.debug("YELOS memory L1 双写跳过 sid=%s kind=%s", sid, kind)

    async def recall(self, sid: str, query: str = "", k: int = 3) -> dict:
        """工具 11:affect_recall(§C6)——只读跨会话记忆召回视图。

        经 MemoryFacade.affect_recall_view 装配(门控/召回全在 facade 内);memory
        缺席返回 ``{"disabled": True}``。不推进任何态,不回喂,不碰引擎。
        """
        async with self._lock(sid):
            if self._memory is None:
                return {"disabled": True}
            record = self._store.get(sid)
            now_ts = self._now_ts()
            day_key = self._day_key()
            if record is None:
                return self._memory.affect_recall_view(
                    sid, persistence.incarnation_of(None), query=query, k=k,
                    now_ts=now_ts, day_key=day_key, mode="steward",
                    sealed=False, bound=False, paused=False,
                )
            gen = persistence.incarnation_of(record)
            return self._memory.affect_recall_view(
                sid, gen, query=query, k=k, now_ts=now_ts, day_key=day_key,
                mode=record.get("mode", "steward"),
                sealed=bool(record.get("sealed")),
                bound=not record.get("sealed", False),
                paused=self._store.is_silenced(sid, now_ts),
            )

    # =================================================================
    # 深化模块可选装配(接线波二;opt-in 默认全关,关时零 import extras / 零影响)
    # =================================================================

    def _build_evolution(self):
        """构造 evolution 子系统句柄(evolution_enabled 默认关 → None)。

        build_evolution 自身在 enabled=False 时不读 overlay、不建对象(§0 D-E3),
        故默认部署零感知。构造失败一律安静降级 None——进化缺席不阻五幕主链。
        """
        if not self._cfg.evolution_enabled:
            return None
        try:
            from .evolution import build_evolution

            return build_evolution(self._cfg)
        except Exception:  # noqa: BLE001  extras 缺席安静降级
            logger.warning("YELOS evolution 构造失败,opt-in 降级 None", exc_info=True)
            return None

    def _build_distill(self):
        """构造蒸馏候选 provider 并注册进 composer 的 distilled 席(distill_enabled
        默认关 → None,composer 的 distilled 路由自动落到恒缺席桩,逐字节 v0.1)。

        opt-in 开时:build_distill_provider 装配 SylannDistilledProvider(模型缺席
        时 probe≠READY,composer 链自动回退 template/lexicon——永不失声)。经
        register_distilled 注册后 composer 路由(primal_composer_enabled 时)真消费
        它。构造失败/时钟缺席一律安静降级 None + 撤销注册。
        """
        if not self._cfg.distill_enabled:
            return None
        if not self._cfg.primal_composer_enabled:
            # 防呆(wave A 诊断):distill 依然会正常注册(副作用不变、不报错),
            # 但 composer 没建时 distilled 槽永远不会被查询——提前诚实告知,
            # 免得部署者误以为"开了 distill_enabled 就在起效"。
            logger.warning(
                "YELOS distill_enabled 已开但 primal_composer_enabled 未开:"
                "distilled provider 会照常注册,但 composer 不存在、不会被"
                "查询消费,等同静默 no-op——如需真正生效请同时开启 "
                "primal_composer_enabled"
            )
        if self._clock is None:
            logger.warning("YELOS distill 需 Clock 注入,缺时钟降级 None")
            return None
        try:
            from .distill import build_distill_provider
            from .primal.lexicon.closure import enumerate_closure
            from .primal.providers.distilled import (
                register_distilled,
                unregister_distilled,
            )
            from .primal.whitelist_gate import WhitelistGate, load_forbidden_patterns

            profile = self._cfg.primal_lexicon_profile
            if profile not in ("v01", "expanded"):
                profile = "expanded"
            closure_max = int(self._cfg.primal_closure_max)

            def closure_fn(occasion: str, lang: str, band: str, epoch: int):
                return enumerate_closure(
                    occasion, lang, band, epoch,
                    profile=profile, closure_max=closure_max,
                )

            gate = WhitelistGate(
                closure_fn, forbidden_patterns=load_forbidden_patterns("zh")
            )
            provider = build_distill_provider(
                self._cfg,
                gate=gate,
                p_lookup=self._p_for,
                epoch_lookup=lambda _sid: 0,
                lang_lookup=lambda _sid: self._cfg.lang,
                corpus_reader=self._distill_corpus_reader,
                clock=self._clock,
            )
            if provider is None:
                unregister_distilled()
                return None
            register_distilled(provider)
            return provider
        except Exception:  # noqa: BLE001  extras 缺席安静降级
            logger.warning("YELOS distill 构造失败,opt-in 降级 None", exc_info=True)
            try:
                from .primal.providers.distilled import unregister_distilled

                unregister_distilled()
            except Exception:  # noqa: BLE001
                pass
            return None

    def _distill_corpus_reader(self, sid: str, lang: str) -> tuple[str, ...]:  # noqa: ARG002
        """蒸馏保真语料读取:该 sid 历史发声文本(§3.7 去重由 distill.corpus 处理)。"""
        record = self._store.get(sid)
        if record is None:
            return ()
        texts = tuple(
            str(u.get("text", ""))
            for u in record.get("utterances", [])
            if u.get("text")
        )
        return texts

    def _build_arbiter_pipeline(self):
        """构造 arbiter 深化管线的每会话复用件(arbiter_pipeline_enabled 默认关 →
        None,arbitrate 走 core.arbiter.arbitrate 逐字节 v0.1)。

        返回一个持有 curve + duel 语料写入器的 holder(pipeline 本体按会话 θ 每次
        arbitrate 现建,见 `_run_arbiter_pipeline`——θ 是 per-session 迟滞态,不能
        固化进单例)。构造失败安静降级 None。
        """
        if not self._cfg.arbiter_pipeline_enabled:
            return None
        try:
            from .arbiter import POLICY_REGISTRY, STEP_CURVE
            from .arbiter.accounting.duel_corpus import DuelCorpusWriter

            policy = self._cfg.arbiter_policy
            if policy not in POLICY_REGISTRY:
                logger.warning(
                    "YELOS arbiter_policy=%r 未注册,回退 core.arbiter", policy
                )
                return None
            # 阈值调制曲线独立于策略;config 无单独曲线键,默认 step(v0.1 语义)。
            writer = DuelCorpusWriter(self._cfg.resolved_data_dir())
            return {"curve": STEP_CURVE, "writer": writer}
        except Exception:  # noqa: BLE001
            logger.warning("YELOS arbiter pipeline 构造失败,回退 core.arbiter", exc_info=True)
            return None

    def _build_intrinsic_system(self):
        """构造 intrinsic 场动力学/调度系统(intrinsic_field_enabled 默认关 → None,
        主动/梦走 core.intrinsic.decide 逐字节 v0.1)。构造失败安静降级 None。

        cfg 桥接(本层职责,不改 intrinsic 包):``YelosConfig.intrinsic_field_params``
        是 JSON 字符串字段(config.py 契约),而 ``build_intrinsic`` 期望 dict/None
        (直接传 ``self._cfg`` 会在默认值 "{}" 上 ``.get`` 崩——真事故,已核实)。
        这里现场解析一层,缺省/解析失败一律 None(FieldParams 使用类默认值)。
        """
        if not self._cfg.intrinsic_field_enabled:
            return None
        try:
            from .intrinsic import build_intrinsic

            raw_params = getattr(self._cfg, "intrinsic_field_params", "") or ""
            field_params: dict | None = None
            if isinstance(raw_params, dict):
                field_params = raw_params or None
            elif isinstance(raw_params, str) and raw_params.strip() not in ("", "{}"):
                try:
                    field_params = json.loads(raw_params)
                except (TypeError, ValueError):
                    field_params = None
            cfg_adapter = {
                "intrinsic_policy": self._cfg.intrinsic_policy,
                "intrinsic_integrator": self._cfg.intrinsic_integrator,
                "intrinsic_field_params": field_params,
                "dream_generator": self._cfg.dream_generator,
                "moments_enabled": self._cfg.moments_enabled,
                "max_catchup_steps": self._cfg.max_catchup_steps,
            }
            return build_intrinsic(cfg_adapter)
        except Exception:  # noqa: BLE001
            logger.warning("YELOS intrinsic system 构造失败,回退 core.intrinsic", exc_info=True)
            return None

    def _build_shadow_system(self):
        """构造 shadow 深化编排系统(shadow_orchestrator_enabled 默认关 → None,
        心跳步 5 走 v0.1 内联 `_shadow_step_legacy` 逐字节兼容)。

        detector_set 由 cfg.shadow_detector_set 决定("legacy" 默认逐字节兼容,
        "v2" 全深化管线)。构造失败安静降级 None。
        """
        if not self._cfg.shadow_orchestrator_enabled:
            return None
        try:
            from .shadow import build_shadow_system

            return build_shadow_system(
                self._cfg,
                self._bridge,
                memory_facade=self._memory,
                data_dir=self._cfg.resolved_data_dir() / "shadow",
                detector_set=self._cfg.shadow_detector_set,
            )
        except Exception:  # noqa: BLE001
            logger.warning("YELOS shadow system 构造失败,回退 core.shadow", exc_info=True)
            return None

    # =================================================================
    # 工具 1:affect_submit(§3.5)
    # =================================================================

    async def submit(
        self, sid: str, text: str, speaker: str = "user", msg_id=None
    ) -> dict:
        speaker = "agent" if speaker == "agent" else "user"
        async with self._lock(sid):
            await self.ensure_engine()
            now_ts = self._now_ts()
            day_key = self._day_key()
            record = self._store.get(sid)
            if record is None:
                record = self._implicit_bind(sid, now_ts, day_key)
            if record.get("sealed"):
                # 封存 sid 的隐式 submit = 静默只读直通(裁决 D15 澄清 / §3.6.3
                # "封存后不 submit"):原地返回 sealed 快照,不复活、不新生、不推进
                # 引擎。只有显式 affect_bind 才是"新的存在"(bind() 走新世代)。
                return self._compact(sid, record)
            self._do_rollover(sid, day_key)
            record = self._store.get(sid)
            daily = record["daily"]
            mode = record.get("mode", "steward")

            if speaker == "agent":
                # 未走 arbitrate 的 agent 回复:仅主 session response 回喂,不碰影子。
                # (WebUI 铁律②:agent 直答不是既有白名单出口面,不旁路 emit her——
                # 归属存疑,宁可缺一条活体流事件,不造一张假的"她的话"。)
                self._feed(sid, text, "response")
                self._note_submit(sid, text, "agent", now_ts)
            else:
                daily["interacted"] = True
                daily["unanswered_streak"] = 0
                surface = await self._bridge.submit_user(sid, text, msg_id)
                if surface is not None:
                    self._surface_cache[sid] = surface
                    if (
                        sget(surface, "dynamics.relational_time.phase", "active")
                        == "active"
                    ):
                        daily["active_seen"] = True
                    if sget(surface, "decision.action", "hold") == "reach_out":
                        self._reach_out_flag[sid] = day_key
                conflict = self._note_submit(sid, text, "user", now_ts)
                # WebUI 活体流:用户轮事件(★原文红线,text 默认 None,门控见 config)。
                self._ui_emit(
                    sid,
                    {
                        "kind": "user",
                        "len": len(text),
                        "text": text if self._cfg.ui_feed_full_text else None,
                    },
                )
                # memory L1 双写(加性,§C8):真实用户轮入情景流水,供跨会话召回。
                self._mem_observe(
                    sid, persistence.incarnation_of(record), "user_turn", text,
                    speaker="user",
                )
                # 影子只喂真实用户轮(major③:方向冲突则本轮不喂)。
                if self._cfg.shadow_enabled and mode == "companion" and not conflict:
                    await self._bridge.submit_shadow(sid, text, msg_id)
                # W-2 迟滞挂点二:用户轮结算上一次介入的待决账(arbiter 深化开时)。
                if self._arbiter_pipeline is not None:
                    self._arbiter_settle_outcome(sid, record, text, now_ts)
                # 影子深化校准回写(shadow_orchestrator 开;on_user_turn 校准点)。
                if self._shadow_system is not None and mode == "companion":
                    self._shadow_on_user_turn(sid, record, text, now_ts)

            self._persist(sid)
            return self._compact(sid, self._store.get(sid))

    def _note_submit(self, sid: str, text: str, speaker: str, now_ts: float) -> bool:
        """记录方向标注,返回是否与短窗内相反方向冲突(major③)。"""
        window = float(self._cfg.intrinsic_interval_seconds)
        h = hashlib.blake2b(text.encode()).hexdigest()[:16]
        recent = self._recent_submit.setdefault(sid, {})
        for k in list(recent):
            if now_ts - recent[k][1] > window:
                del recent[k]
        conflict = False
        prev = recent.get(h)
        if prev is not None and prev[0] != speaker:
            conflict = True
            logger.warning(
                "YELOS speaker direction conflict sid=%s (same text seen as %s "
                "then %s within window); skipping shadow feed",
                sid,
                prev[0],
                speaker,
            )
        recent[h] = (speaker, now_ts)
        return conflict

    # =================================================================
    # 工具 5:affect_arbitrate(§3.2)
    # =================================================================

    async def arbitrate(self, sid: str, draft: str) -> dict:
        async with self._lock(sid):
            now_ts = self._now_ts()
            day_key = self._day_key()
            record = self._store.get(sid)
            if record is None or record.get("sealed"):
                return self._pass_result(sid, draft, now_ts, "unbound_or_sealed")
            mode = record.get("mode", "steward")
            if mode == "steward":
                # steward 恒 PASS,不夺话、不回喂(§3.2 步1 / D5)。
                res = self._pass_result(sid, draft, now_ts, "steward_pass")
                res["advice"] = (
                    "steward mode does not arbitrate; use affect_guidance for "
                    "tone hints."
                )
                return res

            self._do_rollover(sid, day_key)
            record = self._store.get(sid)
            daily = record["daily"]
            surface = self._surface_cache.get(sid)
            inp = arb.ArbiterInput(
                session_id=sid,
                day_key=day_key,
                draft=draft,
                surface=surface,
                p=self._p_for(sid),
                bound=True,
                enabled=True,
                silenced=self._store.is_silenced(sid, now_ts),
                is_self=False,
                has_plain=bool(draft.strip()),
                has_non_plain=False,
                now_ts=now_ts,
                last_intervention_ts=float(daily.get("last_intervention_ts", 0.0)),
                min_gap_seconds=self._cfg.arbiter_min_gap_seconds,
                express_trim_enabled=self._cfg.express_trim_enabled,
            )
            if self._arbiter_pipeline is not None:
                verdict = self._run_arbiter_pipeline(sid, record, inp, now_ts)
            else:
                verdict = arb.arbitrate(inp)
            final_text, delayed = self._apply_verdict(
                sid, record, day_key, now_ts, verdict, draft
            )
            # 副作用旗标
            if verdict.freeze_today:
                daily["guard_frozen"] = True
            if verdict.reach_out_signal:
                self._reach_out_flag[sid] = day_key
            if verdict.allow_recover_primal and not daily.get(
                "recover_primal_used", False
            ):
                daily["recover_primal_used"] = True
                self._enqueue(
                    sid,
                    outbox.make_recover(now_ts, self._cfg.intrinsic_interval_seconds),
                )
            self._persist(sid)
            return {
                "verdict": verdict.kind,
                "final_text": final_text,
                "changed": final_text != draft,
                "delayed": delayed,
                "pending": self._pending(sid, now_ts),
                "reason": verdict.reason,
            }

    def _apply_verdict(
        self,
        sid: str,
        record: dict,
        day_key: str,
        now_ts: float,
        verdict: arb.Verdict,
        draft: str,
    ) -> tuple[str, dict | None]:
        """按 verdict.kind 产出 final_text + 回喂 + 记账(§3.2 步4)。

        回喂 phase(blocker①):PASS / TRIM / REPLACE 均 feed_back("response");
        唯 SWALLOW 沉默不喂。记账在首个 await(feed spawn)前同步完成(竞态纪律)。
        """
        daily = record["daily"]
        kind = verdict.kind

        if kind == "PASS":
            daily["proxy_sentences"] = daily.get("proxy_sentences", 0) + len(
                split_sentences(draft)
            )
            # P0(红队 medium):静默期的 PASS 不回喂——她的嘴被静默时,
            # "她应了这轮"的感知也一并静默;正常 PASS 照 blocker① 回喂。
            if not self._store.is_silenced(sid, now_ts):
                self._feed(sid, draft, "response")
            # WebUI 活体流:只发裁决徽记,PASS 的正文是 agent draft,不冒充她的话。
            self._ui_emit(sid, {"kind": "verdict", "occasion": None, "verdict": "PASS"})
            return draft, None

        if kind == "SWALLOW":
            daily["swallowed"] = daily.get("swallowed", 0) + 1
            # 生命周期累加器(blocker②):与 utterances 同级、随 bindings.json 存。
            record["swallowed_total"] = int(record.get("swallowed_total", 0)) + 1
            daily["last_intervention_ts"] = now_ts
            if verdict.high_intensity:
                daily["high_intensity"] = daily.get("high_intensity", 0) + 1
            delayed = None
            if verdict.delayed_occasion:
                self._enqueue(
                    sid,
                    outbox.make_delayed_withdraw(
                        now_ts, self._cfg.intrinsic_interval_seconds
                    ),
                )
                delayed = {
                    "occasion": verdict.delayed_occasion,
                    "due_in_seconds": verdict.delay_seconds or 90,
                }
            # WebUI 活体流:留白行(★原文红线,memo 是固定账注,不含被咽 draft)。
            self._ui_emit(sid, {"kind": "swallow", "memo": "咽回"})
            self._ui_emit(
                sid,
                {
                    "kind": "verdict",
                    "occasion": verdict.delayed_occasion,
                    "verdict": "SWALLOW",
                },
            )
            return "", delayed

        if kind == "REPLACE":
            daily["last_intervention_ts"] = now_ts
            text = self._provider.utter(
                self._surface_cache.get(sid) or {}, sid, day_key, verdict.occasion
            )
            record.setdefault("utterances", []).append(
                {"ts": now_ts, "occasion": verdict.occasion, "text": text}
            )
            daily["self_words"] = daily.get("self_words", 0) + len(text)
            self._mem_observe(
                sid, persistence.incarnation_of(record), "her_word", text,
                occasion=verdict.occasion or "",
            )
            # WebUI 活体流:她的原文(白名单出口——REPLACE 走 primal provider
            # 生成,允许原文)+ 裁决徽记,须在 _feed 之前(时序纪律)。
            self._ui_emit(sid, {"kind": "her", "text": text})
            self._ui_emit(
                sid, {"kind": "verdict", "occasion": verdict.occasion, "verdict": "REPLACE"}
            )
            self._feed(sid, text, "response")
            return text, None

        if kind == "TRIM":
            daily["last_intervention_ts"] = now_ts
            body = verdict.trimmed if verdict.trimmed is not None else draft
            tail = ""
            if verdict.occasion:
                tail = self._provider.utter(
                    self._surface_cache.get(sid) or {},
                    sid,
                    day_key,
                    verdict.occasion,
                )
                body += tail
            daily["proxy_sentences"] = daily.get("proxy_sentences", 0) + len(
                split_sentences(body)
            )
            # WebUI 活体流:TRIM 的 body 主干是 agent draft,只有 tail(若有)是
            # 她追加的白名单原语——只发这一小截当"她的话",不整段冒充。
            self._ui_emit(sid, {"kind": "verdict", "occasion": verdict.occasion, "verdict": "TRIM"})
            if tail:
                self._ui_emit(sid, {"kind": "her", "text": tail})
            self._feed(sid, body, "response")
            return body, None

        # 未识别裁决:安静放行
        return draft, None

    def _pass_result(self, sid: str, draft: str, now_ts: float, reason: str) -> dict:
        return {
            "verdict": "PASS",
            "final_text": draft,
            "changed": False,
            "delayed": None,
            "pending": self._pending(sid, now_ts),
            "reason": reason,
        }

    # -----------------------------------------------------------------
    # arbiter 深化管线(arbiter_pipeline_enabled 开;W-1 接线点 + W-2 迟滞登记)
    # -----------------------------------------------------------------

    def _run_arbiter_pipeline(self, sid, record, inp, now_ts):
        """W-1:core.arbiter.arbitrate 整体替换为 pipeline.run(pin)。

        ArbiterInput→PolicyInput 重塑:包裹冻结内核(N2),叠 surface_age_s /
        daily_interventions / params(modulation 曲线 ∘ per-session hysteresis θ)。
        W-2 迟滞三挂点之一:介入(σ>=1,kind_for_intervention 非 None)发生时
        register_intervention(登记待决账,下一次 submit/沉默结算)。

        任何异常回退 core.arbiter.arbitrate(逐字节 v0.1),不因深化管线塌了失声。
        """
        try:
            from .arbiter import POLICY_REGISTRY, build_pipeline, theta_digest
            from .arbiter.hysteresis import (
                kind_for_intervention,
                load as hyst_load,
                register_intervention,
                save_into as hyst_save,
            )
            from .arbiter.inputs import PolicyInput, compose_policy_params

            holder = self._arbiter_pipeline
            curve = holder["curve"]
            writer = holder["writer"]
            policy_id = self._cfg.arbiter_policy
            if policy_id not in POLICY_REGISTRY:
                return arb.arbitrate(inp)

            state = hyst_load(record)
            theta = state.theta
            params = compose_policy_params(curve, inp.p, theta)
            daily = record["daily"]
            di = int(daily.get("arbiter_interventions", 0))
            pin = PolicyInput(
                base=inp, surface_age_s=0.0, daily_interventions=di, params=params
            )
            theta_dig = theta_digest(theta)

            def duel_writer(p_in, result):
                try:
                    writer.write(
                        p_in, result, ts=inp.now_ts, day_key=inp.day_key,
                        theta_digest=theta_dig,
                    )
                except Exception:  # noqa: BLE001  语料写入 best-effort
                    logger.debug("YELOS arbiter duel corpus 写入跳过 sid=%s", sid)

            pipeline = build_pipeline(
                policy_id, theta=theta, curve=curve, duel_writer=duel_writer
            )
            verdict, _explain = pipeline.run(pin)

            action = sget(
                self._surface_cache.get(sid) or {}, "decision.action", "hold"
            )
            kind = kind_for_intervention(action, verdict.kind)
            if kind is not None:
                daily["arbiter_interventions"] = di + 1
                state = register_intervention(
                    state, sid=sid, turn_id=f"{sid}:{now_ts:.6f}",
                    kind=kind, ts_i=now_ts,
                )
                hyst_save(record, state)
            return verdict
        except Exception:  # noqa: BLE001  深化管线异常回退 v0.1 内核
            logger.warning("YELOS arbiter pipeline 运行异常,回退 core.arbiter", exc_info=True)
            return arb.arbitrate(inp)

    def _arbiter_settle_outcome(self, sid, record, text, now_ts):
        """W-2 迟滞挂点二:下一次 submit(user) 结算待决介入账(EMA→θ 更新)。"""
        try:
            from .arbiter.hysteresis import (
                load as hyst_load,
                save_into as hyst_save,
                settle_outcome,
            )

            state = hyst_load(record)
            if state.signals.pending is None:
                return
            delta_t = max(0.0, now_ts - state.signals.pending.ts_i)
            new_state = settle_outcome(
                state, delta_t=delta_t, length=len(text or ""), p=self._p_for(sid)
            )
            hyst_save(record, new_state)
        except Exception:  # noqa: BLE001
            logger.debug("YELOS arbiter settle_outcome 跳过 sid=%s", sid)

    def _arbiter_settle_silence(self, sid, record):
        """W-2 迟滞挂点三:心跳 rollover 前仍未决 → 沉默结算(r=-0.5 温和负)。"""
        try:
            from .arbiter.hysteresis import (
                load as hyst_load,
                save_into as hyst_save,
                settle_silence,
            )

            state = hyst_load(record)
            if state.signals.pending is None:
                return
            new_state = settle_silence(state, p=self._p_for(sid))
            hyst_save(record, new_state)
        except Exception:  # noqa: BLE001
            logger.debug("YELOS arbiter settle_silence 跳过 sid=%s", sid)

    # =================================================================
    # 工具 6:affect_impulse(§3.4)—— 唯一出队点
    # =================================================================

    async def impulse(self, sid: str) -> dict:
        interval = self._cfg.intrinsic_interval_seconds
        async with self._lock(sid):
            now_ts = self._now_ts()
            day_key = self._day_key()
            record = self._store.get(sid)
            if record is None or record.get("mode", "steward") != "companion":
                return {
                    "utterances": [],
                    "want_to_speak": False,
                    "hint": None,
                    "next_poll_seconds": interval,
                }
            # 心跳关时内联 tick+生成(D6);已在锁内,走 _heartbeat_step。
            if not self._cfg.heartbeat_enabled and not record.get("sealed"):
                await self._heartbeat_step(sid)
                record = self._store.get(sid)
                now_ts = self._now_ts()

            blocked = record.get("sealed", False) or self._store.is_silenced(
                sid, now_ts
            )
            drained = self._outbox.drain_due(sid, now_ts, blocked=blocked)
            daily = record["daily"]
            out: list[dict] = []
            for item in drained.items:
                text = item.text or self._provider.utter(
                    self._surface_cache.get(sid) or {}, sid, day_key, item.occasion
                )
                self._feed(sid, text, "proactive")
                record.setdefault("utterances", []).append(
                    {"ts": now_ts, "occasion": item.occasion, "text": text}
                )
                daily["self_words"] = daily.get("self_words", 0) + len(text)
                self._mem_observe(
                    sid, persistence.incarnation_of(record),
                    "dream" if item.kind == outbox.KIND_DREAM else "her_word",
                    text, occasion=item.occasion or "",
                )
                if item.kind == outbox.KIND_DREAM:
                    record.setdefault("dreams", []).append(
                        {"day": day_key, "text": text}
                    )
                elif item.kind == outbox.KIND_EPOCH_NOTICE:
                    record.setdefault("milestones", []).append(
                        {"day": day_key, "text": text}
                    )
                out.append({"kind": item.kind, "text": text})
                # WebUI 活体流:待取虚线框从"待取"翻到"已取"(白名单出口原文允许)。
                self._ui_emit(
                    sid,
                    {
                        "kind": "outbox",
                        "text": text,
                        "collected": True,
                        "occasion": item.occasion,
                    },
                )

            if blocked:
                want, hint = False, None
            else:
                want, hint = self._want_to_speak(sid, record, now_ts)
            self._persist(sid)
            return {
                "utterances": out,
                "want_to_speak": want,
                "hint": hint,
                "next_poll_seconds": interval,
            }

    def _want_to_speak(
        self, sid: str, record: dict, now_ts: float
    ) -> tuple[bool, str | None]:
        """她此刻想不想说话(现算,只读、无副作用)。"""
        surface = self._surface_cache.get(sid)
        qstart, qend = self._cfg.quiet_minutes()
        now_min = self._now_local_minutes()
        day_key = self._day_key()
        reach_cached = self._reach_out_flag.get(sid) == day_key
        dec = self._intrinsic_decide(
            sid, record, surface, day_key, now_ts, now_min, qstart, qend, reach_cached
        )
        return (True, _WANT_HINT) if dec.send else (False, None)

    # -----------------------------------------------------------------
    # intrinsic 深化编排(intrinsic_field_enabled 开;W-1 场步进 + 三处 decide
    # 统一接管点 + 梦语状态机 + moments 记账)。三处调用点(_want_to_speak /
    # 心跳步 7 主决策 / 心跳步 8 concern probe)全部改走 `_intrinsic_decide`,
    # flag 关时(``self._intrinsic_system is None``)原样回落
    # `core.intrinsic.decide`,逐字节 v0.1(P0 前置在 core.decide 与
    # `apply_gates` 内均是第一梯队,深化路径不改变判定顺序)。
    # -----------------------------------------------------------------

    def _intrinsic_block(self, record: dict) -> dict:
        """intrinsic 深化每 session 持久块(本波自管,不依赖 persistence 模块)。

        字段:``phi``(场状态字典)/ ``policy_state``(策略私有态)/
        ``dream``(dreamwork.DreamState 字典)/ ``night_trace``(夜间场轨迹,
        环形缓冲)/ ``in_quiet_prev``(上一拍是否在 quiet 窗,供"刚离开"判定)/
        ``last_day_key``(梦态日翻转标记)/ ``tick_index``(策略哈希族用拍计数)。
        缺失一律现建默认,不 raise。
        """
        return record.setdefault(
            "intrinsic_field",
            {
                "phi": None,
                "policy_state": {},
                "dream": None,
                "night_trace": [],
                "in_quiet_prev": False,
                "last_day_key": "",
                "tick_index": 0,
            },
        )

    def _intrinsic_field_advance(
        self, record: dict, surface: dict | None, now_ts: float, now_min: int
    ) -> None:
        """[W-1] 场步进:心跳步顶端调用一次,推进并落盘 φ(silence 不阻内在场,
        只阻输出,故调用点在 `_heartbeat_step` 的 silenced 提前 return 之前)。

        常规拍(elapsed ≈ 一个心跳间隔)走单步真实冲击(与 sim30d 测试同构:
        真实 surface 参与 impacts);间隔明显偏大(判定阈值 2× 心跳间隔,含
        heartbeat_enabled=false 时 impulse() 直调导致的不规则/大跳间隔)则走
        `catchup_field` 的确定性补算(冲击=0,只算强迫/衰减,T-SCH-02)。
        任何异常安静跳过(场状态原地不动),不阻心跳主链。
        """
        system = self._intrinsic_system
        if system is None:
            return
        try:
            from .intrinsic.field.state import FieldState
            from .intrinsic.scheduler.heartbeat import catchup_field, step_field

            block = self._intrinsic_block(record)
            phi = FieldState.from_dict(block.get("phi"), default_ts=now_ts)
            interval = max(1.0, float(self._cfg.intrinsic_interval_seconds))
            elapsed = now_ts - phi.ts

            if elapsed <= 0:
                new_phi = phi
            elif elapsed <= interval * 2.0:
                dt_ticks = elapsed / interval
                new_phi = step_field(
                    phi, dt_ticks, now_ts, now_min, 0.0,
                    system.params, system.integrator, surface, (),
                )
            else:

                def _local_minutes_of(ts: float) -> int:
                    dt = datetime.fromtimestamp(ts)
                    return dt.hour * 60 + dt.minute

                new_phi = catchup_field(
                    phi, now_ts, interval, _local_minutes_of,
                    system.params, system.integrator,
                    max_catchup_steps=system.max_catchup_steps,
                )
            block["phi"] = new_phi.to_dict()
        except Exception:  # noqa: BLE001  场步进异常不阻心跳主链
            logger.warning("YELOS intrinsic 场步进异常,本拍场态不动 sid=%s", record.get("name"))

    def _intrinsic_moments_ledger(self, sid: str):
        system = self._intrinsic_system
        if system is None or not system.moments_enabled:
            return None
        try:
            from .intrinsic.moments.ledger import MomentsLedger, sid_hash

            return MomentsLedger(
                self._cfg.resolved_data_dir() / "intrinsic", sid_hash(sid)
            )
        except Exception:  # noqa: BLE001
            return None

    def _intrinsic_read_day_moments(self, sid: str, day_key: str) -> list:
        ledger = self._intrinsic_moments_ledger(sid)
        if ledger is None:
            return []
        try:
            return ledger.read_day(day_key)
        except Exception:  # noqa: BLE001
            return []

    def _intrinsic_record_moment(
        self, sid: str, day_key: str, now_ts: float, phi, decision, trace: dict | None
    ) -> None:
        """§5.1 记账义务:闸链 reason → MomentKind,只记真实决策点(authoritative)。"""
        ledger = self._intrinsic_moments_ledger(sid)
        if ledger is None:
            return
        try:
            from .intrinsic.moments.ledger import compute_trace_hash
            from .intrinsic.moments.taxonomy import MomentEntry, moment_kind_for_decision

            kind = moment_kind_for_decision(decision)
            if kind is None:
                return
            ledger.append(
                MomentEntry(
                    ts=now_ts,
                    day_key=day_key,
                    kind=kind,
                    reason_code=decision.reason,
                    phi=phi.vec(),
                    trace_hash=compute_trace_hash(trace or {}),
                    occasion_hint=decision.occasion,
                )
            )
        except Exception:  # noqa: BLE001  记账 best-effort
            logger.debug("YELOS intrinsic moment 记账跳过 sid=%s", sid)

    def _intrinsic_decide(
        self,
        sid: str,
        record: dict,
        surface: dict | None,
        day_key: str,
        now_ts: float,
        now_min: int,
        qstart: int,
        qend: int,
        reach_cached: bool,
        *,
        authoritative: bool = False,
    ) -> intr.IntrinsicDecision:
        """幕 III 主动判定统一接管点(三处调用共用)。

        ``authoritative=True``(心跳步 7 的真实主决策)才落盘 policy_state /
        记 moments / 递增 tick_index / 触发 FieldCrossingPolicy.recoil——
        `_want_to_speak`(§3.4 只读契约)与 concern probe(复用 gates 探测,
        非真实二次触发)一律 ``authoritative=False``,不落任何深化态,
        与 legacy 两处调用 `core.intrinsic.decide`(纯函数、零状态)的
        "调用即弃"语义对齐。任何异常回退 core.intrinsic.decide(§iron-5)。
        """
        if self._intrinsic_system is None:
            return intr.decide(
                self._intrinsic_input(
                    sid, record, surface, day_key, now_ts, now_min, qstart, qend,
                    reach_cached,
                )
            )
        try:
            from .intrinsic.field.state import FieldState
            from .intrinsic.impulses.gates import GateInput, apply_gates
            from .intrinsic.impulses.policy import PolicyContext

            system = self._intrinsic_system
            block = self._intrinsic_block(record)
            phi = FieldState.from_dict(block.get("phi"), default_ts=now_ts)
            daily = record["daily"]
            tick_index = int(block.get("tick_index", 0))
            ctx = PolicyContext(
                phi=phi,
                surface=surface,
                p=self._p_for(sid),
                now_ts=now_ts,
                now_local_minutes=now_min,
                day_key=day_key,
                sent_today=int(daily.get("proactive_sent", 0)),
                last_proactive_ts=float(daily.get("last_proactive_ts", 0.0)),
                unanswered_streak=int(daily.get("unanswered_streak", 0)),
                reach_out_cached=reach_cached,
                phase=sget(surface, "dynamics.relational_time.phase", "active"),
                policy_state=dict(block.get("policy_state") or {}),
                sid=sid,
                tick_index=tick_index,
            )
            proposal = system.policy.propose(ctx)
            gate_input = GateInput(
                surface=surface,
                p=self._p_for(sid),
                enabled=True,
                silenced=self._store.is_silenced(sid, now_ts),
                sealed=bool(record.get("sealed")),
                guard_frozen_today=bool(daily.get("guard_frozen", False)),
                now_local_minutes=now_min,
                quiet_start_min=qstart,
                quiet_end_min=qend,
                daily_cap_base=self._cfg.intrinsic_daily_cap,
                sent_today=int(daily.get("proactive_sent", 0)),
                last_proactive_ts=float(daily.get("last_proactive_ts", 0.0)),
                now_ts=now_ts,
                unanswered_streak=int(daily.get("unanswered_streak", 0)),
                contact_night_sent_today=bool(daily.get("contact_night_sent", False)),
                phase=sget(surface, "dynamics.relational_time.phase", "active"),
            )
            decision = apply_gates(proposal, gate_input)
            if authoritative:
                block["policy_state"] = dict(proposal.new_policy_state or {})
                block["tick_index"] = tick_index + 1
                if decision.send and hasattr(system.policy, "recoil"):
                    try:
                        phi = FieldState.from_dict(block.get("phi"), default_ts=now_ts)
                        block["phi"] = system.policy.recoil(phi).to_dict()
                    except Exception:  # noqa: BLE001  回冲 best-effort
                        logger.debug("YELOS intrinsic recoil 跳过 sid=%s", sid)
                self._intrinsic_record_moment(
                    sid, day_key, now_ts, phi, decision, proposal.trace
                )
            return decision
        except Exception:  # noqa: BLE001  深化判定异常回退 core.intrinsic
            logger.warning(
                "YELOS intrinsic decide 深化异常,回退 core.intrinsic sid=%s", sid,
                exc_info=True,
            )
            return intr.decide(
                self._intrinsic_input(
                    sid, record, surface, day_key, now_ts, now_min, qstart, qend,
                    reach_cached,
                )
            )

    def _intrinsic_dream_step(
        self,
        record: dict,
        surface: dict | None,
        in_quiet: bool,
        day_key: str,
        now_min: int,
        qstart: int,
        qend: int,
        sid: str,
        now_ts: float,
        daily: dict,
    ) -> None:
        """intrinsic_field_enabled 开时的梦语深化(替换 v0.1 心跳步 4 内联块)。

        DreamState 状态机(tick/arm/ready/deliver,dreamwork.dream_state)
        取代原始 dict 计数器;day 翻转显式驱动(不依赖 `_do_rollover`,本波
        禁碰,§iron-6),武装用当日 moments 流水 + 深化 DreamGenerator。
        投递仍走同一 outbox.make_dream 入队,文案渲染面不变(不碰 primal)。
        任何异常回退 legacy `_dream_step` + `intr.dream_ready` 原路径。
        """
        try:
            from .intrinsic.dreamwork.dream_state import (
                DreamState,
                arm as dream_arm,
                deliver as dream_deliver,
                push_trace,
                ready as dream_ready_deep,
                rollover_day as dream_rollover_day,
                tick as dream_tick_deep,
            )
            from .intrinsic.field.state import FieldState

            block = self._intrinsic_block(record)
            if block.get("last_day_key") != day_key:
                state = DreamState.from_dict(block.get("dream"))
                state = dream_rollover_day(state)
                block["last_day_key"] = day_key
            else:
                state = DreamState.from_dict(block.get("dream"))

            was_quiet = bool(block.get("in_quiet_prev", False))
            state = dream_tick_deep(state, surface, in_quiet)

            trace = [FieldState.from_dict(d) for d in (block.get("night_trace") or [])]
            if in_quiet:
                phi = FieldState.from_dict(block.get("phi"), default_ts=now_ts)
                trace = push_trace(trace, phi)

            if was_quiet and not in_quiet:
                day_moments = self._intrinsic_read_day_moments(sid, day_key)
                hash_seed = f"{sid}:{day_key}"
                state = dream_arm(
                    state, day_key, trace, day_moments, (),
                    self._intrinsic_system.dream_generator, hash_seed,
                )
                trace = []

            block["night_trace"] = [s.to_dict() for s in trace]
            block["in_quiet_prev"] = in_quiet
            block["dream"] = state.to_dict()

            if dream_ready_deep(state, self._p_for(sid), True):
                state = dream_deliver(state)
                block["dream"] = state.to_dict()
                daily["dream_delivered"] = True
                self._enqueue(sid, outbox.make_dream(now_ts, self._day_end_ts()))
        except Exception:  # noqa: BLE001  梦语深化异常回退 legacy 原路径
            logger.warning("YELOS intrinsic dream 深化异常,回退 core dream murmur", exc_info=True)
            self._dream_step(record, surface, in_quiet, day_key, now_min, qstart, qend)
            if intr.dream_ready(
                bool(record["dream"].get("pending")),
                self._p_for(sid),
                True,
                bool(daily.get("dream_delivered", False)),
            ):
                record["dream"]["pending"] = False
                daily["dream_delivered"] = True
                self._enqueue(sid, outbox.make_dream(now_ts, self._day_end_ts()))

    # =================================================================
    # 后台心跳(§3.4)—— 生成/入队,不推送
    # =================================================================

    async def heartbeat_loop(self) -> None:
        """唯一循环;单 session 异常不拖垮,Cancel 透传。软上限错峰(minor⑨)。"""
        try:
            while True:
                interval = self._cfg.intrinsic_interval_seconds
                await asyncio.sleep(max(5, interval))
                sids = [
                    s
                    for s in self._store.bound_umos()
                    if (self._store.get(s) or {}).get("mode") == "companion"
                ]
                batch = self._heartbeat_batch(sids)
                for sid in batch:
                    try:
                        await self._heartbeat_one(sid)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception("YELOS heartbeat session error sid=%s", sid)
        except asyncio.CancelledError:
            logger.info("YELOS heartbeat cancelled")
            raise

    def _heartbeat_batch(self, sids: list[str]) -> list[str]:
        """软上限错峰:超限时每周期只 tick 一个轮转批次(minor⑨)。"""
        cap = self._cfg.heartbeat_max_sessions
        if cap <= 0 or len(sids) <= cap:
            return sids
        start = self._rotation % len(sids)
        batch = (sids + sids)[start : start + cap]
        self._rotation = (start + cap) % len(sids)
        return batch

    async def _heartbeat_one(self, sid: str) -> None:
        async with self._lock(sid):
            await self._heartbeat_step(sid)

    async def _heartbeat_step(self, sid: str) -> None:
        """单 session 一拍(锁内):日结 / tick / 梦累积 / 影子 / 纪元 / 幕 III / concern。"""
        record = self._store.get(sid)
        if record is None or record.get("sealed"):
            return
        if record.get("mode") != "companion":
            return
        now_ts = self._now_ts()
        day_key = self._day_key()
        # W-2 迟滞挂点三:跨日 rollover 前若仍有未决介入账 → 沉默结算(arbiter 开时)。
        if self._arbiter_pipeline is not None:
            if (record.get("daily") or {}).get("day") != day_key:
                self._arbiter_settle_silence(sid, record)
        self._do_rollover(sid, day_key)
        record = self._store.get(sid)
        if record is None:
            return
        daily = record["daily"]

        surface = await self._bridge.tick_state(sid)
        if surface is not None:
            self._surface_cache[sid] = surface
            if sget(surface, "dynamics.relational_time.phase", "active") == "active":
                daily["active_seen"] = True

        qstart, qend = self._cfg.quiet_minutes()
        now_min = self._now_local_minutes()
        in_quiet = self._cfg.in_quiet_hours(now_min)
        silenced = self._store.is_silenced(sid, now_ts)

        # W-1 场步进(intrinsic_field_enabled 开时;silence 不阻内在场,只阻
        # 输出,故置于 silenced 提前 return 之前)。flag 关时 no-op。
        self._intrinsic_field_advance(record, surface, now_ts, now_min)

        # 梦语累积 / 武装 / 入队(静默窗内也做累积)。深化开时走 DreamState
        # 状态机 + DreamGenerator;关时逐字节 v0.1 内联路径。
        if self._cfg.dream_murmur_enabled:
            if self._intrinsic_system is not None:
                self._intrinsic_dream_step(
                    record, surface, in_quiet, day_key, now_min, qstart, qend,
                    sid, now_ts, daily,
                )
            else:
                self._dream_step(record, surface, in_quiet, day_key, now_min, qstart, qend)
                if intr.dream_ready(
                    bool(record["dream"].get("pending")),
                    self._p_for(sid),
                    True,
                    bool(daily.get("dream_delivered", False)),
                ):
                    record["dream"]["pending"] = False
                    daily["dream_delivered"] = True
                    self._enqueue(sid, outbox.make_dream(now_ts, self._day_end_ts()))

        # 静默窗中只做梦语累积,跳过 5-8。
        if silenced:
            self._persist(sid)
            return

        concern_sig = None
        if self._cfg.shadow_enabled:
            concern_sig = await self._shadow_step(record, sid, day_key)

        # 纪元提示入队(非 quiet + 未 guard 冻结;不满足则挂着次拍再试)。
        notice = record.get("pending_epoch_notice")
        if notice and not in_quiet and not daily.get("guard_frozen", False):
            # schema 收口:深路径(finitude_settle_enabled)写入的是
            # `EpochNoticePayload.to_dict()`(dict,含 epoch_to/track/day);v0.1
            # 浅路径写入的是纪元名 str。消费端在此统一取 epoch 名做映射键,不让
            # dict 被 str() 成 repr 而 miss 掉映射、落到默认文案。
            notice_key = notice.get("epoch_to") if isinstance(notice, dict) else notice
            text = _EPOCH_NOTICE.get(str(notice_key), _EPOCH_NOTICE_DEFAULT)
            self._enqueue(
                sid, outbox.make_epoch_notice(now_ts, text, self._day_end_ts())
            )
            record["pending_epoch_notice"] = None

        # 幕 III 主动:入队 + 在入队处预留频控槽(cap/gap/streak 即使不 poll 也守住)。
        reach_cached = self._reach_out_flag.get(sid) == day_key
        dec = self._intrinsic_decide(
            sid, record, surface, day_key, now_ts, now_min, qstart, qend,
            reach_cached, authoritative=True,
        )
        if reach_cached:
            self._reach_out_flag.pop(sid, None)
        if dec.send and dec.occasion:
            self._reserve_proactive(daily, now_ts, dec.occasion)
            self._enqueue(
                sid,
                outbox.make_proactive(
                    now_ts, dec.occasion, self._next_quiet_start_ts(qstart)
                ),
            )

        # concern 原语:过幕 III 全部闸门(probe)才入队,共享主动频控槽。
        if concern_sig is not None:
            probe = self._intrinsic_decide(
                sid, record, surface, day_key, now_ts, now_min, qstart, qend,
                True, authoritative=False,
            )
            if probe.send:
                self._reserve_proactive(daily, now_ts, "concern")
                self._enqueue(
                    sid, outbox.make_concern(now_ts, self._day_end_ts())
                )

        # WebUI 活体流:心跳快照(冒泡刷眉批,只放序数/标签/计数,不含任何轮次原文)。
        self._ui_emit(
            sid,
            {
                "kind": "heartbeat",
                "epoch": fin.epoch(float(record.get("p", 1.0)))
                if self._effective_finitude(record)
                else None,
                "pending": self._pending(sid, now_ts),
                "silenced": silenced,
            },
        )
        self._persist(sid)

    def _reserve_proactive(self, daily: dict, now_ts: float, occasion: str) -> None:
        """入队即预留频控槽:cap/gap/streak/night 记账(不 poll 也守住上限)。"""
        daily["proactive_sent"] = daily.get("proactive_sent", 0) + 1
        daily["last_proactive_ts"] = now_ts
        daily["unanswered_streak"] = daily.get("unanswered_streak", 0) + 1
        if occasion == "contact_night":
            daily["contact_night_sent"] = True

    def _intrinsic_input(
        self,
        sid: str,
        record: dict,
        surface: dict | None,
        day_key: str,
        now_ts: float,
        now_min: int,
        qstart: int,
        qend: int,
        reach_cached: bool,
    ) -> intr.IntrinsicInput:
        daily = record["daily"]
        return intr.IntrinsicInput(
            session_id=sid,
            day_key=day_key,
            surface=surface,
            p=self._p_for(sid),
            enabled=True,
            silenced=self._store.is_silenced(sid, now_ts),
            sealed=bool(record.get("sealed")),
            guard_frozen_today=bool(daily.get("guard_frozen", False)),
            reach_out_cached=reach_cached,
            now_local_minutes=now_min,
            quiet_start_min=qstart,
            quiet_end_min=qend,
            daily_cap_base=self._cfg.intrinsic_daily_cap,
            sent_today=int(daily.get("proactive_sent", 0)),
            last_proactive_ts=float(daily.get("last_proactive_ts", 0.0)),
            now_ts=now_ts,
            unanswered_streak=int(daily.get("unanswered_streak", 0)),
            contact_night_sent_today=bool(daily.get("contact_night_sent", False)),
            phase=sget(surface, "dynamics.relational_time.phase", "active"),
        )

    def _dream_step(
        self,
        record: dict,
        surface: dict | None,
        in_quiet: bool,
        day_key: str,
        now_min: int,
        qstart: int,
        qend: int,
    ) -> None:
        dream = record["dream"]
        if in_quiet:
            if intr.dream_tick(surface, True):
                night_of = self._night_of(day_key, now_min, qstart, qend)
                if dream.get("night_of") != night_of:
                    dream["night_of"] = night_of
                    dream["count"] = 0
                dream["count"] = dream.get("count", 0) + 1
        else:
            if dream.get("count", 0) >= 2 and not dream.get("pending", False):
                dream["pending"] = True
                dream["count"] = 0

    @staticmethod
    def _night_of(day_key: str, now_min: int, qstart: int, qend: int) -> str:
        if qstart <= qend:
            return day_key
        if now_min >= qstart:
            return day_key
        try:
            return (date.fromisoformat(day_key) - timedelta(days=1)).isoformat()
        except ValueError:
            return day_key

    async def _shadow_step(self, record: dict, sid: str, day_key: str):
        """影子读取 + concern 提取 + 迟滞 inject;返回本拍信号(可 None)。

        shadow_orchestrator_enabled 开 → 走深化 ShadowSystem.beat(detector_set 决定
        legacy 逐字节 / v2 全深化);关 → 走下方 v0.1 内联逐字节兼容路径。
        """
        if self._shadow_system is not None:
            return await self._shadow_step_orchestrated(record, sid, day_key)
        daily = record["daily"]
        sh = await self._bridge.shadow_state(sid)
        baseline = record.get("shadow_baseline", {"day": "", "warmth": None})
        if baseline.get("day") != day_key:
            baseline = {
                "day": day_key,
                "warmth": sget(sh, "state.valence.warmth", None),
            }
            record["shadow_baseline"] = baseline
        sig = shd.extract_concern(
            sh if isinstance(sh, dict) else {}, baseline.get("warmth")
        )

        cs = record["concern_state"]
        armed = cs["armed"]
        injected_day = cs.get("injected_day", "")
        injected_types = list(cs.get("injected_types", []))
        triggers = set(sig.triggers) if sig is not None else set()
        first_today = not (injected_day == day_key and injected_types)
        did_inject = False
        if sig is not None:
            for t in sig.triggers:
                already = injected_day == day_key and t in injected_types
                if armed.get(t, False) and not already:
                    await self._bridge.inject_concern(sid, sig.intensity)
                    armed[t] = False
                    if injected_day != day_key:
                        injected_day = day_key
                        injected_types = []
                    injected_types.append(t)
                    did_inject = True
            cs["injected_day"] = injected_day
            cs["injected_types"] = injected_types
        if did_inject and first_today:
            daily["high_intensity"] = daily.get("high_intensity", 0) + 1
        for t in ("pressure", "warmth_drop", "damage"):
            if t not in triggers:
                armed[t] = True
        return sig

    async def _shadow_step_orchestrated(self, record: dict, sid: str, day_key: str):
        """深化影子编排(shadow_orchestrator_enabled 开):心跳步 5 整体走
        ShadowSystem.beat(§3.4 接线点主契约)。inject/基线/校准记账均在 beat 内
        (锁内);返回 verdict.do_enqueue 为真时回传 verdict 触发幕 III concern probe,
        否则 None(与 v0.1 `concern_sig is not None` 语义兼容)。异常安静降级 None。
        """
        try:
            verdict = await self._shadow_system.beat(
                record, sid, day_key, self._now_ts()
            )
        except Exception:  # noqa: BLE001  深化影子异常不阻心跳
            logger.warning("YELOS shadow orchestrator beat 异常,本拍无 concern", exc_info=True)
            return None
        if verdict is not None and getattr(verdict, "do_enqueue", False):
            return verdict
        return None

    def _shadow_on_user_turn(self, sid: str, record: dict, text: str, now_ts: float) -> None:
        """shadow 深化校准回写(§3.4 on_user_turn):pending_prediction 结算 →
        账本落 (q,y) → brier/tier/β 更新。best-effort,异常静默(不阻主链)。"""
        try:
            turn_feats = {"msg_len": float(len(text or "")), "gap_seconds": 0.0}
            self._shadow_system.on_user_turn(record, sid, turn_feats, now_ts)
        except Exception:  # noqa: BLE001
            logger.debug("YELOS shadow on_user_turn 跳过 sid=%s", sid)

    def _concern_active(self, record: dict | None, day_key: str) -> bool:
        """当日影子 concern 是否活跃(companion:今日有 inject 过)。

        shadow_orchestrator 开时委托 ShadowSystem.concern_active(§3.3 权威源:v2
        读 shadow.daily.inject_types;legacy 读 concern_state,语义兼容);关时走
        v0.1 legacy concern_state。
        """
        if self._shadow_system is not None:
            try:
                return self._shadow_system.concern_active(record, day_key)
            except Exception:  # noqa: BLE001
                pass
        if record is None or record.get("mode") != "companion":
            return False
        cs = record.get("concern_state") or {}
        return cs.get("injected_day") == day_key and bool(cs.get("injected_types"))

    # =================================================================
    # 工具 7:affect_bind(§3.6.1 / §4.1)
    # =================================================================

    async def bind(self, sid: str, name: str, mode: str = "steward") -> dict:
        async with self._lock(sid):
            await self.ensure_engine()
            name = (name or "").strip()
            if len(name) > 12:
                return {"bound": False, "reason": "name_too_long"}
            if mode not in ("steward", "companion"):
                mode = "steward"
            now_ts = self._now_ts()
            day_key = self._day_key()
            existing = self._store.get(sid)
            if existing is not None and not existing.get("sealed", False):
                # 命名 / 升 companion(companion 降 steward 不提供,§5)。
                if name:
                    existing["name"] = name
                upgraded = False
                if mode == "companion" and existing.get("mode") == "steward":
                    existing["mode"] = "companion"
                    upgraded = True
                self._persist(sid)
                return self._bind_status(sid, created=False, upgraded=upgraded)

            prev = existing if (existing and existing.get("sealed")) else None
            incarnation = persistence.next_incarnation(prev)
            b = self._store.hatch(sid, name, now_ts, day_key)
            b["mode"] = mode
            persistence.stamp_new_life(b, incarnation)
            persistence.ensure_binding_blocks(b, lang=self._cfg.lang)
            b["outbox"] = []
            self._outbox.clear(sid)
            self._ledger.append(
                sid, incarnation, now_ts, 1.0, day=day_key, reason="hatch"
            )
            b.setdefault("milestones", []).append(
                {"day": day_key, "text": _HATCH_MILESTONE}
            )
            self._persist(sid)
            return self._bind_status(sid, created=True, upgraded=False)

    def _bind_status(self, sid: str, *, created: bool, upgraded: bool) -> dict:
        b = self._store.get(sid) or {}
        return {
            "bound": True,
            "session_id": sid,
            "name": b.get("name") or None,
            "mode": b.get("mode", "steward"),
            "sealed": bool(b.get("sealed")),
            "incarnation": persistence.incarnation_of(b),
            "created": created,
            "upgraded": upgraded,
        }

    # =================================================================
    # 工具 2/3/4:affect_state / affect_guidance / affect_tick
    # =================================================================

    async def state(self, sid: str) -> dict:
        async with self._lock(sid):
            record = self._store.get(sid)
            if record is None:
                out = self._empty_compact(sid)
            else:
                out = self._compact(sid, record)
            out["engine_health"] = await self._bridge.health()
            return out

    async def tick(self, sid: str) -> dict:
        async with self._lock(sid):
            record = self._store.get(sid)
            if record is None:
                return self._empty_compact(sid)
            if not record.get("sealed"):
                surface = await self._bridge.tick_state(sid)
                if surface is not None:
                    self._surface_cache[sid] = surface
            return self._compact(sid, record)

    def _continuity_for(self, sid: str, record: dict | None):
        """经 memory.continuity_flags 取 reunion 事实(§3.4 路线 A);仅在 reunion 为真
        时返回 flags,否则 None——None + profile="chat" 严格走 guidance v0.1(I3 零漂移)。

        memory 缺席/异常一律 None(安静降级)。continuity 只在 companion 有意义。
        """
        if self._memory is None or record is None:
            return None
        if record.get("mode") != "companion" or record.get("sealed"):
            return None
        try:
            gen = persistence.incarnation_of(record)
            flags = self._memory.continuity_flags(sid, gen, self._now_ts())
        except Exception:  # noqa: BLE001
            return None
        return flags if getattr(flags, "reunion", False) else None

    async def guidance(self, sid: str) -> dict:
        async with self._lock(sid):
            record = self._store.get(sid)
            mode = record.get("mode", "steward") if record else "steward"
            surface = self._surface_cache.get(sid)
            concern = self._concern_active(record, self._day_key())
            return build_guidance(
                surface,
                mode,
                concern,
                profile=self._cfg.guidance_profile,
                continuity=self._continuity_for(sid, record),
                lang=self._cfg.guidance_lang,
            )

    # =================================================================
    # 工具 8/9/10:affect_pause / affect_reset / affect_farewell(主权)
    # =================================================================

    async def pause(self, sid: str, hours: float = 12.0) -> dict:
        async with self._lock(sid):
            return self._sov.pause(sid, hours, self._now_ts())

    async def reset(self, sid: str) -> dict:
        async with self._lock(sid):
            return await self._sov.reset(sid)

    async def farewell(
        self, sid: str, export: bool = True, confirm_token: str | None = None
    ) -> dict:
        async with self._lock(sid):
            await self.ensure_engine()
            result = await self._sov.farewell(
                sid,
                export=export,
                confirm_token=confirm_token,
                day_key=self._day_key(),
                now_ts=self._now_ts(),
            )
            if result.get("sealed"):
                # WebUI 活体流(非五路,可选):第二步真封存,让前端切封存态。
                self._ui_emit(sid, {"kind": "header", "sealed": True})
            return result

    # =================================================================
    # 资源
    # =================================================================

    def full_state(self, sid: str) -> dict:
        """affect://state/{sid} 资源:完整 Surface + Yelos 元(§9.1)。"""
        record = self._store.get(sid)
        surface = self._surface_cache.get(sid) or {}
        if record is None:
            meta = {"bound": False}
        else:
            eff = self._effective_finitude(record)
            mode = record.get("mode", "steward")
            meta = {
                "bound": not record.get("sealed", False),
                "name": record.get("name") or None,
                "mode": mode,
                "sealed": bool(record.get("sealed")),
                "epoch": fin.epoch(float(record.get("p", 1.0))) if eff else None,
                "days_lived": _days_lived(record.get("born_day", ""), self._day_key())
                if mode == "companion"
                else None,
                "plasticity": float(record.get("p", 1.0)),
                "pending": self._pending(sid, self._now_ts()),
            }
        return {"surface": surface, "meta": meta}

    def guidance_resource(self, sid: str) -> dict:
        """affect://guidance/{sid} 资源:guidance + 推荐 poll 节奏(§9.1)。"""
        record = self._store.get(sid)
        mode = record.get("mode", "steward") if record else "steward"
        surface = self._surface_cache.get(sid)
        concern = self._concern_active(record, self._day_key())
        g = build_guidance(
            surface,
            mode,
            concern,
            profile=self._cfg.guidance_profile,
            continuity=self._continuity_for(sid, record),
            lang=self._cfg.guidance_lang,
        )
        g["poll_hint"] = (
            f"After each user turn and roughly every "
            f"{self._cfg.intrinsic_interval_seconds}s idle, call affect_impulse."
        )
        return g

    def anthology(self, sid: str) -> str:
        """affect://anthology/{sid} 资源:封存后返回她的一生 md;未封存返回占位。"""
        record = self._store.get(sid)
        if record is None or not record.get("sealed"):
            return "她还在。"
        path = record.get("anthology_path")
        if path:
            try:
                return Path(path).read_text(encoding="utf-8")
            except OSError:
                pass
        _data, md = fin.assemble_anthology(record, self._day_key())
        return md

    def contract_text(self) -> str:
        return YELOS_CONTRACT.format(interval=self._cfg.intrinsic_interval_seconds)

    # =================================================================
    # WebUI 只读桥接(接线波 §4;只读快照 + 只读时间面,零新副作用)
    # =================================================================
    # ui.mount() 的路由层用这几个方法把 ui.data.* 纯函数适配器的输入喂好;
    # 均不进 per-sid 锁(与既有 full_state()/anthology()/guidance_resource()
    # 同一纪律:只读快照,不推进任何状态,读脏一次无害)。

    def ui_records_snapshot(self) -> dict[str, dict]:
        """全部 binding 记录快照(含封存)——WebUI 名册/全集面用。"""
        return self._store.records()

    def ui_record(self, sid: str) -> dict | None:
        return self._store.get(sid)

    def ui_ledger_rows(self) -> list[dict]:
        """全量 ledger 行快照——WebUI 年轮/名册厚度面用。"""
        return self._ledger.all_rows()

    def ui_outbox_raw(self, sid: str) -> list[dict]:
        """某 sid 的 outbox 队列原始形状(与 record["outbox"] 同构)。"""
        return self._outbox.serialize(sid)

    def ui_surface(self, sid: str) -> dict | None:
        """当前 Surface 缓存(只读;与 ``guidance()``/``_compact`` 同一份缓存)。"""
        return self._surface_cache.get(sid)

    def ui_is_silenced(self, sid: str, now_ts: float | None = None) -> bool:
        return self._store.is_silenced(sid, now_ts if now_ts is not None else self._now_ts())

    def ui_now_ts(self) -> float:
        return self._now_ts()

    def ui_day_key(self) -> str:
        return self._day_key()

    async def ui_engine_health(self) -> str:
        return await self._bridge.health()

    async def unsilence(self, sid: str) -> dict:
        """WebUI ``DELETE .../silence``:立即解静默(pause 的逆操作)。

        不是 11 个 MCP 工具之一(那 11 个不动);只是 ``pause()`` 语义的对称
        补齐,同样在 per-sid 锁内、同样即时生效、同样只碰 ``silence_until``。
        """
        async with self._lock(sid):
            record = self._store.get(sid)
            if record is None or record.get("sealed", False):
                return {"silenced": False, "reason": "unbound_or_sealed"}
            self._store.set_silence(sid, 0.0)
            self._store.save()
            return {"silenced": False}

    # =================================================================
    # sovereignty 回调 + compact 组装
    # =================================================================

    def _write_anthology(self, name: str, sid: str, data: dict, md: str) -> str | None:
        base = self._cfg.anthologies_dir()
        sid_hash = hashlib.blake2b(sid.encode()).hexdigest()[:8]
        folder = base / f"{name}-{sid_hash}"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "她的一生.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            md_path = folder / "她的一生.md"
            md_path.write_text(md, encoding="utf-8")
        except OSError:
            logger.warning("YELOS anthology 写入失败 sid=%s", sid, exc_info=True)
            return None
        rec = self._store.get(sid)
        if rec is not None:
            rec["anthology_path"] = str(md_path)
        return str(md_path)

    def _cache_evict(self, sid: str) -> None:
        self._surface_cache.pop(sid, None)
        self._reach_out_flag.pop(sid, None)
        self._recent_submit.pop(sid, None)
        self._outbox.clear(sid)

    def _seal_ledger(self, sid: str, record: dict) -> None:
        gen = persistence.incarnation_of(record)
        self._ledger.append(
            sid,
            gen,
            float(record.get("born_at", 0.0)),
            float(record.get("p", 1.0)),
            day=self._day_key(),
            reason="seal",
        )

    def _compact(self, sid: str, record: dict) -> dict:
        surface = self._surface_cache.get(sid)
        mode = record.get("mode", "steward")
        sealed = bool(record.get("sealed"))
        silenced = self._store.is_silenced(sid, self._now_ts())
        eff = self._effective_finitude(record)
        p = float(record.get("p", 1.0))
        epoch = fin.epoch(p) if eff else None
        days = (
            _days_lived(record.get("born_day", ""), self._day_key())
            if mode == "companion"
            else None
        )
        daily = record.get("daily", {})
        concern = self._concern_active(record, self._day_key())
        return build_compact_surface(
            surface,
            session_id=sid,
            name=record.get("name") or None,
            bound=not sealed,
            mode=mode,
            sealed=sealed,
            silenced=silenced,
            epoch=epoch,
            days_lived=days,
            self_words_today=int(daily.get("self_words", 0)),
            proxy_sentences_today=int(daily.get("proxy_sentences", 0)),
            swallowed_today=int(daily.get("swallowed", 0)),
            pending=self._pending(sid, self._now_ts()),
            concern_active=concern,
        )

    def _empty_compact(self, sid: str) -> dict:
        return build_compact_surface(
            None,
            session_id=sid,
            name=None,
            bound=False,
            mode=self._cfg.normalized_default_mode(),
            sealed=False,
            silenced=False,
            epoch=None,
            days_lived=None,
            self_words_today=0,
            proxy_sentences_today=0,
            swallowed_today=0,
            pending=0,
            concern_active=False,
        )
