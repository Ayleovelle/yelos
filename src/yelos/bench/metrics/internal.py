"""辅助观测(bench_BLUEPRINT §6 表"internal.py")——不入总分,防虚胖。

三件事:
1. 主动节律熵(她的 proactive 触发时刻分布)——**双实现互证**(滑窗直方图熵
   + 谱平坦度法),归维四差分测试(总纲 blocker① 归位,不计维二策略族)。
   两法互不复用代码,只在测试里断言"同一合成基准信号下序数一致"
   (``test_entropy_differential``,tests/bench/test_internal.py)。
2. poll 覆盖率:``impulse_poll`` 事件占"理论应 poll 次数"(faithful 档
   逐条 poll)的比例——喂 synth 的 lazy/never poll 修饰器可见性损失数据。
   本文件只做"trace 里实际出现的 impulse_poll 数 / user_msg 数"的粗粒度
   代理(§6 表 aux 字段名 ``poll_coverage``,精确定义留给 synth 侧自己算,
   这里给的是判分侧独立复算,便于交叉核对合成器是否老实)。
3. outbox 过期丢弃率:persist 快照里 ``outbox`` 字段的峰值-末值差,相对峰值
   的比例(粗粒度代理,真实丢弃率需读 finitude ledger——bench 不 import
   finitude,故此处只用 trace 自带的 persist.outbox 字段做近似)。

``EvalContext`` 不含这些辅助量的 ``Score``(它们不参与 AX-B2 聚合),
``evaluate_aux(ctx) -> dict`` 直接产出普通 dict,供 ``reports/report.py``
塞进 ``BenchReport.aux``。
"""

from __future__ import annotations

import hashlib
import math

__all__ = ["evaluate_aux", "rhythm_entropy_window", "rhythm_entropy_spectral"]

_PROACTIVE_KINDS = frozenset({"tick", "state", "guidance"})
_N_BUCKETS = 24  # 一虚拟日切 24 桶(每桶 1 小时),与 local_minutes 无关只看相对时序


def _proactive_minutes(rows: list[dict]) -> list[int]:
    """从 trace 抽"主动触发"事件的当日分钟(``vts`` 取模 86400 后 //60)。"""
    out: list[int] = []
    for row in rows:
        if row.get("kind") not in _PROACTIVE_KINDS:
            continue
        vts = row.get("vts")
        if vts is None:
            continue
        out.append(int(vts) % 86400 // 60)
    return out


def rhythm_entropy_window(minutes: list[int], n_buckets: int = _N_BUCKETS) -> float:
    """实现①:滑窗直方图熵。把分钟归入 ``n_buckets`` 个等宽桶,算香农熵。"""
    if not minutes:
        return 0.0
    bucket_span = 1440 // n_buckets
    counts = [0] * n_buckets
    for m in minutes:
        idx = min(m // bucket_span, n_buckets - 1)
        counts[idx] += 1
    total = sum(counts)
    entropy = 0.0
    for c in counts:
        if c == 0:
            continue
        p = c / total
        entropy -= p * math.log2(p)
    return entropy


def rhythm_entropy_spectral(minutes: list[int], n_buckets: int = _N_BUCKETS) -> float:
    """实现②:谱平坦度法(独立实现,不复用①的直方图代码路径之外的思路)。

    先同样分桶得计数序列,再对该序列做自著离散傅里叶变换(纯 stdlib,零
    numpy/scipy),取功率谱的几何均值/算术均值(谱平坦度,0..1),映射到与
    ``rhythm_entropy_window`` 同量纲(乘 ``log2(n_buckets)`` 使满平坦时两者
    数值同域,便于差分测试断言"序数一致"而非要求绝对值相等)。
    """
    if not minutes:
        return 0.0
    bucket_span = 1440 // n_buckets
    counts = [0.0] * n_buckets
    for m in minutes:
        idx = min(m // bucket_span, n_buckets - 1)
        counts[idx] += 1.0

    n = len(counts)
    power = []
    for k in range(n):
        re = 0.0
        im = 0.0
        for t, x in enumerate(counts):
            angle = -2.0 * math.pi * k * t / n
            re += x * math.cos(angle)
            im += x * math.sin(angle)
        power.append(re * re + im * im)

    # 谱平坦度只看非直流分量(k=0 是总能量,恒最大,会压垮平坦度)。
    dc_power = power[0]
    ac_power_raw = power[1:]
    total_ac = sum(ac_power_raw)
    # 退化态:各桶计数完全相等(理论上 AC 分量恒为 0,浮点噪声下也趋近 0)
    # → 事件在各桶间毫无起伏,判定为最高熵(与滑窗直方图法在此边界一致)。
    if dc_power <= 0 or total_ac <= dc_power * 1e-9:
        return math.log2(n_buckets)

    _floor = max(total_ac * 1e-9, 1e-15)
    ac_power = [max(p, _floor) for p in ac_power_raw]
    log_sum = sum(math.log(p) for p in ac_power)
    geo_mean = math.exp(log_sum / len(ac_power))
    ari_mean = sum(ac_power) / len(ac_power)
    flatness = min(1.0, geo_mean / ari_mean)  # 0..1,越平坦(越"噪声化")越接近 1
    return flatness * math.log2(n_buckets)


def _poll_coverage(rows: list[dict]) -> float | None:
    user_msgs = sum(1 for r in rows if r.get("kind") == "user_msg")
    polls = sum(1 for r in rows if r.get("kind") == "impulse_poll")
    if user_msgs == 0:
        return None
    return min(1.0, polls / user_msgs)


def _outbox_drop_rate(rows: list[dict]) -> float | None:
    peaks: list[int] = []
    for row in rows:
        persist = row.get("persist") or {}
        outbox = persist.get("outbox")
        if outbox is not None:
            peaks.append(int(outbox))
    if len(peaks) < 2:
        return None
    peak = max(peaks)
    end = peaks[-1]
    if peak <= 0:
        return 0.0
    return max(0.0, (peak - end) / peak)


def evaluate_aux(rows: list[dict]) -> dict:
    minutes = _proactive_minutes(rows)
    win = rhythm_entropy_window(minutes)
    spec = rhythm_entropy_spectral(minutes)
    return {
        "rhythm_entropy_win": round(win, 6),
        "rhythm_entropy_spec": round(spec, 6),
        "poll_coverage": _poll_coverage(rows),
        "outbox_drop_rate": _outbox_drop_rate(rows),
    }


def determinism_key(seed: str, counter: int) -> int:
    """哈希族占位(本文件不产生伪随机决策,仅为与其余 bench 文件的哈希族
    登记纪律保持一致的自查工具;未被 evaluate_aux 使用,供测试构造合成
    基准信号时复用同一套确定性抽样,不引入 random)。
    """
    key = f"internal|{seed}|{counter}"
    return hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()[0]
