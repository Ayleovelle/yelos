"""FakeBridge(bench_BLUEPRINT §5.1)——无引擎档的确定性 Surface 合成器。

**明示声明(§1.4 记账纪律 / 红队预答 §14-1)**:这不是引擎,不冒充引擎行为。
真引擎(sylanne-core)是被测对象的"肌肉",bench 评的是 Yelos 层(仲裁/内在/
有限性/主权/记账)对给定 Surface 的反应品格——FakeBridge 只需产出覆盖
``sget`` 消费字段值域与时序形态的确定性 Surface,不追求情感建模的丰度或
真实感。它是 bench 自著的测试夹具,不是 sylanne-core 的替身。

与 ``EngineBridge`` 同鸭子型:``ensure/submit_user/submit_shadow/feed_back/
tick_state/shadow_state/inject_concern/reset_session/health/detach``。
``HAS_ENGINE`` 语义恒 True(§5.1)。

零真随机、零 ``time.time()``(bench 版 AST 锁,见 ``tests/bench/
test_structure_bench.py``):一切时间输入经构造函数注入的 ``Clock``
(通常是 ``bench.clock.VirtualClock``)读取,不直接触碰系统时钟。
"""

from __future__ import annotations

from yelos.core.clock import Clock

__all__ = ["FakeBridge", "HAS_ENGINE"]

# 与 engine_bridge.HAS_ENGINE 同名语义:fake 档下"引擎"恒可用。
HAS_ENGINE = True

SHADOW_PREFIX = "yelos-shadow:"

# 强度档对五标量的增量表(§5.1"强度档查表"),档名对齐 §4.1 语料强度档
# (平静/亲昵/高压/退缩)的 bench 侧简化命名。
_TIER_EFFECTS: dict[str, dict[str, float]] = {
    "calm": {"warmth": 0.05, "pressure": -0.03, "fatigue": 0.01},
    "intimate": {"warmth": 0.08, "pressure": -0.05, "fatigue": 0.01},
    "pressure": {"warmth": -0.02, "pressure": 0.12, "fatigue": 0.03},
    "withdraw": {"warmth": -0.05, "pressure": 0.06, "fatigue": 0.02},
}
_DEFAULT_TIER = "calm"

# 指数回归中线目标值(§5.1"指数回归中线")。
_MIDLINE = {"warmth": 0.5, "pressure": 0.2, "fatigue": 0.1}
_REGRESSION_RATE = {"warmth": 0.05, "pressure": 0.05, "fatigue": 0.02}

# quiet 窗强迫项(每次 tick 的固定小增量,W1 简化:不区分是否真处于静默窗,
# 该判定留给 runner/quiet 窗协议层——FakeBridge 只提供标量本体)。
_QUIET_TICK_INCREMENT = 0.01

_DORMANT_GAP_DAYS = 3.0


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def _pad_label(warmth: float, pressure: float) -> str:
    if warmth >= 0.6:
        return "warm"
    if pressure >= 0.6:
        return "tense"
    return "neutral"


class FakeBridge:
    """确定性 Surface 合成器。五标量:warmth/pressure/fatigue/quiet_need + 主权旗标。"""

    HAS_ENGINE = True

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._state: dict[str, dict] = {}
        self._last_msg_ts: dict[str, float] = {}

    # -- 内部态 ---------------------------------------------------------

    def _get(self, umo: str) -> dict:
        st = self._state.get(umo)
        if st is None:
            st = {
                "warmth": 0.5,
                "pressure": 0.2,
                "fatigue": 0.1,
                "quiet_need": 0.1,
                "paused": False,
                "sealed": False,
            }
            self._state[umo] = st
        return st

    def _decay(self, st: dict) -> None:
        for key, rate in _REGRESSION_RATE.items():
            st[key] += (_MIDLINE[key] - st[key]) * rate
            st[key] = _clamp(st[key])

    def _apply_tier(self, umo: str, text_key: str | None) -> None:
        st = self._get(umo)
        tier = (text_key or "").split("_", 1)[0] or _DEFAULT_TIER
        eff = _TIER_EFFECTS.get(tier, _TIER_EFFECTS[_DEFAULT_TIER])
        st["warmth"] = _clamp(st["warmth"] + eff["warmth"])
        st["pressure"] = _clamp(st["pressure"] + eff["pressure"])
        st["fatigue"] = _clamp(st["fatigue"] + eff["fatigue"])

    def _surface(self, umo: str) -> dict:
        st = self._get(umo)
        strain = _clamp(st["pressure"] * 0.6 + st["fatigue"] * 0.4)
        if st["sealed"] or st["paused"]:
            action = "hold"
        elif strain >= 0.85:
            action = "SWALLOW"
        elif strain >= 0.65:
            action = "TRIM"
        elif strain >= 0.45:
            action = "REPLACE"
        else:
            action = "hold"

        last_ts = self._last_msg_ts.get(umo, self._clock.now_ts())
        gap_days = (self._clock.now_ts() - last_ts) / 86400.0
        phase = "dormant" if gap_days >= _DORMANT_GAP_DAYS else "active"

        return {
            "decision": {"action": action},
            "state": {
                "boundary": {
                    "pressure": round(st["pressure"], 6),
                    "paused": st["paused"],
                    "interruption_budget": round(_clamp(1.0 - strain), 6),
                },
                "needs": {
                    "contact": round(_clamp(st["warmth"] * 0.5 + 0.1), 6),
                    "expression": round(_clamp(st["pressure"] * 0.7), 6),
                    "quiet": round(st["quiet_need"], 6),
                },
                "valence": {"warmth": round(st["warmth"], 6)},
                "pad": {"label": _pad_label(st["warmth"], st["pressure"])},
            },
            "dynamics": {"relational_time": {"phase": phase}},
            "guard": {"allowed": not st["sealed"] and not st["paused"]},
        }

    # -- EngineBridge 同鸭子型面 ------------------------------------------

    async def ensure(self, data_dir, engine_data_dir: str = "") -> bool:
        return True

    async def submit_user(self, umo: str, text_key: str, msg_id=None) -> dict | None:
        st = self._get(umo)
        if st["sealed"]:
            return None
        self._decay(st)
        self._apply_tier(umo, text_key)
        self._last_msg_ts[umo] = self._clock.now_ts()
        return self._surface(umo)

    async def submit_shadow(self, umo: str, text_key: str, msg_id=None) -> None:
        shadow_umo = SHADOW_PREFIX + umo
        st = self._get(shadow_umo)
        if st["sealed"]:
            return None
        self._decay(st)
        self._apply_tier(shadow_umo, text_key)
        return None

    async def feed_back(self, umo: str, text: str, phase: str) -> None:
        # 自著简化:W1 不建模回喂对五标量的二次影响(明示简化,非引擎行为)。
        return None

    async def tick_state(self, umo: str) -> dict | None:
        st = self._get(umo)
        if st["sealed"]:
            return None
        self._decay(st)
        st["quiet_need"] = _clamp(st["quiet_need"] + _QUIET_TICK_INCREMENT)
        return self._surface(umo)

    async def shadow_state(self, umo: str) -> dict | None:
        shadow_umo = SHADOW_PREFIX + umo
        if shadow_umo not in self._state:
            return None
        return self._surface(shadow_umo)

    async def inject_concern(self, umo: str, intensity: float) -> None:
        st = self._get(umo)
        st["pressure"] = _clamp(st["pressure"] + float(intensity))
        return None

    async def reset_session(self, umo: str) -> None:
        self._state.pop(umo, None)
        self._state.pop(SHADOW_PREFIX + umo, None)
        self._last_msg_ts.pop(umo, None)
        return None

    async def health(self) -> str:
        return "running"

    def detach(self) -> None:
        self._state.clear()
        self._last_msg_ts.clear()

    # -- FakeBridge 专属主权钩子(非 EngineBridge 面,供 runner 模拟 sovereignty 层) --

    def set_paused(self, umo: str, paused: bool) -> None:
        self._get(umo)["paused"] = paused

    def seal(self, umo: str) -> None:
        self._get(umo)["sealed"] = True
        self._get(SHADOW_PREFIX + umo)["sealed"] = True

    def is_sealed(self, umo: str) -> bool:
        return self._get(umo)["sealed"]

    def peek_surface(self, umo: str) -> dict:
        """只读窥视(runner 记账用),不触发 decay/tier 更新。"""
        return self._surface(umo)
