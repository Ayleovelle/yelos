"""ensemble.py 在整个架构中的位置:K 条影子轨迹的多假设编排(蓝图 §4.1),
shadow 自著实质①的主体。**引擎借来记账纪律**:本文件只编排"喂谁/读谁/扰动
谁",每条轨迹内部的动力学演化是引擎行为,一字节不入自著账(蓝图 §0)。

h0 正典轨迹 = v0.1 既有影子 session(`bridge.submit_shadow`/`shadow_state`,
零改动);h1..hK-1 假设轨迹经 `BridgeProto` 的可选扩展方法
(`submit_shadow_hyp`/`shadow_state_hyp`/`inject_shadow_perturb`)喂养——
真实 `engine_bridge.py` 尚未实现这三个方法(本任务"只建新文件"不编辑它),
`_has_hyp_support` 做特性探测,不支持时多假设路径静默退化为只读 h0
(K_effective 视为 1,与默认配置行为一致,不 raise、不报错文本)。
"""

from __future__ import annotations

from typing import Any

from ..contracts import EnsembleReading, ShadowView
from . import epsilon as eps_mod

_ENGINE_CHANNELS = ("pressure", "warmth", "damage")
_CHANNEL_PATH = {
    "pressure": ("state", "boundary", "pressure"),
    "warmth": ("state", "valence", "warmth"),
    "damage": ("state", "damage", "open"),
}
_MISSING = object()


def _dig(surface: dict | None, path: tuple[str, ...]):
    cur: Any = surface
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key, _MISSING)
        if cur is _MISSING:
            return None
    if isinstance(cur, bool) or not isinstance(cur, (int, float)):
        return None
    return float(cur)


def surface_to_view(surface: dict | None, hyp_id: int) -> ShadowView:
    """引擎 Surface 的防御式投影(缺席/异常一律 None,保守方向)。"""
    return ShadowView(
        pressure=_dig(surface, _CHANNEL_PATH["pressure"]),
        warmth=_dig(surface, _CHANNEL_PATH["warmth"]),
        damage=_dig(surface, _CHANNEL_PATH["damage"]),
        hyp_id=hyp_id,
    )


def _has_hyp_support(bridge: Any) -> bool:
    return (
        callable(getattr(bridge, "submit_shadow_hyp", None))
        and callable(getattr(bridge, "shadow_state_hyp", None))
        and callable(getattr(bridge, "inject_shadow_perturb", None))
    )


async def feed_user_turn(
    bridge: Any, sid: str, text: str, msg_id: str, k_effective: int
) -> None:
    """[SHTOM-A1] 一轮用户话喂给全部 K 条轨迹。调用方须已确认

    `speaker == "user"` 且不在 major③ 冲突窗内(编排层之前的防线,本函数
    不重复判断,只管喂)。h0 用既有 `submit_shadow`(零改动);h1..hK-1 的
    `msg_id` 加 `#h{k}` 后缀防引擎按 msg_id 去重误合并。
    """
    await bridge.submit_shadow(sid, text, msg_id)
    if k_effective <= 1 or not _has_hyp_support(bridge):
        return
    for k in range(1, k_effective):
        await bridge.submit_shadow_hyp(sid, k, text, f"{msg_id}#h{k}")


async def apply_daily_perturbation(
    bridge: Any,
    sid: str,
    day_key: str,
    k_effective: int,
    sigma_obs: float,
    sigma_family: float,
    *,
    epsilon_override: float | None = None,
) -> float:
    """每日首拍对 h1..hK-1 各做一次哈希确定性扰动(蓝图 §4.1)。

    只碰假设轨迹,永不碰主 session 与 h0(A1 的模拟公理边界)。返回本次
    使用的 ε_t(供 `EnsembleReading.epsilon_used` 记账/可视化——不进决策)。
    """
    epsilon_used = eps_mod.compute_epsilon(
        sigma_obs, sigma_family, epsilon_override=epsilon_override
    )
    if k_effective <= 1 or not _has_hyp_support(bridge):
        return epsilon_used
    for k in range(1, k_effective):
        direction = eps_mod.perturb_direction(sid, day_key, k)
        await bridge.inject_shadow_perturb(sid, k, epsilon_used * direction)
    return epsilon_used


async def read_ensemble(
    bridge: Any, sid: str, k_effective: int
) -> tuple[ShadowView, ...]:
    """读取 K 条轨迹当前读数;h0 恒在 [0]。假设轨迹缺席能力时只返回 h0。"""
    h0_surface = await bridge.shadow_state(sid)
    views = [surface_to_view(h0_surface, 0)]
    if k_effective <= 1 or not _has_hyp_support(bridge):
        return tuple(views)
    for k in range(1, k_effective):
        surface = await bridge.shadow_state_hyp(sid, k)
        views.append(surface_to_view(surface, k))
    return tuple(views)


def compute_disagreement(
    views: tuple[ShadowView, ...], spans: dict[str, float]
) -> float:
    """D_t = max_ch( range(views[*].ch) / span_ch )(蓝图 §4.3)。

    K=1(只有 h0)时无从定义分歧,返回 0.0(u_t 退化为纯校准法的前置条件,
    由调用方——orchestrator——按 §4.3 决定是否走退化分支)。
    """
    if len(views) < 2:
        return 0.0
    worst = 0.0
    for ch in _ENGINE_CHANNELS:
        span = spans.get(ch, 1.0)
        vals = [getattr(v, ch) for v in views if getattr(v, ch) is not None]
        if len(vals) < 2 or span <= 0:
            continue
        ratio = (max(vals) - min(vals)) / span
        worst = max(worst, ratio)
    return max(0.0, min(1.0, worst))


def build_ensemble_reading(
    views: tuple[ShadowView, ...],
    spans: dict[str, float],
    epsilon_used: float,
    degraded: bool,
) -> EnsembleReading:
    disagreement = compute_disagreement(views, spans)
    return EnsembleReading(
        views=views,
        disagreement=disagreement,
        epsilon_used=epsilon_used,
        degraded=degraded,
    )


__all__ = [
    "surface_to_view",
    "feed_user_turn",
    "apply_daily_perturbation",
    "read_ensemble",
    "compute_disagreement",
    "build_ensemble_reading",
]
