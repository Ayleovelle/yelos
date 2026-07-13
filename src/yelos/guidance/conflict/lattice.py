"""A2 保守偏序格:每维定义"保守度"全序,冲突消解 = 取该维保守方向的最大元
(join)。数值排名与 v0.1 ``_TONE_RANK`` 完全一致,length/pace 排名把 v0.1
分支逻辑里隐含的偏序显式化(蓝图 §9 Q1:没有发明新数学,只是显式化)。

性质(T2 测试逐条对应,不在本文件重复证明,只保证实现满足):
    - join 幂等 / 交换 / 结合(数值 max 天然满足)
    - ∀ 子集 S,resolve(S) ⊒ S 中最保守成员(max 天然满足)
    - S ⊆ S' ⇒ resolve(S') ⊒ resolve(S)(加元素不减 max,天然满足)
"""

from __future__ import annotations

# tone:brief 最保守(4),warm 最开放(0)。与 v0.1 _TONE_RANK 数值一致。
TONE_RANK: dict[str, int] = {
    "brief": 4,
    "gentle": 3,
    "neutral": 2,
    "direct": 1,
    "warm": 0,
}
TONE_DEFAULT = "neutral"

# length(companion 语义):short 最保守,medium 是无贡献默认。
LENGTH_RANK: dict[str, int] = {"medium": 0, "long": 1, "short": 2}
LENGTH_DEFAULT = "medium"

# pace(companion 语义):give_space 最保守,steady 是无贡献默认。
PACE_RANK: dict[str, int] = {"steady": 0, "relaxed": 1, "give_space": 2}
PACE_DEFAULT = "steady"


def join_tone(tones: list[str]) -> str:
    """tone 冲突取更保守(§4.2:gentle/brief 胜 warm/direct)。"""
    if not tones:
        return TONE_DEFAULT
    return max(tones, key=lambda t: TONE_RANK.get(t, TONE_RANK[TONE_DEFAULT]))


def join_length(lengths: list[str]) -> str:
    """length 冲突:short ≻ long ≻ medium(companion 语义)。

    调用方须已按 profile 的 ``neutralize_short`` 位提前剔除 "short" 贡献
    (steward 中性化在 interpreter 层做,lattice 本身不知道 mode/profile)。
    """
    if not lengths:
        return LENGTH_DEFAULT
    return max(lengths, key=lambda v: LENGTH_RANK.get(v, LENGTH_RANK[LENGTH_DEFAULT]))


def join_pace(paces: list[str]) -> str:
    """pace 冲突:give_space ≻ relaxed ≻ steady(companion 语义)。

    调用方须已按 profile 的 ``neutralize_pace`` 位提前清空贡献列表。
    """
    if not paces:
        return PACE_DEFAULT
    return max(paces, key=lambda v: PACE_RANK.get(v, PACE_RANK[PACE_DEFAULT]))


def join_respect_pause(flags: list[bool]) -> bool:
    """respect_pause:布尔 OR(任一触发即 True,无中性化位)。"""
    return any(flags)
