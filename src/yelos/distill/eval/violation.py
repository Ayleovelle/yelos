"""在整个架构中的位置:越界率(闸前测:白名单外输出占比,蓝图 §1)。

衡量模型**原始**候选(闸介入前)有多少会被 whitelist_gate 拦下——不是
安全指标(DA1 已保证安全,拦截率恒 100%),而是模型质量指标:越界率越
高,说明模型离"她会说的话"越远,即便闸兜底也意味着更频繁的回退/换档。
"""

from __future__ import annotations

from dataclasses import dataclass

from yelos.primal.whitelist_gate import WhitelistGate


@dataclass(frozen=True)
class ViolationResult:
    total: int
    violations: int

    @property
    def rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.violations / self.total


def violation_rate(
    candidates: list[tuple[str, str, str, str, int, tuple[str, ...]]],
    gate: WhitelistGate,
) -> ViolationResult:
    """``candidates``:每项 (canonical, occasion, lang, band, epoch, corpus)。

    与 ``WhitelistGate.check`` 签名一一对应,调用方(通常是 eval 报告
    生成流程)负责喂入模型对一批 occasion/band/epoch 组合的原始候选。
    """
    total = len(candidates)
    violations = 0
    for canonical, occasion, lang, band, epoch, corpus in candidates:
        result = gate.check(canonical, occasion, lang, band, epoch, corpus)
        if not result.ok:
            violations += 1
    return ViolationResult(total=total, violations=violations)


__all__ = ["ViolationResult", "violation_rate"]
