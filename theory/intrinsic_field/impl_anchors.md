---
# impl_anchors.md —— theory-trace CI 消费的机器可读锚点表(yaml front-matter)。
# 在整个架构中的位置:axioms.md/theorems.md 的索引化投影,供 CI 扫双向引用
# (公理 -> 代码注释 `# [AX-n]` / `# [TH-n]`,代码 -> 本表),不重复定义事实。
anchors:
  - id: AX-1
    statement: "有界性:φ 恒 ∈ [0,1]^4"
    file: src/yelos/intrinsic/field/state.py
    symbol: FieldState.clipped
    tests: [T-FLD-01]
  - id: AX-2
    statement: "自然衰减:无强迫无冲击时单调趋向 φ_eq"
    file: src/yelos/intrinsic/field/dynamics.py
    symbol: decay_term
    tests: [T-FLD-02]
  - id: AX-3
    statement: "昼夜强迫:1440min 周期分段余弦,确定性"
    file: src/yelos/intrinsic/circadian/forcing.py
    symbol: forcing
    tests: [T-CIR-01]
  - id: AX-4
    statement: "冲击有界:范数 ≤ I_max"
    file: src/yelos/intrinsic/field/impacts.py
    symbol: IMPACT_TABLE
    tests: [T-FLD-03]
  - id: AX-5
    statement: "输入借用界定:白名单字段,非仿射转录"
    file: src/yelos/intrinsic/field/impacts.py
    symbol: SURFACE_WHITELIST
    tests: [T-FLD-04]
  - id: AX-6
    statement: "闸门独立:公共硬闸链不可被策略绕过"
    file: src/yelos/intrinsic/impulses/gates.py
    symbol: GATE_CHAIN
    tests: [T-GAT-01]
  - id: AX-7
    statement: "确定性:零 random/time.time(),哈希族驱动"
    file: src/yelos/intrinsic/impulses/poisson_budget.py
    symbol: _thin
    tests: [T-DET-01]
  - id: AX-8
    statement: "时间入参化:经 Clock 协议喂入"
    file: src/yelos/intrinsic/scheduler/heartbeat.py
    symbol: step_field
    tests: [T-SCH-03]
  - id: TH-1
    statement: "无强迫收敛(压缩映射证明)"
    file: theory/intrinsic_field/theorems.md
    symbol: "TH-1 证明附文"
    tests: [T-FLD-02]
  - id: TH-2
    statement: "冲击响应有界(峰值/回落步数上界)"
    file: theory/intrinsic_field/theorems.md
    symbol: "TH-2 证明附文"
    tests: [T-FLD-03]
  - id: TH-3
    statement: "昼夜锁相(猜想,不得引用为依据)"
    file: src/yelos/intrinsic/circadian/phase_learn.py
    symbol: PhaseLearner
    tests: [T-CIR-02]
---

本文件正文留空:全部机器可核对内容在上方 front-matter。人类可读版见
`axioms.md` / `theorems.md`。
