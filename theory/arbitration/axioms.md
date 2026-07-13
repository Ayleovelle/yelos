# arbitration 公理表(theory/arbitration/axioms.md)

> 在整个架构中的位置:arbiter 模块理论层(维一)。本文件是
> `arbiter_BLUEPRINT.md §1.1` 的机器可核对版本——每条公理带 ID、代码锚点
> (代码内注释 `AX:Ax.y`)、测试锚点;theory-trace 检查器扫双向引用(有公理
> 无锚点 / 有锚点无公理均判失败)。不与 `impl_anchors.md` 重复维护事实,
> 后者是本文件的 yaml 索引化投影。
>
> 红队裁决(总纲 §7 第 3 条)在本文件内全文生效:**深度叙事挂
> hysteresis,不挂"介入率有界定理";1/min_gap 上界只称推论;不自封
> "全平台形式化最高"**——A1 不以"格"自夸形式化,A3 的长程上界如实标
> "推论 C1",不称定理。

## 状态空间

verdict 全序:`V = {PASS, TRIM, REPLACE, SWALLOW}`,强度函数
`σ: V -> {0,1,2,3}`(`lattice.py::SIGMA`)。仲裁管线:
`ArbiterPipeline = 前置守卫链 ∘ 策略核 ∘ 后置降格滤波链`。
hysteresis 状态 `θ = (δ_sw, δ_rp, δ_ex, γ) ∈ Box ⊂ R^4`,由双 EMA
`(fast, slow)` 驱动的共识门更新(`hysteresis/updater.py`)。

## 公理表

| ID | 公理 | 代码锚点 | 测试锚点 |
|---|---|---|---|
| A1 | 介入强度全序:σ(PASS)=0 ⊑ σ(TRIM)=1 ⊑ σ(REPLACE)=2 ⊑ σ(SWALLOW)=3;σ 仅用于比较,不参与算术加权,不以"格"自夸形式化 | `arbiter/lattice.py::SIGMA` | `tests/arbiter/test_lattice.py::test_sigma_total_order` |
| A2 | 滤波器单调性:前置守卫 g 只能产 σ=0 的 PASS(组合根装配期 fail-fast 校验);后置滤波 f 满足 σ(f(v)) <= σ(v)(只降不升) | `arbiter/pipeline.py::ArbiterPipeline.run`、`arbiter/guards/base.py` | `tests/arbiter/test_pipeline.py::test_postfilter_downgrade_only_property`、`test_guard_only_pass` |
| A3 | 不应期时序:任意两次相继介入(σ>=1)的时距 >= min_gap。**推论 C1(如实标"推论",不称定理)**:长程介入率 <= 1/min_gap,是 A3 的平凡推论,不产生新可观测行为,不入深度账 | `arbiter/guards/min_gap.py` | `tests/arbiter/test_policy_invariants.py::test_refractory_all_policies_random_trajectory` |
| A4 | 主权覆盖:P0(未绑定/禁用/静默)⇒ PASS,先于守卫链其余各条、策略核、hysteresis、调制的一切;∀θ∈Box、∀policy、∀P0 输入,σ(pipeline(x))=0。铁域声明:hysteresis 可变异集 MUTABLE_SET 与 {P0 语义, min_gap, narrow_p, high_intensity 判据, 哈希键型, 白名单} 交集为空,是结构性保证(θ dataclass 字段集里根本没有这些字段),不是运行时检查 | `arbiter/guards/p0_sovereignty.py`、`arbiter/hysteresis/params.py::MUTABLE_SET` | `tests/arbiter/test_policy_invariants.py::test_p0_pass_all_policies_all_theta_box_vertices`、`test_adversarial.py::test_theta_box_vertices_no_sovereignty_violation` |
| A5.1 | 信赖域:每个可变异参数 θ_k 有硬界 [lo_k, hi_k](Box),每次更新后投影回 Box | `arbiter/hysteresis/params.py::Theta.project` | `tests/arbiter/test_hysteresis.py::test_theta_stays_in_box_random_ten_thousand_steps` |
| A5.2 | 步长有界:单事件更新 \|Δθ_k\| <= η0·step_k(step_k 为参数级步长上限常量) | `arbiter/hysteresis/updater.py::apply_update` | `tests/arbiter/test_hysteresis.py::test_single_step_delta_bounded_by_p_step` |
| A5.3 | 学习率-有限性耦合:η(P) = η0·P,单调不减于 P;P=0 ⇒ η=0 | `arbiter/hysteresis/updater.py::learning_rate` | `tests/arbiter/test_hysteresis.py::test_learning_rate_monotone_in_p` |
| A5.4 | 共识门:参数仅在快慢 EMA 同号(共识)时移动;非共识 ⇒ Δθ=0 | `arbiter/hysteresis/ema.py::EmaState.consensus`、`arbiter/hysteresis/updater.py::apply_update` | `tests/arbiter/test_hysteresis.py::test_non_consensus_zero_movement` |
| A5.5 | 确定性可回放:θ 轨迹是 outcome 事件序列的确定性函数;无 random、无时钟直读,时间入参化 | `arbiter/hysteresis/updater.py`(纯函数,零 IO)、`arbiter/hysteresis/__init__.py::settle_outcome/settle_silence` | `tests/arbiter/test_hysteresis.py::test_replay_twice_identical`、`test_prefix_replay_consistency` |
| A6 | 记账守恒:swallowed_total 生命周期单调不减;daily.high_intensity 仅由 pressure>=0.75 的 SWALLOW 递增;两计数器的递增点唯一(`accounting/ledger.py`),任何策略不得旁路 | `arbiter/accounting/ledger.py::ArbiterLedger.record_verdict` | `tests/arbiter/test_accounting.py::test_counters_monotone_over_simulated_binding`、`test_single_increment_point_ast_scan` |

## 诚实边界(记账纪律附注)

- A1 的 σ 值**仅用于比较**(A2 单调性判据 / DuelPolicy 取 min),不参与任何
  加权求和;不自称"格结构"的理论重量,只是一个全序标签。
- A3 的"长程介入率 <= 1/min_gap"是**推论 C1**,不是定理——它是 min_gap
  硬约束的直接算术推论,v0.1 早已保证,本波不产生新可观测行为,不计入
  hysteresis 的深度叙事。
- r(outcome 代理信号,`hysteresis/signals.py`)是**代理信号**,测的是
  "介入后你的回应形态",不是真实感受;可能错,所以步长小 + 共识门 + Box
  ——错也错不远,这条与 shadow 的"模拟不是读心"同宗,原样写入本文件
  存照(与 `hysteresis/signals.py` 模块 docstring 一致)。
