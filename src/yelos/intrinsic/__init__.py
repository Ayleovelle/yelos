"""intrinsic/ 在整个架构中的位置:幕 III 内在生活模拟全系统(核心人格模块)。

组合根:`build_intrinsic(cfg) -> IntrinsicSystem` 把场参数/积分器/主动策略
/梦生成器按配置装配好;`GATE_CHAIN`(闸链顺序常量,AX-6)与策略/生成器
注册表在本文件显式暴露,供 scheduler/ 与测试引用。

`core/intrinsic.py`(v0.1)**原文件不删不改**——`ThresholdPolicy` 以包装
方式复用它的 `decide` 触发段(intrinsic_BLUEPRINT §0.3)。

子包依赖方向(无环):
```
field/circadian/moments → 仅 core 工具 + 标准库
impulses                → field/circadian
dreamwork               → field/moments + primal(白名单闸,跨模块允许)
scheduler               → 其余全部(编排层)
viz                      → moments/field(只读)
```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config_defaults import (
    DEFAULT_DREAM_GENERATOR,
    DEFAULT_INTRINSIC_INTEGRATOR,
    DEFAULT_INTRINSIC_POLICY,
    DEFAULT_MAX_CATCHUP_STEPS,
    DEFAULT_MOMENTS_ENABLED,
    cfg_get,
)
from .dreamwork.dream_state import DreamGenerator
from .dreamwork.residue import ResidueAggregation
from .dreamwork.wander import MarkovWander
from .field.integrators import EulerIntegrator, Integrator, TrapezoidIntegrator
from .field.state import FieldParams
from .impulses.field_crossing import FieldCrossingPolicy
from .impulses.gates import GATE_CHAIN
from .impulses.poisson_budget import PoissonBudgetPolicy
from .impulses.policy import ProactivePolicy
from .impulses.threshold import ThresholdPolicy

# --- 组合根外不可改的注册表(§2.1/§6.4)-----------------------------------

INTEGRATOR_REGISTRY: dict[str, type[Integrator]] = {
    "euler": EulerIntegrator,
    "trapezoid": TrapezoidIntegrator,
}

POLICY_REGISTRY: dict[str, type[ProactivePolicy]] = {
    "threshold": ThresholdPolicy,
    "field_crossing": FieldCrossingPolicy,
    "poisson_budget": PoissonBudgetPolicy,
}

DREAM_GENERATOR_NAMES: tuple[str, ...] = ("residue", "wander")


@dataclass(frozen=True)
class IntrinsicSystem:
    """`build_intrinsic` 的装配结果;字段只读,策略可经 `policy_name`(binding)
    中途切换(§3.2:触发脾气是习性不是体质,不同于 finitude 老化模型)。
    """

    params: FieldParams
    integrator: Integrator
    policy: ProactivePolicy
    policy_name: str
    dream_generator: DreamGenerator
    dream_generator_name: str
    moments_enabled: bool
    max_catchup_steps: int


def _build_integrator(name: str) -> Integrator:
    cls = INTEGRATOR_REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"未知 intrinsic_integrator={name!r};可选:{tuple(INTEGRATOR_REGISTRY)}"
        )
    return cls()


def _build_policy(name: str) -> ProactivePolicy:
    cls = POLICY_REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"未知 intrinsic_policy={name!r};可选:{tuple(POLICY_REGISTRY)}"
        )
    return cls()


def _build_dream_generator(name: str) -> tuple[DreamGenerator, str]:
    if name == "residue":
        return ResidueAggregation(), "residue"
    if name == "wander":
        return MarkovWander(fallback=ResidueAggregation()), "wander"
    raise ValueError(f"未知 dream_generator={name!r};可选:{DREAM_GENERATOR_NAMES}")


def build_intrinsic(cfg: Any = None) -> IntrinsicSystem:
    """组合根:按配置装配 `IntrinsicSystem`。`cfg` 缺键一律回落默认(不 raise)。"""
    policy_name = cfg_get(cfg, "intrinsic_policy", DEFAULT_INTRINSIC_POLICY)
    integrator_name = cfg_get(cfg, "intrinsic_integrator", DEFAULT_INTRINSIC_INTEGRATOR)
    field_params_override = cfg_get(cfg, "intrinsic_field_params", None)
    dream_generator_name = cfg_get(cfg, "dream_generator", DEFAULT_DREAM_GENERATOR)
    moments_enabled = bool(cfg_get(cfg, "moments_enabled", DEFAULT_MOMENTS_ENABLED))
    max_catchup_steps = int(
        cfg_get(cfg, "max_catchup_steps", DEFAULT_MAX_CATCHUP_STEPS)
    )

    params = (
        FieldParams.from_dict(field_params_override)
        if field_params_override
        else FieldParams()
    )
    params.validate()

    integrator = _build_integrator(integrator_name)
    policy = _build_policy(policy_name)
    dream_generator, dream_generator_name = _build_dream_generator(dream_generator_name)

    return IntrinsicSystem(
        params=params,
        integrator=integrator,
        policy=policy,
        policy_name=policy_name,
        dream_generator=dream_generator,
        dream_generator_name=dream_generator_name,
        moments_enabled=moments_enabled,
        max_catchup_steps=max_catchup_steps,
    )


__all__ = [
    "GATE_CHAIN",
    "INTEGRATOR_REGISTRY",
    "POLICY_REGISTRY",
    "DREAM_GENERATOR_NAMES",
    "IntrinsicSystem",
    "build_intrinsic",
]
