"""持久化层:bindings.json 的原子读写 + BindingStore API。

蓝图 §8 / YELOS_SPEC §7.4。纯 JSON 层,零 astrbot / 零 sylanne_core /
零 random;KV 双写由 main 做,settle 单调由 finitude 保证。
日结(settle)只在 rollover 一个入口发生;lower_p 只降不升。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

# --- §8.1 磁盘结构默认块 -------------------------------------------------


def _new_daily(day_key: str) -> dict:
    """新的一天:日翻转时整块重置的 daily 块(§8.1)。"""
    return {
        "day": day_key,
        "interacted": False,
        "active_seen": False,
        "high_intensity": 0,
        "proactive_sent": 0,
        "last_proactive_ts": 0.0,
        "unanswered_streak": 0,
        "contact_night_sent": False,
        "self_words": 0,
        "swallowed": 0,
        "proxy_sentences": 0,
        "last_intervention_ts": 0.0,
        "guard_frozen": False,
        "revoke_used": False,
        "dream_delivered": False,
        "recover_primal_used": False,
    }


def _new_concern_state() -> dict:
    """非 daily 块:armed 跨日持久(红队 F11b)。"""
    return {
        "armed": {"pressure": True, "warmth_drop": True, "damage": True},
        "injected_day": "",
        "injected_types": [],
    }


def _new_binding(name: str, now_ts: float, day_key: str) -> dict:
    """一个绑定的完整初始结构(§8.1),含非 daily 的 concern_state。"""
    return {
        "name": name,
        "born_at": now_ts,
        "born_day": day_key,
        "p": 1.0,
        "sealed": False,
        "seal_kind": None,
        "silence_until": 0.0,
        "daily": _new_daily(day_key),
        "concern_state": _new_concern_state(),
        "dream": {"night_of": "", "count": 0, "pending": False},
        "shadow_baseline": {"day": "", "warmth": None},
        "pending_epoch_notice": None,
        "epoch_history": [],
        "milestones": [],
        "utterances": [],
        "dreams": [],
    }


# --- §8.2 BindingStore --------------------------------------------------


class BindingStore:
    """bindings.json 的内存镜像 + 原子持久化。

    每次状态变更后由调用方 save();写路径同步小文件,在事件循环里可接受。
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._data: dict[str, dict] = self._load()

    # -- 加载 / 损坏回退 --------------------------------------------------

    def _load(self) -> dict[str, dict]:
        """load;损坏 → 回退空表并保留 .corrupt 备份。"""
        if not self._path.exists():
            return {}
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, ValueError):
            self._backup_corrupt()
            return {}
        if not isinstance(data, dict):
            self._backup_corrupt()
            return {}
        return data

    def _backup_corrupt(self) -> None:
        """把损坏的原文件移到同名 .corrupt(尽力而为,失败静默)。"""
        corrupt = self._path.with_name(self._path.name + ".corrupt")
        try:
            os.replace(self._path, corrupt)
        except OSError:
            pass

    # -- 读 --------------------------------------------------------------

    def get(self, umo: str) -> dict | None:
        return self._data.get(umo)

    def bound_umos(self) -> list[str]:
        """未封存的绑定列表。"""
        return [u for u, b in self._data.items() if not b.get("sealed", False)]

    def records(self) -> dict[str, dict]:
        """全部绑定记录的浅拷贝(含封存)——只读镜像,供 WebUI 名册面等只读消费者
        用,不暴露内部 ``_data`` 引用本身(调用方改这份拷贝的顶层键不影响本店)。
        """
        return dict(self._data)

    def is_silenced(self, umo: str, now_ts: float) -> bool:
        b = self._data.get(umo)
        if b is None:
            return False
        return now_ts < b.get("silence_until", 0.0)

    # -- 写(内存态;调用方随后 save)------------------------------------

    def hatch(self, umo: str, name: str, now_ts: float, day_key: str) -> dict:
        """孵化;已存在且未封存 → 拒绝(ValueError)。"""
        existing = self._data.get(umo)
        if existing is not None and not existing.get("sealed", False):
            raise ValueError("already bound")
        b = _new_binding(name, now_ts, day_key)
        self._data[umo] = b
        return b

    def seal(self, umo: str, kind: str) -> None:
        b = self._data.get(umo)
        if b is None:
            return
        b["sealed"] = True
        b["seal_kind"] = kind

    def set_silence(self, umo: str, until_ts: float) -> None:
        b = self._data.get(umo)
        if b is None:
            return
        b["silence_until"] = until_ts

    def lower_p(self, umo: str, new_p: float) -> None:
        """只降不升:new_p 高于当前 p 时钳制为当前 p。"""
        b = self._data.get(umo)
        if b is None:
            return
        cur = b.get("p", 1.0)
        b["p"] = new_p if new_p < cur else cur

    def rollover(
        self, umo: str, day_key: str, settle_fn: Callable[[float, dict], float]
    ) -> float | None:
        """跨日单入口日结:用昨日 daily 调 settle_fn 得新 P(单调),再重置 daily。

        settle_fn(p, 昨日daily) -> 新P,由 main 包装 finitude.settle_day。
        未跨日返回 None。settle 只在此处发生 → 单调性只需守这一个门。
        """
        b = self._data.get(umo)
        if b is None:
            return None
        daily = b.get("daily")
        if daily is not None and daily.get("day") == day_key:
            return None
        if daily is None:
            b["daily"] = _new_daily(day_key)
            return None
        new_p = settle_fn(b.get("p", 1.0), daily)
        cur = b.get("p", 1.0)
        if new_p > cur:  # settle 已保证单调,双保险只降不升
            new_p = cur
        b["p"] = new_p
        b["daily"] = _new_daily(day_key)
        return new_p

    # -- 原子写 ----------------------------------------------------------

    def save(self) -> None:
        """原子写:tmp + os.replace。"""
        tmp = self._path.with_name(self._path.name + ".tmp")
        text = json.dumps(self._data, ensure_ascii=False, indent=2)
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self._path)
