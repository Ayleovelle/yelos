"""hysteresis/store.py 在整个架构中的位置。

binding record 增量块 ``arbiter_hyst`` 的读写与 schema 迁移(INTEGRATION_SPEC
§2.1 权威表 / arbiter_BLUEPRINT §5.5)。**不开新锁**(N8):调用方负责把
读写包在既有的 per-session 锁路径内(登记在 arbitrate 锁段、结算在
submit(user) 锁段、沉默结算在心跳 rollover 前)——本文件只提供纯数据
读写函数,不持锁、不触碰 time.time()/random。

缺块兼容(v0.1 record 无本块)⇒ 加载即初始化默认值,不 raise(T-H7)。
"""

from __future__ import annotations

from dataclasses import dataclass

from .ema import EmaState
from .params import Theta
from .signals import PendingOutcome, SessionSignalState

SCHEMA_VERSION = 1
_RING_CAP = 32


def default_block() -> dict:
    """binding 缺 ``arbiter_hyst`` 块时的初始化默认值(T-H7)。"""
    return {
        "v": SCHEMA_VERSION,
        "theta": {"d_sw": 0.0, "d_rp": 0.0, "d_ex": 0.0, "gamma": 1.0},
        "fast": 0.0,
        "slow": 0.0,
        "n_events": 0,
        "pending": None,
        "gaps": [],
        "lens": [],
    }


@dataclass(frozen=True)
class HystState:
    """``arbiter_hyst`` 块的强类型视图(store 读写的中间表示)。"""

    theta: Theta
    ema: EmaState
    n_events: int
    signals: SessionSignalState


def load(record: dict) -> HystState:
    """从 binding record 读取 ``arbiter_hyst``;缺块 -> 默认值(T-H7)。"""
    block = record.get("arbiter_hyst")
    if not isinstance(block, dict):
        block = default_block()
    theta = Theta.from_dict(block.get("theta", {}))
    ema = EmaState(fast=block.get("fast", 0.0), slow=block.get("slow", 0.0))
    n_events = int(block.get("n_events", 0))
    pending_raw = block.get("pending")
    pending = (
        PendingOutcome(
            sid=pending_raw["sid"],
            turn_id=pending_raw["turn_id"],
            kind=pending_raw["kind"],
            ts_i=pending_raw["ts_i"],
        )
        if pending_raw
        else None
    )
    gaps = list(block.get("gaps", []))[-_RING_CAP:]
    lens = list(block.get("lens", []))[-_RING_CAP:]
    signals = SessionSignalState(gaps=gaps, lens=lens, pending=pending)
    return HystState(theta=theta, ema=ema, n_events=n_events, signals=signals)


def dump(state: HystState) -> dict:
    """把 ``HystState`` 序列化回 binding record 可存的 dict 块。"""
    pending = state.signals.pending
    return {
        "v": SCHEMA_VERSION,
        "theta": state.theta.to_dict(),
        "fast": state.ema.fast,
        "slow": state.ema.slow,
        "n_events": state.n_events,
        "pending": (
            {
                "sid": pending.sid,
                "turn_id": pending.turn_id,
                "kind": pending.kind,
                "ts_i": pending.ts_i,
            }
            if pending is not None
            else None
        ),
        "gaps": list(state.signals.gaps)[-_RING_CAP:],
        "lens": list(state.signals.lens)[-_RING_CAP:],
    }


def save_into(record: dict, state: HystState) -> None:
    """原地把 state 写回 record["arbiter_hyst"](调用方负责持锁与 save())。"""
    record["arbiter_hyst"] = dump(state)
