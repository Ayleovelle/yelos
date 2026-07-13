"""theory-trace CI(律四):扫描 `impl_anchors.md` front-matter 与代码/测试的双向引用。

对每条锚点:①引用的源文件必须存在;②该文件内必须能找到对应的
`[AX-n]`/`[TH-n]` 标记(docstring 或注释均可,只要求可 grep 到,不强制
逐字节 `# [AX-n]` 单一格式);③引用的每个测试 ID 必须能在
`tests/intrinsic/` 下某处找到(字符串出现即可,轻量级双向核对,不做
语义执行)。无锚公理 = 挂起本测试(律四)。
"""

from __future__ import annotations

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ANCHORS_PATH = _REPO_ROOT / "theory" / "intrinsic_field" / "impl_anchors.md"
_TESTS_DIR = Path(__file__).parent


def _load_anchors() -> list[dict]:
    text = _ANCHORS_PATH.read_text(encoding="utf-8")
    # front-matter 在两个 '---' 之间。
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


def test_impl_anchors_file_exists_and_parseable() -> None:
    assert _ANCHORS_PATH.exists()
    anchors = _load_anchors()
    assert len(anchors) >= 8  # AX-1..AX-8 至少


def test_every_anchor_source_file_exists_and_tagged() -> None:
    anchors = _load_anchors()
    for anchor in anchors:
        anchor_id = anchor["id"]
        file_path = _REPO_ROOT / anchor["file"]
        assert file_path.exists(), f"{anchor_id}: 锚点文件不存在 {file_path}"
        content = file_path.read_text(encoding="utf-8")
        tag = f"[{anchor_id}]"
        assert tag in content, f"{anchor_id}: 锚点文件 {file_path} 内找不到标记 {tag}"


def test_every_anchor_test_id_appears_somewhere_in_tests_dir() -> None:
    anchors = _load_anchors()
    test_source = _all_test_source()
    for anchor in anchors:
        for test_id in anchor.get("tests", ()):
            haystack = test_source.lower().replace("-", "").replace("_", "")
            needle = test_id.lower().replace("-", "").replace("_", "")
            assert needle in haystack, (
                f"{anchor['id']}: 测试 ID {test_id} 在 tests/intrinsic/ 下找不到引用"
            )
