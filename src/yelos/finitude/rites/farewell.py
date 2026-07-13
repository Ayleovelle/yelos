"""rites/farewell.py 在整个架构中的位置:两段式送别摘要的内容组装(finitude_BLUEPRINT §7.1)。

server 侧两段式(首调返 token+摘要不封存,二调携 token 才 seal)零改动;本模块只
**接管摘要的内容**(此前是 server 内联拼装)。`est_remaining_active_days` 取自
`projection`——这是 projection 的运行时消费点(篡改 estimate → 摘要数字变 →
`test_rites.py::test_summary_consumes_projection` 挂)。
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from ..epochs import fixed
from .incarnation import aging_of

if TYPE_CHECKING:
    from ..ledger_ext import LifeReplay
    from ..projection.contracts import ProjectionData


def _days_lived(born_day: str, day_key: str) -> int | None:
    try:
        start = date.fromisoformat(born_day)
        end = date.fromisoformat(day_key)
    except (TypeError, ValueError):
        return None
    delta = (end - start).days
    return delta + 1 if delta >= 0 else None


def farewell_summary(
    record: dict, replay: "LifeReplay", proj: "ProjectionData"
) -> dict:
    """首段摘要(机器结构,server 直接入返回体)。

    {name, days_lived, current_epoch, utter_count, swallowed_total,
     dreams_count, aging_model, est_remaining_active_days}
    """
    name = record.get("name") or "她"
    born_day = str(record.get("born_day") or "")
    contract_p = record.get("p", 0.0)
    if not isinstance(contract_p, (int, float)) or isinstance(contract_p, bool):
        contract_p = 0.0

    utterances = record.get("utterances")
    dreams = record.get("dreams")
    swallowed_total = record.get("swallowed_total", 0)
    if not isinstance(swallowed_total, int) or isinstance(swallowed_total, bool):
        swallowed_total = 0

    return {
        "name": name,
        "days_lived": _days_lived(born_day, proj.as_of_day),
        "current_epoch": fixed.epoch_of(float(contract_p)),
        "utter_count": len(utterances) if isinstance(utterances, list) else 0,
        "swallowed_total": swallowed_total,
        "dreams_count": len(dreams) if isinstance(dreams, list) else 0,
        "aging_model": aging_of(record).model,
        "est_remaining_active_days": proj.est_remaining_active_days,
    }


__all__ = ["farewell_summary"]
