# evolution 公理集(axioms.md)

来源:`_build/modules/evolution_BLUEPRINT.md` §1(权威原文,本文件为施工期照录 +
锚点核对副本,冲突以蓝图为准)。基础设施降格:只写真承重的四条约束陈述,
**无非平凡定理**(负清单见文末,不立收敛定理、不立单调改进定理)。

## A1 可变异域公理

任一代的变异集 M_g ⊆ {k ∈ Registry : mutable(k)=True}。候选基因组仅在可变异维
上与亲代不同;域界裁剪 g_k ∈ [lo_k, hi_k]。

锚:`guards/static_check.py::check_mutation_set` `# EVO-A1`。
测试:`tests/evolution/test_guards_iron.py`。

去掉它缺什么:变异提案可以偷偷改未注册键或越界值,注册表不再是唯一事实源。

## A2 铁域公理

∀代 g、∀铁参数 k(immutable=True):value_g(k) ≡ value_hatch(k)。铁域含一切主权
语义、输出面白名单、单调公理参数、P0 语义(具体清单见 evolution_BLUEPRINT §3.2)。
铁域校验双段:变异前静态拒 + 变异后全量性质测试拒(两段都过才落谱系为 accepted)。

锚:`guards/static_check.py::check_mutation_set` `# EVO-A2`、
`guards/property_gate.py::run_property_gate` `# EVO-A2`。
测试:`tests/evolution/test_guards_iron.py`(对抗集固化)。

去掉它缺什么:进化可以漂移 min_gap/quiet_hours/lifespan 这类主权硬约束,opt-in
运维工具变成主权破坏工具。

## A3 漂移速度上界公理

∀代 g、∀可变参数 k:|value_g(k) − value_{g−1}(k)| ≤ step_cap_k,其中
step_cap_k = velocity_bound × (hi_k − lo_k)(枚举参数每代至多变一档)。策略的
步长参数是该上界的实现,不是另一套约束。

锚:`variation/base.py::clamp_step` `# EVO-A3`(一切策略提案的唯一出口)。
测试:`tests/evolution/test_velocity_bound.py`。

去掉它缺什么:一代之内可以把参数拍到任意值,"慢漂移"退化为空话。

## A4 回滚完备性公理

lineage 是追加式全事件账;∀已记录代 g,`rollback(g)` 重建的 overlay 与该代
accepted 时写盘的 overlay **字节级相等**。推论(平凡,不称定理):每个现行参数
值可溯源到 hatch 默认或唯一一条 accepted 记录。

锚:`lineage/ledger.py::LineageLedger.reconstruct` `# EVO-A4`、
`lineage/ledger.py::LineageLedger.rollback` `# EVO-A4`。
测试:`tests/evolution/test_lineage_rollback.py`(往返字节断言)、
`tests/evolution/test_lineage_integrity.py`(溯源完备)。

去掉它缺什么:漂移出问题时无法一键回到任意代,opt-in 工具变成不可逆的赌注。

## 不立的定理(负清单,防 cosplay)

- **不立"收敛定理"**:模式搜索在此适应度(bench 分,非光滑非凸)上无可证收敛,
  谎称有就是律四违例。
- **不立"适应度单调改进定理"**:selection 只保证"劣不落地"(T3),不保证代代
  更好——环境即 bench 剧本变了分就变。

## 猜想区

无。本模块不设猜想条目。
