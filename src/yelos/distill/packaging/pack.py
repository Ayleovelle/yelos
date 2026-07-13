"""在整个架构中的位置:模型打包(蓝图 §3.4)。

产物:``<name>.tar.gz`` + ``<name>.manifest.json``(sha256 逐文件)+
``MODEL_CARD.md``。体积另账:权重可选下载,不进 wheel、不进 git。
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

from .model_card import ModelCard


@dataclass(frozen=True)
class PackManifest:
    files: dict  # 相对路径 -> sha256
    total_size_bytes: int = field(default=0)

    def to_dict(self) -> dict:
        return {"files": dict(self.files), "total_size_bytes": self.total_size_bytes}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def pack(model_path: Path, card: ModelCard, out: Path) -> PackManifest:
    """把 ``model_path``(目录或单文件)+ 模型卡打成一个 tar.gz bundle。

    ``out`` 是不带后缀的基名;实际写出 ``{out}.tar.gz`` / ``{out}.manifest.json``
    / ``{out}/MODEL_CARD.md``(卡与清单同目录,便于 loader 侧只读校验不必解包)。
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if model_path.is_file():
        files = [model_path]
    else:
        files = sorted(p for p in model_path.rglob("*") if p.is_file())

    file_hashes: dict[str, str] = {}
    total = 0
    tar_path = out.with_suffix(".tar.gz")
    base_dir = model_path if model_path.is_dir() else model_path.parent
    with tarfile.open(tar_path, "w:gz") as tar:
        for f in files:
            rel = str(f.relative_to(base_dir)) if model_path.is_dir() else f.name
            file_hashes[rel] = _sha256_file(f)
            total += f.stat().st_size
            tar.add(f, arcname=rel)

    card_with_size = ModelCard(
        tier=card.tier,
        corpus_hash=card.corpus_hash,
        corpus_scope=card.corpus_scope,
        license=card.license,
        size_bytes=total,
        train_config=card.train_config,
        determinism_note=card.determinism_note,
        model_hash=card.model_hash,
    )
    card_path = out.with_name(out.name + ".MODEL_CARD.md")
    card_path.write_text(card_with_size.render_markdown(), encoding="utf-8")

    manifest = PackManifest(files=file_hashes, total_size_bytes=total)
    manifest_path = out.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


__all__ = ["PackManifest", "pack"]
