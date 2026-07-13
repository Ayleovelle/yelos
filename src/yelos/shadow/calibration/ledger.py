"""ledger.py 在整个架构中的位置:[SHTOM-A3] 预测-结果账本(蓝图 §7.1/§2.3
第 3 行"shadow 校准账本 jsonl")。落盘路径由组合根传入(默认约定
`<data_dir>/shadow/calibration/{sid_hash}.jsonl`,§2.3);脱敏纪律:只存数值
特征(`features`/`proxy`),不存原文。

三件事收在一处:① 落一条预测(`record_prediction`,fire 时调用,若已有未结
账的旧预测先计入 `unresolved` 不计 Brier);② 结账并回写滚动统计
(`resolve_prediction`,`on_user_turn` 或静默超时路径调用);③ 静默超时批量
检查(`check_and_resolve_silence`,每拍调用)。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..contracts import OutcomeRecord, PredictionRecord
from . import brier as brier_mod
from . import gate_policy


def sid_ledger_hash(sid: str) -> str:
    """文件名脱敏(与 memory/primal 同精神:不把原始会话标识落进文件名)。"""
    return hashlib.sha256(sid.encode("utf-8")).hexdigest()[:16]


def default_ledger_path(data_dir: Path, sid: str) -> Path:
    return Path(data_dir) / "shadow" / "calibration" / f"{sid_ledger_hash(sid)}.jsonl"


def resolved_row(pred: dict[str, Any], outcome: OutcomeRecord) -> dict[str, Any]:
    return {
        "ts": outcome.ts,
        "pred_ts": outcome.pred_ts,
        "day": pred.get("day", ""),
        "ctype": outcome.ctype,
        "q": pred.get("q", 0.5),
        "y": outcome.y,
        "features": pred.get("features", {}),
        "proxy": outcome.proxy,
    }


class CalibrationLedger:
    """append-only jsonl 账本。单文件按 sid 拆分(与 primal pool_snapshots
    同惯例),每行一条已结账的 `(q,y)` 记录。
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, row: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def tail(self, ctype: str, limit: int) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("ctype") == ctype:
                    rows.append(row)
        return rows[-limit:] if limit > 0 else rows


def record_prediction(shadow_block: dict[str, Any], pred: PredictionRecord) -> None:
    """[SHTOM-A3] fire 时落一条预测。旧未结预测先按"无结果"关账(不计入
    Brier,只计 `unresolved`),不硬造 y(§7.1 诚实记账)。
    """
    pending = shadow_block.setdefault("pending_prediction", {})
    old = pending.get(pred.ctype)
    if old is not None:
        calib = shadow_block["calibration"].setdefault(pred.ctype, {})
        calib["unresolved"] = int(calib.get("unresolved", 0)) + 1
    pending[pred.ctype] = {
        "ts": pred.ts,
        "day": pred.day,
        "ctype": pred.ctype,
        "q": pred.q,
        "features": dict(pred.features),
    }


def resolve_prediction(
    shadow_block: dict[str, Any],
    ledger: CalibrationLedger,
    ctype: str,
    outcome: OutcomeRecord,
    *,
    window: int = 60,
) -> None:
    """结账:落 `(q,y)` 行 → 重算滚动 Brier/分箱 → 迟滞过的 tier。"""
    pending = shadow_block.setdefault("pending_prediction", {})
    pred = pending.get(ctype)
    if pred is None:
        return
    row = resolved_row(pred, outcome)
    ledger.append(row)
    pending[ctype] = None

    rows = ledger.tail(ctype, window)
    brier, n, bins = brier_mod.compute_brier(rows)
    calib = shadow_block["calibration"].setdefault(ctype, {})
    calib["brier"] = brier
    calib["n"] = n
    calib["bins"] = [list(b) for b in bins]
    candidate = gate_policy.tier_for_brier(brier, n)
    calib["tier"] = gate_policy.tier_with_hysteresis(calib, candidate)


def check_and_resolve_silence(
    shadow_block: dict[str, Any],
    ledger: CalibrationLedger,
    now_ts: float,
    *,
    window: int = 60,
) -> list[str]:
    """每拍调用:36h 静默超时的在途预测强制结账 y=1(§7.2)。返回本次结账的
    ctype 列表(空表示无超时)。
    """
    from . import outcome as outcome_mod

    resolved: list[str] = []
    pending = shadow_block.get("pending_prediction", {})
    for ctype, pred in list(pending.items()):
        if pred is None:
            continue
        if outcome_mod.is_silence_timeout(pred, now_ts):
            out = outcome_mod.silence_outcome(pred, now_ts)
            resolve_prediction(shadow_block, ledger, ctype, out, window=window)
            resolved.append(ctype)
    return resolved


__all__ = [
    "sid_ledger_hash",
    "default_ledger_path",
    "resolved_row",
    "CalibrationLedger",
    "record_prediction",
    "resolve_prediction",
    "check_and_resolve_silence",
]
