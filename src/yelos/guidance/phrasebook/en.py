"""en 句库——RE8 母语审校门控:未过审前 ``UNLOCKED = False``,运行时一律
回落 zh(锁而不假,§9 诚实自评 1)。草稿句面先占位,不构成用户可见行为。
"""

from __future__ import annotations

UNLOCKED = False

PHRASES_EN: dict[str, str] = {
    "WITHDRAW": "She wants to pull back a little — give her room, don't press.",
    "RECOVER": "She's recovering — go gentle, don't push.",
    "REACH_OUT": "She seems to want to get closer — you can open with something.",
    "EXPLORE": "She's a little curious — fine to bring up something new.",
    "GUARD_DECISION": "She's guarding a boundary — keep it short, don't cross it.",
    "EXPRESS": "She has something to say — give her room to unfold it.",
    "STRAIN": "Rhythm's tight — keep the reply short.",
    "FATIGUE": "She's tired — don't drag it out.",
    "WARM_HIGH": "Mood's good — tone can be livelier.",
    "WARM_LOW": "Mood's low — go softer.",
    "DAMAGE": "She's carrying some hurt — be gentler overall.",
    "AUTONOMY": "Autonomy is tight — no commands, offer choices.",
    "QUIET": "She wants quiet — say less.",
    "EXPRESSION": "She wants to express — don't cut her off.",
    "DORMANT": "It's been a while — open back up gently.",
    "CAUTION": "She's not fully sure — avoid absolute claims.",
    "CONCERN": "She seems a little worried about you — a caring word would help.",
    "GUARD_BLOCKED": "She's holding back — don't push this direction.",
}
