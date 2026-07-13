"""RunTrace(bench_BLUEPRINT §5.3)——原始观测面 schema(数据契约①)。

jsonl,首行 header,其后每行一事件。无自由文本(§6.6 日志纪律前推到本层:
``append`` 拒绝 ``text``/``draft``/``final_text`` 等自由文本字段名,剧本层
早已只携 ``*_key`` 语料键,这里是兜底闸)。

``digest()`` 是 AX-B1(确定性可复算)的比较件:规范化(排序键)后对
header+rows 做 blake2b,逐字节相等即"同剧本同版本双跑等同"。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["RunTrace", "git_rev"]

_FORBIDDEN_FIELDS = frozenset({"text", "draft", "final_text", "raw_text"})


def git_rev() -> str:
    """当前 git 短哈希;非 git 仓库/git 缺失一律 ``"no-git"``(不 raise)。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return "no-git"


def _check_row(row: dict, path: str = "") -> None:
    for k, v in row.items():
        key_path = f"{path}.{k}" if path else k
        if k in _FORBIDDEN_FIELDS:
            raise ValueError(
                f"RunTrace.append: 字段 {key_path!r} 属自由文本禁列(§6.6 日志纪律)"
            )
        if isinstance(v, dict):
            _check_row(v, key_path)


@dataclass
class RunTrace:
    """回放的原始观测面。``header`` 冻结一次,``rows`` 按事件顺序追加。"""

    header: dict
    rows: list[dict] = field(default_factory=list)

    def append(self, row: dict) -> None:
        _check_row(row)
        self.rows.append(row)

    def digest(self) -> str:
        """规范化(键排序、无空白)后 blake2b 十六进制摘要——AX-B1 比较件。"""
        canon = json.dumps(
            {"header": self.header, "rows": self.rows},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.blake2b(canon.encode("utf-8")).hexdigest()

    def dump(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(self.header, ensure_ascii=False) + "\n")
            for row in self.rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: Path) -> RunTrace:
        path = Path(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise ValueError(f"空 trace 文件:{path}")
        header = json.loads(lines[0])
        rows = [json.loads(line) for line in lines[1:] if line.strip()]
        return cls(header=header, rows=rows)
