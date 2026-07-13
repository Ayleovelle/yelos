"""evolution genome REGISTRY 校验接线测试(wave A 诊断收尾:evolution 在 session

热路径 NOT DRIVEN 是设计使然,不动;问题是 ``validate_registry()``(SPEC
§3.8/X8 ghost-param 校验)从不被调用——一个引用了已改名/不存在参数的陈旧
基因组 key 会变成静默死账)。

修法落点:``config.py`` 的 ``config.load()`` 组装层,``evolution.overlay.json``
→ genome 应用(``apply_overlay``)之后调用 ``validate_registry()``。

覆盖:

- 无 overlay(evolution_enabled 开或关都一样):config.load() 不校验、不报错,
  默认路径字节不变。
- evolution_enabled 关 + overlay 存在(哪怕带陈旧 key):默认部署零感知,
  不校验、不报错——只有 opt-in 打开时才检查。
- evolution_enabled 开 + overlay 存在 + REGISTRY 全部合法键:校验通过,
  config.load() 正常返回。
- evolution_enabled 开 + overlay 存在 + REGISTRY 混入陈旧/幽灵键(引用不
  存在的 config 属性):validate_registry 拦截,config.load() 清晰报错,
  错误信息里点名该 key。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from yelos import config as config_mod  # noqa: E402
from yelos.evolution.genome.spec import GeneSpec  # noqa: E402


def _write_config_file(tmp_path: Path, **overrides) -> Path:
    cfg_path = tmp_path / "yelos.config.json"
    payload = {"data_dir": str(tmp_path / "data")}
    payload.update(overrides)
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")
    return cfg_path


def _write_overlay(data_dir: Path, values: dict) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = data_dir / "evolution.overlay.json"
    overlay_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "deployment_id": "test-deploy",
                "gen": 1,
                "values": values,
            }
        ),
        encoding="utf-8",
    )
    return overlay_path


# --- 默认路径不破 ---------------------------------------------------------


def test_no_overlay_default_build_unaffected(tmp_path: Path, monkeypatch) -> None:
    """无 overlay 文件:即便 evolution_enabled=True,也不调用 validate_registry。"""
    calls = []
    from yelos.evolution.genome import registry as registry_mod

    real_validate = registry_mod.validate_registry

    def spy(cfg):
        calls.append(cfg)
        return real_validate(cfg)

    monkeypatch.setattr(registry_mod, "validate_registry", spy)

    cfg_path = _write_config_file(tmp_path, evolution_enabled=True)
    cfg = config_mod.load(cfg_path)
    assert cfg.evolution_enabled is True
    assert calls == []  # 无 overlay -> 不校验,行为原样


def test_evolution_disabled_with_stale_overlay_is_noop(tmp_path: Path, monkeypatch) -> None:
    """evolution_enabled 关(默认):哪怕 overlay 里混了陈旧 key,也零感知不报错。"""
    from yelos.evolution.genome import registry as registry_mod

    ghost_spec = GeneSpec(
        key="__ghost_stale_param__",
        module="intrinsic",
        kind="int",
        lo=1,
        hi=6,
        choices=(),
        default=3,
        mutable=True,
        semantics="test-only ghost key",
    )
    monkeypatch.setattr(
        registry_mod, "REGISTRY", registry_mod.REGISTRY + (ghost_spec,)
    )

    cfg_path = _write_config_file(tmp_path)  # evolution_enabled 默认 False
    data_dir = tmp_path / "data"
    _write_overlay(data_dir, {})

    cfg = config_mod.load(cfg_path)  # 不应抛
    assert cfg.evolution_enabled is False


# --- opt-in 且 overlay 真存在:校验生效 -------------------------------------


def test_overlay_with_legal_registry_passes(tmp_path: Path) -> None:
    """overlay 存在 + REGISTRY 全部合法键(真实注册表):校验通过,正常返回。"""
    cfg_path = _write_config_file(tmp_path, evolution_enabled=True)
    data_dir = tmp_path / "data"
    _write_overlay(data_dir, {"intrinsic_daily_cap": 4})

    cfg = config_mod.load(cfg_path)  # 不应抛
    assert cfg.evolution_enabled is True


def test_overlay_with_ghost_registry_key_is_rejected(tmp_path: Path, monkeypatch) -> None:
    """overlay 存在 + REGISTRY 混入陈旧/幽灵键:validate_registry 拦截,报错点名该 key。"""
    from yelos.evolution.genome import registry as registry_mod

    ghost_spec = GeneSpec(
        key="__ghost_stale_param__",
        module="intrinsic",
        kind="int",
        lo=1,
        hi=6,
        choices=(),
        default=3,
        mutable=True,
        semantics="test-only ghost key: 模拟已改名/不存在的 config 属性",
    )
    monkeypatch.setattr(
        registry_mod, "REGISTRY", registry_mod.REGISTRY + (ghost_spec,)
    )

    cfg_path = _write_config_file(tmp_path, evolution_enabled=True)
    data_dir = tmp_path / "data"
    _write_overlay(data_dir, {})

    with pytest.raises(ValueError) as excinfo:
        config_mod.load(cfg_path)

    assert "__ghost_stale_param__" in str(excinfo.value)


def test_overlay_with_domain_violation_is_rejected(tmp_path: Path, monkeypatch) -> None:
    """REGISTRY 默认值越出声明域界同样被拦截、报错点名该 key。"""
    from yelos.evolution.genome import registry as registry_mod

    bad_spec = GeneSpec(
        key="__ghost_domain_violation__",
        module="intrinsic",
        kind="int",
        lo=1,
        hi=6,
        choices=(),
        default=99,  # 越出 [1,6] 域界
        mutable=True,
        semantics="test-only domain violation",
    )
    monkeypatch.setattr(
        registry_mod, "REGISTRY", registry_mod.REGISTRY + (bad_spec,)
    )

    cfg_path = _write_config_file(tmp_path, evolution_enabled=True)
    data_dir = tmp_path / "data"
    _write_overlay(data_dir, {})

    with pytest.raises(ValueError) as excinfo:
        config_mod.load(cfg_path)

    assert "__ghost_domain_violation__" in str(excinfo.value)
