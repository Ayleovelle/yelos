"""orchestrator.py 在整个架构中的位置:心跳步 5 的新实现体(蓝图 §2/§10),
一拍管线的宿主。`ShadowSystem` 是 `build_shadow_system` 的装配产物,
`session.py`(未来接线,超出本任务"只建新文件"范围)只持这一个句柄:

```
system = build_shadow_system(cfg, bridge, det, memory_facade=..., ledger_root=...)
verdict = await system.beat(record, sid, day_key, now_ts)
system.on_user_turn(record, sid, turn_feats, now_ts)
active = system.concern_active(record, day_key)
```

默认 `detector_set="legacy"`:整条 `beat()` 直接委派 `signals.legacy_compat.
legacy_beat`,与 v0.1 `session._shadow_step` 逐字节等价(golden 闸,§0 兼容
纪律)。`detector_set="v2"` 时才走 §10 决策表的完整八步管线(ensemble/
baseline/四检测器/迟滞/闸链/校准/敏感化全部接通)。

全表锁内执行的假设:`beat`/`on_user_turn` 由调用方(session.py 未来接线)
包在 per-session lock 临界区内调用(RE6),本文件自身不加锁——与 v0.1
`_shadow_step` 的既有纪律一致(锁的归属在 session 层,不在被调用的纯逻辑
层)。异常纪律同 v0.1:调用方应 `try/except` 单拍失败不拖垮心跳循环——本
文件让异常自然抛出,不在内部吞掉(吞掉会让红队看不见退化点)。
"""

from __future__ import annotations

import logging
from typing import Any

from .baseline import legacy as legacy_baseline_mod
from .baseline import rolling
from .binding_v2 import (
    BASELINE_CHANNELS,
    CTYPES,
    ensure_shadow_block,
    reset_daily_if_new_day,
)
from .calibration import ledger as ledger_mod
from .calibration import outcome as outcome_mod
from .contracts import (
    BaselineView,
    ConcernVerdict,
    DayContext,
    PredictionRecord,
    ShadowConfig,
)
from .gates.chain import GateContext, run_gate_chain
from .sensitization import scar
from .signals import hysteresis as hyst_mod
from .signals import legacy_compat
from .signals.protocol import REARM_RATIO, TH_BASE
from .simulator import epsilon as eps_mod
from .simulator.budget import BudgetTracker, calls_for_k
from .simulator.ensemble import (
    apply_daily_perturbation,
    build_ensemble_reading,
    read_ensemble,
)

logger = logging.getLogger("yelos.shadow")

_ENGINE_CHANNELS = ("pressure", "warmth", "damage")
_DETECTORS = None  # 延迟绑定,避免与 signals/__init__ 的 DETECTOR_REGISTRY 产生模块级循环 import 时机问题


def _detector_registry():
    global _DETECTORS
    if _DETECTORS is None:
        from .signals import DETECTOR_REGISTRY

        _DETECTORS = DETECTOR_REGISTRY
    return _DETECTORS


class ShadowSystem:
    def __init__(
        self,
        cfg: ShadowConfig,
        bridge: Any,
        *,
        memory_facade: Any = None,
        ledger_factory: Any = None,
        detector_set: str = "legacy",
    ) -> None:
        self._cfg = cfg
        self._bridge = bridge
        self._memory = memory_facade
        self._ledger_factory = ledger_factory or (
            lambda sid: ledger_mod.CalibrationLedger(_no_ledger_path())
        )
        self._detector_set = detector_set
        self._budget: dict[str, BudgetTracker] = {}
        self._ledgers: dict[str, Any] = {}

    # -- 内部装配 ---------------------------------------------------------

    def _budget_for(self, sid: str) -> BudgetTracker:
        bt = self._budget.get(sid)
        if bt is None:
            bt = BudgetTracker()
            self._budget[sid] = bt
        return bt

    def _ledger_for(self, sid: str):
        ledger = self._ledgers.get(sid)
        if ledger is None:
            ledger = self._ledger_factory(sid)
            self._ledgers[sid] = ledger
        return ledger

    # -- §3.4 心跳步 5 新签名 -----------------------------------------------

    async def beat(
        self,
        record: dict[str, Any],
        sid: str,
        day_key: str,
        now_ts: float,
        *,
        probe_allowed: bool = True,
    ) -> ConcernVerdict | None:
        if not self._cfg.shadow_enabled:
            return None
        if record.get("mode") != "companion":
            return None
        if record.get("sealed") or (record.get("daily") or {}).get(
            "guard_frozen", False
        ):
            return None

        if self._detector_set == "legacy":
            try:
                sh_surface = await self._bridge.shadow_state(sid)
            except Exception:
                logger.exception("shadow.beat: shadow_state read failed (legacy path)")
                return None
            return await legacy_compat.legacy_beat(
                record, sid, sh_surface, day_key, self._bridge
            )

        return await self._beat_v2(
            record, sid, day_key, now_ts, probe_allowed=probe_allowed
        )

    async def _beat_v2(
        self,
        record: dict[str, Any],
        sid: str,
        day_key: str,
        now_ts: float,
        *,
        probe_allowed: bool,
    ) -> ConcernVerdict | None:
        shadow_block = ensure_shadow_block(record)
        is_new_day = shadow_block["daily"].get("day") != day_key

        if is_new_day:
            interactions_final = shadow_block["daily"].get("interactions_today", 0)
            shadow_block["baselines"]["interactions"]["day"] = interactions_final
            for ch in BASELINE_CHANNELS:
                rolling.rollover_day(shadow_block["baselines"][ch], day_key, ch)
        reset_daily_if_new_day(shadow_block, day_key)

        requested_k = max(1, min(3, int(self._cfg.shadow_hypotheses)))
        quota = int(self._cfg.shadow_engine_calls_per_beat)
        bt = self._budget_for(sid)
        k_effective, degraded = bt.decide_k(requested_k, quota)

        try:
            views = await read_ensemble(self._bridge, sid, k_effective)
        except Exception:
            logger.exception("shadow.beat: read_ensemble failed")
            return None
        bt.record(calls_for_k(k_effective))

        if not views:
            return None
        h0 = views[0]
        if h0.pressure is None and h0.warmth is None and h0.damage is None:
            return None  # 引擎缺席,保守方向(§10 步 1)

        if self._memory is not None:
            gen = int(record.get("incarnation", 0) or 0)
            try:
                mem_baseline = self._memory.baseline_context(sid, gen, day_key)
            except Exception:
                mem_baseline = None
        else:
            mem_baseline = None
        for ch in ("warmth", "pressure"):
            legacy_baseline_mod.bootstrap_from_memory(
                shadow_block["baselines"][ch], ch, mem_baseline
            )

        # X6 裁定(INTEGRATION_SPEC §3.6):familiarity 继续从 memory 取,沿用
        # W1 过渡公式 0.9+0.2*familiarity 折减 concern 强度(§3.6 原话"W3 shadow
        # 深化时 familiarity 继续从 memory 取")。memory 缺席时 factor=1.0
        # (中性,不折减)。
        familiarity = (
            getattr(mem_baseline, "familiarity", None)
            if mem_baseline is not None
            else None
        )
        familiarity_factor = 0.9 + 0.2 * familiarity if familiarity is not None else 1.0

        prev_pressure = shadow_block["baselines"]["pressure"].get("_prev_tick_value")
        pressure_slope = 0.0
        if prev_pressure is not None and h0.pressure is not None:
            pressure_slope = h0.pressure - prev_pressure
        if h0.pressure is not None:
            shadow_block["baselines"]["pressure"]["_prev_tick_value"] = h0.pressure

        channel_values = {
            "pressure": h0.pressure,
            "warmth": h0.warmth,
            "damage": h0.damage,
        }
        for ch, val in channel_values.items():
            if val is not None:
                rolling.observe_tick(shadow_block["baselines"][ch], val)

        base_views: dict[str, BaselineView] = {
            ch: rolling.get_baseline_view(shadow_block["baselines"][ch], ch)
            for ch in BASELINE_CHANNELS
        }

        ewma_vars = {
            ch: shadow_block["baselines"][ch].get("ewma_var", 0.0)
            for ch in _ENGINE_CHANNELS
        }
        dispersions = {ch: base_views[ch].dispersion for ch in _ENGINE_CHANNELS}
        sigma_obs = eps_mod.compute_sigma_obs(ewma_vars)
        sigma_family = eps_mod.compute_sigma_family(dispersions)

        epsilon_used = sigma_obs  # 记账占位,若日首拍施加扰动会覆盖为真实 ε_t
        if is_new_day and k_effective > 1:
            try:
                epsilon_used = await apply_daily_perturbation(
                    self._bridge, sid, day_key, k_effective, sigma_obs, sigma_family
                )
            except Exception:
                logger.exception("shadow.beat: apply_daily_perturbation failed")
                epsilon_used = eps_mod.compute_epsilon(sigma_obs, sigma_family)
        else:
            epsilon_used = eps_mod.compute_epsilon(sigma_obs, sigma_family)

        reading = build_ensemble_reading(
            views, rolling.CHANNEL_SPAN, epsilon_used, degraded
        )

        ledger = self._ledger_for(sid)
        ledger_mod.check_and_resolve_silence(
            shadow_block, ledger, now_ts, window=self._cfg.shadow_calibration_window
        )

        day_ctx = DayContext(
            day_key=day_key,
            interactions_today=int(shadow_block["daily"].get("interactions_today", 0)),
            last_gap_seconds=float(shadow_block["daily"].get("last_gap_seconds", 0.0)),
            msg_len_ewma=float(shadow_block["baselines"]["msg_len"].get("day") or 0.0),
            th_eff=scar.compute_th_eff_table(TH_BASE, shadow_block["sensitization"]),
            pressure_slope=pressure_slope,
            in_quiet=False,
            week_gap_median=float(
                shadow_block["baselines"]["rhythm"].get("week") or 0.0
            ),
            interactions_7d_avg=float(
                shadow_block["baselines"]["interactions"].get("week") or 0.0
            ),
            interactions_month_avg=float(
                shadow_block["baselines"]["interactions"].get("month") or 0.0
            ),
            msg_len_month_avg=float(
                shadow_block["baselines"]["msg_len"].get("month") or 0.0
            ),
        )

        best_verdict: ConcernVerdict | None = None
        registry = _detector_registry()
        for ctype, detect_fn in registry.items():
            raw = detect_fn(h0, base_views, day_ctx)
            if raw is None:
                # 未越阈:re-arm 检查走 hysteresis(strength=0)。
                hyst_state = shadow_block["hysteresis"][ctype]
                new_state, _ = hyst_mod.step(hyst_state, 0.0, 1.0, REARM_RATIO, day_key)
                shadow_block["hysteresis"][ctype] = new_state
                continue

            calib_entry = shadow_block["calibration"][ctype]
            tier = calib_entry.get("tier", "observe")
            disagreement = reading.disagreement if k_effective > 1 else 0.0
            brier = calib_entry.get("brier")
            b_norm = brier if brier is not None else 0.0
            if k_effective <= 1:
                u_t = b_norm  # §4.3:K=1 时退化为纯校准法
            else:
                u_t = 0.5 * disagreement + 0.5 * b_norm
            conf = max(0.0, min(1.0, 1.0 - u_t))

            ctx = GateContext(
                mode=record.get("mode", "companion"),
                shadow_enabled=self._cfg.shadow_enabled,
                sealed_or_frozen=bool(record.get("sealed"))
                or bool((record.get("daily") or {}).get("guard_frozen")),
                degraded=degraded,
                probe_allowed=probe_allowed,
                intensity_fn=self._cfg.shadow_intensity_fn,
                familiarity_factor=familiarity_factor,
            )
            new_state, verdict, _trace = run_gate_chain(
                raw,
                hysteresis_state=shadow_block["hysteresis"][ctype],
                day_key=day_key,
                conf=conf,
                tier=tier,
                ctx=ctx,
            )
            shadow_block["hysteresis"][ctype] = new_state
            if verdict is not None:
                pred = PredictionRecord(
                    ts=now_ts,
                    day=day_key,
                    ctype=ctype,
                    q=verdict.q,
                    features={
                        "disagreement": disagreement,
                        "epsilon": epsilon_used,
                        "strength": raw.strength,
                        "beta": float(
                            shadow_block["sensitization"][ctype].get("beta", 0.0)
                        ),
                        "brier": b_norm,
                    },
                )
                ledger_mod.record_prediction(shadow_block, pred)
                shadow_block["daily"]["concern_count"] = (
                    shadow_block["daily"].get("concern_count", 0) + 1
                )
                shadow_block["daily"]["inject_types"] = list(
                    set(shadow_block["daily"].get("inject_types", [])) | {ctype}
                )
                if verdict.do_inject:
                    try:
                        await self._bridge.inject_concern(sid, verdict.intensity)
                    except Exception:
                        logger.exception("shadow.beat: inject_concern failed")
                if best_verdict is None or verdict.intensity > best_verdict.intensity:
                    best_verdict = verdict

        return best_verdict

    def on_user_turn(
        self,
        record: dict[str, Any],
        sid: str,
        turn_feats: dict[str, float],
        now_ts: float,
    ) -> None:
        """校准回写点(§3.4):`submit(speaker=user)` 下一轮,调用方须在
        per-session lock 临界区内调。同步更新 rhythm/msg_len 活动通道 +
        interactions_today 计数(供 withdrawal/rhythm_break 参照)。
        """
        shadow_block = ensure_shadow_block(record)
        gap_seconds = float(turn_feats.get("gap_seconds", 0.0))
        msg_len = float(turn_feats.get("msg_len", 0.0))

        shadow_block["daily"]["interactions_today"] = (
            shadow_block["daily"].get("interactions_today", 0) + 1
        )
        shadow_block["daily"]["last_gap_seconds"] = gap_seconds
        rolling.observe_tick(shadow_block["baselines"]["rhythm"], gap_seconds)
        rolling.observe_tick(shadow_block["baselines"]["msg_len"], msg_len)

        ledger = self._ledger_for(sid)
        for ctype in CTYPES:
            pending = shadow_block["pending_prediction"].get(ctype)
            if pending is None:
                continue
            proxy_feats = {
                "gap_seconds": gap_seconds,
                "msg_len": msg_len,
                "week_gap_median": shadow_block["baselines"]["rhythm"].get("week")
                or 0.0,
                "msg_len_ewma": shadow_block["baselines"]["msg_len"].get("day") or 0.0,
            }
            out = outcome_mod.extract_outcome_from_turn(pending, proxy_feats, now_ts)
            ledger_mod.resolve_prediction(
                shadow_block,
                ledger,
                ctype,
                out,
                window=self._cfg.shadow_calibration_window,
            )
            scar.update_beta(shadow_block["sensitization"][ctype], out.y)

    def concern_active(self, record: dict | None, day_key: str) -> bool:
        """guidance 消费面(替换 `session._concern_active`,语义兼容)。"""
        if record is None or record.get("mode") != "companion":
            return False
        if self._detector_set == "legacy":
            cs = record.get("concern_state") or {}
            return cs.get("injected_day") == day_key and bool(cs.get("injected_types"))
        shadow_block = record.get("shadow") or {}
        daily = shadow_block.get("daily") or {}
        return daily.get("day") == day_key and bool(daily.get("inject_types"))


def _no_ledger_path():
    """未注入 `ledger_factory` 时的兜底路径(仅供未接线场景不 raise;真实
    组合根总是应传入基于 data_dir 的工厂函数)。
    """
    from pathlib import Path

    return Path(".") / "_shadow_ledger_unwired.jsonl"


__all__ = ["ShadowSystem"]
