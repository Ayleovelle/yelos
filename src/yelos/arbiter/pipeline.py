"""pipeline.py 在整个架构中的位置。

AX:A2 的组装点:``ArbiterPipeline`` = 前置守卫链 ∘ 策略核 ∘ 后置降格
滤波链。管线语义表(arbiter_BLUEPRINT §2.1):

| 阶段       | TablePolicy(默认)                  | Smooth/Conservative/Duel |
|------------|--------------------------------------|---------------------------|
| 前置守卫链 | 跳过(冻结内核自含同语义守卫)          | 逐条执行,命中短路 PASS    |
| 策略核     | ``core.arbiter.arbitrate`` 直调       | ``policy.decide(pin)``    |
| 后置滤波   | 跳过(内核自含调制闸/narrow)           | 逐条降格滤波               |

即:``policy_id=="table"`` 时组合根应传入空 guards/post_filters 元组;
其余策略传入 ``guards.GUARD_CHAIN``/``guards.POST_FILTERS``。本类本身
对这一区分无感知,只忠实执行传入的序列——区分逻辑在组合根
(``arbiter/__init__.py::build_pipeline``)。
"""

from __future__ import annotations

from typing import Callable, Sequence

from ..core.arbiter import Verdict
from .explain import Explain, GuardFire, theta_digest as _theta_digest_fn
from .guards.base import Guard, PostFilter
from .hysteresis.params import Theta
from .inputs import PolicyInput
from .lattice import sigma_of
from .policies.base import PolicyProtocol
from .policies.duel import DuelResult


class ArbiterPipeline:
    def __init__(
        self,
        guards: Sequence[Guard],
        policy: PolicyProtocol,
        post_filters: Sequence[PostFilter],
        *,
        theta: Theta | None = None,
        duel_writer: Callable[[PolicyInput, DuelResult], None] | None = None,
    ) -> None:
        self._guards = tuple(guards)
        self._policy = policy
        self._post_filters = tuple(post_filters)
        self._theta = theta if theta is not None else Theta()
        self._duel_writer = duel_writer

    @property
    def policy_id(self) -> str:
        return self._policy.policy_id

    def run(self, pin: PolicyInput) -> tuple[Verdict, Explain]:
        guard_trace: list[GuardFire] = []
        for g in self._guards:
            v = g(pin)
            name = getattr(g, "__name__", getattr(g, "guard_id", repr(g)))
            if v is not None:
                # AX:A2 类型不变量运行时兜底(组合根装配期已跑过合成网格自检)。
                assert sigma_of(v) == 0 and v.kind == "PASS", (
                    f"guard {name} 违反 A2:返回了 σ>0 的 verdict"
                )
                guard_trace.append(GuardFire(name, True))
                return v, Explain(
                    v.kind,
                    self._policy.policy_id,
                    tuple(guard_trace),
                    (),
                    self._digest(),
                )
            guard_trace.append(GuardFire(name, False))

        verdict = self._policy.decide(pin)

        if self._duel_writer is not None and hasattr(self._policy, "evaluate"):
            result: DuelResult = self._policy.evaluate(pin)  # type: ignore[attr-defined]
            if result.diverged:
                self._duel_writer(pin, result)

        filter_trace: list[str] = []
        for f in self._post_filters:
            before = verdict
            verdict = f(verdict, pin)
            assert sigma_of(verdict) <= sigma_of(before), (
                f"post filter {getattr(f, '__name__', f)} 违反 A2:σ 被升格"
            )
            if verdict is not before:
                filter_trace.append(getattr(f, "__name__", repr(f)))

        return verdict, Explain(
            verdict.kind,
            self._policy.policy_id,
            tuple(guard_trace),
            tuple(filter_trace),
            self._digest(),
        )

    def _digest(self) -> str:
        return _theta_digest_fn(self._theta)
