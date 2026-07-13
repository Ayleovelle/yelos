"""arbiter 包组合根:在整个架构中的位置。

幕 II 话语权仲裁的深化包(arbiter_BLUEPRINT v1.0)。装配:
守卫序列表(§2.1 GUARD_CHAIN/POST_FILTERS)、策略注册表(policies）、
曲线注册表(modulation)、hysteresis 装配(θ 的 Box/MUTABLE_SET)。

装配期静态校验(N2/A2/A4 的 fail-fast 落地):
1. P0 守卫恒居 guards.GUARD_CHAIN[0](A4);
2. 守卫链只产 PASS(A2,guards.assert_guards_pass_only 跑合成网格);
3. θ schema(hysteresis.params.Theta 字段集)与 MUTABLE_SET 结构性一致
   (A4 铁域声明:两者本就是同一份字段集的两种视图,这里做交叉核对)。

全包只 import ``core.arbiter``(冻结)与 ``core.__init__``
(sget/split_sentences),不 import session/server/engine_bridge——纯逻辑
层纪律继承(总纲律一)。**本波不改 session.py**:把 pipeline 接入真实
运行时路径(W-1 接线,§9)是另一任务的编码前置义务,施工纪律"只建
新文件"下,本包在此提交前是可独立测试、可独立 import 的纯逻辑库。
"""

from __future__ import annotations

from dataclasses import fields as _dc_fields
from typing import Callable

from .accounting import ArbiterLedger, DuelCorpusWriter
from .accounting.duel_corpus import build_row as build_duel_row
from .explain import Explain, GuardFire, taxonomy_for_reason, theta_digest
from .guards import (
    GUARD_CHAIN,
    POST_FILTERS,
    assert_guards_pass_only,
    assert_post_filters_downgrade_only,
    guard_p0_sovereignty,
)
from .hysteresis import MUTABLE_SET, Theta
from .inputs import NARROW_P, PolicyInput, PolicyParams, compose_policy_params
from .lattice import SIGMA, is_downgrade_or_equal, min_sigma_verdict, sigma, sigma_of
from .modulation import CURVE_REGISTRY, STEP_CURVE, ModulationCurve
from .pipeline import ArbiterPipeline
from .policies import (
    CONSERVATIVE_POLICY,
    DUEL_POLICY,
    REGISTRY as POLICY_REGISTRY,
    SMOOTH_POLICY,
    TABLE_POLICY,
    DuelResult,
)
from .policies.duel import DuelPolicy

__all__ = [
    "ArbiterPipeline",
    "PolicyInput",
    "PolicyParams",
    "compose_policy_params",
    "NARROW_P",
    "SIGMA",
    "sigma",
    "sigma_of",
    "min_sigma_verdict",
    "is_downgrade_or_equal",
    "Theta",
    "MUTABLE_SET",
    "CURVE_REGISTRY",
    "STEP_CURVE",
    "ModulationCurve",
    "POLICY_REGISTRY",
    "TABLE_POLICY",
    "SMOOTH_POLICY",
    "CONSERVATIVE_POLICY",
    "DUEL_POLICY",
    "DuelResult",
    "Explain",
    "GuardFire",
    "theta_digest",
    "taxonomy_for_reason",
    "ArbiterLedger",
    "DuelCorpusWriter",
    "build_duel_row",
    "build_pipeline",
    "assemble_checks",
]


def _validate_theta_schema_matches_mutable_set() -> None:
    """AX:A4 铁域声明的结构性交叉核对:Theta dataclass 字段集(去掉内部
    存储细节 gamma_offset 的表现名差异后)应恰好穷尽 MUTABLE_SET。
    """
    theta_fields = {f.name for f in _dc_fields(Theta)}
    if theta_fields != MUTABLE_SET:
        raise AssertionError(
            "Theta schema 与 MUTABLE_SET 不一致(A4 铁域结构性保证被破坏):"
            f"theta_fields={theta_fields} MUTABLE_SET={MUTABLE_SET}"
        )


def _validate_guard_chain_shape() -> None:
    if not GUARD_CHAIN or GUARD_CHAIN[0] is not guard_p0_sovereignty:
        raise AssertionError("A4 违反:P0 守卫必须恒居 GUARD_CHAIN[0]")
    assert_guards_pass_only(GUARD_CHAIN)


def assemble_checks() -> None:
    """组合根装配期的全部静态/fail-fast 校验;import 本包时自动跑一遍
    (见文末),测试也可显式重跑以便定位问题。
    """
    _validate_guard_chain_shape()
    _validate_theta_schema_matches_mutable_set()
    # 后置滤波不变量的轻量自检:构造一枚中性探针跑一遍四种 verdict kind。
    from .core_probe import build_neutral_probe  # 延迟 import,避免循环

    probe = build_neutral_probe()
    assert_post_filters_downgrade_only(POST_FILTERS, probe)


def build_pipeline(
    policy_id: str = "table",
    *,
    theta: Theta | None = None,
    curve: ModulationCurve | None = None,
    duel_writer: Callable[[PolicyInput, DuelResult], None] | None = None,
) -> ArbiterPipeline:
    """组合根的主入口:按 ``policy_id`` 装配一条 ``ArbiterPipeline``。

    ``policy_id=="table"``(默认)时 guards/post_filters 为空元组
    (§2.1 管线语义表:TablePolicy 内核自含同语义守卫/调制闸,跑两遍会
    漂 reason 字符串);其余策略装配完整的 GUARD_CHAIN/POST_FILTERS。
    """
    if policy_id not in POLICY_REGISTRY:
        raise ValueError(f"未注册的 arbiter_policy: {policy_id!r}")
    policy = POLICY_REGISTRY[policy_id]
    theta = theta if theta is not None else Theta()
    if policy_id == "table":
        return ArbiterPipeline((), policy, (), theta=theta, duel_writer=None)
    writer = duel_writer if isinstance(policy, DuelPolicy) else None
    return ArbiterPipeline(
        GUARD_CHAIN, policy, POST_FILTERS, theta=theta, duel_writer=writer
    )


assemble_checks()
