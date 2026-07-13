# impl_anchors.md —— theory-trace 检查器消费的机器可读锚点表(yaml front-matter)。
# 在整个架构中的位置:axioms.md/theorems.md 的索引化投影,供 CI 扫双向引用
# (公理/定理 -> 代码内注释 `AX:Ax.y` / `T1`/`T2`/`T3`,代码 -> 本表),
# 不重复定义事实——本表条目须与 axioms.md/theorems.md 的 ID 逐一对应。
anchors:
  - id: A1
    statement: "介入强度全序:σ(PASS)=0 ⊑ σ(TRIM)=1 ⊑ σ(REPLACE)=2 ⊑ σ(SWALLOW)=3"
    file: src/yelos/arbiter/lattice.py
    symbol: SIGMA
    tests: [tests/arbiter/test_lattice.py]
  - id: A2
    statement: "前置守卫只产 PASS;后置滤波只降不升(σ(f(v))<=σ(v))"
    file: src/yelos/arbiter/pipeline.py
    symbol: ArbiterPipeline.run
    tests: [tests/arbiter/test_pipeline.py, tests/arbiter/test_guards_differential.py]
  - id: A3
    statement: "不应期:相继介入时距 >= min_gap(推论 C1:长程介入率 <= 1/min_gap,不称定理)"
    file: src/yelos/arbiter/guards/min_gap.py
    symbol: guard_min_gap
    tests: [tests/arbiter/test_policy_invariants.py]
  - id: A4
    statement: "主权覆盖:P0 ⇒ PASS,结构性铁域(MUTABLE_SET 与 P0 语义交集为空)"
    file: src/yelos/arbiter/guards/p0_sovereignty.py
    symbol: guard_p0_sovereignty
    tests: [tests/arbiter/test_policy_invariants.py, tests/arbiter/test_adversarial.py]
  - id: A5.1
    statement: "信赖域:θ_k 有硬界 [lo_k,hi_k],更新后投影回 Box"
    file: src/yelos/arbiter/hysteresis/params.py
    symbol: Theta.project
    tests: [tests/arbiter/test_hysteresis.py]
  - id: A5.2
    statement: "步长有界:单事件 |Δθ_k| <= η0·step_k"
    file: src/yelos/arbiter/hysteresis/updater.py
    symbol: apply_update
    tests: [tests/arbiter/test_hysteresis.py]
  - id: A5.3
    statement: "学习率-有限性耦合:η(P)=η0·P"
    file: src/yelos/arbiter/hysteresis/updater.py
    symbol: learning_rate
    tests: [tests/arbiter/test_hysteresis.py]
  - id: A5.4
    statement: "共识门:fast·slow>0 时移动,否则 Δθ=0"
    file: src/yelos/arbiter/hysteresis/ema.py
    symbol: EmaState.consensus
    tests: [tests/arbiter/test_hysteresis.py]
  - id: A5.5
    statement: "确定性可回放:θ 轨迹是事件序列的确定性函数"
    file: src/yelos/arbiter/hysteresis/updater.py
    symbol: apply_update
    tests: [tests/arbiter/test_hysteresis.py]
  - id: A6
    statement: "记账守恒:计数器唯一递增点,单调不减"
    file: src/yelos/arbiter/accounting/ledger.py
    symbol: ArbiterLedger.record_verdict
    tests: [tests/arbiter/test_accounting.py]
  - id: T1
    statement: "学不坏主权:θ 恒在 Box + 铁域不变 + 生涯漂移有界"
    file: src/yelos/arbiter/hysteresis/updater.py
    symbol: apply_update
    tests: [tests/arbiter/test_hysteresis.py::test_theta_stays_in_box_random_ten_thousand_steps]
  - id: T2
    statement: "凝固:P 单调不增 ⇒ 漂移上界单调不增;P=0 精确凝固"
    file: src/yelos/arbiter/hysteresis/updater.py
    symbol: learning_rate
    tests: [tests/arbiter/test_hysteresis.py::test_p_zero_theta_frozen_forever]
  - id: T3
    statement: "个体史分化:存在 h1≠h2 与 x* 使 verdict 分化(本模块深度正身)"
    file: src/yelos/arbiter/hysteresis
    symbol: "(整层:signals+ema+updater+store)"
    tests: [tests/arbiter/test_hysteresis.py::test_individual_history_differentiation_golden]
  - id: T4
    statement: "介入率非平凡上界(候选,未立,不得引用为依据)"
    file: theory/arbitration/theorems.md
    symbol: "T4 登记(未立)"
    tests: []
