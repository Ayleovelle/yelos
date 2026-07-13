"""进程级生命周期回归(修复一/修复二 + 裁决三,冒烟 §5.1/§5.2/§2)。

锁死项:
1. **第二进程启动即锁拒 + 干净非零退出**(修复二 / §5.2):同 data_dir 起第二个
   ``python -m yelos``,进程锁在任何 transport / 事件循环之前同步获取 → 第二进程
   在启动瞬间被 ``ProcessLockError`` 拒绝,打一行 stderr(含持锁 pid 与 data_dir)
   后 ``sys.exit(1)``,30s 内退出、非零码、不 hang。stdio 与 streamable-http 两传输
   都在"起服之前"被拒(证明拒绝时机是进程启动、而非首个客户端连接)。
2. **HTTP 同进程双客户端会话共享一个 SessionManager**(修复一 / §5.1):一个
   streamable-http 进程,两个独立 MCP 客户端会话(两个 mcp-session-id)都能
   initialize + list_tools + 工具调用;且会话 A 建的绑定,会话 B 用同一 session_id
   能读到 → 证明两会话共享同一进程级 manager(而非各自重跑 lifespan 各建一个)。
3. **封存 sid 的隐式 submit 是静默只读直通**(裁决三 / D15 澄清 / §3.6.3):
   封存后隐式 ``affect_submit`` 不复活、不新生 incarnation,原地返回 sealed 快照。

真起服用例(1 的 http 分支、2)用随机高位端口 + 隔离临时 data_dir + 收尾杀进程,
全程 127.0.0.1 本地回环,绝不触碰 ~/.yelos。
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

_SRC = str(Path(__file__).resolve().parent.parent / "src")


# =====================================================================
# 公共 helpers
# =====================================================================


def _child_env(data_dir: Path, transport: str, port: int | None = None) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = _SRC
    env["YELOS_DATA_DIR"] = str(data_dir)
    env["YELOS_TRANSPORT"] = transport
    if port is not None:
        env["YELOS_HTTP_HOST"] = "127.0.0.1"
        env["YELOS_HTTP_PORT"] = str(port)
    return env


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _port_listening(port: int, timeout: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


# =====================================================================
# 1. 第二进程启动即锁拒 + 干净非零退出(修复二,两传输)
# =====================================================================


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
def test_second_process_rejected_at_startup_and_exits_clean(tmp_path, transport):
    """本测试进程先真·持有 data_dir 的 OS 级进程锁(等价"一个存活的 yelos
    正占着"),再起第二个 ``python -m yelos`` 指同一 data_dir → 应在起服前
    即被锁拒、非零退出、30s 内自退,stderr 含持锁 pid 与 data_dir。

    互斥判定现在 100% 由 OS 排他锁裁决(见 persistence.ProcessLock 设计变更
    记录),不再是"预置一份 pid JSON + mock 判活"就能让子进程走到拒绝分支——
    必须真的在这里持有那把锁,子进程的 ``ProcessLock.acquire()`` 才会真的
    在内核层面抢锁失败。这本身就是对红线("同一 data_dir 任一时刻只允许一
    个存活进程持锁")的直接验证。
    """
    from yelos.persistence import ProcessLock

    data_dir = tmp_path / "locked"
    data_dir.mkdir()
    holder_pid = os.getpid()  # 本测试进程,真实持有 OS 锁
    holder_lock = ProcessLock(data_dir)
    holder_lock.acquire()

    try:
        port = _free_port() if transport == "streamable-http" else None
        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "yelos"],
            env=_child_env(data_dir, transport, port),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(tmp_path),
        )
        try:
            try:
                out, _ = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                _kill(proc)
                pytest.fail(
                    f"[{transport}] 第二进程 30s 内未自退(疑似 hang,§5.2 回归)"
                )
        finally:
            _kill(proc)

        assert proc.returncode is not None and proc.returncode != 0, (
            f"[{transport}] 期望非零退出码,实得 {proc.returncode}; 输出:\n{out}"
        )
        assert "another Yelos process" in out, (
            f"[{transport}] stderr 缺持锁诊断:\n{out}"
        )
        assert f"pid={holder_pid}" in out, f"[{transport}] stderr 未点名持锁 pid:\n{out}"
        assert str(data_dir) in out or "locked" in out, (
            f"[{transport}] stderr 未含 data_dir:\n{out}"
        )
        # streamable-http:被拒发生在起服之前 → 端口从未进入监听。
        if transport == "streamable-http":
            assert not _port_listening(port), (
                "被锁拒的 http 进程不应曾监听端口(证明拒绝时机=启动而非客户端连接)"
            )
    finally:
        holder_lock.release()


# =====================================================================
# 2. HTTP 同进程双客户端会话共享一个 SessionManager(修复一)
# =====================================================================


def test_http_two_client_sessions_share_one_process(tmp_path):
    """一个 streamable-http 进程,两个独立客户端会话都跑通核心链;且 A 建的绑定
    B 用同一 session_id 读得到 → 证明共享同一进程级 manager(§5.1 修复)。"""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    data_dir = tmp_path / "http"
    data_dir.mkdir()
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "yelos"],
        env=_child_env(data_dir, "streamable-http", port),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(tmp_path),
    )

    async def scenario() -> None:
        # 等监听(引擎懒启动 + uvicorn 起服预算)。
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            if _port_listening(port):
                break
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                raise AssertionError(f"server 提前退出 rc={proc.returncode}:\n{out}")
            await asyncio.sleep(0.3)
        else:
            raise AssertionError("server 30s 内未监听")

        url = f"http://127.0.0.1:{port}/mcp"
        shared_sid = "shared-across-mcp-sessions"

        # 会话 A:两个客户端会话(不同 mcp-session-id)全程并存,证明同进程多会话。
        async with streamablehttp_client(url) as (ra, wa, _a):
            async with ClientSession(ra, wa) as sess_a:
                await sess_a.initialize()
                tools_a = await sess_a.list_tools()
                assert len(tools_a.tools) == 11  # +affect_recall(接线波第 11 席)

                async with streamablehttp_client(url) as (rb, wb, _b):
                    async with ClientSession(rb, wb) as sess_b:
                        await sess_b.initialize()
                        tools_b = await sess_b.list_tools()
                        assert len(tools_b.tools) == 11

                        async def call(sess, tool, args):
                            res = await sess.call_tool(tool, args)
                            assert not res.isError, f"{tool} error: {res.content}"
                            if res.structuredContent is not None:
                                return res.structuredContent
                            for blk in res.content:
                                if getattr(blk, "type", None) == "text":
                                    return json.loads(blk.text)
                            raise AssertionError(f"{tool}: no content")

                        # A 绑 companion + submit。
                        rb1 = await call(
                            sess_a,
                            "affect_bind",
                            {
                                "session_id": shared_sid,
                                "name": "双面",
                                "mode": "companion",
                            },
                        )
                        assert rb1.get("mode") == "companion"
                        rs1 = await call(
                            sess_a,
                            "affect_submit",
                            {
                                "session_id": shared_sid,
                                "text": "两个会话一颗心。",
                                "speaker": "user",
                            },
                        )
                        assert "pad_label" in rs1

                        # B(另一 mcp-session-id)读同一 session_id → 看得到 A 的绑定
                        #   = 共享同一进程级 SessionManager/BindingStore。
                        rst = await call(
                            sess_b, "affect_state", {"session_id": shared_sid}
                        )
                        assert rst.get("mode") == "companion", (
                            f"会话 B 未见会话 A 的绑定,manager 未共享:{rst}"
                        )
                        assert rst.get("bound") is True

                        # B 也能独立跑只读工具。
                        rg = await call(
                            sess_b, "affect_guidance", {"session_id": shared_sid}
                        )
                        assert "tone" in rg

    try:
        asyncio.run(scenario())
    finally:
        _kill(proc)
        # 收尾:确认没触碰 ~/.yelos(本用例全程隔离 data_dir)。
        assert (data_dir / "bindings.json").exists()


# =====================================================================
# 3. 封存 sid 的隐式 submit 是静默只读直通(裁决三 / D15 澄清 / §3.6.3)
# =====================================================================


def test_sealed_sid_implicit_submit_is_silent_noop(tmp_path):
    """封存后隐式 affect_submit 不复活、不新生 incarnation,原地返回 sealed 快照。"""
    from yelos.config import YelosConfig
    from yelos.engine_bridge import EngineBridge
    from yelos.session import SessionManager

    async def scenario() -> None:
        cfg = YelosConfig(data_dir=str(tmp_path), heartbeat_enabled=False)
        mgr = SessionManager(cfg, EngineBridge(llm_fn=None))
        mgr.load()
        sid = "sealed-then-submit"

        await mgr.bind(sid, "终章", mode="companion")
        await mgr.submit(sid, "先活一轮。", speaker="user")
        inc_before = mgr._store.get(sid).get("incarnation")

        # 两段式封存。
        first = await mgr.farewell(sid, export=True, confirm_token=None)
        token = first["pending_confirm"]["token"]
        sealed = await mgr.farewell(sid, export=True, confirm_token=token)
        assert sealed["sealed"] is True
        assert sid not in mgr._store.bound_umos()  # 不再活跃

        # 隐式 submit on sealed sid:静默只读直通。
        out = await mgr.submit(sid, "封存之后还想说话。", speaker="user")
        assert out.get("sealed") is True, f"应返回 sealed 快照:{out}"
        assert out.get("bound") is False, f"封存后 bound 应为 False:{out}"

        rec = mgr._store.get(sid)
        assert rec.get("sealed") is True
        # 关键:未创建新 incarnation(未惰性新生)、仍不进 bound_umos。
        assert rec.get("incarnation") == inc_before, "封存后隐式 submit 误新生了世代"
        assert sid not in mgr._store.bound_umos()

        # 对照:显式 affect_bind 才是"新的存在"(新世代 incarnation+1)。
        rebind = await mgr.bind(sid, "新生", mode="companion")
        assert rebind["created"] is True
        assert mgr._store.get(sid).get("incarnation") == inc_before + 1
        assert sid in mgr._store.bound_umos()

    asyncio.run(scenario())
