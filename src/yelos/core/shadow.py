# 幕 IV:影子躯体信号提取。蓝图 §6 / YELOS_SPEC §9.1。
#
# 纯逻辑:零 astrbot / 零 sylanne_core / 零 random。dict 进、dataclass 出。
# 影子躯体 = 引擎普通 session,承受用户这一侧的话;本模块只从其 state()
# 快照里读三条通道(压力/暖度跌幅/伤口),映射成一个确定性关切强度。
#
# 输出面白名单 [强制,§6.2]:本模块不含任何面向用户的字符串;唯一对外
# 可见输出由 main 拿 "concern" occasion 问 primal。故此文件所有中文说明
# 一律写成 # 注释(注释不进 AST 常量),字符串字面量全部保持 ASCII,
# 使 test_shadow 的字符串常量扫描断言"无中文陈述句"恒成立。

from __future__ import annotations

from dataclasses import dataclass

# --- 触发阈值与强度映射常量(§6.1)-------------------------------------

# 三路触发阈:压力、单日暖度跌幅、伤口开放度。
_PRESSURE_TH = 0.6
_WARMTH_DROP_TH = 0.25
_DAMAGE_TH = 0.5

# warmth_drop 绝对下限(红队 F11a):仅当当前 warmth 已低于此值才触发,
# 从 0.9 掉到 0.6 仍是暖、不该心疼;压掉首拍峰值采样的系统性误报。
_WARMTH_ABS_FLOOR = 0.45

# 归一化时的暖度跌幅刻度:min(drop / 0.5, 1)。
_WARMTH_DROP_SCALE = 0.5

# 强度映射:intensity = round(floor + span * clamp(m, 0, 1), 3)。
# 0.3 下限保证 inject 有感。
_INTENSITY_FLOOR = 0.3
_INTENSITY_SPAN = 0.7
_INTENSITY_NDIGITS = 3

# Surface 中三条通道的点路径(与主仲裁一致的 state.* 命名)。
_PATH_PRESSURE = "state.boundary.pressure"
_PATH_WARMTH = "state.valence.warmth"
_PATH_DAMAGE = "state.damage.open"

# 触发类型标签(记账/迟滞用;ASCII,进 ConcernSignal.triggers)。
_TRIGGER_PRESSURE = "pressure"
_TRIGGER_WARMTH_DROP = "warmth_drop"
_TRIGGER_DAMAGE = "damage"

_MISSING = object()


@dataclass(frozen=True)
class ConcernSignal:
    intensity: float  # [0,1],inject 用
    triggers: tuple[str, ...]  # {"pressure","warmth_drop","damage"} 子集


# --- 防御式取值(本模块自带,保持 W1 互不 import;§14)------------------


def _dig(surface: dict | None, path: str, default):
    # 点路径安全取值:任一层不是 dict 或键缺失即回退 default。
    cur = surface
    for key in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, _MISSING)
        if cur is _MISSING:
            return default
    return cur


def _num(surface: dict | None, path: str, default: float | None):
    # 只接受真实数值(排除 bool);其余一律回退保守默认。
    val = _dig(surface, path, default)
    if isinstance(val, bool):
        return default
    if isinstance(val, (int, float)):
        return float(val)
    return default


# --- §6.1 信号提取 -----------------------------------------------------


def extract_concern(
    shadow_surface: dict, warmth_day_start: float | None
) -> ConcernSignal | None:
    # 三触发任一命中即产出信号;强度取三路归一化的 max,再线性抬到 [0.3,1]。
    # shadow_surface 为 None(引擎缺席/影子只读失败)时保守返回 None。
    if not isinstance(shadow_surface, dict):
        return None

    pressure = _num(shadow_surface, _PATH_PRESSURE, 0.0)
    warmth = _num(shadow_surface, _PATH_WARMTH, None)
    damage_open = _num(shadow_surface, _PATH_DAMAGE, 0.0)

    triggers: list[str] = []
    ratios: list[float] = []

    # 触发一:压力越阈。归一 (pressure - 0.6) / 0.4。
    if pressure >= _PRESSURE_TH:
        triggers.append(_TRIGGER_PRESSURE)
        ratios.append((pressure - _PRESSURE_TH) / (1.0 - _PRESSURE_TH))

    # 触发二:单日暖度跌幅越阈,且当前暖度已跌破绝对下限。
    # baseline 为 None 则跳过跌幅判定(§2.3 保守方向)。
    if warmth_day_start is not None and warmth is not None:
        drop = warmth_day_start - warmth
        if drop >= _WARMTH_DROP_TH and warmth < _WARMTH_ABS_FLOOR:
            triggers.append(_TRIGGER_WARMTH_DROP)
            ratios.append(min(drop / _WARMTH_DROP_SCALE, 1.0))

    # 触发三:伤口开放度越阈。归一 (open - 0.5) / 0.5。
    if damage_open >= _DAMAGE_TH:
        triggers.append(_TRIGGER_DAMAGE)
        ratios.append((damage_open - _DAMAGE_TH) / (1.0 - _DAMAGE_TH))

    if not triggers:
        return None

    m = max(ratios)
    m = min(max(m, 0.0), 1.0)
    intensity = round(_INTENSITY_FLOOR + _INTENSITY_SPAN * m, _INTENSITY_NDIGITS)
    return ConcernSignal(intensity=intensity, triggers=tuple(triggers))
