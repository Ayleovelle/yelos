"""legacy_compat.py 在整个架构中的位置:`LegacyDetector` 适配壳(蓝图 §2 文件
树 / §0 兼容纪律)。默认配置(K=1、Legacy 检测器集、校准闸观察模式)下,
`orchestrator.py` 走本文件的 `legacy_beat`,是 `core/shadow.extract_concern`
+ v0.1 `session._shadow_step` 迟滞逻辑的逐字节等价搬运——直接读写 v0.1
既有的 `record["concern_state"]`/`record["shadow_baseline"]`(不新造一份影子
状态),保证 131 迁移 `tests/test_shadow.py` 与心跳步 5 golden 行为零漂移。

**唯一新增副作用**:`shadow.daily.concern_count`(X3 接缝,四检测器语义的
唯一权威源)在"当日首次 concern"时刻同步 +1——这是 v0.1 完全没有的新字段,
不影响任何既有可观测行为,只是给 finitude 供数(蓝图 §10 步 7 / §12.3)。

组合根(`shadow/__init__.py::build_shadow_system`)按 `detector_set` 参数
(非 §13 列出的四个正式配置键之一,是本实现为达成"默认逐字节兼容"这条硬
约束而补的一个内部开关,取值 `"legacy"`(默认)|`"v2"`;详见模块交付说明
"疑义记录")决定 `orchestrator.beat()` 走本文件还是 `orchestrator._beat_v2`。
"""

from __future__ import annotations

from typing import Any

from yelos.core import shadow as core_shadow

from ..binding_v2 import ensure_shadow_block, reset_daily_if_new_day
from ..contracts import ConcernVerdict


def _new_concern_state() -> dict[str, Any]:
    return {
        "armed": {"pressure": True, "warmth_drop": True, "damage": True},
        "injected_day": "",
        "injected_types": [],
    }


async def legacy_beat(
    record: dict[str, Any], sid: str, sh_surface: dict | None, day_key: str, bridge: Any
) -> ConcernVerdict | None:
    """v0.1 `session._shadow_step` 的逐字节等价重实现(读写
    `record["concern_state"]`/`record["shadow_baseline"]`/`record["daily"]`,
    与旧实现完全同源同序;唯一新增行为是 `shadow.daily.concern_count` 供数)。

    `bridge.inject_concern` 在此**逐 trigger** 调用(与 v0.1 循环体一致的
    quirk:同一拍若同时新触发 2 个 trigger,会调用 2 次 inject_concern,均用
    同一个 `sig.intensity`——这是 v0.1 既有行为的字面重现,不是本次新引入
    的 bug,golden 兼容要求逐字节保留)。

    `shadow.daily`(concern_count 供数块)的日翻转在函数**入口**无条件执行
    (不依赖本拍是否真的 inject),否则跨日无新触发时 `shadow.daily.day`
    永远卡在旧日期,`concern_count` 会跨日错误累计。
    """
    shadow_block = ensure_shadow_block(record)
    reset_daily_if_new_day(shadow_block, day_key)

    daily = record.setdefault("daily", {})
    baseline = record.get("shadow_baseline") or {"day": "", "warmth": None}
    if baseline.get("day") != day_key:
        baseline = {
            "day": day_key,
            "warmth": _sget(sh_surface, "state.valence.warmth", None),
        }
        record["shadow_baseline"] = baseline

    sig = core_shadow.extract_concern(
        sh_surface if isinstance(sh_surface, dict) else {}, baseline.get("warmth")
    )

    cs = record.setdefault("concern_state", _new_concern_state())
    armed = cs.setdefault(
        "armed", {"pressure": True, "warmth_drop": True, "damage": True}
    )
    injected_day = cs.get("injected_day", "")
    injected_types = list(cs.get("injected_types", []))
    triggers = set(sig.triggers) if sig is not None else set()
    first_today = not (injected_day == day_key and injected_types)
    did_inject = False
    if sig is not None:
        for t in sig.triggers:
            already = injected_day == day_key and t in injected_types
            if armed.get(t, False) and not already:
                await bridge.inject_concern(sid, sig.intensity)
                armed[t] = False
                if injected_day != day_key:
                    injected_day = day_key
                    injected_types = []
                injected_types.append(t)
                did_inject = True
        cs["injected_day"] = injected_day
        cs["injected_types"] = injected_types
    if did_inject and first_today:
        daily["high_intensity"] = daily.get("high_intensity", 0) + 1
        # X3 接缝:concern 的四检测器语义唯一权威源,与旧 daily.high_intensity
        # 计数点同步(蓝图 §10 步 7);Legacy 路径下"四检测器"退化为三触发,
        # 每次真正 inject 记一次。
        shadow_block["daily"]["concern_count"] = (
            shadow_block["daily"].get("concern_count", 0) + 1
        )
        shadow_block["daily"]["inject_types"] = list(
            set(shadow_block["daily"].get("inject_types", [])) | triggers
        )
    for t in ("pressure", "warmth_drop", "damage"):
        if t not in triggers:
            armed[t] = True

    if sig is None:
        return None
    ctype = sig.triggers[0] if sig.triggers else "pressure_spike"
    return ConcernVerdict(
        ctype=ctype,
        intensity=sig.intensity,
        q=0.5,
        do_inject=did_inject,
        do_enqueue=did_inject,
        gate_trace=("legacy",),
    )


_MISSING = object()


def _sget(surface: dict | None, path: str, default):
    cur: Any = surface
    for key in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, _MISSING)
        if cur is _MISSING:
            return default
    return cur


__all__ = ["legacy_beat"]
