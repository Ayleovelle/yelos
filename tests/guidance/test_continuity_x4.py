"""X4(INTEGRATION_SPEC §3.4 路线 A):``continuity`` keyword-only 入参承接
memory 的 reunion 事实;guidance 本身不 import memory(鸭子类型消费)。"""

from __future__ import annotations

from dataclasses import dataclass

from yelos.guidance import build_guidance


@dataclass(frozen=True)
class _FakeContinuity:
    """结构上等价于 ``yelos.memory.contracts.ContinuityFlags``,但本测试
    刻意不 import memory——验证 guidance 只按鸭子类型读 ``.reunion``。"""

    reunion: bool
    long_bond: bool = False
    active_themes: int = 0


def _surface(**overrides) -> dict:
    base = {
        "decision": {"action": "hold"},
        "state": {
            "rhythm": {"strain": 0.0},
            "responsiveness": {"fatigue": 0.0},
            "valence": {"warmth": 0.5},
            "damage": {"accumulated": 0.0},
            "boundary": {"autonomy": 1.0, "paused": False},
            "needs": {"quiet": 0.0, "expression": 0.0},
        },
        "dynamics": {
            "relational_time": {"phase": "active"},  # 非 dormant
            "uncertainty": {"claim_caution": 0.0},
        },
        "guard": {"allowed": True},
    }
    for path, value in overrides.items():
        node = base
        keys = path.split(".")
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
    return base


def test_reunion_true_upgrades_dormant_hint_even_if_phase_active() -> None:
    out = build_guidance(
        _surface(), mode="companion", continuity=_FakeContinuity(reunion=True)
    )
    assert out["tone"] == "gentle"
    assert "很久没联系了，重新开口温和些。" in out["hints"]


def test_reunion_false_does_not_trigger_dormant() -> None:
    out = build_guidance(
        _surface(), mode="companion", continuity=_FakeContinuity(reunion=False)
    )
    assert "很久没联系了，重新开口温和些。" not in out["hints"]


def test_continuity_none_is_byte_identical_to_v01_default() -> None:
    surface = _surface(**{"dynamics.relational_time.phase": "dormant"})
    with_none = build_guidance(surface, mode="companion", continuity=None)
    without_kw = build_guidance(surface, mode="companion")
    assert with_none == without_kw


def test_phase_dormant_still_fires_without_continuity() -> None:
    surface = _surface(**{"dynamics.relational_time.phase": "dormant"})
    out = build_guidance(surface, mode="companion")
    assert "很久没联系了，重新开口温和些。" in out["hints"]


def test_no_hard_dependency_on_memory_module() -> None:
    """静态锁(AST,非子串匹配——避免误伤文档字符串里"不 import memory"这类
    自然语言说明):包内所有 ``.py`` 文件都不含任何以 "memory" 结尾/含
    "memory" 的真实 import 语句。"""
    import ast
    import inspect
    from pathlib import Path

    import yelos.guidance as guidance_module

    pkg_dir = Path(inspect.getfile(guidance_module)).parent
    for py_file in pkg_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "memory" not in alias.name, f"{py_file}: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "memory" not in mod, f"{py_file}: from {mod} import ..."
