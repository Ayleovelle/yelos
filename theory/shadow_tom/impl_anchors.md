# shadow_tom 实现锚点表(公理 ID → 文件:函数 → 测试 ID)

> 律四执行面(蓝图 §1.3):CI 的 theory-trace 检查器扫 `[SHTOM-A*]` 锚点
> 注释,公理无锚 / 核心动力学无公理引用均挂检查。本表是该检查器核对的
> 权威清单,红队按行核。

| 公理 | 文件:函数/类 | 锚点注释 | 测试 ID |
|---|---|---|---|
| A1 | `simulator/ensemble.py:feed_user_turn` | `# [SHTOM-A1]` | `test_simulator.py::test_shadow_fed_only_user_turns` |
| A2 | `gates/exit.py:apply_exit` | `# [SHTOM-A2]` | `test_whitelist.py::test_ast_no_chinese_string_constants` |
| A3 | `calibration/ledger.py:CalibrationLedger.record_prediction` | `# [SHTOM-A3]` | `test_calibration.py::test_bad_calibration_tightens_gate` |
| A4 | `signals/intensity.py:compute_intensity` | `# [SHTOM-A4]` | `test_intensity.py::test_confidence_discount_monotone` |
| A5 | `simulator/epsilon.py:compute_epsilon` | `# [SHTOM-A5]` | `test_uncertainty_ground_truth.py::test_epsilon_drift_does_not_change_fire_set` |
| A6 | `signals/hysteresis.py:step` | `# [SHTOM-A6]` | `test_hysteresis.py::test_armed_persists_across_days` |
| A7 | `sensitization/scar.py:update_beta` | `# [SHTOM-A7]` | `test_sensitization.py::test_monotone_bounded_property` |

对应定理:

| 定理 | 文件:函数 | 测试 ID |
|---|---|---|
| T1 出口封闭性 | `gates/exit.py:apply_exit` | `test_gates.py::test_exit_image_enumeration` |
| T2 敏感化有界 | `sensitization/scar.py:update_beta` | `test_sensitization.py` |
| T3 校准闸单调 | `calibration/gate_policy.py:tier_for_brier` | `test_calibration.py::test_gate_monotone_in_brier` |

理论层与实现层的耦合纪律(与 intrinsic/arbiter 同款):锚点注释只是文档化
交叉引用,不是可执行断言;可执行的是右列测试 ID——CI 的 theory-trace 检查器
（本波交付为静态清单核对，脚本化扫描留作后续 CI 集成任务）核对锚点注释
存在性与本表的映射一致性。
