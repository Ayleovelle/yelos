"""在整个架构中的位置:provider 协议 + 干净缺席异常 + V1 适配器(蓝图 §3/§4)。"""

from __future__ import annotations

from typing import Any, Callable, Protocol


class ProviderUnavailable(Exception):
    """A8 干净缺席:前置条件不满足的协议性信号,composer 捕获即路由下降,

    不外抛给调用方(session 层永远拿到一句可用的话)。
    """


class PrimalProviderV2(Protocol):
    """V1 协议(core.primal.PrimalProvider)的加宽:多 context 与结构化返回。"""

    provider_id: str

    def available(self, sid: str, lang: str) -> bool: ...

    def utter_canonical(
        self,
        surface: dict,
        sid: str,
        day_key: str,
        occasion: str,
        *,
        p: float,
        epoch: int,
        lang: str,
        context: dict | None = None,
    ) -> str: ...


class V1Adapter:
    """把 V1 PrimalProvider(如零改动的 core.primal.LexiconProvider)包装为

    V2 协议,同样可入 composer 回退链(蓝图 §3 明文允许)。V1 provider 没有
    p/epoch/lang/context 概念,adapter 静默丢弃这些多余入参、恒 available。
    """

    def __init__(self, provider_id: str, v1_provider: Any) -> None:
        self.provider_id = provider_id
        self._v1 = v1_provider

    def available(self, sid: str, lang: str) -> bool:  # noqa: ARG002
        return True

    def utter_canonical(
        self,
        surface: dict,
        sid: str,
        day_key: str,
        occasion: str,
        *,
        p: float,
        epoch: int,
        lang: str,
        context: dict | None = None,
    ) -> str:
        return self._v1.utter(surface, sid, day_key, occasion)


ProviderFactory = Callable[[], PrimalProviderV2]

__all__ = ["ProviderUnavailable", "PrimalProviderV2", "V1Adapter", "ProviderFactory"]
