"""test_theory_trace.py —— theory-trace CI(律四,finitude_BLUEPRINT §1.3)。

扫描 `theory/finitude/impl_anchors.md` 的 yaml front-matter,双向核对:①锚点
文件存在且能 grep 到 `[FIN-A*]` 标记;②锚点声明的测试 ID 能在 `tests/finitude/`
下某处找到(字符串出现即可,轻量级核对,不做语义执行)。与
`tests/intrinsic/test_theory_trace.py` 同款纪律。
"""

from __future__ import annotations

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ANCHORS_PATH = _REPO_ROOT / "theory" / "finitude" / "impl_anchors.md"
_TESTS_DIR = Path(__file__).parent


def _load_anchors() -> list[dict]:
    text = _ANCHORS_PATH.read_text(encoding="utf-8")
    parts = text.split("---")
    assert len(parts) >= 3, "impl_anchors.md 缺 yaml front-matter"
    front_matter = parts[1]
    data = yaml.safe_load(front_matter)
    return data["anchors"]


def _all_test_source() -> str:
    chunks = []
    for path in _TESTS_DIR.glob("test_*.py"):
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def test_impl_anchors_file_exists_and_parseable():
    assert _ANCHORS_PATH.exists()
    anchors = _load_anchors()
    assert len(anchors) >= 7  # FIN-A1..FIN-A7 至少


def test_every_anchor_source_file_exists_and_tagged():
    anchors = _load_anchors()
    for anchor in anchors:
        anchor_id = anchor["id"]
        file_path = _REPO_ROOT / anchor["file"]
        assert file_path.exists(), f"{anchor_id}: 锚点文件不存在 {file_path}"
        content = file_path.read_text(encoding="utf-8")
        tag = f"[{anchor_id}]"
        assert tag in content, f"{anchor_id}: 锚点文件 {file_path} 内找不到标记 {tag}"


def test_every_anchor_test_id_appears_somewhere_in_tests_dir():
    anchors = _load_anchors()
    test_source = _all_test_source()
    for anchor in anchors:
        for test_id in anchor.get("tests", ()):
            haystack = test_source.lower().replace("-", "").replace("_", "")
            needle = test_id.lower().replace("-", "").replace("_", "")
            assert needle in haystack, (
                f"{anchor['id']}: 测试 ID {test_id} 在 tests/finitude/ 下找不到引用"
            )
