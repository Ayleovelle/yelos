"""accounting/ledger.py 在整个架构中的位置。

AX:A6 记账守恒公理的唯一落点:swallowed_total 生命周期单调不减;
daily.high_intensity 仅由 pressure>=0.75 的 SWALLOW 递增;两计数器的
递增点**唯一**在本文件(AST 测试锁:全仓 grep 断言无第二处递增,见
tests/arbiter/test_accounting.py)。

verdict 流水:内存环缓冲(每 sid 最近 256 条,无原文),供 viz 时间线与
WebUI 事件环缓冲取数(WEBUI §5.3 形状对齐:``{ts, kind, verdict,
occasion}``)。

N10 履约:arbiter 的义务是 ``daily.high_intensity`` 计数在 finitude
rollover settle 时刻已完整(沉默结算先于 settle,T-A3);ledger `hi`
字段本身的**写入者是 finitude**,本文件不写 plasticity.ledger。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..lattice import sigma_of

_RING_CAP = 256


@dataclass(frozen=True)
class LedgerRow:
    ts: float
    kind: str
    sigma: int
    reason: str
    policy_id: str
    guard_trace_ids: tuple[str, ...]
    high_intensity: bool


class ArbiterLedger:
    """per-sid 记账;binding record 的 daily/lifetime 计数器由调用方持有,
    本类只提供**唯一递增函数** ``record_verdict``,调用方把返回的增量
    应用到 binding 的 ``daily.swallowed``/``swallowed_total``/
    ``daily.high_intensity`` 字段(不重复各处自己 += 1,守 A6)。
    """

    def __init__(self) -> None:
        self._rows: dict[str, list[LedgerRow]] = {}

    def rows_for(self, sid: str) -> tuple[LedgerRow, ...]:
        return tuple(self._rows.get(sid, ()))

    def record_verdict(
        self,
        *,
        sid: str,
        ts: float,
        verdict,
        policy_id: str,
        guard_trace_ids: tuple[str, ...] = (),
    ) -> dict[str, int]:
        """记一行流水,返回**本次应施加的计数增量** ``{"swallowed": 0|1,
        "high_intensity": 0|1}``——调用方(session/binding 层)据此原地
        += 到 record 上;本函数不持有 binding,不做磁盘 IO(纯记账语义,
        持久化落点仍是既有的 BindingStore + per-session 锁,N8)。

        AX:A6 —— 本函数是 swallowed_total / daily.high_intensity 的
        **唯一**语义递增点;任何策略不得旁路(即不得在别处再 += 这两个
        计数器)。
        """
        sig = sigma_of(verdict)
        hi = bool(getattr(verdict, "high_intensity", False))
        row = LedgerRow(
            ts=ts,
            kind=verdict.kind,
            sigma=sig,
            reason=getattr(verdict, "reason", ""),
            policy_id=policy_id,
            guard_trace_ids=guard_trace_ids,
            high_intensity=hi,
        )
        buf = self._rows.setdefault(sid, [])
        buf.append(row)
        if len(buf) > _RING_CAP:
            del buf[: len(buf) - _RING_CAP]
        is_swallow = verdict.kind == "SWALLOW"
        return {
            "swallowed": 1 if is_swallow else 0,
            "high_intensity": 1 if (is_swallow and hi) else 0,
        }
