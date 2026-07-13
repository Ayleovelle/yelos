"""data_dir 解析 + 进程锁 + PlasticityLedger（KV 双写的 MCP 替代）。

蓝图 §1.2 第三持久化面 / §6.1 进程安全 / §7.4 裁决 D8 / §3.6.2 单调性。

这是 server 层模块，只依赖标准库；**不** import `core.binding`——binding
record 以 plain dict 交互，保持解耦、可单测。core/binding.py 逐字搬运（零改动，
§2），本模块承接其原 KV 双写职责的 MCP 语境改造：

- 数据目录解析：`config.data_dir` > ``$YELOS_DATA_DIR`` > ``~/.yelos``（§6.1/§7.3）。
- 进程锁 ``yelos.lock``：一个 data_dir 一个进程；OS 级排他文件锁（真互斥、
  无 TOCTOU、进程退出内核自动释放即自愈，§6.1/R1）。
- ``PlasticityLedger``（jsonl 追加写）：每次 P 下降追加一行；加载
  ``P = min(bindings.json P, 同世代 ledger 末条 P)``；世代键
  ``p:{sid}:{incarnation}``——``incarnation`` 是每 sid 的**单调转世计数器**
  （非 ``int(born_at)``，红队 major⑤/R3），杜绝同秒重生碰撞。
- 生命周期字段落位：新孵化 record 顶层 ``incarnation`` + ``swallowed_total``
  （blocker② 存储侧，与 ``utterances`` 同级随 bindings.json 持久化）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# --- data_dir 解析（§6.1 / §7.3）---------------------------------------


def resolve_data_dir(config_dir: str | None = None) -> Path:
    """解析 Yelos 自己的 data_dir 并确保存在。

    优先级：显式 ``config_dir`` > ``$YELOS_DATA_DIR`` > ``~/.yelos``。
    展开 ``~`` 与环境变量；目录不存在则递归创建。
    """
    raw = config_dir or os.environ.get("YELOS_DATA_DIR") or "~/.yelos"
    path = Path(os.path.expandvars(os.path.expanduser(raw)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_engine_data_dir(data_dir: Path, engine_data_dir: str | None = None) -> Path:
    """解析引擎 data_dir（§7.3）。

    空 = 引擎数据放 ``{data_dir}/engine``（独立，默认）；填 = 共心路径
    （opt-in，用户自保单进程）。返回的目录被确保存在。
    """
    raw = engine_data_dir if engine_data_dir else ""
    if not raw:
        path = Path(data_dir) / "engine"
    else:
        path = Path(os.path.expandvars(os.path.expanduser(raw)))
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- 进程锁（§6.1 / R1）------------------------------------------------
#
# 设计变更记录（并发竞态修复，见 tests/test_process_lock_concurrency_mcp.py）：
#
# 旧实现是 pidfile 型：``os.open(O_CREAT|O_EXCL)`` 建文件 + 事后读 pid 判
# ``_pid_alive``/``_holder_is_pid_reuse``。这在两个进程近乎同时启动时存在
# TOCTOU 竞态——进程 A ``O_EXCL`` 建了文件（拿到空/未写入的文件），在 A 调用
# ``_write`` 落盘 pid 之前，进程 B 也 ``O_EXCL`` 建文件失败→读 holder→读到
# ``None``（A 还没写完）→ 判"无人真持有" → 走接管分支 ``O_TRUNC`` 覆盖。
# 两个进程都"以为"自己接管成功，红线破：同一 data_dir 出现两个存活持锁者。
#
# 新实现改用 **OS 级排他文件锁**（Windows ``msvcrt.locking``／POSIX
# ``fcntl.flock``，均为标准库、不引入新依赖）作为唯一互斥判据：进程存活期
# 全程持有一个打开的文件描述符并在其上加排他锁；拿不到排他锁即等价于"已被
# 另一存活进程持有"。互斥判定的原子性由内核保证——不存在"建了文件但还没
# 写入内容"的可观测中间态，天然没有上述 TOCTOU 窗口。进程退出（含
# crash / 强杀 / kill -9）时内核自动释放该文件锁，天然自愈，不需要
# ``_pid_alive`` / 创建时间 / PID 复用启发式这套走读 pid 判活的旁路逻辑
# （旧版这套逻辑连同其竞态一并整体退休）。
#
# 锁文件仍以 JSON 落一份 ``{"pid": ..., "started_at": ...}``——但这只是
# **诊断旁路**（供 acquire 失败时的错误信息报出"是谁持有的"），互斥判定
# 100% 以 OS 排他锁的成败为准，不再读这份 JSON 做决策。


class ProcessLockError(RuntimeError):
    """data_dir 已被另一个存活的 Yelos 进程持有。"""


class _LockContendedError(Exception):
    """内部信号：本次 OS 排他锁请求未拿到（已被占用），非用户可见异常。"""


#: 文件开头保留给 OS 锁的"纯锁标记"字节区间大小——诊断 JSON 内容一律从
#: 偏移 ``_LOCK_MARKER_SIZE`` 之后写起，绝不与被锁字节区间重叠。原因见
#: ``_lock_fd_exclusive_nonblocking`` 文档串：Windows 的字节区间锁是
#: **强制锁**，其他句柄（哪怕同进程的另一个句柄）读被锁字节区间会直接拿到
#: ``PermissionError``；把诊断内容错开放在锁标记之后，才能让"锁被占用时
#: 报出持锁 pid"这条诊断路径在 Windows 上也读得到。
_LOCK_MARKER_SIZE = 1


def _lock_fd_exclusive_nonblocking(fd: int) -> None:
    """在 ``fd`` 的锁标记区间上加非阻塞排他锁；已被占用 → ``_LockContendedError``。

    Windows：``msvcrt.locking`` 锁的是从当前文件指针起的一段字节区间，
    且是**强制锁**（mandatory——其他句柄哪怕只是读该区间也会被 OS 拒绝，
    不限于加锁尝试），要求该区间在文件当前大小内，故先确保文件至少有
    ``_LOCK_MARKER_SIZE`` 字节再定位到 0 锁 ``[0, _LOCK_MARKER_SIZE)``。
    POSIX：``fcntl.flock`` 是**劝告锁**（advisory——只影响其他 ``flock``
    调用，不阻止普通 read/write），直接锁整个打开的文件（不分字节区间），
    与文件大小无关，字节区间划分对 POSIX 无意义但不影响正确性。两平台
    语义一致：非阻塞、锁不到就立即失败，从不阻塞等待（阻塞等待会让第二
    进程在拿不到锁时卡住，而不是按红线干净 ``ProcessLockError`` 退出）。
    """
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        if os.fstat(fd).st_size < _LOCK_MARKER_SIZE:
            os.write(fd, b"\0" * _LOCK_MARKER_SIZE)
            os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, _LOCK_MARKER_SIZE)
        except OSError as exc:
            raise _LockContendedError from exc
    else:
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise _LockContendedError from exc


def _unlock_fd(fd: int) -> None:
    """尽力而为释放 ``fd`` 上的排他锁（失败静默——反正随后就 close）。"""
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, _LOCK_MARKER_SIZE)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass


class ProcessLock:
    """``data_dir/yelos.lock``：OS 级排他文件锁，真互斥、无 TOCTOU、自愈。

    互斥判定 100% 由 OS 排他锁的持有/释放决定：

    - 锁已被另一存活进程持有 → OS 拒绝加锁 → ``acquire`` 抛
      ``ProcessLockError``（消息尽力而为附上诊断 pid，来自锁文件里的旁路
      JSON，仅供人读，不参与判定）。
    - 持有者进程已死（crash / 强杀 / kill -9）→ 内核在进程退出时自动释放
      该文件锁 → 下一个 ``acquire`` 直接拿到锁，不需要任何"判活"逻辑。
    - PID 号被 OS 回收给无关新进程 → 与上一条同理：旧持锁进程的文件锁早
      已随其退出被内核释放，新进程即便复用了同一 PID 号也不持有任何锁 →
      接管方仍能干净拿到锁。

    进程存活期需要**全程持有**返回的文件描述符（存于 ``self._fd``）——
    OS 锁只在描述符打开期间生效，关闭描述符（含进程退出）即释放。
    """

    def __init__(self, data_dir: Path, filename: str = "yelos.lock") -> None:
        self._path = Path(data_dir) / filename
        self._held = False
        self._fd: int | None = None

    @property
    def path(self) -> Path:
        return self._path

    def _read_holder(self) -> int | None:
        """尽力而为读锁文件里的诊断 pid（仅供报错文案，不参与互斥判定）。

        显式跳过开头 ``_LOCK_MARKER_SIZE`` 字节（锁标记区间，Windows 上
        持锁期间该区间对其他句柄不可读，见 ``_lock_fd_exclusive_nonblocking``）
        只读之后的诊断 JSON——这样即便当前正是"被另一存活进程持有"的
        contention 场景，也读得到诊断 pid，而不是每次都读失败退化成
        ``pid=None``。任何读取失败（文件不存在/无权限/内容损坏）一律
        安静返回 ``None``——诊断信息是尽力而为，绝不能因为读失败就影响
        ``acquire`` 已经由 OS 锁决出的互斥结论。
        """
        try:
            fd = os.open(self._path, os.O_RDONLY)
        except OSError:
            return None
        try:
            os.lseek(fd, _LOCK_MARKER_SIZE, os.SEEK_SET)
            chunks = []
            while True:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                chunks.append(chunk)
        except OSError:
            return None
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            payload = json.loads(b"".join(chunks).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        pid = payload.get("pid")
        return int(pid) if isinstance(pid, int) and not isinstance(pid, bool) else None

    def acquire(self) -> None:
        """取锁；已被另一存活进程持有则抛 ``ProcessLockError``。

        对同一个 ``ProcessLock`` 实例重复调用是幂等的（已持有则直接返回，
        不会去跟自己抢锁）。互斥判定见类文档。
        """
        if self._held:
            return  # 同一实例重复 acquire：幂等 no-op，不与自己抢锁。

        fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            _lock_fd_exclusive_nonblocking(fd)
        except _LockContendedError:
            holder = self._read_holder()
            os.close(fd)
            raise ProcessLockError(
                f"another Yelos process (pid={holder}) owns this "
                f"data_dir: {self._path.parent}"
            ) from None

        # 拿到 OS 排他锁——安全地重写诊断旁路信息（此刻绝无并发写者）。
        # 内容从 _LOCK_MARKER_SIZE 偏移之后写起，绝不覆盖被锁的标记字节。
        payload = json.dumps(
            {"pid": os.getpid(), "started_at": _now()}, ensure_ascii=False
        ).encode("utf-8")
        os.lseek(fd, _LOCK_MARKER_SIZE, os.SEEK_SET)
        os.write(fd, payload)
        os.fsync(fd)
        try:
            os.ftruncate(fd, _LOCK_MARKER_SIZE + len(payload))
        except OSError:
            pass  # 尽力而为；诊断信息缺失不影响互斥语义

        self._fd = fd
        self._held = True

    def release(self) -> None:
        """释放锁：解锁 + 关闭描述符（尽力而为）。

        刻意**不删锁文件**：unlink 与 unlock 之间存在窗口——若在此窗口内
        另一进程已重新 open+lock 同一路径，此时 unlink 会摘掉目录项，
        之后第三个进程对同路径 ``O_CREAT`` 会拿到**新** inode 并再次成功
        加锁，与仍持有旧 inode 锁的第二进程并存 → 互斥被击穿（经典的
        delete-while-locked TOCTOU）。锁文件常驻磁盘无害：互斥性完全由
        OS 锁的持有/释放决定，从不依赖文件是否存在；下次 acquire 直接
        对既存文件重新 open+lock 即可。
        """
        if not self._held or self._fd is None:
            return
        _unlock_fd(self._fd)
        try:
            os.close(self._fd)
        except OSError:
            pass
        self._fd = None
        self._held = False

    def __enter__(self) -> ProcessLock:
        self.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()


# --- 世代 / 生命周期字段（§3.6.2 / §7.4 / blocker②）-------------------

_DEFAULT_INCARNATION = 1


def incarnation_of(record: dict | None) -> int:
    """读 record 顶层世代号；缺失（旧记录/未落位）保守视作第 1 世。"""
    if not isinstance(record, dict):
        return _DEFAULT_INCARNATION
    value = record.get("incarnation")
    if isinstance(value, int) and value >= 1:
        return value
    return _DEFAULT_INCARNATION


def next_incarnation(prev_record: dict | None) -> int:
    """新孵化应用的世代号。

    首次孵化（无前世记录）= 1；seal 后对同 sid 重新孵化 = 前世世代 + 1
    （红队 major⑤：单调转世计数器，与时钟精度无关，杜绝同秒重生碰撞）。
    调用时机：在 ``BindingStore.hatch`` **替换旧记录之前**读前世 record。
    """
    if prev_record is None:
        return _DEFAULT_INCARNATION
    return incarnation_of(prev_record) + 1


def stamp_new_life(record: dict, incarnation: int) -> None:
    """在新孵化 record 顶层落位世代号与生命周期累加器（存储侧）。

    - ``incarnation``：世代键 ``p:{sid}:{incarnation}`` 的世代分量。
    - ``swallowed_total``：被咽回句数的**生命周期累加器**（blocker②），与
      ``utterances`` 同级、随 bindings.json 持久化；SWALLOW 路径每次 +1 由
      arbitrate/session 层负责（本函数只保证初值落位、round-trip 不丢）。
    """
    record["incarnation"] = int(incarnation)
    record["swallowed_total"] = 0


# --- 深化模块 binding 块增量（INTEGRATION_SPEC §2.1，加性/缺块默认/世代随孵化重置）--

# 顶层一生一语默认（primal A7）。utter_provenance 环缓冲上限（primal §2.1）。
DEFAULT_LANG = "zh"
UTTER_PROVENANCE_CAP = 200


def ensure_binding_blocks(record: dict, *, lang: str = DEFAULT_LANG) -> dict:
    """确保 record 上存在深化波的**简单增量块**；缺块补默认，绝不 raise。

    只落 stdlib 可表达、不牵扯任一模块内核的加性块（INTEGRATION_SPEC §2.1）：

    - ``lang``: str（顶层，一生一语 A7）——缺则取传入 lang（默认 "zh"）。
    - ``utter_provenance``: list（环缓冲 cap 200）——缺则空。
    - ``guidance_profile``: str（顶层，可选）——**不预置**（缺 → guidance 默认
      "chat"，见 §2.1 缺省列）；只在已存在时做类型纠正，避免污染默认 bindings.json。
    - ``daily.moments_counts``: dict（intrinsic W2）——缺则空 dict。

    复杂的模块自有块（``arbiter_hyst`` / ``shadow`` schema2 / ``intrinsic_field``
    / ``aging`` / ``epoch2``）不在此预置：它们由各 owner 模块在**读取点**惰性缺块
    补默认（arbiter ``hysteresis.store.load`` / shadow ``ensure_shadow_block`` 等），
    只在对应 opt-in 路径真正触达时才落盘，从而 opt-in 关时默认 bindings.json
    逐字节不变（保 1191 绿）。世代重置由 ``stamp_new_life`` 于新孵化重建 record
    达成——新生 record 天然拿到本函数的默认，不继承前世块。

    幂等：已存在且类型正确的块原样保留。返回同一 record（允许链式）。
    """
    if not isinstance(record, dict):
        return record
    if not isinstance(record.get("lang"), str) or not record.get("lang"):
        record["lang"] = str(lang) if lang else DEFAULT_LANG
    if not isinstance(record.get("utter_provenance"), list):
        record["utter_provenance"] = []
    elif len(record["utter_provenance"]) > UTTER_PROVENANCE_CAP:
        # 加载既有超长环缓冲时收敛到 cap（尾部保留，最新在后）。
        record["utter_provenance"] = record["utter_provenance"][-UTTER_PROVENANCE_CAP:]
    daily = record.get("daily")
    if isinstance(daily, dict) and not isinstance(daily.get("moments_counts"), dict):
        daily["moments_counts"] = {}
    return record


# --- PlasticityLedger（§7.4 裁决 D8）----------------------------------


@dataclass
class LedgerEntry:
    """一条 ledger 行（jsonl）。``gen`` = incarnation，非 int(born_at)。"""

    sid: str
    gen: int
    born_at: float
    p: float
    ts: float
    day: str
    reason: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "sid": self.sid,
                "gen": self.gen,
                "born_at": self.born_at,
                "p": self.p,
                "ts": self.ts,
                "day": self.day,
                "reason": self.reason,
            },
            ensure_ascii=False,
        )


def _now() -> float:
    import time

    return time.time()


class PlasticityLedger:
    """``plasticity.ledger``（jsonl，追加写）——KV 双写的 MCP 替代。

    每次 P 下降追加一行；加载对每 sid 取**同 incarnation** 末条 P，与
    bindings.json 的 P 取 min（分叉只更老、不返老还童，R3）。世代不匹配的
    行（前世 incarnation）被忽略 → 重生不继承旧 P。追加写单行 flush+fsync，
    比 bindings.json 全量原子写更抗崩（崩在 bindings.json 半写时 ledger 仍权威）。
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    # -- 追加写（原子单行）----------------------------------------------

    def append(
        self,
        sid: str,
        gen: int,
        born_at: float,
        p: float,
        *,
        day: str,
        reason: str,
        ts: float | None = None,
    ) -> None:
        """追加一行 P 记录。写失败静默（引擎缺席安静降级的同款纪律）。"""
        entry = LedgerEntry(
            sid=sid,
            gen=int(gen),
            born_at=float(born_at),
            p=float(p),
            ts=_now() if ts is None else float(ts),
            day=str(day),
            reason=str(reason),
        )
        line = entry.to_json() + "\n"
        try:
            fd = os.open(self._path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
            try:
                os.write(fd, line.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass  # 尽力而为；bindings.json 仍是主权威快照

    # -- 读 --------------------------------------------------------------

    def _iter_entries(self):
        """逐行 yield 合法条目；空文件/损坏行/缺文件安静跳过。"""
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            sid = obj.get("sid")
            gen = obj.get("gen")
            p = obj.get("p")
            if not isinstance(sid, str):
                continue
            if not isinstance(gen, int):
                continue
            if not isinstance(p, (int, float)) or isinstance(p, bool):
                continue
            yield obj

    def last_p(self, sid: str, gen: int) -> float | None:
        """同 sid **同世代** 的末条 P；无匹配返回 None。"""
        result: float | None = None
        for obj in self._iter_entries():
            if obj["sid"] == sid and int(obj["gen"]) == int(gen):
                result = float(obj["p"])
        return result

    def effective_p(self, sid: str, gen: int, bindings_p: float) -> float:
        """加载合并：``min(bindings_p, 同世代 ledger 末条 P)``。

        无同世代 ledger 记录（新孵化 / 前世世代不匹配）→ 用 bindings_p
        原样（重生不继承旧 P）。
        """
        last = self.last_p(sid, gen)
        if last is None:
            return float(bindings_p)
        return min(float(bindings_p), last)

    def all_rows(self) -> list[dict]:
        """全量合法 ledger 行的只读列表(WebUI 年轮/名册适配层用)。

        与 ``_iter_entries()`` 同一份防御式解析(损坏行/缺文件安静跳过),只是
        物化成 list 供调用方多次遍历(适配层不持有本对象、不重新解析文件)。
        """
        return list(self._iter_entries())
