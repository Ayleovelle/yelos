"""在整个架构中的位置:回退健全性(蓝图 §1;DA2 消费者)。

三情形全回退探针:缺席(absent)/ 超时(timeout)/ 越界(rejected,全候选被
闸拦截)——三者都必须走协议性回退(``ProviderUnavailable``),不得让异常
或坏文本逃逸给调用方。``distill.trace.jsonl`` 的 ``eval.fallback_probe``
消费者身份(§5 数据契约)即本文件:读 trace 判回退健全。
"""

from __future__ import annotations

from typing import Callable

from yelos.primal.providers import ProviderUnavailable


def probe_one(call: Callable[[], str]) -> bool:
    """单一情形探针:True = 健全(协议性回退),False = 异常逃逸或未回退。"""
    try:
        call()
    except ProviderUnavailable:
        return True
    except Exception:  # noqa: BLE001  非协议异常逃逸即不健全
        return False
    return False  # 没抛异常但期望其回退 ⇒ 不健全(调用方需保证场景确实触发条件)


def fallback_probe(scenarios: dict[str, Callable[[], str]]) -> dict[str, bool]:
    """``scenarios`` 键 ∈ {"absent", "timeout", "rejected"}(§5 schema),

    值是触发对应情形后调用 ``provider.utter_canonical`` 的零参闭包。
    """
    return {name: probe_one(call) for name, call in scenarios.items()}


__all__ = ["probe_one", "fallback_probe"]
