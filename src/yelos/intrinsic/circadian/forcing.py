"""circadian/forcing.py 在整个架构中的位置:C(τ) 昼夜强迫曲线([AX-3])。

C(τ) 为 1440min 周期分段(此处用平滑余弦近似,"分段"体现在每通道各自
独立的相位/振幅,不是单一全局曲线的四份复制)余弦强迫;参数 =(基线相位
⊕ 学到的用户相位偏移,来自 circadian/phase_learn.py)。确定性:同 τ 同
相位偏移同值,零 random/time.time()(AX-7)。

quiet_hours 硬窗**不在此**——本曲线只是叠加的软强迫,硬窗的主权语义在
impulses/gates.py(intrinsic_BLUEPRINT §0.3 明文:硬窗永远最后裁决)。
"""

from __future__ import annotations

import math

# 本地定义(而非 `from ..field.state import Vec4`):circadian/ 依赖方向纪律
# (intrinsic_BLUEPRINT §2.1)是"field/circadian/moments → 仅 core 工具 +
# 标准库",circadian 不得反向耦合 field(哪怕只是借一个类型别名)。
Vec4 = tuple[float, float, float, float]

MINUTES_PER_DAY = 1440

# 每通道基线峰值相位(分钟,0..1439)与振幅(强迫项量级 << 衰减项,软调制)。
# 语义:drive 午后达峰(想找你说话的白天欲望);languor 深夜达峰(倦意/退避);
# longing 午夜前达峰(牵挂在夜里最浓);afterglow 傍晚达峰(交互后的余温窗)。
BASE_PHASE_MIN: Vec4 = (14 * 60, 23 * 60, 22 * 60, 19 * 60)
AMPLITUDE: Vec4 = (0.04, 0.03, 0.025, 0.015)


def forcing(
    local_minutes: int,
    phase_offset_min: float = 0.0,
    *,
    base_phase_min: Vec4 = BASE_PHASE_MIN,
    amplitude: Vec4 = AMPLITUDE,
) -> Vec4:
    """[AX-3] 昼夜强迫:C(τ),τ = local_minutes,phase_offset_min 为学到的偏移。

    每通道 `C_k(τ) = amplitude_k · cos(2π·(τ − (phase_k + offset)) / 1440)`。
    """
    tau = float(local_minutes) % MINUTES_PER_DAY
    out = []
    for phase_k, amp_k in zip(base_phase_min, amplitude):
        shifted_phase = (phase_k + phase_offset_min) % MINUTES_PER_DAY
        angle = 2.0 * math.pi * (tau - shifted_phase) / MINUTES_PER_DAY
        out.append(amp_k * math.cos(angle))
    return tuple(out)  # type: ignore[return-value]


__all__ = ["MINUTES_PER_DAY", "BASE_PHASE_MIN", "AMPLITUDE", "forcing"]
