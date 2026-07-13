"""引擎桥(蓝图 §9 / §2)——sylanne_core import 的唯一落点。

职责:与 SylannEngine 说话。ImportError 守卫 + major==2 门控;引擎缺席
(HAS_ENGINE=False 或未 ensure)时所有方法安静返回 None/False,绝不 raise。
回喂协议、inject 仅 concern 一处均在此收口。terminate 禁调 release_shared。

搬运自 astrbot 版,按蓝图 §2 微改三处(其余逐字):
① logger 换标准库 logging(原 astrbot.api.logger);
② plugin 串换 "yelos-mcp"(原 "astrbot_plugin_yelos");
③ ensure 的 data_dir 解析走 persistence(§7.3:独立 data_dir 下引擎数据落
   {data_dir}/engine;engine_data_dir 非空则指共心路径,opt-in)。
submit/feed_back/tick_state/shadow_state/inject_concern/detach 契约原样。
"""

from __future__ import annotations

import logging

from . import persistence

logger = logging.getLogger("yelos.engine_bridge")

try:
    import sylanne_core
    from sylanne_core import SylanneEngine

    HAS_ENGINE = sylanne_core.__version__.split(".")[0] == "2"
except ImportError:
    SylanneEngine = None  # type: ignore[assignment,misc]
    HAS_ENGINE = False


SHADOW_PREFIX = "yelos-shadow:"

# 回喂协议白名单(蓝图 §9 强制):她主动/回复的话才回喂,phase 只这两枚。
_FEED_PHASES = ("response", "proactive")


class EngineBridge:
    """与共享引擎说话的薄桥。引擎缺席时全部安静降级。"""

    def __init__(self, llm_fn):
        # llm_fn: async (system, user) -> str;由 server 构造并注入,桥不实现适配。
        self._llm = llm_fn
        self._engine = None

    async def ensure(self, data_dir, engine_data_dir: str = "") -> bool:
        """懒启动共享引擎;已就绪则幂等返回 True。引擎缺席/失败返回 False,不 raise。

        data_dir 解析走 persistence(§2③/§7.3):engine_data_dir 空 →
        {data_dir}/engine(默认独立);非空 → 该路径(共心 opt-in)。
        """
        if not HAS_ENGINE:
            return False
        if self._engine is not None:
            return True
        try:
            resolved = persistence.resolve_engine_data_dir(data_dir, engine_data_dir)
            self._engine = await SylanneEngine.shared(
                resolved,
                llm=self._llm,
                plugin="yelos-mcp",
            )
        except Exception:
            logger.warning("YELOS 引擎懒启动失败,降级为无引擎运行", exc_info=True)
            self._engine = None
            return False
        return True

    async def submit_user(self, umo, text, msg_id) -> dict | None:
        """主 session 回源;返回最新 Surface(缺席返回 None)。"""
        if self._engine is None:
            return None
        return await self._engine.submit(umo, text, msg_id=msg_id)

    async def submit_shadow(self, umo, text, msg_id) -> None:
        """影子 session 回源(只喂用户的话)。主/影子 session_id 不同,不会误合并。"""
        if self._engine is None:
            return None
        await self._engine.submit(SHADOW_PREFIX + umo, text, msg_id=msg_id)
        return None

    async def feed_back(self, umo, text, phase: str) -> None:
        """回喂实际外发文本。phase 只取 response 或 proactive,越界安静忽略。"""
        if self._engine is None:
            return None
        if phase not in _FEED_PHASES:
            return None
        await self._engine.submit(umo, text, flags=[phase])
        return None

    async def tick_state(self, umo) -> dict | None:
        """心跳:tick 推进(禁传 force,走 45s 收敛)后取 state 快照。"""
        if self._engine is None:
            return None
        await self._engine.tick(umo)
        return await self._engine.state(umo)

    async def shadow_state(self, umo) -> dict | None:
        """只读影子 state,不 tick、不推进。"""
        if self._engine is None:
            return None
        return await self._engine.state(SHADOW_PREFIX + umo)

    async def inject_concern(self, umo, intensity: float) -> None:
        """幕 IV 唯一 inject 出口,五枚举内 revelation。"""
        if self._engine is None:
            return None
        await self._engine.inject(
            umo,
            source="yelos.shadow",
            influence_type="revelation",
            intensity=intensity,
        )
        return None

    # -- 影子多假设(K>1 ensemble;接线波 §5,K=1 默认不依赖)------------------

    def _hyp_umo(self, umo, hyp: int) -> str:
        """第 hyp 号影子假设的 session key。hyp<=0 退化为单假设主影子 key
        (与 ``submit_shadow``/``shadow_state`` 完全同键,K=1 逐字节兼容)。"""
        if hyp <= 0:
            return SHADOW_PREFIX + umo
        return f"{SHADOW_PREFIX}{hyp}:{umo}"

    async def submit_shadow_hyp(self, umo, text, msg_id, hyp: int) -> None:
        """向第 hyp 号影子假设回源(shadow ensemble K>1)。引擎缺席安静降级。"""
        if self._engine is None:
            return None
        await self._engine.submit(self._hyp_umo(umo, hyp), text, msg_id=msg_id)
        return None

    async def shadow_state_hyp(self, umo, hyp: int) -> dict | None:
        """只读第 hyp 号影子假设 state,不 tick、不推进。缺席返回 None。"""
        if self._engine is None:
            return None
        return await self._engine.state(self._hyp_umo(umo, hyp))

    async def inject_shadow_perturb(
        self, umo, intensity: float, hyp: int = 0
    ) -> None:
        """对第 hyp 号影子假设注入扰动(ensemble 探测,revelation 五枚举内)。

        与主 inject_concern 同出口纪律;缺席安静降级。hyp<=0 时作用于主影子。
        """
        if self._engine is None:
            return None
        await self._engine.inject(
            self._hyp_umo(umo, hyp),
            source="yelos.shadow",
            influence_type="revelation",
            intensity=intensity,
        )
        return None

    async def reset_session(self, umo) -> None:
        """幕外主权 reset:清空主 + 影子 session 的引擎情感态(保留绑定)。

        引擎缺席安静降级。绑定 record 本身由 sovereignty 层保留——此处只抹掉
        引擎里累积的八维情感/影子疤痕,不动她的身份与年龄(§3.6/§4.1 tool#9)。
        """
        if self._engine is None:
            return None
        await self._engine.reset(umo)
        await self._engine.reset(SHADOW_PREFIX + umo)
        return None

    async def health(self) -> str:
        """引擎健康:"running" | "degraded"。缺席/异常一律 "degraded"(§7.5)。"""
        if self._engine is None:
            return "degraded"
        try:
            status = self._engine.health()  # SDK health() 为同步,返回 dict
        except Exception:
            return "degraded"
        # HealthStatus.status ∈ {init, running, degraded, closed}(EngineStatus)。
        state = status.get("status") if isinstance(status, dict) else None
        return "running" if state == "running" else "degraded"

    def detach(self) -> None:
        """terminate 清理:只置空自己的引用。禁调 release_shared(进程级运维,不归插件)。"""
        self._engine = None
