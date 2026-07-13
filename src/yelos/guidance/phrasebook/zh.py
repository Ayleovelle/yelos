"""正典句库(zh)——v0.1 18 句逐字收编,零语义漂移。

白名单纪律(A1/I5):全部是"对 agent 说她怎样/该怎么回"的祈使/描述句,
主语恒为"她",不对用户下第二人称诊断("你+状态谓词"式)。唯一登记在案的
例外是 CONCERN(她像是有点担心"你"——"你"是她关心的对象，不是对用户状态
的断言),见 tests/test_guidance_mcp.py 的既定纪律。
"""

from __future__ import annotations

PHRASES_ZH: dict[str, str] = {
    "WITHDRAW": "她想收一收，别追问，给点空间。",
    "RECOVER": "她在缓，温和点，别施压。",
    "REACH_OUT": "她像是想靠近，可以主动搭句话。",
    "EXPLORE": "她有点好奇，可以聊点新的。",
    "GUARD_DECISION": "她在守边界，简短些，别越线。",
    "EXPRESS": "她有话想说，给她展开的空间。",
    "STRAIN": "节律紧，回短一点。",
    "FATIGUE": "她累了，别拖长。",
    "WARM_HIGH": "心情不错，语气可以活泼些。",
    "WARM_LOW": "情绪低，语气温柔些。",
    "DAMAGE": "她受过些伤，整体软一点。",
    "AUTONOMY": "自主权紧，别命令式，给选择。",
    "QUIET": "她想静一静，少说点。",
    "EXPRESSION": "她想表达，别打断。",
    "DORMANT": "很久没联系了，重新开口温和些。",
    "CAUTION": "她不太笃定，回复别下绝对结论。",
    "CONCERN": "她像是有点担心你，可以关心一句。",
    "GUARD_BLOCKED": "她在克制，别硬推这个方向。",
}
