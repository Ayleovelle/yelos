"""distill 测试固定件:假 gate / 假 loader,零 torch、零真权重(§6 stub 纪律)。"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from yelos.bench.clock import VirtualClock
from yelos.distill.packaging.verify import LoadState


@dataclass(frozen=True)
class FakeGateResult:
    ok: bool
    tier: str = "R"
    reason: str = ""


class FakeGate:
    """闭集白名单:只放行 ``allowed`` 集合内的文本(测试用,非真 closure)。"""

    def __init__(self, allowed: set[str] | None = None):
        self.allowed = allowed if allowed is not None else set()
        self.calls: list[str] = []

    def check(self, canonical, occasion, lang, band, epoch, corpus):  # noqa: ARG002
        self.calls.append(canonical)
        return FakeGateResult(ok=canonical in self.allowed)


class FakeLoader:
    """满足 ``ModelLoader`` 对外接口(probe/get),状态由测试直接摆放。"""

    def __init__(self, state: LoadState, backend=None):  # noqa: ANN001
        self._state = state
        self._backend = backend
        self.get_calls = 0

    def probe(self) -> LoadState:
        return self._state

    def get(self):  # noqa: ANN201
        self.get_calls += 1
        if self._backend is None:
            raise RuntimeError("FakeLoader: 无 backend")
        return self._backend


@pytest.fixture
def virtual_clock() -> VirtualClock:
    return VirtualClock(start_ts=1_700_000_000.0)


@pytest.fixture
def fixed_deps():
    """provider 构造所需的最小依赖闭包(除 loader/gate/reranker/clock 外)。"""
    return {
        "p_lookup": lambda sid: 0.5,  # noqa: ARG005
        "epoch_lookup": lambda sid: 0,  # noqa: ARG005
        "lang_lookup": lambda sid: "zh",  # noqa: ARG005
        "corpus_reader": lambda sid, lang: ("你好。", "在的。"),  # noqa: ARG005
    }


__all__ = ["FakeGate", "FakeGateResult", "FakeLoader", "virtual_clock", "fixed_deps"]
