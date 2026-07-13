"""ledger_ext.py 在整个架构中的位置:账本深化(finitude_BLUEPRINT §5 / INTEGRATION_SPEC §2.2)。

`LedgerExt` 是 `persistence.PlasticityLedger` 的**组合包装**(持有引用,不继承不改类,
v0.1 `persistence.py` 零改动)——`PlasticityLedger.append()` 只写固定的 7 个字段,无法
承载 v2 增量字段,故本类直接向**同一个** ledger 文件追加自己的 jsonl 行(与
`PlasticityLedger.append`/`persistence.LedgerEntry` 同构的写法:单行 `os.write` +
`os.fsync`,失败静默)。

v2 增量字段(§5.1):
| reason | 新增字段 |
|---|---|
| settle_day | hi, concern, [f], [model_fallback] |
| hatch | model |
| epoch_shift(新 reason) | epoch_to, track |

读侧兼容论证(§5.2):`PlasticityLedger._iter_entries` 只要求 sid/gen/p 三键,未知字段
与未知 reason 自然穿透;epoch_shift 行的 p = 当时契约 P(不产生新的 P 变化),min 合并
语义不破坏。写侧:v0.1 `persistence.py` 零改动。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yelos.persistence import PlasticityLedger


def _now() -> float:
    import time

    return time.time()


class LedgerExt:
    """`PlasticityLedger` 的 v2 字段写手 + replay 读取器。"""

    def __init__(self, ledger: "PlasticityLedger") -> None:
        self._ledger = ledger

    @property
    def path(self) -> Path:
        return self._ledger.path

    # -- 写(直接向同一文件追加,承载 v2 字段)------------------------------

    def _append_raw(self, row: dict) -> None:
        line = json.dumps(row, ensure_ascii=False) + "\n"
        try:
            fd = os.open(
                self._ledger.path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644
            )
            try:
                os.write(fd, line.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass  # 尽力而为,与 PlasticityLedger.append 同款纪律

    def append_hatch(
        self,
        sid: str,
        gen: int,
        born_at: float,
        p: float,
        *,
        day: str,
        model: str,
        ts: float | None = None,
    ) -> None:
        self._append_raw(
            {
                "sid": sid,
                "gen": int(gen),
                "born_at": float(born_at),
                "p": float(p),
                "ts": _now() if ts is None else float(ts),
                "day": str(day),
                "reason": "hatch",
                "model": str(model),
            }
        )

    def append_settle(
        self,
        sid: str,
        gen: int,
        born_at: float,
        p: float,
        *,
        day: str,
        hi: int,
        concern: int,
        f: float | None = None,
        model_fallback: bool = False,
        ts: float | None = None,
    ) -> None:
        row = {
            "sid": sid,
            "gen": int(gen),
            "born_at": float(born_at),
            "p": float(p),
            "ts": _now() if ts is None else float(ts),
            "day": str(day),
            "reason": "settle_day",
            "hi": int(hi),
            "concern": int(concern),
        }
        if f is not None:
            row["f"] = float(f)
        if model_fallback:
            row["model_fallback"] = True
        self._append_raw(row)

    def append_epoch_shift(
        self,
        sid: str,
        gen: int,
        born_at: float,
        p: float,
        *,
        day: str,
        epoch_to: str,
        track: str,
        ts: float | None = None,
    ) -> None:
        self._append_raw(
            {
                "sid": sid,
                "gen": int(gen),
                "born_at": float(born_at),
                "p": float(p),
                "ts": _now() if ts is None else float(ts),
                "day": str(day),
                "reason": "epoch_shift",
                "epoch_to": str(epoch_to),
                "track": str(track),
            }
        )

    # -- 读(唯一事实源:replay)-------------------------------------------

    def _iter_rows(self, sid: str, gen: int):
        path = self._ledger.path
        if not path.exists():
            return
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get("sid") != sid:
                continue
            try:
                if int(obj.get("gen", -1)) != int(gen):
                    continue
            except (TypeError, ValueError):
                continue
            yield obj

    def replay(self, sid: str, gen: int) -> "LifeReplay":
        """从 ledger 行流重建一生:P 序列、活跃日序数、纪元史、hi/concern 日谱。"""
        p_series: list[tuple[str, float]] = []
        f_series: list[tuple[str, float]] = []
        epoch_events: list[dict] = []
        hi_by_day: dict[str, int] = {}
        concern_by_day: dict[str, int] = {}
        active_day_count = 0
        model_id: str | None = None

        for obj in self._iter_rows(sid, gen):
            reason = obj.get("reason")
            day = obj.get("day", "")
            p = obj.get("p")
            if isinstance(p, (int, float)):
                p_series.append((day, float(p)))
            if reason == "hatch":
                model_id = obj.get("model")
            elif reason == "settle_day":
                active_day_count += 1
                hi = obj.get("hi")
                if isinstance(hi, int):
                    hi_by_day[day] = hi
                concern = obj.get("concern")
                if isinstance(concern, int):
                    concern_by_day[day] = concern
                f = obj.get("f")
                if isinstance(f, (int, float)):
                    f_series.append((day, float(f)))
            elif reason == "epoch_shift":
                epoch_events.append(
                    {
                        "day": day,
                        "epoch_to": obj.get("epoch_to"),
                        "track": obj.get("track"),
                    }
                )

        return LifeReplay(
            sid=sid,
            gen=gen,
            model_id=model_id,
            p_series=p_series,
            f_series=f_series,
            epoch_events=epoch_events,
            hi_by_day=hi_by_day,
            concern_by_day=concern_by_day,
            active_day_count=active_day_count,
        )


@dataclass(frozen=True)
class LifeReplay:
    """从 ledger 回放重建的一生(单一事实源,供 viz 三渲染器 + anthology P 曲线章共用)。"""

    sid: str
    gen: int
    model_id: str | None
    p_series: list[tuple[str, float]] = field(default_factory=list)
    f_series: list[tuple[str, float]] = field(default_factory=list)
    epoch_events: list[dict] = field(default_factory=list)
    hi_by_day: dict[str, int] = field(default_factory=dict)
    concern_by_day: dict[str, int] = field(default_factory=dict)
    active_day_count: int = 0

    def final_p(self) -> float | None:
        return self.p_series[-1][1] if self.p_series else None


__all__ = ["LedgerExt", "LifeReplay"]
