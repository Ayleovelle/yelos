"""MCP 层持久化测试(蓝图 §8.2 test_persistence.py 一行)。

锁什么(权威条目):
    ledger 追加/加载 min 合并 / 世代隔离用 incarnation 计数器 / 进程锁
    (第二进程拒启,stale 接管) / bindings.json 原子写 + .corrupt 回退 /
    同秒重生(born_at 差<1s)仍全新 P、不继承前世(major⑤)/
    swallowed_total 生命周期累计(blocker②)。

本文件测 ``persistence.py``(PlasticityLedger / ProcessLock / incarnation
helpers)与 ``session.SessionManager``(经真实 arbitrate/bind/rollover 流验证
swallowed_total 累计与世代隔离的端到端行为)。SessionManager 用
``EngineBridge(llm_fn=None)`` 且不调 ``ensure()``——引擎缺席安静降级
(HAS_ENGINE 分支或未连接均返回 None),不依赖真实 sylanne_core 服务,只借
其 submit/tick 契约的"缺席安静降级"路径跑通 session 时序;surface 由测试
直接注入 ``_surface_cache`` 来驱动 arbiter 决策表(与 core 测试同款做法,
纯粹是"喂 surface、跑纯函数"，非绕过契约)。

无需 fastmcp/mcp SDK——这些锁全在 persistence/session 层,不碰 server.py
协议面,故不受"环境缺 fastmcp"影响,可直接 ``python -m pytest`` 自验。
"""

from __future__ import annotations

import asyncio
import json
import os
import time

import pytest

from yelos import persistence
from yelos.config import YelosConfig
from yelos.core.binding import BindingStore
from yelos.engine_bridge import EngineBridge
from yelos.session import SessionManager

# =====================================================================
# PlasticityLedger:追加 / 同世代 min 合并 / 世代隔离
# =====================================================================


def test_ledger_append_monotonic_via_real_settle(tmp_path):
    """真实 settle_day 序列追加进 ledger 后,同 sid/gen 的 P 轨迹单调不增。"""
    ledger = persistence.PlasticityLedger(tmp_path / "plasticity.ledger")
    p = 1.0
    trace = [p]
    for day in range(1, 11):
        from yelos.core.finitude import settle_day

        p = settle_day(
            p,
            was_active_day=True,
            high_intensity_events=day % 3,
            lifespan_active_days=100,
        )
        trace.append(p)
        ledger.append(
            "sid-mono",
            1,
            born_at=1000.0,
            p=p,
            day=f"2026-01-{day:02d}",
            reason="settle_day",
        )
    # 逐条严格非增(settle_day 结构性单调的持久化侧回归)。
    for a, b in zip(trace, trace[1:]):
        assert b <= a
    assert ledger.last_p("sid-mono", 1) == pytest.approx(trace[-1])


def test_ledger_effective_p_same_generation_min_merge(tmp_path):
    """加载合并:P = min(bindings.json P, 同世代 ledger 末条 P)(§7.4/D8)。"""
    ledger = persistence.PlasticityLedger(tmp_path / "plasticity.ledger")
    ledger.append(
        "sid-a", 1, born_at=1000.0, p=0.9, day="2026-01-01", reason="settle_day"
    )
    ledger.append(
        "sid-a", 1, born_at=1000.0, p=0.7, day="2026-01-02", reason="settle_day"
    )
    # bindings.json 侧比 ledger 末条更高(崩溃前未来得及写低值)→ 取更低者。
    assert ledger.effective_p("sid-a", 1, bindings_p=0.95) == pytest.approx(0.7)
    # 反过来:bindings.json 侧更低(极端场景)→ 仍取更低者,不返老还童。
    assert ledger.effective_p("sid-a", 1, bindings_p=0.5) == pytest.approx(0.5)


def test_ledger_generation_mismatch_ignored_new_life_not_inherited(tmp_path):
    """世代不匹配(ledger 是前世 incarnation)→ 忽略,重生不继承旧 P。"""
    ledger = persistence.PlasticityLedger(tmp_path / "plasticity.ledger")
    ledger.append(
        "sid-b", 1, born_at=1000.0, p=0.1, day="2026-01-01", reason="settle_day"
    )
    # 新孵化是 gen=2,ledger 只有 gen=1 的低 P 记录 → 不合并,用 bindings_p 原样。
    assert ledger.effective_p("sid-b", 2, bindings_p=1.0) == pytest.approx(1.0)
    assert ledger.last_p("sid-b", 2) is None


def test_ledger_corrupt_and_partial_lines_skipped(tmp_path):
    """损坏/半行(崩溃写到一半)安静跳过,不炸加载(§7.4 尽力而为)。"""
    path = tmp_path / "plasticity.ledger"
    ledger = persistence.PlasticityLedger(path)
    ledger.append(
        "sid-c", 1, born_at=1000.0, p=0.8, day="2026-01-01", reason="settle_day"
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"sid": "sid-c", "gen": 1, "p": 0.\n')  # 半行(未闭合 JSON),独立一行
    ledger.append(
        "sid-c", 1, born_at=1000.0, p=0.6, day="2026-01-02", reason="settle_day"
    )
    assert ledger.last_p("sid-c", 1) == pytest.approx(0.6)


# =====================================================================
# 崩溃分叉:bindings.json 半写 + ledger 仍权威
# =====================================================================


def test_crash_fork_bindings_json_stale_ledger_authoritative(tmp_path):
    """崩溃分叉:bindings.json 落后(半写/未刷),ledger 追加写已落盘 → 加载取更老。

    模拟:BindingStore 内存 P 已降到 0.6 但 save() 前进程崩溃(json 仍是旧值
    1.0);同拍 ledger.append 先于 save 发生且已 fsync,ledger 权威。
    """
    bindings_path = tmp_path / "bindings.json"
    ledger_path = tmp_path / "plasticity.ledger"

    store = BindingStore(bindings_path)
    store.hatch("sid-crash", "测试", now_ts=1000.0, day_key="2026-01-01")
    b = store.get("sid-crash")
    persistence.stamp_new_life(b, 1)
    store.save()  # 落盘 P=1.0、incarnation=1(崩溃前的旧真身)

    ledger = persistence.PlasticityLedger(ledger_path)
    # 崩溃前一拍:P 已算出 0.6 并 append 成功,但 bindings.json 还没来得及 save。
    ledger.append(
        "sid-crash", 1, born_at=1000.0, p=0.6, day="2026-01-02", reason="settle_day"
    )

    # "重启"重新加载 bindings.json(仍是崩溃前的 1.0)+ ledger 合并。
    reloaded = BindingStore(bindings_path)
    rb = reloaded.get("sid-crash")
    assert rb is not None
    json_p = float(rb.get("p", 1.0))
    assert json_p == pytest.approx(1.0)  # 确认 json 侧确实落后(崩溃分叉已发生)
    gen = persistence.incarnation_of(rb)
    eff = ledger.effective_p("sid-crash", gen, json_p)
    assert eff == pytest.approx(0.6)  # 分叉只更老,ledger 权威
    reloaded.lower_p("sid-crash", eff)
    assert reloaded.get("sid-crash")["p"] == pytest.approx(0.6)


# =====================================================================
# 同秒重生:世代键用 incarnation 计数器,不用 int(born_at)(major⑤/R3)
# =====================================================================


def test_same_second_reborn_generation_key_no_collision(tmp_path):
    """同秒重生(born_at 差<1s)仍是全新世代,不与前世合并(major⑤ 核心用例)。"""
    bindings_path = tmp_path / "bindings.json"
    ledger_path = tmp_path / "plasticity.ledger"
    store = BindingStore(bindings_path)
    ledger = persistence.PlasticityLedger(ledger_path)

    t0 = 1720000000.100000
    prev = None
    gen1 = persistence.next_incarnation(prev)
    assert gen1 == 1
    b1 = store.hatch("sid-reborn", "初代", now_ts=t0, day_key="2026-01-01")
    persistence.stamp_new_life(b1, gen1)
    ledger.append(
        "sid-reborn", gen1, born_at=t0, p=1.0, day="2026-01-01", reason="hatch"
    )
    # 前世老去到接近静止。
    ledger.append(
        "sid-reborn", gen1, born_at=t0, p=0.02, day="2026-06-01", reason="settle_day"
    )
    store.lower_p("sid-reborn", 0.02)
    store.seal("sid-reborn", "farewell")
    store.save()

    # 同一秒内(int(t0) == int(t1),差 <1s)重新孵化——旧世代键算法会碰撞。
    t1 = t0 + 0.4
    assert int(t0) == int(t1)  # 前提:确实同秒,旧 int(born_at) 键会撞
    prev_record = store.get("sid-reborn")  # 已封存的前世记录
    gen2 = persistence.next_incarnation(prev_record)
    assert gen2 == 2  # 单调转世计数器,与时钟精度无关

    b2 = store.hatch("sid-reborn", "新生", now_ts=t1, day_key="2026-01-01")
    persistence.stamp_new_life(b2, gen2)
    ledger.append(
        "sid-reborn", gen2, born_at=t1, p=1.0, day="2026-01-01", reason="hatch"
    )
    store.save()

    reloaded = BindingStore(bindings_path)
    rb = reloaded.get("sid-reborn")
    json_p = float(rb.get("p", 1.0))
    assert json_p == pytest.approx(1.0)  # 新生命 record 本身就是 1.0
    gen_of_new = persistence.incarnation_of(rb)
    assert gen_of_new == 2
    eff = ledger.effective_p("sid-reborn", gen_of_new, json_p)
    # 关键断言:新生命的有效 P 仍是 1.0——没有被前世 gen=1 的 0.02 拉低合并。
    assert eff == pytest.approx(1.0)
    # 而前世世代仍留档、可考古,不受影响。
    assert ledger.last_p("sid-reborn", 1) == pytest.approx(0.02)


def test_incarnation_of_missing_field_defaults_to_first_gen():
    """旧记录/未落位 incarnation 字段 → 保守视作第 1 世(不炸)。"""
    assert persistence.incarnation_of(None) == 1
    assert persistence.incarnation_of({}) == 1
    assert persistence.incarnation_of({"incarnation": 0}) == 1  # 非法值兜底
    assert persistence.incarnation_of({"incarnation": 3}) == 3


# =====================================================================
# 进程锁:OS 级排他文件锁,真互斥、无 TOCTOU、自愈(R1,并发竞态修复)
# =====================================================================
#
# 旧版 pidfile + _pid_alive/_process_start_time/_holder_is_pid_reuse 这套
# "读 pid 判活"启发式已整体退休(见 persistence.py 模块注释的设计变更记录)。
# 互斥判定现在 100% 由 OS 排他锁(Windows msvcrt.locking / POSIX
# fcntl.flock)的成败决定,不再有可 monkeypatch 的"判活"函数可打——下面这批
# 单测直接在**同一测试进程内用第二个原始文件描述符抢占 OS 锁**来模拟"另一
# 存活进程持有锁",这比旧版 mock _pid_alive 更贴近真实机制(锁的成败是内核
# 裁决的,不是靠读一段可以被随意 monkeypatch 的 Python 逻辑)。真·多进程并发
# 与 kill 后自愈见 test_process_lock_concurrency_mcp.py(要求:真 subprocess,
# 不允许 mock)。


def test_process_lock_fresh_acquire_succeeds(tmp_path):
    """全新 data_dir、无锁文件 → 首次 acquire 直接成功,诊断 pid 落本进程。"""
    lock = persistence.ProcessLock(tmp_path)
    lock.acquire()
    assert (tmp_path / "yelos.lock").exists()
    assert lock._read_holder() == os.getpid()
    lock.release()
    # 刻意不删锁文件(见 release 文档串:避免 delete-while-locked TOCTOU),
    # 但互斥性不再依赖文件是否存在——下一个 acquire 仍应顺利拿到锁。
    assert (tmp_path / "yelos.lock").exists()
    lock2 = persistence.ProcessLock(tmp_path)
    lock2.acquire()
    lock2.release()


def test_process_lock_rejected_when_os_lock_already_held(tmp_path):
    """锁文件上的 OS 排他锁已被(模拟的)另一持有者占住 → acquire 抛
    ProcessLockError,错误信息带诊断 pid 与 data_dir。

    用同进程内独立打开的第二个文件描述符直接抢占 OS 锁,模拟"另一存活
    进程持有该锁"——这是真实机制的直接产物,不依赖任何可 monkeypatch 的
    判活函数(旧版依赖 _pid_alive,新版无此类函数可打)。
    """
    lock_path = tmp_path / "yelos.lock"
    holder_pid_marker = 999999
    fake_holder_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        persistence._lock_fd_exclusive_nonblocking(fake_holder_fd)
        payload = json.dumps(
            {"pid": holder_pid_marker, "started_at": time.time()}
        ).encode("utf-8")
        os.lseek(fake_holder_fd, persistence._LOCK_MARKER_SIZE, os.SEEK_SET)
        os.write(fake_holder_fd, payload)
        os.fsync(fake_holder_fd)

        lock = persistence.ProcessLock(tmp_path)
        with pytest.raises(persistence.ProcessLockError) as excinfo:
            lock.acquire()
        assert f"pid={holder_pid_marker}" in str(excinfo.value)
        assert str(tmp_path) in str(excinfo.value)
        assert not lock._held
    finally:
        persistence._unlock_fd(fake_holder_fd)
        os.close(fake_holder_fd)


def test_process_lock_takeover_after_release_no_error(tmp_path):
    """持有者释放(正常 release,含"进程退出即释放"的语义等价物)后,
    第二个 ProcessLock 可平静接管,不报错、诊断 pid 更新为接管者。"""
    lock1 = persistence.ProcessLock(tmp_path)
    lock1.acquire()
    lock1.release()

    lock2 = persistence.ProcessLock(tmp_path)
    lock2.acquire()  # 不应抛
    assert lock2._read_holder() == os.getpid()
    lock2.release()


def test_process_lock_self_reacquire_is_idempotent(tmp_path):
    """同一 ProcessLock 实例重复 acquire 是幂等 no-op,不会去跟自己抢锁。"""
    lock = persistence.ProcessLock(tmp_path)
    lock.acquire()
    lock.acquire()  # 重复调用:不应抛、不应产生第二把锁
    lock.release()
    # 释放一次即可(即便重复 acquire 过);随后可被别的实例接管。
    lock2 = persistence.ProcessLock(tmp_path)
    lock2.acquire()
    lock2.release()


def test_process_lock_release_without_acquire_is_noop(tmp_path):
    """从未 acquire 过就 release → 安静 no-op,不炸。"""
    lock = persistence.ProcessLock(tmp_path)
    lock.release()  # 不应抛


def test_process_lock_context_manager_releases_on_exit(tmp_path):
    """``with ProcessLock(...) as lock`` 退出即释放,之后可被别的实例接管。"""
    with persistence.ProcessLock(tmp_path) as lock:
        assert lock._held
        assert lock._read_holder() == os.getpid()
    lock2 = persistence.ProcessLock(tmp_path)
    lock2.acquire()
    lock2.release()


def test_resolve_data_dir_and_engine_data_dir(tmp_path, monkeypatch):
    """data_dir 解析优先级与引擎 data_dir 默认独立子目录(§6.1/§7.3)。"""
    monkeypatch.delenv("YELOS_DATA_DIR", raising=False)
    explicit = str(tmp_path / "explicit")
    resolved = persistence.resolve_data_dir(explicit)
    assert resolved == (tmp_path / "explicit").resolve() or resolved.exists()
    engine_dir = persistence.resolve_engine_data_dir(resolved, None)
    assert engine_dir == (resolved / "engine")
    assert engine_dir.exists()
    shared = str(tmp_path / "shared-engine")
    engine_dir2 = persistence.resolve_engine_data_dir(resolved, shared)
    assert engine_dir2.exists()
    assert str(engine_dir2).rstrip("\\/").endswith("shared-engine")


# =====================================================================
# swallowed_total 生命周期累计(blocker②)——经真实 arbitrate + rollover 流
# =====================================================================


def _make_manager(tmp_path) -> SessionManager:
    cfg = YelosConfig(data_dir=str(tmp_path))
    bridge = EngineBridge(llm_fn=None)  # 未 ensure() → 全程安静降级,无需真引擎
    mgr = SessionManager(cfg, bridge)
    mgr.load()
    return mgr


def _withdraw_surface(pressure: float) -> dict:
    return {
        "decision": {"action": "withdraw"},
        "state": {"boundary": {"pressure": pressure}},
        "dynamics": {"relational_time": {"phase": "active"}},
    }


def test_swallowed_total_accumulates_lifecycle_not_just_daily(tmp_path):
    """SWALLOW 每次 +1 生命周期累加器;daily.swallowed 日翻转清零但
    swallowed_total 跨日累计不丢(蓝图 §3.2 步4 / blocker②)。"""

    async def _run():
        mgr = _make_manager(tmp_path)
        sid = "sid-swallow"
        await mgr.bind(sid, "小忍", mode="companion")
        # 强制高压 withdraw → SWALLOW(P≥0.5 时阈值 0.75)。
        mgr._surface_cache[sid] = _withdraw_surface(0.9)

        r1 = await mgr.arbitrate(sid, "我不想说了。")
        assert r1["verdict"] == "SWALLOW"
        assert r1["final_text"] == ""
        record = mgr._store.get(sid)
        assert record["swallowed_total"] == 1
        assert record["daily"]["swallowed"] == 1

        # 越过不应期,同日再触发一次 SWALLOW。
        record["daily"]["last_intervention_ts"] = 0.0
        mgr._surface_cache[sid] = _withdraw_surface(0.9)
        r2 = await mgr.arbitrate(sid, "算了，没什么。")
        assert r2["verdict"] == "SWALLOW"
        record = mgr._store.get(sid)
        assert record["swallowed_total"] == 2
        assert record["daily"]["swallowed"] == 2

        # 手动触发跨日 rollover:daily.swallowed 应清零,swallowed_total 不受影响。
        mgr._do_rollover(sid, "2099-01-01")
        record = mgr._store.get(sid)
        assert record["daily"]["swallowed"] == 0
        assert record["swallowed_total"] == 2  # 生命周期累加器跨日不清零

        # 新的一天再咽一次:累加器继续累计,不是"只算末日"。
        record["daily"]["last_intervention_ts"] = 0.0
        mgr._surface_cache[sid] = _withdraw_surface(0.9)
        r3 = await mgr.arbitrate(sid, "还是不说了。")
        assert r3["verdict"] == "SWALLOW"
        record = mgr._store.get(sid)
        assert record["swallowed_total"] == 3
        assert record["daily"]["swallowed"] == 1  # 当日只有这一次

    asyncio.run(_run())


def test_swallowed_total_feeds_anthology_not_daily_only(tmp_path):
    """assemble_anthology 的"被咽回句数"读 swallowed_total,不是 daily.swallowed
    (否则末日以外的咽回全部低报,blocker②)。"""
    from yelos.core.finitude import assemble_anthology

    record = {
        "name": "小忍",
        "born_day": "2026-01-01",
        "p": 0.5,
        "swallowed_total": 7,
        "daily": {"swallowed": 1},  # 只有末日这一次
        "epoch_history": [],
        "utterances": [],
        "dreams": [],
        "milestones": [],
    }
    data, md = assemble_anthology(record, "2026-01-10")
    assert data["被咽回句数"] == 7
    assert "共 7 句没能说出口" in md


def test_swallowed_total_survives_rebind_reset_but_reborn_starts_fresh(tmp_path):
    """farewell 封存后重新 affect_bind 是新的存在:新 record 的 swallowed_total
    从 0 起算,不继承前世咽回数(与 P 不继承同源纪律)。"""

    async def _run():
        mgr = _make_manager(tmp_path)
        sid = "sid-swallow-reborn"
        await mgr.bind(sid, "小忍", mode="companion")
        mgr._surface_cache[sid] = _withdraw_surface(0.9)
        await mgr.arbitrate(sid, "闭嘴好了。")
        record = mgr._store.get(sid)
        assert record["swallowed_total"] == 1
        gen1 = record["incarnation"]

        # 送别(两段式:先拿 token,再携 token 真正 seal)。
        first = await mgr.farewell(sid, export=False)
        token = first["pending_confirm"]["token"]
        second = await mgr.farewell(sid, export=False, confirm_token=token)
        assert second["sealed"] is True

        # 重新孵化(新的存在)。
        await mgr.bind(sid, "新生", mode="companion")
        reborn = mgr._store.get(sid)
        assert reborn["incarnation"] == gen1 + 1
        assert reborn["swallowed_total"] == 0  # 不继承前世咽回数

    asyncio.run(_run())
