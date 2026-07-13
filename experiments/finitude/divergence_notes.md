# 双轨分歧观察记录(finitude_BLUEPRINT §4.3/§13,T4 猜想的证据积累区)

本文件是 A 轨(固定边界)与 B 轨(序参量相变)分歧数据的观察笔记,不是证明。
T4(双轨包络引理)在 `theory/finitude/theorems.md` 中标注为**猜想**,不作为
任何实现分支的依据(律四)——本文件只记录施工期用小规模合成轨迹观察到的现象,
供未来 bench 30/90/365 虚拟日剧本(`finitude_lifetimes.yaml`,W3 排期表 §13 项)
积累更大样本的分歧证据。

## 观察 1:词典粒度限制 B 轨早期灵敏度

当前 `primal.LEXICON`(经 `lexicon_data.all_base_pools`)每场合仅 3~5 句、
共 10 场合,`shrink_pool` 的截断长度是整数阶跃函数(`round(len*p)`)。这意味着
`rho_lex(p)` 对 p 的响应是**分段常数**,不是连续曲线——序参量 Ψ 的"联动突变"
判据(A6)在词库量级小的情况下,ΔΨ 的取值集合本身就稀疏,B 轨判据的实际
灵敏度受词库粒度制约。finitude_BLUEPRINT §14.3-3 已如实标注此局限:
"序参量相变"的理论叙事要等 primal 词库深化(W1 之后词条量上来)之后才真正丰满。

## 观察 2:reserve 模型下 A/B 两轨输入天然不同源

非 reserve 模型下,A 轨与 B 轨都读同一个契约 P(P_expr ≡ P),两轨分歧只来自
判据本身(固定边界 vs 序参量突变检测器)的算法差异。reserve 模型下 B 轨改读
P_expr(=F,可日间波动),A 轨仍读契约 P(=S,严格单调)——这是**双轨分歧数据最
富的来源**(finitude_BLUEPRINT §4.2 原文断言),因为两轨此时连输入信号本身
都不同源,不只是判据不同。本仓 `tests/finitude/test_models_distinguish.py::
test_reserve_p_expr_recovers_and_bounded` 已固化"P_expr 在无事件段回升"的行为,
是这一分歧来源的直接前提条件(P_expr 回升 → B 轨判据的 Δρ_lex/Δρ_budget 可能
反向,不会跟随 A 轨继续"变老")。

## 观察 3:冷启动退化窗口(前 5 个活跃日)与真实分歧窗口的重叠风险

`order_parameter` 权威轨的冷启动退化(A5/§4.4 决策表脚注)覆盖生命最初的
`MIN_SAMPLES=5` 个活跃日。若一段生命的第一次真实纪元跃迁恰好落在这个窗口内
(短寿命/极端参数场景下可能发生),该次跃迁的"权威通告"会被退化逻辑代驱为
A 轨,产生的 divergence 行仍会正确分类为 `a_only`/`b_only`,但"B 轨本该有
表现却被冷启动压制"这件事本身不会在 divergence.jsonl 里留下专门的标记
(只能通过对照"冷启动期内"这个时间窗事后推断)。未来若要更细粒度地区分
"B 轨真的没反应"与"B 轨被冷启动压制",需要在 divergence 行 schema 里补一个
`cold_start: bool` 字段——本蓝图未要求,这里记一笔留给红队判断是否值得加。

## 后续证据积累计划

`tests/finitude/conftest.py` 的 `run_trajectory` 夹具与
`experiments/finitude/model_comparison.json` 已提供四模型 × TRAJ-D1 的基础
数值面;bench 30/90/365 虚拟日剧本(尚未在本波实现,是 §13 排期表 F-W4 的
产出物)接上后,可对更长轨迹、更多随机事件序列重复上述三点观察,用真实统计
(如 A/B 跃迁时刻集的中位数滞后)取代本文件目前的定性描述。
