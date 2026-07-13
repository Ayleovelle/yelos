"""固化夹具生成器(intrinsic_BLUEPRINT §3.2):三条虚拟时钟 30 日事件轨迹。

`tests/intrinsic/fixtures/trajectory_{step,ramp,silence}.json` 是**确定性**
生成的产物(纯函数,零 random)——本脚本是它们的唯一权威生成源,重跑本
脚本应得到逐字节相同的文件(可重现,不是手工攒的死数据)。

三条轨迹(§3.2):
- `trajectory_step`(阶跃冲击日):每日固定 tick 处 contact/expression 从低
  瞬间跳到高位并保持全天——用于 O1/O2(Threshold 零时滞对照组)。
- `trajectory_ramp`(缓坡积累日):每日前半段线性爬升,后半段维持高位平台
  ——用于 O2(FieldCrossing 时滞 ≥1 拍)/O3(高场平台期弥散度对比)/O4。
- `trajectory_silence`(静默长日):全天 contact/expression 维持低位——O1
  的负对照(全程不触发,三策略在此日理应"同样安静",衬出前两条轨迹上
  的差异才是真差异而非噪声)。

每条轨迹:`N_DAYS` 天 × `TICKS_PER_DAY` 拍,每拍一个 `{day, tick, contact,
expression, pressure, quiet}` 记录(30 分钟/拍)。
"""

from __future__ import annotations

import json
from pathlib import Path

N_DAYS = 30
TICKS_PER_DAY = 48  # 30 分钟/拍
TICK_SECONDS = 1800


def _day_key(day_index: int) -> str:
    # 简化:不做真实日历换算,day_key 只需逐日唯一且可排序。
    return f"2026-{(day_index // 28) + 1:02d}-{(day_index % 28) + 1:02d}"


def _local_minutes(tick_in_day: int) -> int:
    return (tick_in_day * (1440 // TICKS_PER_DAY)) % 1440


def gen_step() -> list[dict]:
    """阶跃冲击日:contact/expression 与伴随的 concern 事件同拍瞬间跳变并保持。

    事件强度恒定(非渐进)驱动场随后续拍逐步积累(慢通道 longing 的 Λ 小,
    积累需要多拍)——Threshold 因读 Surface 瞬时值而零时滞触发,
    FieldCrossing 因读场累积历史而有正时滞,天然区分(O1/O2 的基础)。
    """
    jump_tick = 10
    out = []
    for d in range(N_DAYS):
        for t in range(TICKS_PER_DAY):
            high = t >= jump_tick
            out.append(
                {
                    "day": _day_key(d),
                    "tick": t,
                    "local_minutes": _local_minutes(t),
                    "contact": 0.7 if high else 0.1,
                    "expression": 0.55 if high else 0.1,
                    "pressure": 0.1,
                    "quiet": 0.1,
                    "events": [["concern", 0.5]] if high else [],
                }
            )
    return out


_RISE_END = 8
_PLATEAU_END = 14
_FALL_END = 22
_INTENSITY_SCALE = 0.35


def _ramp_frac(t: int) -> float:
    """分段线性:爬升(0..RISE_END)→ 平台(..PLATEAU_END)→ 回落(..FALL_END)→

    零(FALL_END..TICKS_PER_DAY,充分的纯衰减静默窗,供慢通道 longing 每日
    真正回落,否则跨日棘轮式抬升会让"下阈迟滞带"永不再命中,策略无法
    每日重新武装——调参记录见 tests/intrinsic/test_policy_distinguishability.py
    调参笔记)。
    """
    if t <= _RISE_END:
        return t / float(_RISE_END)
    if t <= _PLATEAU_END:
        return 1.0
    if t <= _FALL_END:
        return max(0.0, 1.0 - (t - _PLATEAU_END) / float(_FALL_END - _PLATEAU_END))
    return 0.0


def gen_ramp() -> list[dict]:
    """缓坡积累日:前段 Surface + concern 事件强度线性爬升 → 短平台 → 回落 →

    充分静默窗(供慢通道每日真正回落,次日重新武装)。平台/回落段给 O3
    (日内触发弥散度对比)提供足够长的"高场期"窗口。
    """
    out = []
    for d in range(N_DAYS):
        for t in range(TICKS_PER_DAY):
            frac = _ramp_frac(t)
            out.append(
                {
                    "day": _day_key(d),
                    "tick": t,
                    "local_minutes": _local_minutes(t),
                    "contact": 0.1 + 0.8 * frac,
                    "expression": 0.1 + 0.6 * frac,
                    "pressure": 0.1,
                    "quiet": 0.1,
                    "events": [["concern", _INTENSITY_SCALE * frac]]
                    if frac > 0
                    else [],
                }
            )
    return out


def gen_silence() -> list[dict]:
    """静默长日:全天低位、零事件——O1 的负对照(三策略理应同样安静)。"""
    out = []
    for d in range(N_DAYS):
        for t in range(TICKS_PER_DAY):
            out.append(
                {
                    "day": _day_key(d),
                    "tick": t,
                    "local_minutes": _local_minutes(t),
                    "contact": 0.1,
                    "expression": 0.1,
                    "pressure": 0.1,
                    "quiet": 0.6,
                    "events": [],
                }
            )
    return out


def write_all(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, gen_fn in (
        ("step", gen_step),
        ("ramp", gen_ramp),
        ("silence", gen_silence),
    ):
        path = root / f"trajectory_{name}.json"
        path.write_text(
            json.dumps(gen_fn(), ensure_ascii=False, indent=None), encoding="utf-8"
        )


if __name__ == "__main__":
    write_all(Path(__file__).parent)
