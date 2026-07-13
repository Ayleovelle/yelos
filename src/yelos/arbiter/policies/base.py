"""policies/base.py 在整个架构中的位置。

策略协议 + 注册表。协议:``decide(PolicyInput) -> Verdict``,纯函数,
零 IO 零时钟(DuelPolicy 的分歧语料副作用不在 ``decide`` 里发生——见
``policies/duel.py`` 的 ``evaluate`` 分离设计)。
"""

from __future__ import annotations

from typing import Protocol

from ...core.arbiter import Verdict
from ..inputs import PolicyInput


class PolicyProtocol(Protocol):
    policy_id: str

    def decide(self, pin: PolicyInput) -> Verdict: ...


REGISTRY: dict[str, PolicyProtocol] = {}


def register(policy: PolicyProtocol) -> PolicyProtocol:
    REGISTRY[policy.policy_id] = policy
    return policy
