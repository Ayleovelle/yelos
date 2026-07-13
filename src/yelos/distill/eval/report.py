"""在整个架构中的位置:eval 报告落盘(蓝图 §5 数据契约 eval_report.json)。

schema:``{tier, corpus_hash, model_hash, violation_rate_pregate,
fidelity_js: {occasion: float}, fallback_probe: {...}: pass/fail,
distinct_n}``。落 bench 目录(M10 报告契约,进 regression 视野)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


def distinct_n(texts: tuple[str, ...], n: int = 2) -> float:
    """distinct-n 多样性:唯一 n-gram 数 / 总 n-gram 数;空输入 ⇒ 0.0。"""
    total = 0
    grams: set[str] = set()
    for text in texts:
        for i in range(len(text) - n + 1):
            grams.add(text[i : i + n])
            total += 1
    if total == 0:
        return 0.0
    return len(grams) / total


@dataclass(frozen=True)
class EvalReport:
    tier: str
    corpus_hash: str
    model_hash: str
    violation_rate_pregate: float
    fidelity_js: dict = field(default_factory=dict)
    fallback_probe: dict = field(default_factory=dict)
    distinct_n: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "corpus_hash": self.corpus_hash,
            "model_hash": self.model_hash,
            "violation_rate_pregate": self.violation_rate_pregate,
            "fidelity_js": dict(self.fidelity_js),
            "fallback_probe": dict(self.fallback_probe),
            "distinct_n": self.distinct_n,
        }

    @staticmethod
    def from_dict(raw: dict) -> "EvalReport":
        return EvalReport(
            tier=str(raw.get("tier", "")),
            corpus_hash=str(raw.get("corpus_hash", "")),
            model_hash=str(raw.get("model_hash", "")),
            violation_rate_pregate=float(raw.get("violation_rate_pregate", 0.0)),
            fidelity_js=dict(raw.get("fidelity_js", {})),
            fallback_probe=dict(raw.get("fallback_probe", {})),
            distinct_n=float(raw.get("distinct_n", 0.0)),
        )

    def render_markdown(self) -> str:
        lines = [
            "# Yelos distill eval 报告",
            "",
            f"- tier: {self.tier}",
            f"- corpus_hash: {self.corpus_hash}",
            f"- model_hash: {self.model_hash}",
            f"- violation_rate_pregate: {self.violation_rate_pregate:.4f}",
            f"- distinct_n: {self.distinct_n:.4f}",
            "",
            "## fidelity_js(逐场合,越小越保真)",
            "",
        ]
        for occasion, score in sorted(self.fidelity_js.items()):
            lines.append(f"- {occasion}: {score:.4f}")
        lines += ["", "## fallback_probe(三情形回退健全性)", ""]
        for name, ok in sorted(self.fallback_probe.items()):
            lines.append(f"- {name}: {'pass' if ok else 'FAIL'}")
        lines.append("")
        return "\n".join(lines)


def write_report(report: EvalReport, out_dir: Path) -> tuple[Path, Path]:
    """写 ``eval_report.json`` + ``eval_report.md`` 到 ``out_dir``(bench 目录)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_report.json"
    md_path = out_dir / "eval_report.md"
    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    md_path.write_text(report.render_markdown(), encoding="utf-8")
    return json_path, md_path


__all__ = ["EvalReport", "distinct_n", "write_report"]
