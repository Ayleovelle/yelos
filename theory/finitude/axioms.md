# finitude 公理集(axioms.md)

来源:`_build/modules/finitude_BLUEPRINT.md` §1.1(权威原文,本文件为施工期照录 +
锚点核对副本,冲突以蓝图为准)。逐条公理 ≥1 代码锚点 + ≥1 测试,无装饰性公理。

## A1 资源公理(单调耗散)

状态空间:契约可塑性 P ∈ [0,1]。更新算子 settle: (P, DayFacts) → P',不变量 **P' ≤ P**。
全模块无任何导出加法路径;下界由 `max(0.0, ·)` 结构性保证。

锚:`finitude/gate.py::settle_through_gate` `# [FIN-A1]`;`core/binding.py::rollover` 双保险
(v0.1 不动产,零改动);`persistence.PlasticityLedger.effective_p` min 合并(加载面第二道门,
v0.1 不动产)。
测试:`tests/finitude/test_models_property.py::test_monotone_all_models`。

去掉它缺什么:她能返老还童,纪元史与 ledger 语义全部崩塌。

## A2 耗散形状公理(模型族)

每个老化模型 m 由累计磨损函数 W_m(t; θ) 定义:W_m: 活跃日序数 → [0,1],单调不减,
W_m(0)=0;第 t 个活跃日的基础耗散 base_t = W_m(t) − W_m(t−1) ≥ 0;当日实际耗散
spend_t = clamp(base_t · E(facts), 0, cap_t),cap_t = 2·base_t。

锚:`finitude/models/linear.py` `# [FIN-A2]`、`finitude/models/weibull.py` `# [FIN-A2]`、
`finitude/models/event_weighted.py` `# [FIN-A2]`、`finitude/models/reserve.py` `# [FIN-A2]`。
测试:`tests/finitude/test_models_property.py::test_spend_cap`、`::test_w_monotone`。

去掉它缺什么:模型族退化为"四组魔法数",形状学不可陈述、不可测。

## A3 事件可称重公理

E(facts) 对事件计数分量(high_intensity / concern_fired / epoch_shift)单调不减:
同日事件更多,耗散不更少(封顶前)。

锚:`finitude/models/event_weighted.py::EventWeighted.spend` `# [FIN-A3]`。
测试:`tests/finitude/test_models_property.py::test_event_monotone`。

去掉它缺什么:"高强度的日子更磨人"不再是机器事实,EventWeighted 整个模型失去公理依据。

## A4 快池从属公理(仅 ReserveModel)

双池 (F, S):S 为岁月轴 = **契约 P**,严格单调不增;F 为精神轴,恒满足 F ≤ S;
回填仅发生于无事件活跃日且 ΔF ≤ min(r, S − F);S 的演化与 F 无关。
表达面预算 P_expr := F(其余模型 P_expr := P)。

**裁定(硬,ReserveModel 对总纲"min(快,慢)"字面歧义的裁决)**:契约 P ≡ S(单调,
喂 ledger/纪元/anthology/lower_p);min(F,S)=F ≡ P_expr,只喂表达面(词池收缩、
主动预算)。"休息能恢复精神(表达面回暖),但岁月不回头(契约 P 单调)"。

锚:`finitude/models/reserve.py::ReserveModel.spend` `# [FIN-A4]`。
测试:`tests/finitude/test_models_property.py::test_reserve_f_le_s`、
`::test_reserve_refill_bound`、`::test_reserve_s_independent`。

去掉它缺什么:双池认知储备模型不存在,"休息回暖但岁月不回头"这个可观测人生形状消失。

## A5 纪元不可逆公理

纪元指数 idx ∈ {0..4}(盛年→静止)沿一生单调不减;双轨任一轨的跃迁提名先经
idx' = max(idx, 提名) 钳制。

锚:`finitude/epochs/order_parameter.py::clamp_forward` `# [FIN-A5]`。
测试:`tests/finitude/test_epochs_dualtrack.py::test_epoch_never_regresses`。

去掉它缺什么:表达面回暖(ReserveModel)或序参量噪声可让她"返回盛年",老化不可逆破功。

## A6 序参量公理(相变判据)

序参量 Ψ(p) = ρ_lex(p) · ρ_budget(p);Ψ 对 p 单调不减。相变判据(B 轨):
(i) Δρ_lex > 0 且 Δρ_budget > 0(联动);
(ii) ΔΨ ≥ θ · median(|ΔΨ| 最近 W 个活跃日),θ=3.0,W=14,样本 <5 不触发。

锚:`finitude/epochs/order_parameter.py::psi` / `::detect` `# [FIN-A6]`。
测试:`tests/finitude/test_epochs_dualtrack.py::test_psi_monotone`、
`::test_transition_criterion_golden`、`::test_cold_start_no_fire`。

去掉它缺什么:B 轨没有判据,"纪元是相变"退化为修辞,双轨分歧数据失去定义。

## A7 世代冻结公理(一生只有一种老法)

model_id 与参数 θ 在 hatch 时刻从 config 读入并冻结于 `record.aging`;此后一切 settle
只读 record,config 中途变更不影响在世生命;更换老法的唯一途径是 seal → 重孵。

锚:`finitude/rites/incarnation.py::stamp_aging` `# [FIN-A7]`;`finitude/__init__.py`
组合根只从 record 取模型。
测试:`tests/finitude/test_rites.py::test_model_frozen_mid_life`、
`::test_rehatch_reads_new_config`。

去掉它缺什么:"一生"失去同一性——中途换模型等于换了一条 P 轨迹的物理定律。
