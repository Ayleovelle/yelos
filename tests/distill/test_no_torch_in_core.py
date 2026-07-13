"""AST 扫 src/yelos:torch 引用仅存在于

``distill/trainer/{rnn_tiny,transformer_tiny}.py``(依赖公理②)。
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "yelos"
_ALLOWED_TORCH_FILES = {
    SRC_DIR / "distill" / "trainer" / "rnn_tiny.py",
    SRC_DIR / "distill" / "trainer" / "transformer_tiny.py",
}


def _top_level(dotted: str) -> str:
    return dotted.split(".")[0]


def _imports_torch(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_top_level(a.name) == "torch" for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module:
            if _top_level(node.module) == "torch":
                return True
    return False


def test_torch_only_imported_in_two_allowed_files():
    offenders = []
    for path in sorted(SRC_DIR.rglob("*.py")):
        if path in _ALLOWED_TORCH_FILES:
            continue
        if _imports_torch(path):
            offenders.append(str(path.relative_to(SRC_DIR)))
    assert not offenders, f"以下文件违规 import torch:{offenders}"


def test_allowed_torch_files_actually_import_torch():
    for path in _ALLOWED_TORCH_FILES:
        assert path.is_file(), f"{path} 应存在"
        assert _imports_torch(path), f"{path} 应 import torch(否则守卫无意义)"
