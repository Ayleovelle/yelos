"""epochs/dualtrack.py 在整个架构中的位置:双轨并跑器 + 分歧记录器(finitude_BLUEPRINT §4.3/§4.4)。

每次 settle 后调用一次 `DualTrack.observe`:同时跑 A 轨(固定边界,读契约 P)与 B 轨
(序参量相变,读 P_expr),按 `finitude_epoch_track` 权威表(§4.4)决定当次是否要通告/
落 milestone,并把分歧行追加写 `epoch_divergence.jsonl`(损坏行安静跳过,与
`PlasticityLedger` 同款读纪律)。

**冷启动退化(§4.4 决策表脚注)**:权威轨为 order_parameter 且 B 轨检测器样本不足
(`len(state.deltas) < MIN_SAMPLES`)时,通告退化为 A 轨代驱——避免"新生命前五天纪元机
失灵"。此退化只影响"是否通告/落 milestone",不影响 divergence 行的 a_only/b_only/both
分类(分类恒基于两轨各自的真实触发情况)。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import fixed
from .order_parameter import MIN_SAMPLES, OpDetectorState, detect


@dataclass
class DualTrackOutcome:
    a_fired: str | None  # A 轨本次跃迁到的纪元名,未跃迁则 None
    b_fired: bool  # B 轨本次是否判定相变
    b_epoch_nominee: (
        str | None
    )  # B 轨提名的纪元名(经 clamp_forward 钳制的 b_index 对应名)
    notify_epoch: str | None  # 本次实际应通告的纪元名(按权威表决定),无则 None
    notify_track: str | None  # "A" | "B" | None,与 notify_epoch 成对
    divergence_rows: list[dict] = field(default_factory=list)


def _divergence_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / "epoch_divergence.jsonl"


def _append_divergence(data_dir: str | Path, row: dict) -> None:
    path = _divergence_path(data_dir)
    line = json.dumps(row, ensure_ascii=False) + "\n"
    try:
        fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass  # 尽力而为,分歧数据非权威记账面


def decide_notification(
    track_authority: str,
    cold_start: bool,
    a_fired: str | None,
    b_fired: bool,
    b_epoch_nominee: str | None,
) -> tuple[str | None, str | None]:
    """决策表(§4.4)的纯函数正身,独立可测(6 行逐格)。

    | 权威轨 | A | B | 动作 |
    |---|---|---|---|
    | fixed | 是 | 是/否 | 通告 A |
    | fixed | 否 | 是/否 | 无通告 |
    | order_parameter(热) | 否 | 是 | 通告 B(钳制后) |
    | order_parameter(热) | 是 | 否 | 无通告 |
    | order_parameter(冷启动) | 是 | * | 通告 A(退化代驱) |
    | order_parameter(冷启动) | 否 | * | 无通告 |
    """
    if track_authority == "fixed":
        return (a_fired, "A") if a_fired else (None, None)
    # order_parameter
    if cold_start:
        return (a_fired, "A") if a_fired else (None, None)
    if b_fired:
        return (b_epoch_nominee, "B")
    return (None, None)


def read_divergence(data_dir: str | Path) -> list[dict]:
    """读 `epoch_divergence.jsonl`;损坏行安静跳过(与 PlasticityLedger 同款读纪律)。"""
    path = _divergence_path(data_dir)
    if not path.exists():
        return []
    out: list[dict] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


class DualTrack:
    """并跑器:持有 sid/gen/权威轨配置 + B 轨检测器态,产出 `DualTrackOutcome`。"""

    def __init__(
        self,
        sid: str,
        gen: int,
        track_authority: str,
        state: OpDetectorState | None = None,
        cap: int = 3,
        data_dir: str | Path | None = None,
    ) -> None:
        self.sid = sid
        self.gen = gen
        self.track_authority = (
            track_authority
            if track_authority in ("fixed", "order_parameter")
            else "fixed"
        )
        self.state = state or OpDetectorState()
        self.cap = cap
        self.data_dir = data_dir

    def observe(
        self,
        day: str,
        p_old: float,
        p_new: float,
        p_expr_old: float,
        p_expr_new: float,
    ) -> DualTrackOutcome:
        a_fired = fixed.transition(p_old, p_new)

        cold_start = len(self.state.deltas) < MIN_SAMPLES
        new_state, b_fired = detect(self.state, day, p_expr_old, p_expr_new, self.cap)
        self.state = new_state

        b_epoch_nominee: str | None = None
        if b_fired:
            idx = min(new_state.b_index, len(fixed.EPOCH_NAMES) - 1)
            b_epoch_nominee = fixed.EPOCH_NAMES[idx]

        notify_epoch, notify_track = decide_notification(
            self.track_authority, cold_start, a_fired, b_fired, b_epoch_nominee
        )

        rows: list[dict] = []
        if a_fired and b_fired:
            event = "both"
        elif a_fired:
            event = "a_only"
        elif b_fired:
            event = "b_only"
        else:
            event = None

        if event is not None:
            row = {
                "sid": self.sid,
                "gen": self.gen,
                "day": day,
                "event": event,
                "a_epoch": a_fired if a_fired else fixed.epoch_of(p_new),
                "b_index": new_state.b_index,
                "p": p_new,
                "p_expr": p_expr_new,
                "psi": None,  # 见下方补算,避免重复算两次 psi 造成的浮点漂移风险
                "dpsi": None,
            }
            from .order_parameter import psi as _psi

            psi_new = _psi(p_expr_new, self.cap)
            psi_old = _psi(p_expr_old, self.cap)
            row["psi"] = psi_new
            row["dpsi"] = psi_old - psi_new
            rows.append(row)
            if self.data_dir is not None:
                _append_divergence(self.data_dir, row)

        return DualTrackOutcome(
            a_fired=a_fired,
            b_fired=b_fired,
            b_epoch_nominee=b_epoch_nominee,
            notify_epoch=notify_epoch,
            notify_track=notify_track,
            divergence_rows=rows,
        )


__all__ = ["DualTrack", "DualTrackOutcome", "read_divergence"]
