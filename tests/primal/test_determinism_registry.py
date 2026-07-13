"""AST:primal 包内 hashlib 仅 determinism.py;无 random/墙钟/astrbot/

sylanne_core import(core 纪律扩展);键格式 golden;pick 键与 v0.1
字面一致。锁 A3/律一。
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

PRIMAL_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "yelos" / "primal"
FORBIDDEN_MODULES = {"astrbot", "sylanne_core", "random", "time", "datetime"}
# time/datetime 允许在类型注解/文档字符串中提及,但不允许被 import——primal
# 全部时间输入走 now_ts 参数,不许自己摸墙钟。


def _top_level(dotted: str) -> str:
    return dotted.split(".")[0]


def _all_py_files() -> list[Path]:
    return sorted(PRIMAL_DIR.rglob("*.py"))


@pytest.mark.parametrize(
    "path", _all_py_files(), ids=lambda p: str(p.relative_to(PRIMAL_DIR))
)
def test_no_forbidden_imports_anywhere(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert _top_level(alias.name) not in FORBIDDEN_MODULES, (
                    f"{path}: 禁止 import {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert _top_level(node.module) not in FORBIDDEN_MODULES, (
                f"{path}: 禁止 from {node.module} import ..."
            )


@pytest.mark.parametrize(
    "path", _all_py_files(), ids=lambda p: str(p.relative_to(PRIMAL_DIR))
)
def test_hashlib_only_in_determinism_py(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits.extend(a.name for a in node.names if _top_level(a.name) == "hashlib")
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and _top_level(node.module) == "hashlib"
        ):
            hits.append(node.module)
    if path.name == "determinism.py":
        assert hits, "determinism.py 应该是唯一的 hashlib 落点,但没找到 import"
    else:
        assert not hits, f"{path} 违规 import hashlib(唯一落点应是 determinism.py)"


# --- 键格式 golden ----------------------------------------------------------


def test_pick_key_format_matches_v01_literal():
    from yelos.primal import determinism

    sid, day_key, occasion = "sid1", "2026-07-11", "concern"
    key = f"{sid}|{day_key}|{occasion}"
    expected = hashlib.sha256(key.encode()).digest()[0]
    assert determinism.h_byte(key) == expected


def test_key_registry_documents_all_key_ids():
    from yelos.primal import determinism

    expected_ids = {
        "pick",
        "tpl_pat",
        "tpl_slot",
        "mkv_step",
        "prosody",
        "morph_seed",
        "rerank",
        # W2 intrinsic 新键型(只增不删,INTEGRATION_SPEC §2.4/§3.9;
        # intrinsic_BLUEPRINT §6.4 登记点)。
        "poisson",
        "dream",
        "batch",
        # W5 distill 新键型(只增不删,INTEGRATION_SPEC §3.8;
        # distill_BLUEPRINT §3.1 登记点)。
        "distill",
        # W5 evolution 新键型(只增不删,INTEGRATION_SPEC §3.9;
        # evolution_BLUEPRINT §2.2 登记点)。
        "evo",
    }
    assert set(determinism.KEY_REGISTRY.keys()) == expected_ids
    for key_id, meta in determinism.KEY_REGISTRY.items():
        assert "format" in meta and "granularity" in meta and "consumer" in meta


def test_h_byte_deterministic():
    from yelos.primal import determinism

    assert determinism.h_byte("k") == determinism.h_byte("k")


def test_h_bytes_length_and_determinism():
    from yelos.primal import determinism

    a = determinism.h_bytes("k|0", 40)
    b = determinism.h_bytes("k|0", 40)
    assert len(a) == 40
    assert a == b


def test_text_digest_deterministic_and_short():
    from yelos.primal import determinism

    d1 = determinism.text_digest("你好。")
    d2 = determinism.text_digest("你好。")
    assert d1 == d2
    assert len(d1) == 8  # blake2b digest_size=4 -> 8 hex chars
