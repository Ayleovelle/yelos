"""stub 纪律(distill_BLUEPRINT §6):可编程候选序列,全链测试零 torch、

零真权重。``StubBackend`` 满足 ``trainer.protocol.ModelBackend`` 协议。
"""

from __future__ import annotations

from yelos.core.clock import Clock


class StubLoadError(RuntimeError):
    """StubBackend 可编程抛出,模拟"加载期失败"路径。"""


class StubBackend:
    """可编程候选序列:合法句 / 越界句 / 超时 / 异常。"""

    def __init__(
        self,
        candidates: list[str],
        model_hash: str = "stub-hash",
        *,
        clock: Clock | None = None,
        delay_ms: float = 0.0,
        raise_on_generate: Exception | None = None,
    ) -> None:
        self._candidates = candidates
        self._model_hash = model_hash
        self._clock = clock
        self._delay_ms = delay_ms
        self._raise_on_generate = raise_on_generate

    @property
    def model_hash(self) -> str:
        return self._model_hash

    def generate(self, seed: str, k: int, budget_ms: int) -> list[str]:  # noqa: ARG002
        if self._raise_on_generate is not None:
            raise self._raise_on_generate
        if self._clock is not None and self._delay_ms:
            self._clock.advance(self._delay_ms / 1000.0)  # 假时钟推进,不真睡
        return list(self._candidates[:k])


__all__ = ["StubBackend", "StubLoadError"]
