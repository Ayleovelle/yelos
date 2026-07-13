"""3 档 EffectiveProfile 常量 + steward 抑制矩阵参数化(蓝图 §3.4/§4.4/§4.5)。

诚实边界(§9 Q3):不是策略族,三档是同一解释器 + 同一规则集上的参数化档位
(维二只计 1 算法);每档与 chat 的可观测差异由 test_profiles_matrix.py 固化。
"""

from __future__ import annotations

from .model import EffectiveProfile
from .rules import _P_TEMP

# coding:砍闲聊温度类(prio 3),留 CAUTION(prio 3 但明确保留)/CONCERN(prio 1
# 不受影响)。用 drop_priorities 整体剔除 prio 3,但 CAUTION 例外——用
# hint_key 白名单更精确,故这里改用"排除集合"而非单纯 priority 判定。
_CODING_KEEP_AT_TEMP = frozenset({"CAUTION"})

_PROFILES: dict[str, EffectiveProfile] = {
    "coding": EffectiveProfile(
        name="coding",
        hint_cap=2,
        drop_priorities=frozenset({_P_TEMP}),
    ),
    "chat": EffectiveProfile(
        name="chat",
        hint_cap=3,
        drop_priorities=frozenset(),
    ),
    "voice": EffectiveProfile(
        name="voice",
        hint_cap=3,
        drop_priorities=frozenset(),
        voice_fields=True,
    ),
}


def resolve_profile(name: str, mode: str) -> EffectiveProfile:
    """按 profile 名 + mode 解出最终生效档位(steward 抑制位在此按 mode 置位)。

    未知 profile 名保守回落 "chat"(不炸、不静默改变调用方预期之外的行为)。
    """
    base = _PROFILES.get(name, _PROFILES["chat"])
    if mode != "steward":
        return base
    return EffectiveProfile(
        name=base.name,
        hint_cap=base.hint_cap,
        drop_priorities=base.drop_priorities,
        neutralize_short=True,
        neutralize_pace=True,
        drop_truncation_hints=True,
        voice_fields=base.voice_fields,
    )


def profile_keeps_hint_at_dropped_priority(profile_name: str, hint_key: str) -> bool:
    """coding 档在 prio=_P_TEMP 整体剔除之外,单独放行 CAUTION(§4.4 表)。"""
    if profile_name != "coding":
        return False
    return hint_key in _CODING_KEEP_AT_TEMP


__all__ = ["resolve_profile", "profile_keeps_hint_at_dropped_priority"]
