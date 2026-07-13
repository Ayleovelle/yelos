"""finitude/ 在整个架构中的位置:幕 V 有限性 —— 可塑性动力学与"她的一生"(核心人格模块)。

组合根:`build_settle_fn(record, sid, ...) -> Callable[[float, dict], float]` 产出
`persistence.PlasticityLedger`/`core.binding.BindingStore.rollover` 所需的 settle_fn
闭包——`v0.1 rollover` 契约零改动:仍是单入口、仍返回 new_p、双保险仍在 binding 侧。

`core/finitude.py`(v0.1)**原文件不删不改**——`LinearDecay` 委托它的 `settle_day`
公式(finitude_BLUEPRINT §3.1),`epochs/fixed.py` 委托它的 `epoch`/`epoch_transition`。

子包依赖方向(无环,finitude_BLUEPRINT §2):
```
dayfacts ← models ← gate ← __init__(本文件)
epochs ← __init__
ledger_ext ← __init__(session 层未来调用)
anthology ← rites.farewell
projection ← rites.farewell 与 viz.hourglass
viz ← anthology.templates
```

**施工期接线疑义(诚实记录)**:蓝图 §2 给的 `build_settle_fn` 示例签名只有
`(record, ledger, ledger_ext, dualtrack, config)` 五个位置参数,未显式列 `sid`。
`sid` 是向 ledger/divergence 写行的结构性必需量(record 本身不含 sid 字段——
`persistence._new_binding` 不落 sid,umo 只是 `BindingStore._data` 的外层键),
本实现在签名首位追加 `sid: str`(keyword 其余保持精神一致,未强行照抄
`dualtrack` 单独传入——`DualTrack` 改为组合根内部按 `record["epoch2"]` 现场构造,
理由:调用方不必在每次 rollover 前手工装配一个 DualTrack 实例)。这是本模块与
session.py 未来接线(W-1..W-4,本波不做,`session.py` 禁止编辑)的编码前置约定,
留给红队核验。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from . import config_defaults
from .dayfacts import extract_dayfacts
from .epochs import DualTrack, DualTrackOutcome, OpDetectorState
from .gate import settle_through_gate
from .ledger_ext import LedgerExt, LifeReplay
from .models import MODEL_REGISTRY, build_model
from .rites import (
    AgingSpec,
    aging_of,
    build_notice,
    expr_p,
    farewell_summary,
    stamp_aging,
)

if TYPE_CHECKING:
    from yelos.persistence import PlasticityLedger


def _rings_active_days(record: dict, entry_cumulative: int) -> int:
    history = record.get("epoch_history") or []
    prev_cumulative = 0
    if history:
        last = history[-1]
        if isinstance(last, dict):
            prev_cumulative = last.get("active_days_settled_at", 0)
    return max(1, entry_cumulative - prev_cumulative)


def build_settle_fn(
    record: dict,
    sid: str,
    *,
    ledger: "PlasticityLedger | None" = None,
    ledger_ext: LedgerExt | None = None,
    config: Any = None,
    data_dir: str | Path | None = None,
) -> Callable[[float, dict], float]:
    """产出 `binding.rollover` 所需的 `settle_fn(p, 昨日daily) -> new_p`。

    闭包内完成(§10.1 决策表):effective_finitude 短路 → extract_dayfacts →
    按 record.aging.model 取模型 → settle_through_gate → 副作用登记(aging 块 /
    ledger v2 行 / dualtrack 观测 / milestone+notice+pool_snapshot)。
    """

    def settle_fn(p: float, daily: dict) -> float:
        mode = record.get("mode", "steward")
        if mode != "companion" or not config_defaults.finitude_globally_on(config):
            return p  # §10.1 行1:不构造副作用,无 ledger 行

        lifespan = config_defaults.lifespan_active_days(config)
        facts = extract_dayfacts(record, daily, lifespan)
        if not facts.was_active_day:
            return p  # §10.1 行2:gate 会短路,但连 ledger 行也不写

        spec = aging_of(record)
        model, fell_back = build_model(spec.model, spec.params, fast=spec.fast)
        outcome = settle_through_gate(model, p, facts)
        new_p = outcome.new_p

        gen = record.get("incarnation", 1)
        born_at = record.get("born_at", 0.0)
        day = facts.day

        # P_expr 前后值(§3.5):在改写 record.aging 之前用旧 spec 算,避免顺序错乱。
        p_expr_old = spec.fast if spec.model == "reserve" else p
        if spec.model == "reserve" and outcome.fast_pool is not None:
            p_expr_new = outcome.fast_pool
        else:
            p_expr_new = new_p

        aging_block = record.setdefault(
            "aging",
            {
                "model": spec.model,
                "params": spec.params,
                "active_days_settled": 0,
                "fast": 1.0,
            },
        )
        aging_block["active_days_settled"] = spec.active_days_settled + 1
        if outcome.fast_pool is not None:
            aging_block["fast"] = outcome.fast_pool

        if ledger_ext is not None:
            ledger_ext.append_settle(
                sid,
                gen,
                born_at,
                new_p,
                day=day,
                hi=facts.high_intensity,
                concern=facts.concern_fired,
                f=outcome.extras.get("f"),
                model_fallback=fell_back,
            )

        cap = config_defaults.active_budget_cap(config)
        track_authority = config_defaults.finitude_epoch_track(config)
        epoch2_state = OpDetectorState.from_dict(record.get("epoch2"))
        dt = DualTrack(
            sid=sid,
            gen=gen,
            track_authority=track_authority,
            state=epoch2_state,
            cap=cap,
            data_dir=data_dir,
        )
        dt_outcome: DualTrackOutcome = dt.observe(day, p, new_p, p_expr_old, p_expr_new)
        record["epoch2"] = dt.state.to_dict()

        if dt_outcome.notify_epoch:
            history = record.setdefault("epoch_history", [])
            entry: dict[str, Any] = {
                "day": day,
                "epoch": dt_outcome.notify_epoch,
                "track": dt_outcome.notify_track,
                "p": new_p,
                "p_expr": p_expr_new,
            }
            try:
                from yelos.primal import pool_snapshot

                snap = pool_snapshot(p_expr_new)
                entry["pools"] = snap
                if history and isinstance(history[-1], dict):
                    prev_pools = history[-1].get("pools")
                    if isinstance(prev_pools, dict):
                        lost: dict[str, list[str]] = {}
                        for occ, words in prev_pools.items():
                            cur_words = set(snap.get(occ, ()))
                            lost_words = [w for w in words if w not in cur_words]
                            if lost_words:
                                lost[occ] = lost_words
                        if lost:
                            entry["lost"] = lost
            except Exception:  # noqa: BLE001  primal 缺席安静降级(既有纪律同款)
                pass

            entry["active_days_settled_at"] = aging_block["active_days_settled"]
            entry["active_days"] = _rings_active_days(
                record, aging_block["active_days_settled"]
            )
            history.append(entry)

            milestones = record.setdefault("milestones", [])
            milestones.append({"day": day, "text": f"跃迁到{dt_outcome.notify_epoch}"})

            if ledger_ext is not None:
                ledger_ext.append_epoch_shift(
                    sid,
                    gen,
                    born_at,
                    new_p,
                    day=day,
                    epoch_to=dt_outcome.notify_epoch,
                    track=dt_outcome.notify_track,
                )
            record["pending_epoch_notice"] = build_notice(
                dt_outcome.notify_epoch, dt_outcome.notify_track, day
            ).to_dict()

        return new_p

    return settle_fn


__all__ = [
    "build_settle_fn",
    "config_defaults",
    "extract_dayfacts",
    "settle_through_gate",
    "MODEL_REGISTRY",
    "build_model",
    "DualTrack",
    "DualTrackOutcome",
    "OpDetectorState",
    "LedgerExt",
    "LifeReplay",
    "AgingSpec",
    "aging_of",
    "stamp_aging",
    "expr_p",
    "farewell_summary",
    "build_notice",
]
