# finitude 定理集(theorems.md)

来源:`_build/modules/finitude_BLUEPRINT.md` §1.2。

## T1 归零时刻定理

无事件、全活跃的一生在第 L 个活跃日恰好 P=0(L=lifespan_active_days),对 linear 与
weibull 成立(Σ base_t = W(L) = 1);对 event_weighted 为 P(L) = 1 − α0 > 0
(平静的一生活得更久,这是该模型的可观测签名);对 reserve 同 linear(S 轴)。

证明:各 W 的伸缩构造,见各模型文件头。
测试:`tests/finitude/test_models_distinguish.py::test_zero_day`。

## T2 序参量单调定理

p1 ≤ p2 ⇒ Ψ(p1) ≤ Ψ(p2)。

证明梗概:shrink_pool 截取长度 n(p) = max(1, round(|pool|·max(p,0.15))) 对 p 单调不减
(离散格点上枚举证——词典是有限封闭集,可机器枚举);floor(cap·p) 显然单调。
测试即枚举证明本体:`tests/finitude/test_epochs_dualtrack.py::test_psi_monotone`
(全词典 × p ∈ {0, 0.001, ..., 1} 网格)。

## T3 送别完备性定理

设 F_led 为持久面记账字段全集(FIELD_REGISTRY 为其机器体),A 为 anthology 组装映射,
则 ∀ f ∈ F_led,∃ 模板 τ ∈ {长卷, 短笺, 数据附录}:f 在 τ 的渲染输出中有锚(满射覆盖)。

证明:构造性——registry 每条目静态声明覆盖模板集且非空(CI 断言),渲染测试对满记录
逐条目验证探针串出现。**诚实标注:这是构造性守恒断言(工程定理),不是深数学**;它的
价值在于把"一生无损"从修辞变成会挂 CI 的东西。

测试:`tests/finitude/test_anthology_completeness.py`(正向满射)+ `::test_schema_covered`
(反向:record schema 顶层键 ⊆ registry ∪ EXCLUDED)。

## T4 双轨包络引理(猜想,不作实现依据引用)

fixed 轨(A 轨)跃迁时刻集与 B 轨跃迁时刻集在 linear 模型、无事件轨迹上至多相差
⌈W/2⌉ 个活跃日(中位数窗口的滞后界)。

**标注:猜想,反例未寻得**——B 轨对阶跃词典的 ΔΨ 是脉冲式的,滞后界依赖词典结构;
不作为实现依据引用(律四),只作为 divergence 数据的观察假设,由 bench 剧本积累证据。
本仓不含证明,亦不含以此猜想为前提的实现分支。
