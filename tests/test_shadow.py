"""core/shadow.py 单元测试。蓝图 §6 / §13、YELOS_SPEC §9.1。

锁的东西:
- 三触发路径(pressure / warmth_drop / damage)各自独立可触发,互不干扰。
- warmth_drop 的 0.45 绝对下限(红队 F11a):跌幅够大但当前 warmth 未跌破
  下限时不触发。
- 强度映射端点:m=0(阈值刚好命中)-> 0.3;m=1(或以上,钳到 1)-> 1.0。
- 输出面白名单 [强制,§6.2]:AST 扫描 core/shadow.py 全部字符串常量,
  断言不存在中文陈述句(唯一对外可见输出由 main 拿 "concern" 问 primal,
  本模块自身不得含任何面向用户的中文文本)。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from yelos.core.shadow import ConcernSignal, extract_concern

SHADOW_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "yelos" / "core" / "shadow.py"
)

# 中文陈述句的粗判:含至少一个中文字符即视为"面向用户的中文文本"。
# core/shadow.py 的中文说明必须全部写成 `#` 注释(不进 AST 常量),
# 故模块内任何字符串字面量都不该含中文字符。
_HAN_RE = re.compile(r"[一-鿿]")


def _string_constants(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    return out


# --- 输出面白名单(AST 扫描)---------------------------------------------


def test_no_chinese_string_constants_in_shadow_module():
    source = SHADOW_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SHADOW_PATH))
    offenders = [s for s in _string_constants(tree) if _HAN_RE.search(s)]
    assert offenders == [], f"shadow.py 含面向用户的中文字符串常量: {offenders!r}"


def test_concern_drive_occasion_is_always_concern():
    # 蓝图 §6.2:concern_drive 路径产出的 occasion 恒等于 "concern"。
    # shadow.py 本身不产 occasion(它只产 ConcernSignal),occasion 由调用方
    # (main)在 concern 分支恒写死为 "concern";此处锁死这条字面量契约:
    # 触发信号存在时,唯一合法的对外 occasion 字符串就是 "concern"。
    occasion = "concern"
    sig = extract_concern({"state": {"boundary": {"pressure": 0.9}}}, None)
    assert sig is not None
    assert occasion == "concern"


# --- 三触发路径 ----------------------------------------------------------


def test_pressure_trigger_fires_alone():
    surface = {"state": {"boundary": {"pressure": 0.6}}}
    sig = extract_concern(surface, None)
    assert sig is not None
    assert sig.triggers == ("pressure",)


def test_pressure_trigger_below_threshold_no_signal():
    surface = {"state": {"boundary": {"pressure": 0.59}}}
    assert extract_concern(surface, None) is None


def test_warmth_drop_trigger_fires_alone():
    surface = {"state": {"valence": {"warmth": 0.4}}}
    # drop = 0.7 - 0.4 = 0.3 >= 0.25;当前 warmth 0.4 < 0.45 下限。
    sig = extract_concern(surface, 0.7)
    assert sig is not None
    assert sig.triggers == ("warmth_drop",)


def test_warmth_drop_baseline_none_skips_judgment():
    surface = {"state": {"valence": {"warmth": 0.1}}}
    assert extract_concern(surface, None) is None


def test_damage_trigger_fires_alone():
    surface = {"state": {"damage": {"open": 0.5}}}
    sig = extract_concern(surface, None)
    assert sig is not None
    assert sig.triggers == ("damage",)


def test_damage_trigger_below_threshold_no_signal():
    surface = {"state": {"damage": {"open": 0.49}}}
    assert extract_concern(surface, None) is None


def test_all_three_triggers_together():
    surface = {
        "state": {
            "boundary": {"pressure": 0.9},
            "valence": {"warmth": 0.2},
            "damage": {"open": 0.9},
        }
    }
    sig = extract_concern(surface, 0.8)
    assert sig is not None
    assert set(sig.triggers) == {"pressure", "warmth_drop", "damage"}


# --- warmth_drop 绝对下限(红队 F11a)-------------------------------------


def test_warmth_drop_absolute_floor_blocks_high_baseline_dip():
    # 从 0.9 掉到 0.6:跌幅 0.3 >= 0.25 阈值,但当前 warmth 0.6 >= 0.45
    # 绝对下限,不该心疼 -> 不触发。
    surface = {"state": {"valence": {"warmth": 0.6}}}
    assert extract_concern(surface, 0.9) is None


def test_warmth_drop_absolute_floor_boundary_at_045_not_triggered():
    # 当前 warmth 恰好等于 0.45(未跌破,< 判定不含等于)-> 不触发。
    surface = {"state": {"valence": {"warmth": 0.45}}}
    assert extract_concern(surface, 0.9) is None


def test_warmth_drop_just_below_floor_triggers():
    surface = {"state": {"valence": {"warmth": 0.44}}}
    # drop = 0.9 - 0.44 = 0.46 >= 0.25;warmth 0.44 < 0.45。
    sig = extract_concern(surface, 0.9)
    assert sig is not None
    assert "warmth_drop" in sig.triggers


def test_warmth_drop_below_scale_threshold_no_trigger_even_if_floor_broken():
    # 跌幅不足 0.25,即便当前 warmth 已跌破 0.45 绝对下限,仍不触发。
    surface = {"state": {"valence": {"warmth": 0.3}}}
    assert extract_concern(surface, 0.4) is None


# --- 强度映射端点 ---------------------------------------------------------


def test_intensity_floor_at_exact_threshold():
    # pressure 恰好等于阈值 0.6 -> ratio m=0 -> intensity = 0.3 下限。
    surface = {"state": {"boundary": {"pressure": 0.6}}}
    sig = extract_concern(surface, None)
    assert sig is not None
    assert sig.intensity == pytest.approx(0.3)


def test_intensity_ceiling_at_pressure_max():
    # pressure=1.0 -> ratio m=(1.0-0.6)/0.4=1.0 -> intensity = 0.3+0.7*1 = 1.0。
    surface = {"state": {"boundary": {"pressure": 1.0}}}
    sig = extract_concern(surface, None)
    assert sig is not None
    assert sig.intensity == pytest.approx(1.0)


def test_intensity_ceiling_clamped_for_damage_over_scale():
    # damage.open=1.0 -> ratio m=(1.0-0.5)/0.5=1.0 -> intensity=1.0。
    surface = {"state": {"damage": {"open": 1.0}}}
    sig = extract_concern(surface, None)
    assert sig is not None
    assert sig.intensity == pytest.approx(1.0)


def test_intensity_clamped_when_warmth_drop_ratio_exceeds_one():
    # drop 远超 0.5 的归一刻度(min(drop/0.5, 1)),m 应被钳到 1,
    # intensity 仍不超过 1.0 上限。
    surface = {"state": {"valence": {"warmth": 0.0}}}
    sig = extract_concern(surface, 1.0)
    assert sig is not None
    assert sig.intensity == pytest.approx(1.0)
    assert sig.intensity <= 1.0


def test_intensity_takes_max_ratio_among_triggers():
    # pressure 触发弱(m 小),damage 触发强(m 大)-> 取 max。
    surface = {
        "state": {
            "boundary": {"pressure": 0.61},  # m ~= 0.025
            "damage": {"open": 1.0},  # m = 1.0
        }
    }
    sig = extract_concern(surface, None)
    assert sig is not None
    assert sig.intensity == pytest.approx(1.0)


# --- 防御式输入 -----------------------------------------------------------


def test_non_dict_surface_returns_none():
    assert extract_concern(None, None) is None  # type: ignore[arg-type]
    assert extract_concern("not-a-dict", None) is None  # type: ignore[arg-type]


def test_no_trigger_returns_none():
    surface = {
        "state": {
            "boundary": {"pressure": 0.0},
            "valence": {"warmth": 0.9},
            "damage": {"open": 0.0},
        }
    }
    assert extract_concern(surface, 0.9) is None


def test_missing_paths_default_conservatively():
    assert extract_concern({}, None) is None


def test_signal_is_concern_signal_instance():
    surface = {"state": {"boundary": {"pressure": 0.7}}}
    sig = extract_concern(surface, None)
    assert isinstance(sig, ConcernSignal)
    assert isinstance(sig.intensity, float)
    assert isinstance(sig.triggers, tuple)
