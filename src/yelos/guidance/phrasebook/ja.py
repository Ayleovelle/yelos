"""ja 句库——同 en.py:RE8 母语审校门控,未过审前 ``UNLOCKED = False``,
运行时回落 zh。草稿占位,不构成用户可见行为。
"""

from __future__ import annotations

UNLOCKED = False

PHRASES_JA: dict[str, str] = {
    "WITHDRAW": "少し引きたいみたい。追わずに、間を空けて。",
    "RECOVER": "回復中。優しく、追い込まないで。",
    "REACH_OUT": "近づきたそうにしてる。こちらから話しかけていい。",
    "EXPLORE": "ちょっと好奇心が出てる。新しい話題もいい。",
    "GUARD_DECISION": "境界を守ってる。短く、踏み込まないで。",
    "EXPRESS": "話したいことがある。広げる余地をあげて。",
    "STRAIN": "リズムが張ってる。返信は短めに。",
    "FATIGUE": "疲れてる。長引かせないで。",
    "WARM_HIGH": "機嫌がいい。少し明るい調子でいい。",
    "WARM_LOW": "気分が低い。もっと優しく。",
    "DAMAGE": "少し傷を抱えてる。全体的に柔らかく。",
    "AUTONOMY": "自主権がタイト。命令せず選択肢を。",
    "QUIET": "静かにしていたい。言葉少なめに。",
    "EXPRESSION": "表現したがってる。遮らないで。",
    "DORMANT": "しばらく間があった。優しく再開して。",
    "CAUTION": "あまり確信がない。断定は避けて。",
    "CONCERN": "あなたのことを少し心配してるみたい。気にかけてあげて。",
    "GUARD_BLOCKED": "自制してる。この方向を無理に押さないで。",
}
