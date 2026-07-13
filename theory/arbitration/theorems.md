# arbitration 定理与猜想(theory/arbitration/theorems.md)

> 在整个架构中的位置:公理表(axioms.md)之上的推论层。凡标"猜想"或
> "候选,未立"的条目实现不得引用为决策依据(总纲律四)。T4 是本模块
> 唯一登记而不立的候选定理,原样保留红队裁决的措辞纪律。

## 定理表

| ID | 陈述 | 状态 |
|---|---|---|
| T1 学不坏主权定理 | 更新规则 θ_{t+1} = Π_Box(θ_t + η(P_t)·c_t·d_t) 下:(i) ∀t: θ_t ∈ Box;(ii) 铁域参数恒等于其常量(结构性,A4);(iii) 生涯总漂移有界 Σ\|θ_{t+1}-θ_t\| <= η0·step·N,N 由 A3 得 N <= 活跃秒数/min_gap | **证明附文(见下)**,性质测试 T-H1/T-H2 |
| T2 凝固定理 | P_t 单调不增(外部前提,幕 V 单调公理)⇒ 单步漂移上界 η0·P_t·step 单调不增;P_t=0 ⇒ ∀s>=t: θ_s=θ_t(精确凝固,非渐近) | **证明附文(见下)**,性质测试 T-H4 |
| T3 个体史分化命题 | 存在 outcome 历史 h1 != h2 与探针输入 x*,使 pipeline(x*; θ(h1)) != pipeline(x*; θ(h2)) | **构造性证明(见下)**,golden 测试 T-H5(`test_individual_history_differentiation_golden`) |
| T4(候选,未立)介入率非平凡上界 | P<0.5 时 TRIM/REPLACE 类介入率 <= (2P)·(1/min_gap)(在草稿哈希首字节系综均匀假设下) | **未立**——见下方"T4 登记"一节 |

### T1 证明附文

**(i) ∀t: θ_t ∈ Box。** 归纳法:θ_0 ∈ Box(初始化为零向量/单位 γ,平凡属于
Box)。设 θ_t ∈ Box,更新式 θ_{t+1} = Π_Box(θ_t + η(P_t)·c_t·d_t) 对任意实数
输入都先算术更新再投影,而 `Theta.project()`(`hysteresis/params.py`)逐坐标
执行 `clip(x, lo_k, hi_k)`,值域恒为 [lo_k, hi_k];故 θ_{t+1} ∈ Box。∎(投影像
恒在闭凸集内是 clip 函数的定义性质,不依赖 θ_t 是否已在 Box 内。)

**(ii) 铁域参数恒等于其 hatch 常量。** 结构性证明,非运行时检查:
`MUTABLE_SET = {d_sw, d_rp, d_ex, gamma_offset}`(`hysteresis/params.py`)与
`Theta` dataclass 的字段集**逐一相等**(`arbiter/__init__.py::
_validate_theta_schema_matches_mutable_set` 在包 import 时断言此结构性事实)。
min_gap/P0 判据/narrow_p/high_intensity 阈值/哈希键型/白名单**不是** `Theta`
的字段,因此不存在任何 `apply_update` 调用路径可以修改它们——这不是"检查
了没被改",而是"改的语法都不存在"。∎

**(iii) 生涯总漂移有界。** 单步漂移 `|Δθ_k| = |sign·η(P_t)·|r|·step_k| <=
η0·step_k`(A5.2,`|r|<=1`、`η(P_t)<=η0`,`sign∈{-1,0,1}`)。跨全部四分量求和
再对 N 个介入事件求和:`Σ_{t=1}^N Σ_k |Δθ_k^{(t)}| <= N·4·η0·max_k(step_k)`
——省去常数因子写作 `<= η0·step·N`(`step` 取步长表的代表值,精确形式见
`hysteresis/params.py::STEP`)。由 A3,相继两次介入间隔 >= min_gap,故 N 次
介入至多需要 `(N-1)·min_gap` 秒,即 `N <= 活跃秒数/min_gap + 1`——脾气漂移
的总里程被不应期与寿命共同封顶。∎

**性质测试**:T-H1(`test_theta_stays_in_box_random_ten_thousand_steps`,随机
万步更新后 θ 恒在 Box)、T-H2(`test_single_step_delta_bounded_by_p_step`,
单步 |Δθ_k| <= P·step_k)。

### T2 证明附文

由 A5.3,`η(P_t) = η0·P_t`;`P_t` 单调不增(幕 V 单调公理,外部前提,非本
模块承重)⇒ `η(P_t)` 单调不增 ⇒ 单步漂移上界 `η(P_t)·step_k` 单调不增。
当 `P_t = 0` 时,`apply_update` 的第一行 `if consensus == 0 or p <= 0.0:
return theta`(`hysteresis/updater.py`)直接短路返回**原样** θ,不经过任何
算术运算——这是**精确**凝固(exact,非"漂移量趋于零"的渐近凝固):
`∀s>=t: θ_s = θ_t`,因为每一步的更新函数在 `p=0` 处都是恒等函数。∎

**性质测试**:T-H4(`test_drift_strictly_decreasing_with_p_and_zero_at_p0`
与 `test_p_zero_theta_frozen_forever`):P=1.0/0.3/0.0 三档同序列回放,累计
漂移量严格递减且 P=0 时逐步恒为零。

### T3 构造性证明

取 h1 = 连续负反馈驱动 SWALLOW(r=-0.9,400 步,共识门在 EMA 稳定后持续为 1)
⇒ θ(h1).d_sw 收敛并顶到 Box 上界 `+0.05`;h2 = 连续正反馈(r=+0.9,同样
400 步)⇒ θ(h2).d_sw 收敛并顶到 Box 下界 `-0.05`。两段历史下 `d_sw` 相差
`0.10`(Box 全宽),对同一枚 SmoothPolicy 探针 x*(action=withdraw,
pressure=0.64,expr=0.5,P=0.8,4 句草稿),复合阈值合成
`compose_policy_params(StepCurve, P, θ)` 使 swallow_th(h1)=0.80、
swallow_th(h2)=0.70;探针的连续得分 s=0.75(`policies/smooth.py::_score`
的确定性计算,不依赖 θ)恰好落在 `[0.70, 0.80)` 之间,故:
`pipeline(x*; θ(h1)) = REPLACE`(s < 0.80,s >= replace_heavy_th=0.55),
`pipeline(x*; θ(h2)) = SWALLOW`(s >= 0.70)。两者 kind 不同,构造性证毕。∎

**去掉它缺哪个可观测行为**:若 hysteresis 层被移除(θ 恒为零向量,
`test_no_hysteresis_means_no_differentiation` 反证),同一探针在"任何历史"
下 verdict 恒同——因为根本没有"历史"这个自由变量能进入 θ。T3 与
T-H5(golden)是本模块深度叙事唯一的机器凭据:如果这张探针 golden 撑不起
来,"两颗心长出两种脾气"整个深化叙事塌(蓝图 §11.2 第 5 条,原样承认)。

**诚实边界**:本文的具体阈值/权重(SmoothPolicy 的八维权重表)是 Yelos
自著的一组取值,不是蓝图给定的唯一解(见 `policies/smooth.py` 顶部"设计
取舍"1);T3 的数学内容是**存在性命题**(∃h1≠h2,∃x*),不依赖某一组具体
权重——golden 测试固化的是"用这组权重构造出的一个见证",红队若质疑权重
选择,命题本身(存在性)不受影响,只需换一组权重重新构造见证。

**性质测试**:T-H5(golden,`test_individual_history_differentiation_golden`)。

## T4 登记(候选,未立)

**候选陈述**:P<0.5 时,TRIM/REPLACE 类介入尚须过调制闸
(`sha256(key)[0]/255 < P/0.5`),在"草稿哈希首字节于消息系综上均匀"的
模型假设下,TRIM/REPLACE 介入率 <= (2P)·(1/min_gap),对 P<0.5 严格紧于
1/min_gap。

**未立的理由(总纲 §2.2 铁条)**:立"介入率有界定理"必须证严格紧于
1/min_gap 的非平凡上界,并以性质测试展示紧性——紧性测试需要构造哈希首字节
逼近 `2P·255/2` 分位的草稿序列,实测率逼近上界,本波未做此构造性逼近实验,
且候选诚实边界明确:SWALLOW 不过调制闸(它走阈值下调),故候选只覆盖
TRIM/REPLACE 子类,不是全介入率;且依赖系综均匀假设(单会话对抗性构造
草稿可能打破均匀性,`test_adversarial.py::test_adversarial_draft_cannot_
break_min_gap` 只验证了"打不破 min_gap",未验证"打不破均匀假设")。

**做不出逼近轨迹的后果**:按律四,本条永远停留在候选/猜想区,`arbiter/`
包代码**不得**引用 T4 作为任何行为的依据(检索:全包搜索 "T4" 只应出现在
本文件与 docstring 的"未立"说明中,不应出现在任何断言/校验逻辑里)。

## 墓碑登记

无。本模块理论层自 arbiter_BLUEPRINT v1.0 起一次性设计,尚无历史条目被
删除或降级——如未来波次发现某条公理/定理需要墓碑化,按 intrinsic_field
的先例在此登记恢复条件。
