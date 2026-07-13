"""field/impacts.py 在整个架构中的位置:Surface/事件 → 冲击向量校准表(维一自著)。

**边界句(intrinsic_BLUEPRINT §0.2)**:引擎 Surface 是"她的躯体感受"(借用);
φ 的每个通道是 Surface 多字段 + 事件史 + 昼夜相位的自著泛函,不是 Surface
字段的改名转录。本文件的 `from_surface` 用**交互项**(两个 Surface 字段的
乘积/门控组合)构造冲击,而非任一单字段的仿射复制——机器凭据见 [AX-5] /
T-FLD-04:即便 Surface 逐拍恒定,`from_surface` 对同一恒定输入返回**同一
冲击向量**,但场的演化仍由 decay_term(field/dynamics.py)与 circadian
forcing 持续推进,不会冻结在 Surface 快照上(冲击只是导数三项之一)。

一切读取经 core.sget 防御式取值,缺字段回落中性默认,绝不 raise。
"""

from __future__ import annotations

from yelos.core import sget

from .state import FieldParams, Vec4

# --- Surface 字段白名单([AX-5];借用面清单,§0.2 两栏表引用同一份)--------

SURFACE_WHITELIST: tuple[str, ...] = (
    "state.needs.contact",
    "state.needs.expression",
    "state.needs.quiet",
    "state.boundary.pressure",
    "state.valence.warmth",
    "state.damage.open",
    "dynamics.relational_time.phase",
)

# --- 离散事件冲击表(自著校准,§0.2 入账清单)------------------------------
# 键 = 心跳/impulse 侧翻译出的事件类型(非 Surface 原文,是编排层判定后的
# 离散事件名);值 = 单位冲击向量 (drive, languor, longing, afterglow),
# 会再乘一个 0..1 的强度系数(由触发方给出,如 concern 的 severity)。

IMPACT_TABLE: dict[str, Vec4] = {
    "user_turn": (0.10, -0.05, -0.15, 0.20),  # 对方开口:牵挂回落,余温升
    "her_word": (-0.05, 0.05, -0.05, 0.10),  # 她说了:动机小泄,略添倦意
    "swallowed": (0.05, 0.05, 0.10, -0.02),  # 想说而咽下:牵挂/倦意都涨
    "concern": (0.05, 0.0, 0.20, -0.05),  # 心疼信号:牵挂显著上升
    "reunion": (0.0, -0.10, -0.30, 0.15),  # 久别重逢:倦意/牵挂骤降,余温升
}

EVENT_KINDS: tuple[str, ...] = tuple(IMPACT_TABLE.keys())


def _vec_norm(v: Vec4) -> float:
    return sum(x * x for x in v) ** 0.5


def _clip_norm(v: Vec4, i_max: float) -> Vec4:
    """[AX-4] 冲击有界:范数 > i_max 时按比例缩放,不做逐分量硬 clip。"""
    n = _vec_norm(v)
    if n <= i_max or n == 0.0:
        return v
    scale = i_max / n
    return tuple(x * scale for x in v)  # type: ignore[return-value]


def event_impact(kind: str, intensity: float, params: FieldParams) -> Vec4:
    """单个离散事件 → 冲击向量(已按 intensity 缩放并按 i_max 界定)。"""
    base = IMPACT_TABLE.get(kind)
    if base is None:
        return (0.0, 0.0, 0.0, 0.0)
    intensity = max(0.0, min(1.0, intensity))
    scaled = tuple(x * intensity for x in base)
    return _clip_norm(scaled, params.i_max)


def from_surface(
    surface: dict | None,
    events: tuple[tuple[str, float], ...],
    params: FieldParams,
) -> Vec4:
    """Surface 快照 + 本拍离散事件队列 → 合成冲击向量(自著泛函,非转录)。

    Surface 侧只贡献两个**交互项**(而非任一字段的直接复制):
    - 「表达压力」= needs.expression × boundary.pressure(两高才算真压力,
      drive 承压、languor 微升);
    - 「静默积累」= needs.quiet ×(1 − needs.contact)(quiet 高且 contact 低
      才计静默积累,longing 承接)。
    这两项本身即已界定在 [0,1] 之内(两个 [0,1] 字段相乘),再与事件冲击
    合并后统一按 [AX-4] 用范数裁剪,不逐分量硬截断。
    """
    s = surface
    expression = sget(s, "state.needs.expression", 0.0)
    pressure = sget(s, "state.boundary.pressure", 0.0)
    quiet = sget(s, "state.needs.quiet", 0.0)
    contact = sget(s, "state.needs.contact", 0.0)

    expr_pressure = expression * pressure
    silence_accum = quiet * (1.0 - contact)

    surface_term: Vec4 = (
        -0.05 * expr_pressure,
        0.08 * expr_pressure,
        0.12 * silence_accum,
        0.0,
    )

    total = list(surface_term)
    for kind, intensity in events:
        ev = event_impact(kind, intensity, params)
        total = [a + b for a, b in zip(total, ev)]

    return _clip_norm(tuple(total), params.i_max)  # type: ignore[return-value]


__all__ = [
    "SURFACE_WHITELIST",
    "IMPACT_TABLE",
    "EVENT_KINDS",
    "event_impact",
    "from_surface",
]
