"""在整个架构中的位置:语气词强度梯度(蓝图 §8.1)——仅作用于 template 源。

**已知简化(交审须知)**:蓝图原描述"梯度表是 grammar_zh.json 中粒子槽的
三档填充集,不是运行时字符串手术"。但 composer 步骤 12→13 的既定顺序
是先 prosody.plan(canonical) 再 morphology.apply(plan.text),形态输入
已是韵律变换后的文本,若在文法生成阶段就把粒子焊死进 canonical,会
让"槽位选择"与"闸前 canonical"耦合、且无法在 prosody 之后再按 warmth
覆盖。故本实现把语气词粒子作为**闭合候选集的追加后缀**处理:候选集合
本身仍是 §8.1 决策表描述的三档封闭槽位(pool),选择算子仍是收缩代数
(epochal.epoch_pool),只是落笔时机从"文法生成期"挪到"prosody 之后
的追加步",机制上仍是槽位选择而非任意字符串手术。已如实记录,红队
可核对是否需要挪回 template.py 内部(那样需要在文法生成后暂缓一步,
留 prosody 处理占位符,复杂度更高,权衡后选择本方案)。
"""

from __future__ import annotations

from . import epochal

# occasion -> 三档(低/中/高 warmth)语气词候选池,index 0 = 最克制。
PARTICLE_POOL: dict[str, tuple[str, ...]] = {
    "contact_seek": ("", "嗯", "嗯嗯", "嗯嗯!"),
    "express_warm": ("", "嗯", "嗯嗯", "嗯嗯!"),
    "concern": ("", "嗯", "嗯嗯"),
    "recover": ("", "嗯", "嗯嗯"),
    "withdraw_soft": ("", "嗯"),
    "contact_night": ("", "嗯"),
    "dream_murmur": ("",),
}

# 仅这些场合允许"活泼"档带感叹号(§8.1)。
_EXCLAIM_ALLOWED = frozenset({"express_warm", "contact_seek"})


def warmth_tier(surface: dict) -> int:
    """借引擎信号(surface.valence.warmth),缺失给中档保守默认(sget 防御)。

    返回 0(低)/1(中)/2(高)三档 ordinal。
    """
    try:
        valence = surface.get("valence", {}) if isinstance(surface, dict) else {}
        warmth = float(valence.get("warmth", 0.5)) if isinstance(valence, dict) else 0.5
    except (TypeError, ValueError):
        warmth = 0.5
    warmth = max(0.0, min(1.0, warmth))
    if warmth < 0.35:
        return 0
    if warmth < 0.65:
        return 1
    return 2


def select_particle(
    occasion: str, surface: dict, epoch: int, sid: str, incarnation: int
) -> str:
    base_pool = PARTICLE_POOL.get(occasion, ())
    if not base_pool:
        return ""
    pool = epochal.epoch_pool(base_pool, epoch, sid, incarnation)
    tier = warmth_tier(surface)
    idx = min(tier, len(pool) - 1)
    candidate = pool[idx]
    if candidate.endswith("!") and occasion not in _EXCLAIM_ALLOWED:
        candidate = candidate.rstrip("!")
    return candidate


def morph_key(sid: str, incarnation: int) -> str:
    return f"{sid}|{incarnation}|morph_seed"


def apply(
    text: str,
    surface: dict,
    occasion: str,
    epoch: int,
    sid: str,
    incarnation: int,
    lang: str,
    *,
    source_provider: str,
) -> tuple[str, tuple[str, ...]]:
    """§8.1 裁决:仅 template 源施加形态变化;lexicon 源著作句不机改。"""
    if source_provider != "template" or lang != "zh":
        return text, ()
    particle = select_particle(occasion, surface, epoch, sid, incarnation)
    if not particle or particle in text:
        return text, ()
    return f"{text}{particle}", (f"particle:{particle}",)


__all__ = ["PARTICLE_POOL", "warmth_tier", "select_particle", "morph_key", "apply"]
