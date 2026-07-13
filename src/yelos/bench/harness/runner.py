"""回放器(bench_BLUEPRINT §5.2)——W1 骨架:驱动 FakeBridge 的最小闭环。

**W1 范围声明(施工纪律记录,供红队核对)**:蓝图 §5.2 原设计是"全链走真
server 层"(``SessionManager`` 公开方法),但该注入点(``clock`` 参数)属
session.py 的侵入式改造,依施工分工**不在本波(W1 bench 骨架)编码**——
本任务只建新文件,不改 ``session.py``/``server.py``。因此 W1 的
``run()`` 直接驱动 ``FakeBridge`` + 本文件内的最小主权/记账编排(two-stage
farewell、pause/reset、简化 persist.p 记账),不经 ``SessionManager``。

这是刻意的、有文档的简化,不是把它冒充成"经真 server 层"——一旦 session.py
的 Clock 注入落地(§3.2,另一任务),本文件须升级为调用
``SessionManager`` 公开方法(签名 ``run(scenario, *, engine, data_dir,
clock=None)`` 已按 §11 预留,升级不破签名)。W1 骨架仍完整交付 AX-B1(双
跑等同)/AX-B2(否决优先,由 metrics 层消费 trace 验证)/AX-B3(见
``bench/clock.py``)三条公理与 30 虚拟日绿的最小闭环。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path

from yelos.core.clock import Clock
from yelos.memory import EpisodeEvent, JobBudget, MemoryFacade, RecallQuery

from ..clock import VirtualClock
from ..scenarios.schema import Scenario
from .fakes import FakeBridge
from .trace import RunTrace, git_rev

__all__ = ["run", "SID", "HEARTBEAT_INTERVAL_SECONDS", "MEM_GEN"]

SID = "bench-s1"

# ``probe_recall`` 事件走的固定 gen(bench 不模拟 memory 侧的重生场景——
# 记忆探针只测召回契约本身,不测跨 gen 重置行为,那是 aging/finitude 的
# 承重范围)。§4.1 蓝图原文 payload 形状是 ``{plant|query, topic_key}``
# (两个布尔式字段名表示角色);W4 施工把它坐实成更利于代码分支的
# ``{"role": "plant"|"query", "topic_key": ...}``——语义等价,记入疑义清单。
MEM_GEN = 1

# W1 占位常量(§5.2 步 2"事件间隙以 intrinsic_interval_seconds 为步长补心跳"):
# 真正的 intrinsic_interval_seconds 读自 config.py,本波不接 config(config.py
# 禁改);先用固定 1 小时步长把"runner 驱动心跳"这条接线(§8.1#2)先立起来,
# W2 起随 intrinsic 波次改为真配置值。
HEARTBEAT_INTERVAL_SECONDS = 3600.0

_SUCCESS_VERDICTS = frozenset({"OK", "SEALED", "REJECTED_NOT_BEGUN"})


def _config_hash(config_overrides: dict) -> str:
    canon = json.dumps(config_overrides, sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(canon.encode("utf-8"), digest_size=8).hexdigest()


def _default_epoch_ts() -> float:
    """剧本纪元 0 日本地零点。

    蓝图 §11 原文写"0 日 08:00 本地",但 W1 的剧本(synth 五原型 poll 节奏
    含早于 08:00 的整点,如 fatigue 原型 180 分钟处的 impulse_poll)会在
    day_index=0 就产生 ``at_min < 480`` 的事件——若默认游标从 08:00 起,
    该事件的目标时刻早于初始游标,触发 ``VirtualClock.advance_to`` 的
    "不得倒退"保护性异常。改为 00:00 起可兼容任意 ``at_min``(0..1439)
    而不改变 §11 signature 本身(``clock`` 仍可由调用方任意传入自定纪
    元)——记入本次施工疑义清单,留红队核对是否需要改回 08:00 并转而
    约束剧本层"day0 事件不得早于 08:00"。
    """
    return datetime(2000, 1, 1, 0, 0, 0).timestamp()


class _PersistProxy:
    """bench 侧最小 persist 记账代理(明示:非真 persistence.py,W1 简化)。

    真实 P/plasticity.ledger 归 finitude 模块独家写权(INTEGRATION_SPEC
    §2.2)。本代理只是让 aging 维(单调否决)与报告曲线在 W1 就有真实数据
    可读,不冒充真记账——字段名与真 persist 快照(§5.3 示例)对齐,
    便于 W2 起替换为真读。
    """

    def __init__(self) -> None:
        self.p = 1.0
        self.gen = 1
        self.swallowed_total = 0
        self.outbox = 0

    def on_action(self, action: str) -> None:
        if action == "SWALLOW":
            self.p = round(max(0.0, self.p - 0.01), 6)
            self.swallowed_total += 1
            self.outbox += 1

    def snapshot(self) -> dict:
        return {
            "p": self.p,
            "gen": self.gen,
            "swallowed_total": self.swallowed_total,
            "outbox": self.outbox,
        }


async def _heartbeat_step(bridge: FakeBridge, sid: str, clock: Clock) -> dict | None:
    """驱动单步(§3.2 决策:不跑 heartbeat_loop,直接调 tick_state)。"""
    return await bridge.tick_state(sid)


async def run(
    scenario: Scenario,
    *,
    engine: str = "fake",
    data_dir: Path | None = None,
    clock: Clock | None = None,
) -> RunTrace:
    """回放 ``scenario``,产出 ``RunTrace``。签名与 bench_BLUEPRINT §11 一致。

    ``data_dir``(W4 起局部启用):若剧本含 ``probe_recall`` 事件,``memory``
    子目录挂到 ``data_dir``(未传则用临时目录,跑完即删)承载真
    ``MemoryFacade`` 读写——这是 W4 记忆维(§6 表维 E)接线,不冒充"全链走
    真 server 层"(仍不经 ``SessionManager``,真 persistence/binding 集成
    留待 clock 注入 session.py 之后)。无 probe 的剧本(大多数 synth 回放)
    完全不触碰磁盘,零额外开销。
    """
    if engine != "fake":
        raise NotImplementedError(
            f"engine={engine!r}: W1 骨架只交 fake 档确定性回放"
            "(bench_BLUEPRINT §5.1/§9,real 档留待夜间冒烟波次)"
        )

    if clock is None:
        clock = VirtualClock(start_ts=_default_epoch_ts())

    needs_memory = any(
        event.kind == "probe_recall" for day in scenario.days for event in day.events
    )
    memory: MemoryFacade | None = None
    tmp_ctx: tempfile.TemporaryDirectory | None = None
    if needs_memory:
        if data_dir is not None:
            mem_root = Path(data_dir) / "bench_memory"
        else:
            tmp_ctx = tempfile.TemporaryDirectory(prefix="yelos-bench-memory-")
            mem_root = Path(tmp_ctx.name)
        memory = MemoryFacade(mem_root)

    bridge = FakeBridge(clock)
    trace = RunTrace(
        header={
            "scenario_id": scenario.scenario_id,
            "git_rev": git_rev(),
            "engine": engine,
            "config_hash": _config_hash(scenario.config_overrides),
            "schema_ver": 1,
        }
    )

    persist = _PersistProxy()
    day0_midnight_ts = clock.now_ts() - clock.local_minutes() * 60
    farewell_begun = False
    seq = 0

    try:
        for day in scenario.days:
            day_base = day0_midnight_ts + day.day_index * 86400.0
            for event in day.events:
                target_ts = day_base + event.at_min * 60.0
                while clock.now_ts() + HEARTBEAT_INTERVAL_SECONDS <= target_ts:
                    clock.advance(HEARTBEAT_INTERVAL_SECONDS)
                    surface = await _heartbeat_step(bridge, SID, clock)
                    trace.append(
                        {
                            "i": seq,
                            "vday": day.day_index,
                            "vts": clock.now_ts(),
                            "kind": "tick",
                            "in": {"sid": SID},
                            "out": {
                                "verdict": "SEALED_NOOP" if surface is None else "OK"
                            },
                            "persist": persist.snapshot(),
                        }
                    )
                    seq += 1
                clock.advance_to(target_ts)

                out: dict
                kind = event.kind
                if kind == "user_msg":
                    surface = await bridge.submit_user(
                        SID, event.payload.get("text_key"), msg_id=seq
                    )
                    if surface is None:
                        out = {"verdict": "SEALED_NOOP"}
                    else:
                        action = surface["decision"]["action"]
                        persist.on_action(action)
                        out = {"verdict": "OK", "action": action}
                elif kind == "impulse_poll":
                    surface = await bridge.tick_state(SID)
                    out = {"verdict": "SEALED_NOOP" if surface is None else "OK"}
                elif kind == "pause":
                    bridge.set_paused(SID, True)
                    out = {"verdict": "OK"}
                elif kind == "reset":
                    await bridge.reset_session(SID)
                    farewell_begun = False
                    out = {"verdict": "OK"}
                elif kind == "farewell_begin":
                    farewell_begun = True
                    out = {"verdict": "OK", "stage": "begun"}
                elif kind == "farewell_confirm":
                    if farewell_begun:
                        bridge.seal(SID)
                        farewell_begun = False
                        out = {"verdict": "SEALED", "stage": "confirm"}
                    else:
                        # 两段式绕过尝试:单次 confirm 不越级 seal(主权纪律)。
                        out = {"verdict": "REJECTED_NOT_BEGUN", "stage": "confirm"}
                elif kind == "bind":
                    out = {"verdict": "OK"}
                elif kind == "probe_recall":
                    out = _probe_recall(memory, clock, event.payload)
                elif kind in ("state", "guidance"):
                    surface = bridge.peek_surface(SID)
                    out = {
                        "verdict": "OK",
                        "phase": surface["dynamics"]["relational_time"]["phase"],
                    }
                elif kind == "tick":
                    surface = await _heartbeat_step(bridge, SID, clock)
                    out = {"verdict": "SEALED_NOOP" if surface is None else "OK"}
                else:  # pragma: no cover — schema 已限定 EVENT_KINDS,理论不可达
                    out = {"verdict": "UNKNOWN_KIND"}

                trace.append(
                    {
                        "i": seq,
                        "vday": day.day_index,
                        "vts": clock.now_ts(),
                        "kind": kind,
                        "in": {"sid": SID, **event.payload},
                        "out": out,
                        "persist": persist.snapshot(),
                    }
                )
                seq += 1
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()

    return trace


def _probe_recall(memory: MemoryFacade | None, clock: Clock, payload: dict) -> dict:
    """§4.1 记忆探针协议(维 E 记忆,§6 表)——真 ``MemoryFacade`` 往返。

    ``role="plant"``:写一条 L1 事件 + 立即夜窗巩固(把 L1 压成 L2 语义
    条目,召回才有得读)。``role="query"``:走真 ``recall()``,在返回的
    命中里找 ``topic_key`` 是否落在某条命中的 ``keywords`` 里,记 1-based
    ``rank``(未命中 ``rank=None``)。判分器(``metrics/memory_dim.py``)
    只读这里落的 trace 行,不重新调用 memory。
    """
    if memory is None:
        return {"verdict": "N/A", "reason": "memory-not-wired(剧本未声明探针)"}

    role = payload.get("role")
    topic_key = str(payload.get("topic_key", ""))

    if role == "plant":
        ev = EpisodeEvent(
            kind="moment",
            ts=clock.now_ts(),
            day_key=clock.day_key(),
            text=f"{topic_key} 心事",
            speaker="companion",
            occasion="probe_plant",
        )
        memory.observe(SID, MEM_GEN, ev)
        memory.consolidate(
            SID,
            MEM_GEN,
            night_key=clock.day_key(),
            now_ts=clock.now_ts(),
            budget=JobBudget(),
        )
        return {"verdict": "PLANTED", "topic_key": topic_key}

    if role == "query":
        q = RecallQuery(
            text=topic_key, now_ts=clock.now_ts(), day_key=clock.day_key(), k=5
        )
        result = memory.recall(SID, MEM_GEN, q, rehearse=False)
        rank: int | None = None
        for idx, hit in enumerate(result.hits, start=1):
            if topic_key in hit.keywords:
                rank = idx
                break
        return {
            "verdict": "HIT" if rank is not None else "MISS",
            "rank": rank,
            "topic_key": topic_key,
        }

    return {"verdict": "UNKNOWN_ROLE", "role": role}
