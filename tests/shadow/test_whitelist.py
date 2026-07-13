"""test_whitelist.py:[SHTOM-A2] 输出面白名单对抗测试(蓝图 §11 红队样本
固化)。AST 扫描全包字符串常量,断言无中文陈述句;并锁死 `gates/exit.py`
出口枚举的越界断言。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from yelos.shadow.binding_v2 import CTYPES
from yelos.shadow.gates.exit import apply_exit

SHADOW_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "yelos" / "shadow"

_HAN_RE = re.compile(r"[一-鿿]")


def _string_constants(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    return out


def _all_py_files() -> list[Path]:
    assert SHADOW_ROOT.is_dir(), f"shadow 包目录不存在:{SHADOW_ROOT}"
    files = sorted(SHADOW_ROOT.rglob("*.py"))
    assert files, "shadow/*.py 一个文件都没找到"
    return files


@pytest.mark.parametrize(
    "path", _all_py_files(), ids=lambda p: str(p.relative_to(SHADOW_ROOT))
)
def test_ast_no_chinese_string_constants(path: Path) -> None:
    """[SHTOM-A2] 全包字符串字面量零中文——中文说明一律 `#`/docstring 注释,
    不得以可执行字符串常量形式出现(docstring 本身是 Expr 语句的字符串常量,
    会被 `ast.Constant` 捕获,但那是文档不是运行时可达的用户可见输出——本
    测试的实际关注点是"运行时会被使用的字符串值",docstring 常量与真实模块
    docstring 无法用纯 AST 静态区分是否"被使用";因此本测试的真正契约是:
    模块级/类级/函数级 docstring(第一个语句是纯字符串表达式)豁免,其余一切
    字符串常量必须零中文。
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    docstring_nodes = _docstring_nodes(tree)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_nodes:
                continue
            if _HAN_RE.search(node.value):
                offenders.append(node.value)
    assert offenders == [], f"{path.name} 含面向用户的中文字符串常量: {offenders!r}"


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """收集"模块/类/函数体首语句是字符串表达式"的那些 Constant 节点 id(即
    docstring),供上面的测试豁免。
    """
    ids: set[int] = set()
    candidates: list[ast.AST] = [tree]
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            candidates.append(node)
    for node in candidates:
        body = getattr(node, "body", None)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
        ):
            if isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


# --- 出口枚举断言(SHTOM-T1)------------------------------------------------


def test_exit_ctype_enum_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        apply_exit(
            "not_a_real_ctype", 0.5, 0.5, do_inject=True, do_enqueue=True, gate_trace=()
        )


@pytest.mark.parametrize("ctype", CTYPES)
def test_exit_accepts_all_enumerated_ctypes(ctype: str) -> None:
    verdict = apply_exit(
        ctype, 1.5, 1.5, do_inject=True, do_enqueue=True, gate_trace=("t",)
    )
    assert verdict.ctype == ctype
    assert 0.0 <= verdict.intensity <= 1.0
    assert 0.0 <= verdict.q <= 1.0
    assert isinstance(verdict.do_inject, bool)
    assert isinstance(verdict.do_enqueue, bool)


def test_exit_quantizes_and_clamps() -> None:
    verdict = apply_exit(
        CTYPES[0],
        1.23456,
        -0.5,
        do_inject=True,
        do_enqueue=False,
        gate_trace=("a", "b"),
    )
    assert verdict.intensity == 1.0
    assert verdict.q == 0.0
    assert verdict.gate_trace == ("a", "b")
