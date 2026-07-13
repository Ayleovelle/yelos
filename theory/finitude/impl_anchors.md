---
# impl_anchors.md —— theory-trace CI 消费的机器可读锚点表(yaml front-matter)。
# 在整个架构中的位置:axioms.md/theorems.md 的索引化投影,供 CI 扫双向引用
# (公理 -> 代码注释 `# [FIN-A*]`,代码 -> 本表),不重复定义事实。
anchors:
  - id: FIN-A1
    statement: "资源公理:settle 结构性单调,P' <= P"
    file: src/yelos/finitude/gate.py
    symbol: settle_through_gate
    tests: [test_monotone_all_models]
  - id: FIN-A2
    statement: "耗散形状公理:W_m 单调不减,spend 封顶 2*base"
    file: src/yelos/finitude/models/weibull.py
    symbol: WeibullWear.spend
    tests: [test_spend_cap, test_w_monotone]
  - id: FIN-A3
    statement: "事件可称重公理:E(facts) 对事件计数分量单调不减"
    file: src/yelos/finitude/models/event_weighted.py
    symbol: EventWeighted.spend
    tests: [test_event_monotone]
  - id: FIN-A4
    statement: "快池从属公理:F<=S,回填封顶,S 独立于 F"
    file: src/yelos/finitude/models/reserve.py
    symbol: ReserveModel.spend
    tests: [test_reserve_f_le_s, test_reserve_refill_bound, test_reserve_s_independent]
  - id: FIN-A5
    statement: "纪元不可逆公理:idx' = max(idx, 提名)"
    file: src/yelos/finitude/epochs/order_parameter.py
    symbol: clamp_forward
    tests: [test_epoch_never_regresses]
  - id: FIN-A6
    statement: "序参量公理:Psi = rho_lex * rho_budget,单调 + 相变判据"
    file: src/yelos/finitude/epochs/order_parameter.py
    symbol: psi
    tests: [test_psi_monotone, test_transition_criterion_golden, test_cold_start_no_fire]
  - id: FIN-A7
    statement: "世代冻结公理:model/params 在 hatch 时冻结进 record.aging"
    file: src/yelos/finitude/rites/incarnation.py
    symbol: stamp_aging
    tests: [test_model_frozen_mid_life, test_rehatch_reads_new_config]
---

| 公理/定理 | 代码锚 | 测试锚 |
|---|---|---|
| A1 | gate.py::settle_through_gate / core.binding.rollover / persistence.effective_p | test_models_property::test_monotone_all_models |
| A2 | models/*.py 文件头 W 与 E 声明 | test_models_property::test_spend_cap, test_w_monotone |
| A3 | models/event_weighted.py spend() E 项 | test_models_property::test_event_monotone |
| A4 | models/reserve.py | test_models_property::test_reserve_* 三则 |
| A5 | epochs/order_parameter.py::clamp_forward | test_epochs_dualtrack::test_epoch_never_regresses |
| A6 | epochs/order_parameter.py | test_epochs_dualtrack::test_psi_monotone, test_transition_criterion_golden |
| A7 | rites/incarnation.py / finitude/__init__.py 组合根 | test_rites::test_model_frozen_mid_life |
| T1 | models/*.py | test_models_distinguish::test_zero_day |
| T2 | epochs/order_parameter.py | test_epochs_dualtrack::test_psi_monotone(枚举即证明) |
| T3 | anthology/registry.py | test_anthology_completeness 全文件 |
| T4 | (猜想,无实现引用) | bench 剧本 divergence 观察项(本仓不含) |

CI theory-trace:扫描 `# [FIN-A*]` 注释与本表互核,缺锚即挂
(`tests/finitude/test_theory_trace.py`,律四执行面)。
