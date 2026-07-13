"""rites/incarnation.py 在整个架构中的位置:一生只有一种老法(finitude_BLUEPRINT §7.3/§1.1 A7)。

`stamp_aging` 是 hatch 时刻的**唯一写点**:从 config 读 `finitude_model`/
`finitude_model_params` 并冻结进 `record["aging"]`;此后一切 settle 只经 `aging_of`
这个**唯一读点**取模型与参数,config 中途变更不影响在世生命。

与 `persistence.stamp_new_life`/`next_incarnation` 协作(不重复其职责):persistence
管世代号与 swallowed_total,本模块只管 `aging` 块。

对抗用例(红队样本,§11 对抗表):手改 `record["aging"]["model"]="weibull"` 于在世
中途 → 允许(数据是用户的,主权语义),但 model 与 params 必须成套域校验,params
域外(如 weibull k 不是数字/越界)→ 保守回退 linear + `fell_back=True`(不静默吞,
落 ledger settle 行的 `model_fallback: true`)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config_defaults import finitude_model_id, finitude_model_params
from ..models import DEFAULT_MODEL_ID, MODEL_REGISTRY


@dataclass(frozen=True)
class AgingSpec:
    """一次 settle 读到的老法快照(aging_of 的产出)。"""

    model: str
    params: dict
    active_days_settled: int
    fast: float
    fell_back: bool


def validate_params(model_id: str, params: dict) -> bool:
    """params 域校验(§7.3 对抗用例):域外 → False,由调用方回退 linear。"""
    if not isinstance(params, dict):
        return False
    if model_id == "linear":
        return True
    if model_id == "weibull":
        if "k" not in params:
            return True
        k = params["k"]
        if isinstance(k, bool) or not isinstance(k, (int, float)):
            return False
        return 1.0 <= float(k) <= 4.0
    if model_id == "event":
        for key in ("alpha0", "w_hi", "w_cn", "w_ep"):
            if key not in params:
                continue
            v = params[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                return False
        return True
    if model_id == "reserve":
        for key in ("r", "gamma"):
            if key not in params:
                continue
            v = params[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                return False
        return True
    return False


def stamp_aging(record: dict, config: Any) -> None:
    """# [FIN-A7] hatch 时刻唯一写点:model/params 从 config 冻结进 record.aging。"""
    model_id = finitude_model_id(config)
    params = finitude_model_params(config)
    if model_id not in MODEL_REGISTRY or not validate_params(model_id, params):
        model_id = DEFAULT_MODEL_ID
        params = {}
    record["aging"] = {
        "model": model_id,
        "params": dict(params),
        "active_days_settled": 0,
        "fast": 1.0,
    }


def aging_of(record: dict) -> AgingSpec:
    """settle/anthology 唯一读点(含 linear 回退,§7.3)。不改写 record。"""
    aging = record.get("aging")
    if not isinstance(aging, dict):
        return AgingSpec(
            model=DEFAULT_MODEL_ID,
            params={},
            active_days_settled=0,
            fast=1.0,
            fell_back=True,
        )

    raw_model = aging.get("model")
    raw_params = aging.get("params") if isinstance(aging.get("params"), dict) else {}

    active = aging.get("active_days_settled", 0)
    if not isinstance(active, int) or isinstance(active, bool) or active < 0:
        active = 0

    fast = aging.get("fast", 1.0)
    if not isinstance(fast, (int, float)) or isinstance(fast, bool):
        fast = 1.0

    if raw_model not in MODEL_REGISTRY:
        return AgingSpec(
            model=DEFAULT_MODEL_ID,
            params={},
            active_days_settled=active,
            fast=fast,
            fell_back=True,
        )
    if not validate_params(raw_model, raw_params):
        return AgingSpec(
            model=DEFAULT_MODEL_ID,
            params={},
            active_days_settled=active,
            fast=fast,
            fell_back=True,
        )
    return AgingSpec(
        model=raw_model,
        params=raw_params,
        active_days_settled=active,
        fast=fast,
        fell_back=False,
    )


def expr_p(record: dict) -> float:
    """P_expr 接线(finitude_BLUEPRINT §3.5):reserve 模型下 = fast,其余 = 契约 P。

    非 reserve 模型下与 v0.1 逐字节一致(兼容 golden 锁);reserve 下这是模型的
    可观测行为本体。仲裁 modulation、纪元 A 轨、anthology、ledger p 字段仍读契约 P。
    """
    spec = aging_of(record)
    if spec.model == "reserve":
        return spec.fast
    p = record.get("p", 0.0)
    if not isinstance(p, (int, float)) or isinstance(p, bool):
        return 0.0
    return float(p)


__all__ = ["AgingSpec", "validate_params", "stamp_aging", "aging_of", "expr_p"]
