"""在整个架构中的位置:下载校验(蓝图 §3.4);哈希不符即拒载(DA2/R2)。

``LoadState`` 定居本文件(依赖图:``runtime → packaging.verify``);
``runtime/loader.py`` 只消费,不重定义。
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path


class LoadState(Enum):
    ABSENT = "absent"
    HASH_MISMATCH = "hash_mismatch"
    DEPS_MISSING = "deps_missing"
    READY = "ready"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def verify(model_dir: Path, manifest_path: Path | None) -> LoadState:
    """校验 ``model_dir`` 下的模型文件与 manifest 逐文件哈希是否一致。

    ``manifest_path`` 为 None ⇒ 无校验依据,视为 ABSENT(拒绝半信部署,
    DA2 的保守解读:宁可干净缺席,不带病上岗)。manifest 存在但引用文件
    缺失或哈希不符 ⇒ HASH_MISMATCH(R2,loader 拒载)。
    """
    if manifest_path is None or not manifest_path.is_file():
        return LoadState.ABSENT
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return LoadState.HASH_MISMATCH
    files = manifest.get("files", {})
    if not files:
        return LoadState.ABSENT
    for rel, expected_hash in files.items():
        candidate = model_dir / rel
        if not candidate.is_file():
            return LoadState.HASH_MISMATCH
        if _sha256_file(candidate) != expected_hash:
            return LoadState.HASH_MISMATCH
    return LoadState.READY


__all__ = ["LoadState", "verify"]
