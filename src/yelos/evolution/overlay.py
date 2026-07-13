"""overlay.py 在整个架构中的位置:evolution.overlay.json 原子读写(蓝图 §2.1/§3.4)。

persistence 纪律:tmp + ``os.replace``(与 ``core/binding.py``、
``memory/*/store.py`` 等同款,§6.1 原子写)。overlay 只存**与 hatch 默认
不同**的键(D-E2:进化只漂移部署者没有明示意见的参数;``gen=0`` 回滚 →
``values={}`` 字节级 = 从未进化)。

生效时机(D-E1):overlay 只在 ``config.load()`` 单一入口读取——本模块不做
热更新,``apply_overlay`` 只是纯函数合并,真正接线到 ``config.load()``
是另一任务的编码前置义务(config.py 本波禁改,同 §0 施工纪律)。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .genome.registry import REGISTRY, spec_for

SCHEMA_VERSION = 1


def default_overlay_path(data_dir: str | os.PathLike) -> Path:
    return Path(data_dir) / "evolution.overlay.json"


def load_overlay(path: str | os.PathLike) -> dict | None:
    """读 overlay;不存在/schema 坏 → ``None``(调用方回退 hatch 默认 +
    告警,T1 表"schema 坏/gen 与 lineage 不符"分支)。"""
    p = Path(path)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != SCHEMA_VERSION:
        return None
    if "values" not in payload or not isinstance(payload["values"], dict):
        return None
    return payload


def save_overlay(
    path: str | os.PathLike, *, deployment_id: str, gen: int, values: dict
) -> Path:
    """原子写盘(tmp + ``os.replace``),返回写入路径。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA_VERSION,
        "deployment_id": deployment_id,
        "gen": int(gen),
        "values": dict(values),
    }
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)
    return p


def make_overlay_writer(path: str | os.PathLike, *, deployment_id: str, gen: int):
    """给 ``lineage.LineageLedger.rollback`` 注入的写回调(依赖方向:
    lineage 不 import overlay,由调用方在此处把两者接起来)。"""

    def _writer(values: dict) -> Path:
        return save_overlay(path, deployment_id=deployment_id, gen=gen, values=values)

    return _writer


def apply_overlay(overlay_values: dict[str, Any] | None) -> dict[str, Any]:
    """把 overlay 的增量值叠加到 hatch 默认上,产出"现行 genome"(纯函数,
    不做优先级裁决——D-E2 的"文件 > env > overlay > 默认"由 config 装配层
    负责,本函数只管 overlay 自身与 hatch 默认的合并)。"""
    genome = {spec.key: spec.default for spec in REGISTRY}
    if not overlay_values:
        return genome
    for key, value in overlay_values.items():
        spec = spec_for(key)
        if spec is None or not spec.mutable:
            # 幽灵键或铁域键混入 overlay(如文件被手工篡改)一律忽略,
            # 不让损坏的 overlay 撬动铁域(A2 的又一道防线)。
            continue
        genome[key] = value
    return genome


__all__ = [
    "SCHEMA_VERSION",
    "default_overlay_path",
    "load_overlay",
    "save_overlay",
    "make_overlay_writer",
    "apply_overlay",
]
