"""test_genome_registry.py:注册表↔config 默认一致、域界含默认、无未注册幽灵键(A1/A2, T5)。"""

from __future__ import annotations

from yelos.evolution.genome.registry import (
    REGISTRY,
    iron_keys,
    mutable_keys,
    validate_registry,
)

_EXPECTED_IRON = {
    "arbiter_min_gap_seconds",
    "quiet_hours",
    "lifespan_active_days",
    "farewell_token_ttl_seconds",
    "default_mode",
    "finitude_model",
}


def test_registry_no_duplicate_keys():
    keys = [spec.key for spec in REGISTRY]
    assert len(keys) == len(set(keys))


def test_registry_defaults_in_domain():
    for spec in REGISTRY:
        assert spec.in_domain(spec.default), spec.key


def test_iron_set_covers_constitutional_list():
    assert _EXPECTED_IRON <= iron_keys()


def test_mutable_and_iron_disjoint():
    assert mutable_keys() & iron_keys() == set()


def test_validate_registry_passes_against_real_config(base_config):
    problems = validate_registry(base_config)
    assert problems == []


def test_validate_registry_flags_default_drift(base_config):
    from yelos.evolution.genome import registry as reg_mod
    from yelos.evolution.genome.spec import GeneSpec

    # 造一个 default 与真实模块默认值不一致的假注册项,断言 _module_default
    # 能揪出不一致(不 monkeypatch 全局 REGISTRY 单例,保持其余测试干净)。
    bad_spec = GeneSpec(
        key="intrinsic_daily_cap",
        module="intrinsic",
        kind="int",
        lo=1,
        hi=6,
        choices=(),
        default=999,  # 明显不等于真实默认 3
        mutable=True,
        semantics="test-only ghost default",
    )
    found, real_default = reg_mod._module_default(base_config, bad_spec)
    assert found is True
    assert real_default != bad_spec.default


def test_validate_registry_flags_unregistered_ghost_module():
    from yelos.evolution.genome import registry as reg_mod
    from yelos.evolution.genome.spec import GeneSpec

    ghost = GeneSpec(
        key="does_not_exist_anywhere",
        module="arbiter",
        kind="int",
        lo=0,
        hi=1,
        choices=(),
        default=0,
        mutable=True,
        semantics="ghost",
    )
    found, _ = reg_mod._module_default({"quiet_hours": "01:00-08:00"}, ghost)
    assert found is False
