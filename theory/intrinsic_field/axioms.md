# intrinsic_field 公理表(theory/intrinsic_field/axioms.md)

> 在整个架构中的位置:intrinsic 模块理论层(维一)。本文件是 `intrinsic_BLUEPRINT.md §1.1`
> 的机器可核对版本——每条公理带 ID、代码锚点(注释 `# [AX-n]`)、测试锚点;
> theory-trace CI 扫双向引用(有公理无锚点 / 有锚点无公理 均判失败)。
> 不与 impl_anchors.md 重复维护事实,后者是本文件的 yaml 索引化。

## 状态空间

内在场 `φ(t) ∈ Φ = [0,1]^4`,四通道:

| 通道 | 符号 | 语义 | 主要输入源(借用,防御式 sget) |
|---|---|---|---|
| drive(动机)   | φ_d | 想主动找你的势能     | needs.contact, needs.expression, phase |
| languor(倦意) | φ_l | 表达疲乏/退避       | needs.quiet, boundary.pressure, 日内活动量 |
| longing(牵挂) | φ_g | 对你的挂念(慢通道)  | 静默时长, damage.open, concern 事件 |
| afterglow(余温)| φ_a | 交互后的暖意残留(快衰减)| valence.warmth, 交互事件冲击 |

## 更新算子

```
φ_{t+Δ} = clip_[0,1]( φ_t + Δ · ( −Λ ⊙ (φ_t − φ_eq)  +  C(τ_t)  +  Σ_j K·e_j(t) ) )
          衰减项(对角 Λ>0,趋均衡)   昼夜强迫    事件冲击(有界)
```

## 公理表

| ID | 公理 | 代码锚点 | 测试锚点 |
|---|---|---|---|
| AX-1 有界性 | φ 恒 ∈ [0,1]^4;clip 是最后一步,任何项组合不可越界 | `field/state.py::FieldState.clipped` | T-FLD-01 |
| AX-2 自然衰减 | 无强迫无冲击时,每通道单调趋向 φ_eq,速率由对角矩阵 Λ(全正)定 | `field/dynamics.py::decay_term` | T-FLD-02 |
| AX-3 昼夜强迫 | C(τ) 为 1440min 周期分段余弦,参数 =(基线相位 ⊕ 学到的用户相位偏移);确定性,同 τ 同相位同值 | `circadian/forcing.py::forcing` | T-CIR-01 |
| AX-4 冲击有界 | 每类事件冲击向量范数 ≤ I_max(表定);冲击叠加经 clip 截断,无累积爆炸 | `field/impacts.py::IMPACT_TABLE` | T-FLD-03 |
| AX-5 输入借用界定 | 场输入只经 sget 读 Surface 白名单字段;φ 不是任一 Surface 字段的仿射转录——存在 Surface 恒定而 φ 仍演化的轨迹 | `field/impacts.py::SURFACE_WHITELIST` | T-FLD-04 |
| AX-6 闸门独立 | cap×P 预算、quiet 硬窗、P0、min_gap、unanswered、dormant、guard_frozen 是独立于一切策略阈值曲面的公共硬闸;任何策略的 want=True 都必须过全链,链不可被策略配置绕过 | `impulses/gates.py::GATE_CHAIN` | T-GAT-01 |
| AX-7 确定性 | 模块零 random、零 time.time();一切伪随机经哈希族(primal/determinism.py 登记);同状态同时刻同配置 ⇒ 同决策 | `impulses/poisson_budget.py::_thin` | T-DET-01 |
| AX-8 时间入参化 | 场步进的 now_ts/本地分钟/day_key 全部由 scheduler(经 core.clock.Clock 协议)喂入;虚拟时钟可整体替换 | `scheduler/heartbeat.py::step_field` | T-SCH-03 |

## 边界句(记账纪律,§0.2)

引擎 Surface 是"她的躯体感受"(借用);intrinsic 的场 φ 是"她对这些感受的**内在编排**"
(自著)——φ 的每个通道都是 Surface 多字段 + 事件史 + 昼夜相位的自著泛函,不是 Surface
字段的改名转录。防"换皮转录"的机器凭据:AX-5 / T-FLD-04。
