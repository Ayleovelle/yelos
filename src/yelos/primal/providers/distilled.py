"""在整个架构中的位置:M9 挂点(蓝图 §4.4)。

v1 交付:注册面 + 恒缺席的桩。真身(SylannDistilledProvider)由 M9(W5)
经 register_distilled 注册,composer 路由自动生效;其输出走 Tier-S 严格
成员判定(模型只提候选,闸决定出口)。

干净缺席专测消费此模块:桩在链首时 compose 行为与无桩逐字节一致。
"""

from __future__ import annotations

from . import ProviderUnavailable, PrimalProviderV2


class DistilledSlotStub:
    """v1 桩:恒缺席。不是死代码——注册面 + 跳过路径本波即被 composer 消费。"""

    provider_id = "distilled"

    def available(self, sid: str, lang: str) -> bool:  # noqa: ARG002
        return False

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
        raise ProviderUnavailable("distilled stub: v1 恒缺席")


_stub = DistilledSlotStub()
_registry: dict[str, PrimalProviderV2] = {}


def register_distilled(provider: PrimalProviderV2) -> None:
    """M9 波注册真身;provider_id 必须为 "distilled"。"""
    _registry["distilled"] = provider


def unregister_distilled() -> None:
    """测试/回滚用:撤回注册,恢复桩。"""
    _registry.pop("distilled", None)


def get_distilled() -> PrimalProviderV2:
    """composer 路由到 distilled 时的动态解析入口(每次调用现取,不在

    build_composer 时固化——注册可在 composer 建好之后发生)。
    """
    return _registry.get("distilled", _stub)


__all__ = [
    "DistilledSlotStub",
    "register_distilled",
    "unregister_distilled",
    "get_distilled",
]
