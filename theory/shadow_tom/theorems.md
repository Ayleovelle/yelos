# shadow_tom 定理与猜想(SHTOM-T1..T3, 推论, C1)

> 权威链同 `axioms.md`。每条定理给证明梗概或显式标"猜想";不装饰性,每条
> 都能回答红队问句"去掉它缺哪个可观测行为"。

## T1 出口封闭性定理

**陈述**:gates 链 `G` 的像空间是有限可枚举集(inject 强度 ∈ 有限精度
`[0,1]` 3 位量化网格 × concern occasion 单枚举 `{"concern"}` × guidance flag
布尔)。

**证明梗概**:`gates/exit.py` 的出口函数逐支枚举——`do_inject`/`do_enqueue`
均为布尔,`intensity` 经 `round(x, 3)` 量化到有限网格,`ctype` 取自四检测器
枚举闭包。有限支 × 有限值域 → 像有限。

**测试**:`tests/shadow/test_gates.py::test_exit_image_enumeration`。

## T2 敏感化有界定理

**陈述**:任意触发序列回放,`β_c` 轨迹恒 `∈ [β_lo, β_hi]` 且 `th_eff` 恒在
安全域(`th_eff ≥ 触发阈 × 0.5`)。

**证明梗概**:`sensitization/scar.py` 的更新算子是"先加步长再 clamp 到硬界"
的复合;归纳基:初始 `β_c=0 ∈ [β_lo,β_hi]`;归纳步:`clamp(β_c ± δ, β_lo,
β_hi) ∈ [β_lo,β_hi]` 对任意 `β_c` 成立(clamp 定义即保证陪域)。安全域随
`th_base` 与 `β` 的界联合成立(见 `scar.py::SAFE_MARGIN` 断言)。

**测试**:`tests/shadow/test_sensitization.py`(千次随机序列性质测试)。

## T3 校准闸单调定理

**陈述**:固定其余输入,`B` 增(校准变差)⇒ 出口决策弱单调收紧(fire 集合
不增)。

**证明梗概**:`calibration/gate_policy.py` 的 `tier_for_brier` 是 `B` 的阶梯
函数,阶梯边界 `{0.20, 0.30}` 单调划分 `{normal, tight, silent}`,每档的出口
效果集合按 `观察⊇正常⊇收紧⊇静默` 的字面强度单调收紧(`tight` 需要额外
`+0.1` strength 门槛,`silent` 直接拦 concern 原语与 guidance——都是 `normal`
放行集合的真子集)。逐档人工核对 + 网格扫描测试覆盖阶梯的每一段。

**测试**:`tests/shadow/test_calibration.py::test_gate_monotone_in_brier`
(网格扫 B)。

## 推论 T4:当日 inject 上界(不称定理)

同类型当日 `≤1` 次 inject 由 A6 状态机直接保证,四类型当日总 inject `≤4`——
这是构造的平凡推论,如实标注"推论",不包装成"克制定理"(与 arbiter major③
同款诚实)。

## 猜想 C1(显式标注,不被实现引用)

多假设分歧度 `D` 与真实预测误差 `e` 正相关(相关系数下界未证)。地位:猜想;
bench 校准数据积累后回访。**实现只依赖 A4 的折减机制,不依赖本猜想成立**——
`intensity.py` 与 `outcome.py` 均不引用 `D~e` 相关性作为正确性前提,只用 A4
的单调折减。
