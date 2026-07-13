"""accounting/duel_corpus.py 在整个架构中的位置。

DuelPolicy 分歧样本的 jsonl 写入器。**唯一权威路径**
(INTEGRATION_SPEC X1/§3.1 裁定,arbiter_BLUEPRINT §6.2 已按裁定对齐,
不再用蓝图初稿里的 ``bench/corpus/`` 措辞):

    <data_dir>/bench_corpus/arbiter_duel/YYYY-MM.jsonl

字段白名单(N9:只记特征,无原文)——运行时断言 + 本文件顶部 AST 扫描
测试(tests/arbiter/test_duel.py)双锁,禁止出现 ``draft``/``text`` 字段名。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..inputs import PolicyInput
from ..policies.duel import DuelResult

# 字段白名单(唯一权威定义;运行时断言与 AST 测试均以此表为准)
FIELD_WHITELIST = frozenset(
    {"ts", "sid_digest", "features", "verdict_a", "verdict_b", "chosen", "theta_digest"}
)
_FORBIDDEN_SUBSTRINGS = ("draft", "text")


def _sid_digest(sid: str) -> str:
    return hashlib.blake2b(sid.encode()).hexdigest()[:8]


def _extract_features(pin: PolicyInput) -> dict:
    """8 维特征快照(与 SmoothPolicy 消费的维度对齐,但独立计算——不依赖
    smooth.py 内部实现,只读 PolicyInput 公开字段,避免耦合内部权重表)。
    """
    from ...core import sget

    b = pin.base
    surface = b.surface
    return {
        "pressure": float(sget(surface, "state.boundary.pressure", 0.0)),
        "expression": float(sget(surface, "state.needs.expression", 0.0)),
        "fatigue": float(sget(surface, "state.needs.fatigue", 0.0)),
        "action": str(sget(surface, "decision.action", "hold")),
        "p": float(b.p),
        "n_sentences": _n_sentences(b.draft),
        "surface_age_s": float(pin.surface_age_s),
        "daily_interventions": int(pin.daily_interventions),
    }


def _n_sentences(draft: str) -> int:
    from ...core import split_sentences

    return len(split_sentences(draft))


def _assert_whitelisted(row: dict) -> None:
    bad = set(row.keys()) - FIELD_WHITELIST
    if bad:
        raise AssertionError(f"duel_corpus 行含未登记字段:{bad}")
    for name in row:
        low = name.lower()
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            if forbidden in low:
                raise AssertionError(f"duel_corpus 字段名疑似泄漏原文:{name}")


def build_row(
    pin: PolicyInput, result: DuelResult, *, ts: float, theta_digest: str
) -> dict:
    row = {
        "ts": ts,
        "sid_digest": _sid_digest(pin.base.session_id),
        "features": _extract_features(pin),
        "verdict_a": result.verdict_a.kind,
        "verdict_b": result.verdict_b.kind,
        "chosen": result.chosen.kind,
        "theta_digest": theta_digest,
    }
    _assert_whitelisted(row)
    return row


class DuelCorpusWriter:
    """DuelPolicy 分歧样本落盘;懒创建目录,追加写(不覆盖历史月份)。"""

    def __init__(self, data_dir: Path) -> None:
        self._dir = Path(data_dir) / "bench_corpus" / "arbiter_duel"

    def path_for(self, day_key: str) -> Path:
        month = day_key[:7]  # "YYYY-MM"
        return self._dir / f"{month}.jsonl"

    def write(
        self,
        pin: PolicyInput,
        result: DuelResult,
        *,
        ts: float,
        day_key: str,
        theta_digest: str,
    ) -> None:
        if not result.diverged:
            return
        row = build_row(pin, result, ts=ts, theta_digest=theta_digest)
        path = self.path_for(day_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_corpus(data_dir: Path, day_key_prefix: str) -> list[dict]:
    """bench 校验读取器的最小实现(W2 同波交付,W1 已有 harness 骨架消费)。

    ``day_key_prefix`` 形如 ``"YYYY-MM"``;返回该月全部行,逐条做字段
    白名单 schema 校验(读侧防御,写坏的历史文件不应静默通过)。
    """
    path = Path(data_dir) / "bench_corpus" / "arbiter_duel" / f"{day_key_prefix}.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        _assert_whitelisted(row)
        rows.append(row)
    return rows
