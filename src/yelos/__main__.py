"""``python -m yelos`` 入口(蓝图 §7.1 / §6.1)——读配置、抢进程锁、起 server。

传输(§1.1 双传输):``stdio``(默认,Claude Desktop / 本地 agent)与
``streamable-http``(远程 / 守护 daemon)。console_scripts 装 ``yelos`` 命令
指向本模块 ``main``。心跳只在 server 存活期跑——stdio 下 = 客户端会话存活期,
http daemon 下 = 进程存活期(§3.4 诚实边界)。

**进程级初始化(修复,冒烟 §5.1/§5.2)**:进程锁 + SessionManager + 心跳 spawn 从
FastMCP lifespan 上移到这里。理由见 ``server.build_manager`` 文档串。关键次序是
"**先锁后建**":进程锁在任何 transport / 事件循环 / stdio server 之前**同步**获取,
于是——① 第二进程在启动瞬间(而非首个客户端连接时)就被锁拒;② 被锁拒时进程里
还没 spawn 任何任务、也没进 stdio server 等 stdin,``ProcessLockError`` 捕获后
打一行 stderr + ``sys.exit(1)`` 即干净非零退出,不会像旧版那样卡死在 anyio
TaskGroup 收尾(§5.2)。
"""

from __future__ import annotations

import logging
import sys

import anyio

from .config import YelosConfig, load
from .persistence import ProcessLock, ProcessLockError, resolve_data_dir
from .server import build_manager, build_server

logger = logging.getLogger("yelos.main")


async def _serve(mcp, manager, config: YelosConfig) -> None:
    """进程级 serve(单进程一次):懒启动引擎 + 起心跳 + 跑传输 + 优雅关闭。

    进程锁已在 ``main`` 里同步持有;本协程只负责事件循环内的异步装配与传输运行。
    HTTP 下 uvicorn 长驻,期间所有客户端会话共享 ``manager`` 这一个单例
    (per-sid ``asyncio.Lock`` 保证并发正确性,§7.2)。
    """
    # 已有未封存绑定 → 懒启动引擎(缺席安静降级,不 raise)。
    try:
        await manager.ensure_engine()
    except Exception:
        logger.warning("YELOS 引擎懒启动异常,降级为无引擎运行", exc_info=True)
    # 后台心跳(可关;关则 impulse 内联 tick,D6)。
    if config.heartbeat_enabled:
        manager._spawn(manager.heartbeat_loop())  # noqa: SLF001 编排层自持任务集
    logger.info("YELOS 已激活(transport=%s)", config.transport)
    try:
        # transport 已在 config 校验为 stdio | streamable-http(§7.3)。直接调
        # FastMCP 的 async 传输入口,把进程级 setup/teardown 包在外层(而非
        # mcp.run() 内部各自 anyio.run),这样心跳/引擎/锁都是"每进程一次"。
        if config.transport == "streamable-http":
            await mcp.run_streamable_http_async()
        else:
            await mcp.run_stdio_async()
    finally:
        await manager.close()
        logger.info("YELOS 已终止")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load()

    # 先锁后建(§6.1 / 修复二):进程锁同步获取,先于任何 transport / 事件循环 /
    # stdio server。第二进程在此瞬间即被拒;被拒时无已 spawn 任务、无 stdin 等待
    # 可挂起 → 干净非零退出。
    data_dir = resolve_data_dir(config.data_dir)
    lock = ProcessLock(data_dir)
    try:
        lock.acquire()
    except ProcessLockError as exc:
        # exc 消息已含持锁者 pid 与 data_dir(persistence.ProcessLock.acquire)。
        print(f"yelos: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        manager = build_manager(config)
        mcp = build_server(config, manager)
        anyio.run(_serve, mcp, manager, config)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
