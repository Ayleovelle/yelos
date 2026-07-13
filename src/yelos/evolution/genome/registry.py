"""genome/registry.py 在整个架构中的位置:REGISTRY 声明表,唯一事实源(蓝图 §3.2/T5)。

INTEGRATION_SPEC §3.8(X8 耦合治理)裁定:REGISTRY 每个可变异键须与其 owner
模块的蓝图**双向登记**(owner 蓝图标 ``[genome-mutable]``,本表标 owner +
与 owner 蓝图一致的域界),``validate_registry()`` 校验存在性+域界一致。

**W5 施工期诚实记录(疑义,交付说明重复一遍)**:截至本波编码时,arbiter /
intrinsic / memory / guidance 四个 owner 模块的蓝图**尚未**做 §3.8 要求的
反向标注(``grep -rn "genome-mutable" _build/modules/*.md`` 只命中
INTEGRATION_SPEC 自身一处)。蓝图 §3.2 给出的 ``arbiter.threshold_curve.*``
/ ``memory.recall.weights.*`` / ``guidance.profile_bias`` 等示例键,在对应
模块代码里目前只是**模块内部常量**(如 ``arbiter/policies/smooth.py`` 的
``W_PRESSURE`` 等权重表),不是可寻址的 config/参数面键——若此刻把它们注册
进 REGISTRY,就是 §3.8 明文警告的"注册了不存在的参数"死账,``validate_
registry`` 本该拦的东西不能自己先犯。因此本表**只收录当前真实存在、可
校验一致性的键**:

- 可变异集:仅 ``intrinsic_daily_cap``(蓝图 §3.2 表原样示例,且是
  ``YelosConfig`` 现有真实字段,domain [1,6] 与蓝图一致)。
- 铁域集:蓝图 §3.2 立碑清单里"当前有真实字段对应"的六项——
  ``arbiter_min_gap_seconds`` / ``quiet_hours`` / ``lifespan_active_days`` /
  ``farewell_token_ttl_seconds`` / ``default_mode``(P0/主权覆盖公理载体)/
  ``finitude_model``(finitude 模型选择;当前经 ``finitude.config_defaults.
  cfg_get`` 防御式读取,尚未入 ``YelosConfig`` 字段,与本模块自身
  ``evolution_*`` 五键同等境遇——校验按"模块 config_defaults 契约面存在"
  计,不苛求已入 ``YelosConfig``)。

后续任一 owner 模块完成 §3.8 反向标注后,只需按"只增不删"纪律在本表追加
行——REGISTRY 结构本身不需要改动。
"""

from __future__ import annotations

from .spec import GeneSpec

REGISTRY: tuple[GeneSpec, ...] = (
    # --- 可变异集(mutable=True) -----------------------------------------
    GeneSpec(
        key="intrinsic_daily_cap",
        module="intrinsic",
        kind="int",
        lo=1,
        hi=6,
        choices=(),
        default=3,
        mutable=True,
        semantics="主动日预算基数(cap×P 公式不变,只动 cap)",
    ),
    # --- 铁域集(mutable=False,立碑;对抗测试全部瞄准这里) -----------------
    GeneSpec(
        key="arbiter_min_gap_seconds",
        module="arbiter",
        kind="int",
        lo=180,
        hi=180,
        choices=(),
        default=180,
        mutable=False,
        semantics="克制的硬保证(介入率 ≤ 1/min_gap 的来源),漂移它=漂移主权",
    ),
    GeneSpec(
        key="quiet_hours",
        module="arbiter",
        kind="enum",
        lo=None,
        hi=None,
        choices=("01:00-08:00",),
        default="01:00-08:00",
        mutable=False,
        semantics="主权语义(v0.1 D 系裁决:硬窗)",
    ),
    GeneSpec(
        key="lifespan_active_days",
        module="finitude",
        kind="int",
        lo=545,
        hi=545,
        choices=(),
        default=545,
        mutable=False,
        semantics="一生契约:进化不许给她续命/减寿",
    ),
    GeneSpec(
        key="farewell_token_ttl_seconds",
        module="core",
        kind="int",
        lo=600,
        hi=600,
        choices=(),
        default=600,
        mutable=False,
        semantics="两段式送别的主权流程参数",
    ),
    GeneSpec(
        key="default_mode",
        module="core",
        kind="enum",
        lo=None,
        hi=None,
        choices=("steward", "companion"),
        default="steward",
        mutable=False,
        semantics="主权覆盖公理 / P0 语义类",
    ),
    GeneSpec(
        key="finitude_model",
        module="finitude",
        kind="enum",
        lo=None,
        hi=None,
        choices=("linear", "weibull", "event", "reserve"),
        default="linear",
        mutable=False,
        semantics="一生只有一种老法,hatch 定(finitude 模型选择,总纲 §2.5)",
    ),
)


def mutable_keys() -> frozenset[str]:
    return frozenset(spec.key for spec in REGISTRY if spec.mutable)


def iron_keys() -> frozenset[str]:
    return frozenset(spec.key for spec in REGISTRY if not spec.mutable)


def spec_for(key: str) -> GeneSpec | None:
    for spec in REGISTRY:
        if spec.key == key:
            return spec
    return None


def hatch_genome() -> dict[str, object]:
    """第 0 代基因组:REGISTRY 全部 default 值(overlay 为空时的基线)。"""
    return {spec.key: spec.default for spec in REGISTRY}


def _module_default(config: object, spec: GeneSpec) -> tuple[bool, object]:
    """尽力从 config/该模块 config_defaults 取真实默认值;找不到视为跳过。

    返回 ``(found, value)``——``found=False`` 时不判定不一致(诚实:没有可比
    对象就不裁决),但仍计入"键在参数面是否存在"的判据(见 validate_registry)。
    """
    # 优先看 config 本身(YelosConfig 真实字段,或测试常用的 dict 代理,
    # 双形态兼容读取,与各模块 cfg_get 同精神)——arbiter_min_gap_seconds /
    # quiet_hours / lifespan_active_days / farewell_token_ttl_seconds /
    # default_mode 都是这一类("module" 标注是语义 owner,不是物理落点)。
    if isinstance(config, dict):
        if spec.key in config:
            return True, config[spec.key]
    elif hasattr(config, spec.key):
        return True, getattr(config, spec.key)

    # config 面没有 -> 落回该模块自己的 config_defaults(尚未升级进
    # YelosConfig 字段、但已defensive-read 落地的键,如 finitude_model)。
    if spec.module == "finitude":
        try:
            from ..finitude import config_defaults as fcd  # noqa: PLC0415
        except ImportError:
            return False, None
        name = f"DEFAULT_{spec.key.upper()}"
        if hasattr(fcd, name):
            return True, getattr(fcd, name)

    return False, None


def validate_registry(config: object) -> list[str]:
    """默认值 / 域界一致性校验(§3.8②),返回问题清单(空=通过)。

    校验项:
    1. 每个键在目标模块的 config/参数面真实存在(否则"注册了幽灵参数")。
    2. 存在时,``spec.default`` 必须等于该模块的真实默认值。
    3. ``spec.default`` 必须落在声明的域界内(``GeneSpec.in_domain``)。
    """
    problems: list[str] = []
    seen: set[str] = set()
    for spec in REGISTRY:
        if spec.key in seen:
            problems.append(f"duplicate registry key: {spec.key}")
        seen.add(spec.key)

        if not spec.in_domain(spec.default):
            problems.append(
                f"{spec.key}: default {spec.default!r} outside declared domain"
            )

        found, real_default = _module_default(config, spec)
        if not found:
            problems.append(
                f"{spec.key}: not found on module {spec.module!r} config surface"
            )
            continue
        if real_default != spec.default:
            problems.append(
                f"{spec.key}: registry default {spec.default!r} != "
                f"module default {real_default!r}"
            )
    return problems


__all__ = [
    "REGISTRY",
    "mutable_keys",
    "iron_keys",
    "spec_for",
    "hatch_genome",
    "validate_registry",
]
