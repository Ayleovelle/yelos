"""进程锁真·并发实测(R1 红线专项回归)。

红线(唯一成败标准,mock 不算数):同一 data_dir 任一时刻只允许一个存活
yelos 进程持锁,第二个必须 ``acquire`` 失败(``ProcessLockError``)退出。

背景(实测证据驱动的修复):旧版 ``ProcessLock`` 是 pidfile 型
(``os.open(O_CREAT|O_EXCL)`` 建文件 + 事后读 pid 判 ``_pid_alive``)。在两个
进程近乎同时启动时存在 TOCTOU 竞态——``O_EXCL`` 建了文件但尚未写入 pid 的
窗口里,另一进程读到空 holder(``None``)→ 判"无人持有" → 走接管分支
``O_TRUNC`` 覆盖 → 两个进程都"以为"自己接管成功。Claude Desktop 实测复现:
前后 1 秒起了两个 yelos(同 data_dir),锁文件只记一个 pid,但两个进程都照常
绑定/写了 bindings.json——红线破。

新版改用 OS 级排他文件锁(Windows ``msvcrt.locking`` / POSIX
``fcntl.flock``)作为互斥判据,详见 ``persistence.py`` 模块内的设计变更记录。
本文件不信任任何单进程内 mock——**必须**起真实 ``python`` 子进程验证:

1. 两个真子进程近乎同时对同一 data_dir ``acquire()``:恰好一个成功、一个
   抛 ``ProcessLockError``(多轮抓竞态,单轮通过不算数——TOCTOU 类竞态往往
   只在特定时序窗口触发)。
2. 持锁子进程被强杀(``kill()``,等价 crash / kill -9,不给它机会 release)
   后,下一个进程仍能干净接管——自愈,不留永久僵尸锁。
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parent.parent / "src")

# 子进程执行体:acquire 成功打印 "ACQUIRED" 后按需 sleep(给并发窗口/给主测试
# 机会去 kill 它);acquire 失败以 exit code 2 + "REJECTED:" 消息退出;任何其他
# 未预期异常以 exit code 3 退出,方便和"预期内的 ProcessLockError"区分开。
_HOLDER_SNIPPET = """
import sys
sys.path.insert(0, {src!r})
import time
from pathlib import Path
from yelos.persistence import ProcessLock, ProcessLockError

lock = ProcessLock(Path({data_dir!r}))
try:
    lock.acquire()
except ProcessLockError as exc:
    print("REJECTED:" + str(exc), flush=True)
    sys.exit(2)
except Exception as exc:  # noqa: BLE001 - 子进程诊断,故意宽捕获
    print("UNEXPECTED:" + repr(exc), flush=True)
    sys.exit(3)

print("ACQUIRED", flush=True)
time.sleep({sleep})
"""


def _spawn_holder(data_dir: Path, sleep: float) -> subprocess.Popen:
    code = _HOLDER_SNIPPET.format(src=_SRC, data_dir=str(data_dir), sleep=sleep)
    return subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


# =====================================================================
# 1. 真·并发:两个真子进程几乎同时抢同一把锁,多轮抓竞态
# =====================================================================


@pytest.mark.parametrize("round_idx", range(8))
def test_two_real_subprocesses_exactly_one_acquires(tmp_path, round_idx):
    """两个真 python 子进程同时对同一 data_dir acquire():
    恰好一个成功持锁(ACQUIRED / rc=0)、另一个抛 ProcessLockError(rc=2)。

    参数化 8 轮而非单轮循环:每轮独立的 pytest 用例,任何一轮失败都会单独
    报出是第几轮出的竞态,不会被平均掉;数据目录按轮次隔离,轮间互不干扰。
    """
    data_dir = tmp_path / f"round-{round_idx}"
    data_dir.mkdir()

    # 两个子进程几乎同时起——sleep 短暂持锁窗口,足够两边都已进入
    # acquire() 竞争,又不会拖慢测试。
    p1 = _spawn_holder(data_dir, sleep=1.0)
    p2 = _spawn_holder(data_dir, sleep=1.0)

    out1, _ = p1.communicate(timeout=20)
    out2, _ = p2.communicate(timeout=20)
    rc1, rc2 = p1.returncode, p2.returncode

    acquired = [rc == 0 for rc in (rc1, rc2)]
    rejected = [rc == 2 for rc in (rc1, rc2)]

    assert sum(acquired) == 1, (
        f"round {round_idx}: 红线破——期望恰好 1 个进程持锁成功,"
        f"实得 rc1={rc1} rc2={rc2}\nout1={out1!r}\nout2={out2!r}"
    )
    assert sum(rejected) == 1, (
        f"round {round_idx}: 期望恰好 1 个进程被 ProcessLockError 拒绝,"
        f"实得 rc1={rc1} rc2={rc2}\nout1={out1!r}\nout2={out2!r}"
    )
    # 被拒的一方消息里应带诊断(即便读不到 pid 也不该是 UNEXPECTED 异常)。
    rejected_out = out1 if rc1 == 2 else out2
    assert "REJECTED:another Yelos process" in rejected_out


# =====================================================================
# 2. 自愈:持锁进程被强杀后,下一个进程能干净接管(不留永久僵尸锁)
# =====================================================================


def test_takeover_after_holder_is_killed(tmp_path):
    """持锁子进程被 ``kill()``(等价 crash / kill -9,没机会 release)后,
    OS 应自动释放其文件锁;下一个 acquire 应立刻成功,不需要任何"判活"
    启发式、也不会永久卡死。"""
    data_dir = tmp_path / "heal"
    data_dir.mkdir()

    holder = _spawn_holder(data_dir, sleep=30.0)  # 长 sleep:确保还没自然退出就被杀
    try:
        deadline = time.monotonic() + 10.0
        line = ""
        while time.monotonic() < deadline:
            line = holder.stdout.readline()
            if "ACQUIRED" in line:
                break
        else:
            holder.kill()
            pytest.fail(f"持锁子进程 10s 内未拿到锁,最后一行输出:{line!r}")

        # 强杀,不给 release() 任何执行机会——模拟 crash / kill -9。
        holder.kill()
        holder.wait(timeout=10)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10)

    # 下一个进程应能立刻干净接管。
    successor = _spawn_holder(data_dir, sleep=0.1)
    out, _ = successor.communicate(timeout=20)
    assert successor.returncode == 0, (
        f"强杀持锁进程后,接管方应能成功 acquire,实得 rc={successor.returncode}\n{out}"
    )
    assert "ACQUIRED" in out


def test_takeover_after_holder_is_killed_multiple_rounds(tmp_path):
    """多轮"持锁 → 强杀 → 接管"连跑,确认自愈不是偶然一次侥幸命中。"""
    for round_idx in range(3):
        data_dir = tmp_path / f"heal-round-{round_idx}"
        data_dir.mkdir()

        holder = _spawn_holder(data_dir, sleep=30.0)
        deadline = time.monotonic() + 10.0
        line = ""
        while time.monotonic() < deadline:
            line = holder.stdout.readline()
            if "ACQUIRED" in line:
                break
        else:
            holder.kill()
            pytest.fail(
                f"round {round_idx}: 持锁子进程 10s 内未拿到锁,最后输出:{line!r}"
            )

        holder.kill()
        holder.wait(timeout=10)

        successor = _spawn_holder(data_dir, sleep=0.1)
        out, _ = successor.communicate(timeout=20)
        assert successor.returncode == 0, (
            f"round {round_idx}: 强杀后接管失败,rc={successor.returncode}\n{out}"
        )
