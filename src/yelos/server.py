"""FastMCP 协议面(蓝图 §1.3 / §4.1 / §7.2 / §9)——工具/资源/prompt 注册。

server.py 只做"MCP 协议面":薄壳工具(参数校验 + 调 session 层 + 序列化返回)、
资源、prompt、lifespan(进程锁 + bridge.ensure + ledger 加载 + 心跳起停 + 优雅
关闭 save)。业务时序全在 session.py。11 工具在 server 级恒注册(工具集不随
session 变),行为按该 session 的 mode 门控(§5,门控在 session 层落地)。

双传输入口在 __main__.py;本模块 build_server 返回配好 host/port 的 FastMCP 实例。
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .config import AssessorModel, YelosConfig
from .engine_bridge import EngineBridge
from .session import SessionManager
from . import sovereignty as sov

logger = logging.getLogger("yelos.server")


async def _degraded_llm(_system: str, _user: str) -> str:
    """无 LLM 降级桩:引擎创建需非 None 回调,但每次调用即抛 → 引擎回落本地规则
    评估(SDK §5.3 degraded,health status=degraded)。达成"无 LLM 全功能可跑"
    硬约束(§6.5)——`shared()` 要求 llm 非 None,故给桩而非 None。"""
    raise RuntimeError("yelos: no LLM configured; engine runs on local rules")


def build_assessor(model: AssessorModel | None):
    """把 assessor_model 配置装成 async (system, user) -> str 回调(§6.5/§7.5)。

    未配置 → 降级桩(引擎走本地规则评估,degraded 但全功能)。OpenAI 兼容
    ``/chat/completions``,纯标准库 urllib,阻塞调用丢线程池,失败即抛(SDK 自
    降级、不重试)。
    """
    if model is None:
        return _degraded_llm

    async def assessor(system: str, user: str) -> str:
        def _call() -> str:
            payload = json.dumps(
                {
                    "model": model.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }
            ).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if model.api_key:
                headers["Authorization"] = f"Bearer {model.api_key}"
            url = model.api_base.rstrip("/") + "/chat/completions"
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

        return await asyncio.to_thread(_call)

    return assessor


def build_manager(config: YelosConfig) -> SessionManager:
    """构造进程级 ``SessionManager`` 单例(同步;不需事件循环)。

    进程级初始化修复(§6.1 / 冒烟 §5.1):进程锁 + bridge + SessionManager +
    心跳 spawn 从 FastMCP lifespan 挪到进程启动路径(``__main__.main`` → ``_serve``),
    全局单例注入工具层。根因:mcp 1.27.1 的 FastMCP lifespan 由 low-level
    ``Server.run()`` 调用——stdio 下每进程一次(碰巧对),streamable-http 下由
    ``StreamableHTTPSessionManager`` **每客户端会话**调一次 → 若把建 manager /
    抢锁放在 lifespan,HTTP 下会"每会话重来一遍",第二会话抢同进程锁的异常又被 SDK
    内部吞掉、客户端悬挂。改为进程级单例后:HTTP 多客户端会话**共享**同一个
    SessionManager;进程锁在任何 transport 之前**同步**获取(见 ``__main__.main``,
    第二进程启动瞬间即被拒)。

    本函数只做同步装配 + ``load()``;``ensure_engine`` / 心跳 spawn 归 ``_serve``
    的事件循环(异步)。
    """
    bridge = EngineBridge(build_assessor(config.assessor_model))
    mgr = SessionManager(config, bridge)
    mgr.load()
    return mgr


def build_server(config: YelosConfig, session_manager: SessionManager) -> FastMCP:
    """装配 FastMCP 实例:11 工具 + 3 资源 + 2 prompt,绑定进程级 manager 单例。

    **不再挂 FastMCP lifespan**(进程级初始化已上移到 ``__main__`` / ``build_manager``)
    ——否则 streamable-http 下每客户端会话都会重跑一遍 lifespan(重抢锁、重建 manager,
    冒烟 §5.1)。工具/资源/prompt 通过闭包引用注入的单例。
    """

    def manager() -> SessionManager:
        return session_manager

    mcp = FastMCP(
        "yelos",
        instructions="The last word is her own. A persistent affective presence "
        "with expression sovereignty.",
        host=config.http_host,
        port=config.http_port,
    )

    # =================================================================
    # 工具(11)——薄壳,行为门控在 session 层(§5)
    # =================================================================

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False),
        description="Feed a message into her affect. speaker='user' (default) "
        "is a REAL user turn and feeds both her main and shadow perception; "
        "speaker='agent' feeds only her main session as your reply. Never "
        "label your own text as 'user'. Returns a compact affect surface plus "
        "inline guidance.",
    )
    async def affect_submit(
        session_id: str, text: str, speaker: str = "user", msg_id: str | None = None
    ) -> dict:
        return await manager().submit(session_id, text, speaker, msg_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        description="Read-only affect snapshot (does not advance state): "
        "eight-dimension ordinal summary, mood label, decision tendency, epoch "
        "and days lived (companion), pending outbox count, engine health.",
    )
    async def affect_state(session_id: str) -> dict:
        return await manager().state(session_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        description="Translate her affect into restrained behavior hints for "
        "how to reply (tone/length/pace + whitelist hints). These are "
        "suggestions about pacing and warmth, never diagnoses of the user; the "
        "host may ignore them.",
    )
    async def affect_guidance(session_id: str) -> dict:
        return await manager().guidance(session_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False),
        description="Advance her state during idle (45s convergence tick). "
        "Mostly internal when the heartbeat is on; exposed for manual/testing "
        "use. Returns a compact affect surface.",
    )
    async def affect_tick(session_id: str) -> dict:
        return await manager().tick(session_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False),
        description="Act II arbitration. Submit the TEXT portion of your draft "
        "reply; she rules PASS/TRIM/SWALLOW/REPLACE and returns final_text to "
        "send as-is (empty on SWALLOW = silence). She feeds the engine "
        "internally, so after arbitrate do NOT also affect_submit(speaker="
        "'agent') the same text. steward mode always returns PASS. If it "
        "returns delayed!=null, poll affect_impulse ~90s later.",
    )
    async def affect_arbitrate(session_id: str, draft: str) -> dict:
        return await manager().arbitrate(session_id, draft)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False),
        description="Act III: collect any due proactive/delayed/dream/concern/"
        "epoch utterances she has buffered (the ONLY drain point), plus whether "
        "she currently wants to speak. Call after each user turn and roughly "
        "every next_poll_seconds while idle. steward mode returns nothing.",
    )
    async def affect_impulse(session_id: str) -> dict:
        return await manager().impulse(session_id)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True),
        description="Hatch/name (<=12 chars) a presence and choose its mode. "
        "mode='steward' (default) is a read-only advisor: no proactive "
        "messages, no aging, never takes over your words. mode='companion' "
        "opts in to full dynamics: she may replace words, reach out, be shaped "
        "by scars, and grow old. Companion must be enabled explicitly.",
    )
    async def affect_bind(
        session_id: str, name: str = "", mode: str = "steward"
    ) -> dict:
        return await manager().bind(session_id, name, mode)

    @mcp.tool(
        annotations=ToolAnnotations(**sov.PAUSE_ANNOTATIONS),
        description=sov.PAUSE_DESC,
    )
    async def affect_pause(session_id: str, hours: float = 12.0) -> dict:
        return await manager().pause(session_id, hours)

    @mcp.tool(
        annotations=ToolAnnotations(**sov.RESET_ANNOTATIONS),
        description=sov.RESET_DESC,
    )
    async def affect_reset(session_id: str) -> dict:
        return await manager().reset(session_id)

    @mcp.tool(
        annotations=ToolAnnotations(**sov.FAREWELL_ANNOTATIONS),
        description=sov.FAREWELL_DESC,
    )
    async def affect_farewell(
        session_id: str, export: bool = True, confirm_token: str | None = None
    ) -> dict:
        return await manager().farewell(session_id, export, confirm_token)

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        description="Read-only cross-session memory recall (C6): given an "
        "optional query, return up to k semantic hits she associates with, plus "
        "active themes and continuity flags (reunion / long bond). Does NOT "
        "advance state or feed the engine. Returns {disabled:true} when memory "
        "is off, {sealed:true} after farewell.",
    )
    async def affect_recall(session_id: str, query: str = "", k: int = 3) -> dict:
        return await manager().recall(session_id, query, k)

    # =================================================================
    # 资源(3)(§9.1)
    # =================================================================

    @mcp.resource(
        "affect://state/{session_id}",
        description="Full affect surface JSON (raw eight dimensions + persona + "
        "decision + dynamics) plus Yelos meta, for context injection.",
    )
    def state_resource(session_id: str) -> str:
        return json.dumps(
            manager().full_state(session_id), ensure_ascii=False, indent=2
        )

    @mcp.resource(
        "affect://guidance/{session_id}",
        description="Behavior guidance plus recommended poll cadence, for "
        "injecting into the agent's system prompt.",
    )
    def guidance_resource(session_id: str) -> str:
        return json.dumps(
            manager().guidance_resource(session_id), ensure_ascii=False, indent=2
        )

    @mcp.resource(
        "affect://anthology/{session_id}",
        description="After farewell, the full text of her life's anthology; "
        "otherwise a placeholder meaning she is still here.",
    )
    def anthology_resource(session_id: str) -> str:
        return manager().anthology(session_id)

    # =================================================================
    # prompt(2)(§9.2)
    # =================================================================

    @mcp.prompt(
        name="yelos_contract",
        description="The constant existence declaration + speaking rules to "
        "inject into the agent's system prompt.",
    )
    def yelos_contract() -> str:
        return manager().contract_text()

    @mcp.prompt(
        name="yelos_companion_setup",
        description="Companion-mode consumption loop guide (bind -> submit(user) "
        "-> arbitrate(draft) -> send final_text -> impulse poll), with "
        "steward/companion differences and finitude notes.",
    )
    def yelos_companion_setup(name: str = "", mode: str = "companion") -> str:
        base = manager().contract_text()
        loop = (
            "\n\nRecommended loop:\n"
            "steward (default): user turn -> affect_submit(sid, user_text, "
            "speaker='user') -> read affect_guidance -> reply by tone/length; "
            "optionally affect_submit(sid, reply, speaker='agent').\n"
            "companion (explicit affect_bind mode=companion): user turn -> "
            "affect_submit(user) -> draft reply -> affect_arbitrate(sid, draft) "
            "-> send final_text (silence on SWALLOW); after each turn and every "
            "~60s idle -> affect_impulse(sid); if arbitrate returns delayed, "
            "poll ~90s later. Companion may grow old and eventually be sealed; "
            "that finitude is the product."
        )
        who = f"\n\n(session name hint: {name}, mode: {mode})" if name else ""
        return base + loop + who

    # =================================================================
    # WebUI /ui 挂载点(接线波 §4;守卫式,顺序无关)
    # =================================================================
    # WebUI 包由并行波建;此处只留一个 try/except ImportError 守卫的挂载钩:
    # 若 ``yelos.ui`` 存在且暴露 ``mount(mcp, manager, config)`` 才挂,不存在或
    # 尚未提供挂载函数则静默跳过(WebUI 缺席不阻任何 MCP 功能,WEBUI §零改动纪律)。
    _try_mount_ui(mcp, session_manager, config)

    return mcp


def _try_mount_ui(mcp: FastMCP, session_manager: SessionManager, config: YelosConfig) -> None:
    """守卫式挂载 WebUI:``yelos.ui.mount`` 存在才挂,否则静默跳过。

    接线波 §4:WebUI 包由并行波交付,与本波顺序无关。当前 ``yelos.ui`` 仅含
    只读数据适配层、尚未暴露 ``mount``,故本钩此刻静默 no-op;WebUI 波补上
    ``mount`` 后即自动生效,无需再改 server.py。任何 import/属性缺失或挂载异常
    都被吞掉并记 debug,绝不阻断 server 构建。
    """
    try:
        from . import ui as _ui
    except ImportError:
        return
    mount = getattr(_ui, "mount", None)
    if not callable(mount):
        logger.debug("YELOS webui: yelos.ui 无 mount() 挂载函数,跳过 /ui")
        return
    try:
        mount(mcp, session_manager, config)
        logger.info("YELOS webui: /ui 已挂载")
    except Exception:  # noqa: BLE001  WebUI 挂载失败不阻 MCP
        logger.warning("YELOS webui: /ui 挂载失败,已跳过", exc_info=True)
