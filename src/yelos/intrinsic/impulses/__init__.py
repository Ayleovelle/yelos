"""impulses/ 在整个架构中的位置:三套主动策略族 + 公共硬闸链(维二正身)。

策略只提议(propose),闸链裁决(apply_gates)——`want=True` 仍须过公共硬闸
全链([AX-6]),任何策略配置都不可绕过。三套策略:`ThresholdPolicy`(v0.1
包装兼容默认)/ `FieldCrossingPolicy`(场轨迹越阈曲面 + 迟滞)/
`PoissonBudgetPolicy`(非齐次泊松强度=场范数,哈希 thinning)。
"""

from __future__ import annotations
