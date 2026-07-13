"""tests/shadow/conftest.py:共用夹具。`FakeBridge` 实现
`shadow.contracts.BridgeProto` 的全部方法(含 h1..hK-1 扩展方法),供
`detector_set="v2"` 路径的多假设测试使用;不实现引擎真实动力学,只是一个
可编程的读写记录器(蓝图 §0"引擎借来"记账纪律:测试侧的 fake bridge 不产生
任何自著深度记账,只是让自著编排逻辑可测)。
"""

from __future__ import annotations

import pytest


class FakeBridge:
    def __init__(self) -> None:
        self.h0_surfaces: dict[str, dict] = {}
        self.hyp_surfaces: dict[tuple[str, int], dict] = {}
        self.submitted: list[tuple[str, str, str]] = []
        self.submitted_hyp: list[tuple[str, int, str, str]] = []
        self.injected: list[tuple[str, float]] = []
        self.perturbed: list[tuple[str, int, float]] = []

    def set_h0(self, sid: str, surface: dict) -> None:
        self.h0_surfaces[sid] = surface

    def set_hyp(self, sid: str, k: int, surface: dict) -> None:
        self.hyp_surfaces[(sid, k)] = surface

    async def submit_shadow(self, umo: str, text: str, msg_id: str) -> None:
        self.submitted.append((umo, text, msg_id))

    async def submit_shadow_hyp(self, umo: str, k: int, text: str, msg_id: str) -> None:
        self.submitted_hyp.append((umo, k, text, msg_id))

    async def shadow_state(self, umo: str) -> dict | None:
        return self.h0_surfaces.get(umo)

    async def shadow_state_hyp(self, umo: str, k: int) -> dict | None:
        return self.hyp_surfaces.get((umo, k))

    async def inject_concern(self, umo: str, intensity: float) -> None:
        self.injected.append((umo, intensity))

    async def inject_shadow_perturb(self, umo: str, k: int, intensity: float) -> None:
        self.perturbed.append((umo, k, intensity))


class MinimalBridge:
    """只实现 v0.1 三方法,不支持多假设扩展(特性探测应静默退化为 K=1)。"""

    def __init__(self) -> None:
        self.h0_surfaces: dict[str, dict] = {}
        self.injected: list[tuple[str, float]] = []

    def set_h0(self, sid: str, surface: dict) -> None:
        self.h0_surfaces[sid] = surface

    async def submit_shadow(self, umo: str, text: str, msg_id: str) -> None:
        return None

    async def shadow_state(self, umo: str) -> dict | None:
        return self.h0_surfaces.get(umo)

    async def inject_concern(self, umo: str, intensity: float) -> None:
        self.injected.append((umo, intensity))


def surface_with(
    pressure: float | None = None,
    warmth: float | None = None,
    damage: float | None = None,
) -> dict:
    out: dict = {"state": {}}
    if pressure is not None:
        out["state"]["boundary"] = {"pressure": pressure}
    if warmth is not None:
        out["state"]["valence"] = {"warmth": warmth}
    if damage is not None:
        out["state"]["damage"] = {"open": damage}
    return out


class FakeMemoryBaseline:
    def __init__(
        self,
        familiarity: float = 0.5,
        typical_warmth: float = 0.6,
        typical_pressure: float = 0.4,
    ) -> None:
        self.familiarity = familiarity
        self.typical_warmth = typical_warmth
        self.typical_pressure = typical_pressure


class FakeMemoryFacade:
    """X6 消费点用的最小 memory facade 替身(鸭子类型,零依赖 yelos.memory)。"""

    def __init__(self, baseline: FakeMemoryBaseline | None = None) -> None:
        self._baseline = baseline or FakeMemoryBaseline()

    def baseline_context(self, sid: str, gen: int, day_key: str) -> FakeMemoryBaseline:
        return self._baseline


@pytest.fixture
def fake_bridge() -> FakeBridge:
    return FakeBridge()


@pytest.fixture
def minimal_bridge() -> MinimalBridge:
    return MinimalBridge()


def new_binding_record() -> dict:
    """最小可用 record(不依赖 core/binding.py 的 `_new_binding`,只取
    shadow 需要读写的字段子集,保持测试与 binding.py 内部形状解耦)。
    """
    return {
        "mode": "companion",
        "sealed": False,
        "incarnation": 0,
        "daily": {"guard_frozen": False, "high_intensity": 0},
        "concern_state": {
            "armed": {"pressure": True, "warmth_drop": True, "damage": True},
            "injected_day": "",
            "injected_types": [],
        },
        "shadow_baseline": {"day": "", "warmth": None},
    }
