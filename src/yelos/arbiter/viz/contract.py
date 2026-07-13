"""viz/contract.py 在整个架构中的位置。

``arbiter_timeline.json`` 数据契约(schema 成文,版本字段,
arbiter_BLUEPRINT §7.1)。字段形状与 WEBUI §5.3 事件环缓冲的 verdict
事件对齐(``{ts, kind, verdict, occasion}``),不另发明——WebUI 是第二
消费者,不是唯一消费者(仓内活消费者 = 本包渲染器 + bench 指标读取器)。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class VerdictEvent:
    ts: float
    kind: str
    sigma: int
    policy: str
    hi: bool


@dataclass(frozen=True)
class ThetaSnapshot:
    d_sw: float
    d_rp: float
    d_ex: float
    gamma: float


@dataclass(frozen=True)
class RateWindow:
    interventions: int
    turns: int


@dataclass(frozen=True)
class DayTimeline:
    day: str
    verdicts: tuple[VerdictEvent, ...]
    theta: ThetaSnapshot
    rate_window: RateWindow


@dataclass(frozen=True)
class ArbiterTimeline:
    sid_digest: str
    days: tuple[DayTimeline, ...]
    v: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "v": self.v,
            "sid_digest": self.sid_digest,
            "days": [
                {
                    "day": d.day,
                    "verdicts": [asdict(ev) for ev in d.verdicts],
                    "theta": asdict(d.theta),
                    "rate_window": asdict(d.rate_window),
                }
                for d in self.days
            ],
        }


def validate_schema(payload: dict) -> None:
    """最小 schema 校验(bench 读取器共用):版本字段 + 顶层键齐全。"""
    if payload.get("v") != SCHEMA_VERSION:
        raise ValueError(f"arbiter_timeline schema 版本不匹配:{payload.get('v')!r}")
    for key in ("sid_digest", "days"):
        if key not in payload:
            raise ValueError(f"arbiter_timeline 缺字段:{key}")
    for day in payload["days"]:
        for key in ("day", "verdicts", "theta", "rate_window"):
            if key not in day:
                raise ValueError(f"arbiter_timeline.days[].缺字段:{key}")
