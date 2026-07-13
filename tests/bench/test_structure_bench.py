"""结构锁(bench_BLUEPRINT §5.1"AST 锁,test_structure_bench")。

FakeBridge/scenarios/metrics 一律零真随机(``random``)、零 ``time.time()``
直接调用——一切时间输入经构造函数注入的 ``Clock`` 读取。哈希驱动的
``hashlib`` 用法不在禁列(synth.py 的确定性合成靠它,不是"随机")。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BENCH_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "yelos" / "bench"

FORBIDDEN_MODULES = {"random"}


def _top_level(dotted: str) -> str:
    return dotted.split(".")[0]


def _forbidden_imports(tree: ast.AST) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = _top_level(alias.name)
                if mod in FORBIDDEN_MODULES and mod not in hits:
                    hits.append(mod)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = _top_level(node.module)
            if mod in FORBIDDEN_MODULES and mod not in hits:
                hits.append(mod)
    return hits


def _calls_time_time(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "time" and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "time":
                    return True
    return False


def _bench_py_files() -> list[Path]:
    assert BENCH_DIR.is_dir(), f"bench/ 目录不存在:{BENCH_DIR}"
    # clock.py 是 RealClock 的合法落点,允许 time.time()(§3.1 逐字下沉)。
    return sorted(p for p in BENCH_DIR.rglob("*.py") if p.name != "clock.py")


@pytest.mark.parametrize(
    "path", _bench_py_files(), ids=lambda p: str(p.relative_to(BENCH_DIR))
)
def test_bench_module_has_no_random_import(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits = _forbidden_imports(tree)
    assert not hits, f"{path.relative_to(BENCH_DIR)} 违反零随机纪律,命中:{hits}"


@pytest.mark.parametrize(
    "path", _bench_py_files(), ids=lambda p: str(p.relative_to(BENCH_DIR))
)
def test_bench_module_does_not_call_time_time(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not _calls_time_time(tree), (
        f"{path.relative_to(BENCH_DIR)} 直接调用 time.time(),违反"
        "零真实时间读取纪律(一切时间须经注入的 Clock)"
    )
