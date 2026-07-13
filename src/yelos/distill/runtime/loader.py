"""在整个架构中的位置:懒加载 + 缺席探测(蓝图 §3.1;DA2 回退全域性锚点)。

``probe()`` 是 R1–R4(4.1 决策表)的机器形态:ABSENT / HASH_MISMATCH /
DEPS_MISSING / READY 四态穷尽,任何一态非 READY 都由
``runtime/provider.py`` 翻译为 ``ProviderUnavailable``(composer/过渡路由
跳席)。加载失败缓存为 ABSENT,每进程只探测一次(退避,不反复重试)。
"""

from __future__ import annotations

import importlib.util
import threading
from pathlib import Path

from ..packaging.verify import LoadState, verify
from ..trainer import ModelBackend, load_backend, model_file_exists

__all__ = ["ModelLoader", "LoadState"]

_TORCH_TIERS = frozenset({"rnn", "transformer"})


class ModelLoader:
    """懒加载器,持模型路径与哈希;composer 路由前必查 ``probe``。"""

    def __init__(self, model_dir: Path, tier: str, manifest_path: Path | None = None):
        self._model_dir = model_dir
        self._tier = tier
        self._manifest_path = manifest_path or (model_dir / "manifest.json")
        self._cached_state: LoadState | None = None  # None = 尚未探测
        self._cached_backend: ModelBackend | None = None
        self._probed_once = False
        self._lock = threading.Lock()  # RE6:并发 utter 懒加载单次

    @property
    def tier(self) -> str:
        return self._tier

    def _deps_ready(self) -> bool:
        if self._tier not in _TORCH_TIERS:
            return True
        return importlib.util.find_spec("torch") is not None

    def probe(self) -> LoadState:
        """ABSENT / HASH_MISMATCH / DEPS_MISSING / READY(§3.1)。

        每进程一次:成功后固化态,不因后续调用反复重新探测文件系统/import
        (`DA2`:失败退避,避免坏部署每次 utter 都重踩一次磁盘+import 代价)。
        """
        if self._probed_once and self._cached_state is not None:
            return self._cached_state

        self._probed_once = True
        if not model_file_exists(self._tier, self._model_dir):
            self._cached_state = LoadState.ABSENT
            return self._cached_state

        if self._manifest_path.is_file():
            state = verify(self._model_dir, self._manifest_path)
            if state != LoadState.READY:
                self._cached_state = state
                return self._cached_state

        if not self._deps_ready():
            self._cached_state = LoadState.DEPS_MISSING
            return self._cached_state

        self._cached_state = LoadState.READY
        return self._cached_state

    def get(self) -> ModelBackend:
        """懒加载,失败缓存为 ABSENT 不反复重试(每进程一次)。

        RE6:并发 utter 只应触发一次真实加载——双检锁(锁外快路径读缓存,
        锁内二次确认后才真正 ``load_backend``),避免每个并发线程各自
        重复解包/建模型对象。
        """
        state = self.probe()
        if state != LoadState.READY:
            raise RuntimeError(f"ModelLoader.get: 状态非 READY({state})")
        if self._cached_backend is not None:
            return self._cached_backend
        with self._lock:
            if self._cached_backend is None:
                try:
                    self._cached_backend = load_backend(self._tier, self._model_dir)
                except Exception:
                    self._cached_state = LoadState.ABSENT
                    raise
        return self._cached_backend

    def reset(self) -> None:
        """测试用:清空缓存态,强制下次 probe 重新探测。"""
        self._cached_state = None
        self._cached_backend = None
        self._probed_once = False
