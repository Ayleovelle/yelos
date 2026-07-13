"""结构锁测试(BLUEPRINT.md §1 分层边界 / §13 test_structure.py)。

三条硬锁:
1. core/*.py 全模块 AST 遍历:禁止 import astrbot / sylanne_core / random
   (engine_bridge.py 是 sylanne_core 唯一落点,不在此锁范围内)。
2. main.py 不得定义 __del__(定义了就会屏蔽框架 terminate() 调用,见
   INDEX_constraints.md §A.4 / §F.3)。
3. terminate 必须定义在 main.py 的主 Star 子类上(唯一 Star 子类)。

main.py 属于 W2(尚未落地时可能不存在):若不存在,第 2/3 条锁 skip 并给出
提示,不误报为失败;core/*.py 与 engine_bridge.py 已在 W1 落地,第 1 条锁
始终真实运行。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "src" / "yelos"
CORE_DIR = PLUGIN_ROOT / "core"
MAIN_PY = PLUGIN_ROOT / "main.py"

FORBIDDEN_MODULES = {"astrbot", "sylanne_core", "random"}


def _top_level_module(dotted: str) -> str:
    return dotted.split(".")[0]


def _forbidden_imports(tree: ast.AST) -> list[str]:
    """返回模块内命中禁止清单的顶层模块名(去重,保留发现顺序)。"""
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = _top_level_module(alias.name)
                if mod in FORBIDDEN_MODULES and mod not in hits:
                    hits.append(mod)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue  # 相对导入 `from . import x` 之类,module 为 None
            mod = _top_level_module(node.module)
            if mod in FORBIDDEN_MODULES and mod not in hits:
                hits.append(mod)
    return hits


def _core_py_files() -> list[Path]:
    assert CORE_DIR.is_dir(), f"core/ 目录不存在:{CORE_DIR}"
    files = sorted(CORE_DIR.glob("*.py"))
    assert files, "core/*.py 一个文件都没找到,检查路径是否正确"
    return files


@pytest.mark.parametrize(
    "path",
    _core_py_files() if CORE_DIR.is_dir() else [],
    ids=lambda p: p.name,
)
def test_core_module_has_no_forbidden_imports(path: Path) -> None:
    """core/*.py 每个文件都不得 import astrbot / sylanne_core / random。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits = _forbidden_imports(tree)
    assert not hits, (
        f"{path.relative_to(PLUGIN_ROOT)} 违反 core 边界,命中禁止导入:{hits}"
        "(蓝图 §1:core 内零 astrbot import、零 sylanne_core import、零 random"
        " import,时间/状态/配置一律入参传入)"
    )


def test_engine_bridge_is_the_only_sylanne_core_entry_point() -> None:
    """sylanne_core 只准在 engine_bridge.py 落地;core/*.py 里一个都不许有。

    (与上面参数化测试同一断言,这里额外做一次全量交叉检查,防止将来
    在 core/ 之外、engine_bridge.py 之外的某个文件里悄悄引入 sylanne_core
    却没有测试覆盖到。)
    """
    engine_bridge = PLUGIN_ROOT / "engine_bridge.py"
    if not engine_bridge.is_file():
        pytest.skip("engine_bridge.py 尚未落地(W1 未完成),跳过交叉检查")

    other_py_files = [
        p for p in PLUGIN_ROOT.glob("*.py") if p.name != "engine_bridge.py"
    ]
    for path in other_py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert _top_level_module(alias.name) != "sylanne_core", (
                        f"{path.name} 导入了 sylanne_core,"
                        "唯一落点必须是 engine_bridge.py(蓝图 §9)"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert _top_level_module(node.module) != "sylanne_core", (
                    f"{path.name} 导入了 sylanne_core,"
                    "唯一落点必须是 engine_bridge.py(蓝图 §9)"
                )


def _find_star_subclasses(tree: ast.Module) -> list[ast.ClassDef]:
    """main.py 里所有基类名含 'Star' 的类定义(不解析继承链,只按名字匹配,
    与 validate_plugin.py 的检测口径一致)。
    """
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = (
                    base.id
                    if isinstance(base, ast.Name)
                    else (base.attr if isinstance(base, ast.Attribute) else None)
                )
                if base_name == "Star":
                    classes.append(node)
                    break
    return classes


def test_main_py_has_no_dunder_del() -> None:
    """main.py 的插件类不得定义 __del__(会屏蔽框架 terminate() 调用)。"""
    if not MAIN_PY.is_file():
        pytest.skip("main.py 尚未落地(W2 未完成),跳过")

    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))
    del_defs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "__del__"
    ]
    assert not del_defs, (
        "main.py 中不得定义 __del__:框架 _terminate_plugin() 逻辑是"
        "`if __del__ ... elif terminate ...`,一旦有 __del__ 就永远不会"
        "调用 terminate(),资源泄露(INDEX_constraints.md §A.4 / §F.3)"
    )


def test_main_py_has_exactly_one_star_subclass() -> None:
    """main.py 必须恰好定义一个 Star 子类(唯一 Star 子类,蓝图 §10)。"""
    if not MAIN_PY.is_file():
        pytest.skip("main.py 尚未落地(W2 未完成),跳过")

    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))
    star_classes = _find_star_subclasses(tree)
    assert len(star_classes) == 1, (
        f"main.py 应恰好有 1 个 Star 子类,实际找到 {len(star_classes)} 个:"
        f"{[c.name for c in star_classes]}"
        "(0 个 → 插件加载失败;>1 个 → 后续子类覆盖前序,功能丢失)"
    )


def test_terminate_defined_on_main_star_subclass() -> None:
    """terminate 必须定义在 main.py 的主 Star 子类上,而不是子模块里。"""
    if not MAIN_PY.is_file():
        pytest.skip("main.py 尚未落地(W2 未完成),跳过")

    tree = ast.parse(MAIN_PY.read_text(encoding="utf-8"), filename=str(MAIN_PY))
    star_classes = _find_star_subclasses(tree)
    assert star_classes, "main.py 中没有找到 Star 子类,无法校验 terminate 位置"

    for cls in star_classes:
        method_names = {
            node.name
            for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert "terminate" in method_names, (
            f"main.py 中的 Star 子类 {cls.name} 未定义 terminate;"
            "框架按 `data.plugins.<目录名>.main` 完整模块路径查注册表,"
            "terminate 必须在 main.py 的主类上(INDEX_constraints.md §A.3)"
        )


def test_core_package_has_no_forbidden_imports_recursively() -> None:
    """兜底:core/ 目录下(含未来子目录)任何 .py 文件都不许有禁止导入。"""
    if not CORE_DIR.is_dir():
        pytest.skip("core/ 目录尚未落地")

    offenders: dict[str, list[str]] = {}
    for path in CORE_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        hits = _forbidden_imports(tree)
        if hits:
            offenders[str(path.relative_to(PLUGIN_ROOT))] = hits

    assert not offenders, f"core/ 下发现违规导入:{offenders}"
