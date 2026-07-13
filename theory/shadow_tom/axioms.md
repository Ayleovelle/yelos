# shadow_tom 公理集(SHTOM-A1..A7)

> 权威链:`_build/modules/shadow_BLUEPRINT.md` §1.1。本文件是该节的可核对
> 抄本(公理陈述 + 代码锚点 + 测试 ID 三元组),不新增语义,只把蓝图里的
> 七条公理逐条落到实现文件路径,供 `impl_anchors.md` 三元组表与红队核对。

## A1 模拟公理(simulation, not telepathy)

**陈述**:影子状态 `s_sh(t)` 是她自身动力学 F 在用户输入流 `u(1..t)` 上的像:
`s_sh(t) = F(s_sh(t-1), u(t))`。影子对用户真实状态 `x(t)` 的关系只是假设
H0:"x 与 s_sh 经同一动力学同一输入生成"。H0 的成立度不由本公理担保,由
A3 校准担保。

- **可观测行为**:去掉它 → concern 无生成来源,guidance 无温度信号。
- **代码锚点**:`simulator/ensemble.py`(`# [SHTOM-A1]` 喂入编排,只喂
  `speaker="user"` 轮);`engine_bridge.submit_shadow`(借来,锚点只指编排侧,
  本包零 import 之)。
- **测试**:`tests/shadow/test_simulator.py::test_shadow_fed_only_user_turns`。

## A2 输出面白名单公理(P4 形式化)

**陈述**:影子内部状态空间 `S_sh` 与用户可见输出空间 `O` 之间不存在直接
映射;唯一合法输出算子是 gates 链 `G: (ConcernVerdict 候选, CalibrationState,
Budget) -> {inject(intensity), enqueue(concern), guidance_flag}`,且 `O` 的
文本面 = primal `concern` 词典组闭包 ∪ guidance 白名单 hint 集,均为可枚举
封闭集。第二人称状态陈述句式不在 `O` 的文法内。

- **可观测行为**:去掉它 → 影子可自由发言即"诊断用户",产品红线崩塌。
- **代码锚点**:`gates/exit.py`(`# [SHTOM-A2]` 唯一出口函数);全包
  ASCII-only 字符串常量(中文说明一律 `#` 注释)。
- **测试**:`tests/shadow/test_whitelist.py`(AST 常量扫描 + 出口枚举断言)。

## A3 校准公理(预测对观测负责)

**陈述**:每次 fire 判定同时落一条预测记录 `pred=(t,type,q)`(`q∈[0,1]` 为
"用户处于低谷"的确定度);下一有效用户轮的可观测代理特征 `y∈{0,1}` 到达后,
校准账本追加 `(q,y)`,Brier 分 `B = mean((q-y)^2)` 与可靠性分箱随之更新。
校准状态是闸的输入:B 越差,concern 出口越紧(§7 决策表 = `gate_policy.py`)。

- **可观测行为**:去掉它 → "她的心疼有精度记录"消失;故意让影子错,行为不变
  (可证伪点)。
- **代码锚点**:`calibration/ledger.py`(`# [SHTOM-A3]` 落账)/
  `calibration/gate_policy.py`(消费);回写点 `ShadowSystem.on_user_turn`
  (临界区内,§10 契约)。
- **测试**:`tests/shadow/test_calibration.py::test_bad_calibration_tightens_gate`。

## A4 误差有界诚实条款

**陈述**:影子偏差 `|x(t)-s_sh(t)|` 不可观测,但其代理上界可观测:代理误差
`e(t)=|y(t)-q(t)|` 的滚动均值,及集合分歧度 `D(t)`。一切下游消费(inject
强度、guidance 置信)必须以 `conf=f(B,D)` 折减,`f` 单调递减于两者;禁止任何
路径绕过折减直接消费原始强度。

- **可观测行为**:去掉它 → 校准差时 inject 强度不衰减,"不确定就少说"机制
  消失。
- **代码锚点**:`signals/intensity.py`(`# [SHTOM-A4]` 强度 = 信号强度 ×
  校准置信,两套 f 见蓝图 §6.4)。
- **测试**:`tests/shadow/test_intensity.py::test_confidence_discount_monotone`。

## A5 扰动来源公理(ε 非自由旋钮)

**陈述**:多假设扰动幅度 `ε_t` 不是配置常数,是观测量的确定性函数:

```
ε_t = clip( λ · σ_t , ε_lo , ε_hi )
σ_t = w_obs · σ_obs(t) + w_base · σ_family(t)      # w_obs+w_base=1,默认 0.6/0.4
σ_obs(t)    = 三通道(pressure/warmth/damage)观测值的滚动标准差(EWMA 在线方差)
σ_family(t) = 基线族离散度:同一通道日/周/月三窗口基线值的极差归一(取跨通道 max)
```

`λ、ε_lo、ε_hi` 是登记进 evolution genome 的白名单参数(有域界,本波次先以
模块常量落地,genome 注册表接线留待 W5),但 `ε_t` 本身随观测漂移——观测越
乱,假设越散;观测越稳,假设越拢。扰动方向由哈希族确定性生成(键型
`shadow_eps:{sid}:{day_key}:{k}`),同态同日同扰动,全程可回放。

- **可观测行为**:去掉它 → 分歧度退化为 ε 旋钮的函数,量的是旋钮不是知识
  (红队反例:ε→0 给零不确定)。
- **代码锚点**:`simulator/epsilon.py`(本公式唯一实现地,`# [SHTOM-A5]`)。
- **测试**:`tests/shadow/test_uncertainty_ground_truth.py`(真值变化断言响应;
  扫 ε 断言行为不漂)。

## A6 迟滞与当日一次公理

**陈述**:每检测器类型持独立迟滞状态机:`armed -> (越阈 ∧ 当日未 inject) ->
fire -> disarmed -> (信号回落至 re-arm 阈下) -> armed`。`armed` 状态跨日
持久(继承红队 F11b);同类型当日至多 fire 一次(F3c)。

- **可观测行为**:去掉它 → 同一低谷日她反复 inject/反复"你还好吗",克制人设
  崩坏。
- **代码锚点**:`signals/hysteresis.py`(状态机唯一实现,`# [SHTOM-A6]`,四
  检测器实例化)。
- **测试**:`tests/shadow/test_hysteresis.py`(跨日 armed 持久 / 当日一次 /
  回落 re-arm 三分支)。

## A7 敏感化单调有界公理

**陈述**:每 concern 类型 `c` 持敏感化偏置 `β_c ∈ [β_lo, β_hi]`(硬界);被
校准判"真阳"(`y=1`)的触发使 `β_c` 下调(更敏感),被判"假阳"(`y=0`)的
触发使 `β_c` 上调(习惯化);单步步长 `|Δβ| ≤ δ_max`,更新算子在界内单调、
界外截断。有效阈值 `th_eff(c) = th_base(c) + β_c`,恒在检测器安全域内。

- **可观测行为**:去掉它 → 两颗经历不同的心对同类伤有完全相同的痛觉阈值,
  "疤痕有记忆"消失。
- **代码锚点**:`sensitization/scar.py`(`# [SHTOM-A7]`);持久化入 binding
  `shadow.sensitization`。
- **测试**:`tests/shadow/test_sensitization.py::test_monotone_bounded_property`
  (随机触发序列性质测试)。
