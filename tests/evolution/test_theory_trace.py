"""test_theory_trace.py:EVO-A1..A4 锚点注释存在且双向(公理 -> 锚点 -> 测试,律四)。"""

from __future__ import annotations

import re
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parents[2] / "src" / "yelos" / "evolution"
_AXIOMS_MD = Path(__file__).resolve().parents[2] / "theory" / "evolution" / "axioms.md"


def _grep(anchor: str) -> list[Path]:
    hits = []
    for path in _PKG_ROOT.rglob("*.py"):
        if anchor in path.read_text(encoding="utf-8"):
            hits.append(path)
    return hits


def test_all_four_axiom_anchors_present_in_code():
    for anchor in ("EVO-A1", "EVO-A2", "EVO-A3", "EVO-A4"):
        assert _grep(anchor), f"missing code anchor for {anchor}"


def test_axioms_md_references_all_anchors():
    text = _AXIOMS_MD.read_text(encoding="utf-8")
    for anchor in ("EVO-A1", "EVO-A2", "EVO-A3", "EVO-A4"):
        assert anchor in text


def test_axioms_md_has_negative_list_no_convergence_or_monotone_theorem():
    text = _AXIOMS_MD.read_text(encoding="utf-8")
    assert "不立" in text
    assert re.search(r"收敛定理", text)
    assert re.search(r"单调改进定理", text)
