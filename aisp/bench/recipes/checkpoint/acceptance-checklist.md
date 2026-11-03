# checkpoint：验收清单

## 背景

这份文档是 checkpoint 评估的验收清单，按 G0 能跑、G1 旁路可跑、G2 小规模对齐、G3 逐级 scaling、G4 结论登记五个阶段逐条列出需要确认的事项。清单从真实运行跑通前向、反向、optimizer.step 与一次 checkpoint 写入开始，经旁路与小规模对齐、逐级 scaling，到结论登记结束，共 24 条验收项。

## 问题

```viba acceptance_checkpoint
import gates
import levels

AcceptanceCheckpointItem =
  Oneof
  | "g0_real_run" * Hint[{ G0 能跑：真实运行跑通前向、反向、optimizer.step 与一次 checkpoint 写入 }]
  | "g0_checkpoint_implementation_recorded" * Hint[{ G0 能跑：checkpoint 实现名与版本已记录 }]
  | "g0_run_config_recorded" * Hint[{ G0 能跑：运行配置已记录：模型 commit、框架版本、依赖 lock、拓扑、存储挂载 }]
  | "g1_meta_device_same_flow" * Hint[{ G1 旁路可跑：meta device 构建的模型能跑完与 G0 相同的流程 }]
  | "g1_param_grad_present" * Hint[{ G1 旁路可跑：param.grad 存在且逻辑尺寸与真实一致 }]
  | "g1_state_dict_keys_match" * Hint[{ G1 旁路可跑：state_dict() 的键结构与真实运行核对一致 }]
  | "g1_fidelity_boundary_filled" * Hint[{ G1 旁路可跑：保真边界表已填写，存储路径均不为 L0 }]
  | "g1_async_timing_conversion_written" * Hint[{ G1 旁路可跑：异步 checkpoint 的时序折算规则已写明 }]
  | "g2_real_and_bypass_same_observation" * Hint[{ G2 小规模对齐：真实与旁路各跑一次，观测配置相同 }]
  | "g2_byte_count_deviation_within_one_percent" * Hint[{ G2 小规模对齐：应用层与系统层总字节数偏差 ≤ 1%，或偏差已解释 }]
  | "g2_observation_overhead_within_three_percent" * Hint[{ G2 小规模对齐：观测开销单独测量，关键指标变化 ≤ 3% }]
  | "g2_all_items_within_tolerance_or_reviewed" * Hint[{ G2 小规模对齐：全部分项在容差内，或偏差已归因并经评审 }]
  | "g2_alignment_report_uploaded_and_linked" * Hint[{ G2 小规模对齐：对齐报告已上传并回链 }]
  | "g3_levels_executed_in_order" * Hint[{ G3 逐级 scaling：S0 → S1 → S2 → S3 → S4 → S5 逐级执行，未跳级 }]
  | "g3_complete_metrics_per_level" * Hint[{ G3 逐级 scaling：每级都有完整度量，不只测带宽 }]
  | "g3_invariant_deviation_within_tolerance" * Hint[{ G3 逐级 scaling：每条不变量的相邻级偏差在容差内 }]
  | "g3_metadata_and_bytes_reported_separately" * Hint[{ G3 逐级 scaling：元数据操作数与数据字节数分开报告 }]
  | "g3_aggregate_bandwidth_saturation_marked" * Hint[{ G3 逐级 scaling：聚合带宽的饱和拐点已标出 }]
  | "g3_async_timing_conversion_applied" * Hint[{ G3 逐级 scaling：异步写入的时序折算已应用 }]
  | "g3_tail_latency_split_by_node" * Hint[{ G3 逐级 scaling：尾延迟（P99/P999）已按节点拆分排查 }]
  | "g4_latest_run_written_with_backlink" * Hint[{ G4 结论登记：latest_run 已由评估服务写入，回链三要素齐全 }]
  | "g4_coverage_matrix_updated" * Hint[{ G4 结论登记：覆盖度矩阵已更新 }]
  | "g4_unresolved_deviations_registered" * Hint[{ G4 结论登记：未解决的偏差已登记进 playbook/pitfalls.md }]
  | "g4_versions_queryable" * Hint[{ G4 结论登记：checkpoint 实现、框架版本与服务版本均可查 }]

AcceptanceCheckpointSection =
  Object
  * $gate (gates.Gate * Hint[{ 阶段门，取值 G0 到 G4；G0 能跑、G1 旁路可跑、G2 小规模对齐、G3 逐级 scaling、G4 结论登记，与原清单的五个阶段标题一致 }])
  * $items (list[AcceptanceCheckpointItem] * Hint[{ 这个阶段的验收项，按原清单顺序；每条单独勾选 }])

AcceptanceCheckpointLadder =
  list[levels.Level] * Hint[{ G3 的档位顺序：S0 → S1 → S2 → S3 → S4 → S5；逐级执行，未跳级 }]

AcceptanceCheckpointChecklist =
  Object
  * $sections (list[AcceptanceCheckpointSection] * Hint[{ G0 到 G4 五个阶段，按原清单顺序；G0 有 3 条、G1 有 5 条、G2 有 5 条、G3 有 7 条、G4 有 4 条，共 24 条验收项 }])
  * $ladder (AcceptanceCheckpointLadder * Hint[{ G3 要逐级执行的档位顺序 }])

AcceptanceCheckpointProgress =
  Object
  * $checked (list[AcceptanceCheckpointItem] * Hint[{ 已勾选的验收项，按原清单顺序 }])
  * $pending (list[AcceptanceCheckpointItem] * Hint[{ 还没勾选的验收项，按原清单顺序 }])

AcceptanceCheckpointGateVerdict =
  Object
  * $gate (gates.Gate * Hint[{ 这个判定对应的阶段门 }])
  * $passed (bool * Hint[{ 该阶段的验收项是否全部已勾选 }])
  * $pending (list[AcceptanceCheckpointItem] * Hint[{ 该阶段还没勾选的验收项；全部勾选时为空 }])

AcceptanceCheckpointVerdict =
  Object
  * $passed (bool * Hint[{ 五个阶段的验收项是否全部已勾选 }])
  * $gates (list[AcceptanceCheckpointGateVerdict] * Hint[{ 每个阶段一条判定，按 G0 到 G4 的原顺序 }])
```

## 基本操作

先取清单：按原清单结构拿到 G0 到 G4 五个阶段的验收项。开始验收时把全部验收项记为未勾选，之后每确认一条就勾选一条，勾选状态按原清单顺序累积。每完成一个阶段就对这个阶段做判定：该阶段的验收项全部勾选才算通过，没通过时列出还差哪几条。最后对整份清单做判定：五个阶段的验收项全部勾选才算整份通过，并给出每个阶段一条判定。

## 接口

```viba acceptance_checkpoint_api
import acceptance_checkpoint
import gates

Start =
     acceptance_checkpoint.AcceptanceCheckpointProgress
  <- $checklist (acceptance_checkpoint.AcceptanceCheckpointChecklist * Hint[{ 要执行的验收清单：G0 到 G4 五个阶段共 24 条验收项，以及 G3 的逐级档位 }])
  <- Hint[{ 开始验收：按清单把所有验收项记为未勾选，返回初始进度；勾选状态从这里开始累积 }]

CheckItem =
     acceptance_checkpoint.AcceptanceCheckpointProgress
  <- $progress (acceptance_checkpoint.AcceptanceCheckpointProgress * Hint[{ 当前进度：已勾选与未勾选的验收项 }])
  <- $item (acceptance_checkpoint.AcceptanceCheckpointItem * Hint[{ 要勾选的那条验收项 }])
  <- Hint[{ 勾选：把一条验收项记为已勾选，返回更新后的进度；已经勾选的项重复勾选时进度不变 }]

JudgeGate =
     acceptance_checkpoint.AcceptanceCheckpointGateVerdict
  <- $gate (gates.Gate * Hint[{ 要判定的阶段门，取值 G0 到 G4 }])
  <- $progress (acceptance_checkpoint.AcceptanceCheckpointProgress * Hint[{ 当前进度：已勾选与未勾选的验收项 }])
  <- Hint[{ 判定一个阶段：该阶段的验收项全部已勾选时 passed 为 true；否则列出该阶段还没勾选的验收项，返回判定 }]

JudgeChecklist =
     acceptance_checkpoint.AcceptanceCheckpointVerdict
  <- $progress (acceptance_checkpoint.AcceptanceCheckpointProgress * Hint[{ 当前进度：已勾选与未勾选的验收项 }])
  <- Hint[{ 判定整份清单：按 G0 到 G4 逐阶段判定，五个阶段的验收项全部已勾选时 passed 为 true；返回整份判定与每阶段一条判定 }]
```

## 组织

```viba acceptance_checkpoint_flow
import acceptance_checkpoint
import acceptance_checkpoint_api

AcceptanceCheckpointStartDuty =
  Object
  * $step (acceptance_checkpoint_api.Start * Hint[{ 开始：按清单生成初始进度，全部验收项未勾选 }])
  * $progress (acceptance_checkpoint.AcceptanceCheckpointProgress * Hint[{ 这一步的产物：初始进度 }])

AcceptanceCheckpointCheckDuty =
  Object
  * $step (acceptance_checkpoint_api.CheckItem * Hint[{ 勾选：把一条验收项记为已勾选 }])
  * $progress (acceptance_checkpoint.AcceptanceCheckpointProgress * Hint[{ 这一步的产物：更新后的进度 }])

AcceptanceCheckpointJudgeDuty =
  Object
  * $step (acceptance_checkpoint_api.JudgeGate * Hint[{ 阶段判定：该阶段的验收项是否全部勾选 }])
  * $verdict (acceptance_checkpoint.AcceptanceCheckpointGateVerdict * Hint[{ 这一步的产物：该阶段的判定与未勾选项 }])

AcceptanceCheckpointReviewDuty =
  Object
  * $step (acceptance_checkpoint_api.JudgeChecklist * Hint[{ 整份判定：五个阶段是否全部通过 }])
  * $verdict (acceptance_checkpoint.AcceptanceCheckpointVerdict * Hint[{ 这一步的产物：整份清单的判定与每阶段判定 }])

AcceptanceCheckpointFlow =
  Object
  * $checklist (acceptance_checkpoint.AcceptanceCheckpointChecklist * Hint[{ 问题定义：G0 到 G4 五个阶段的验收项与逐级档位 }])
  * $start (AcceptanceCheckpointStartDuty * Hint[{ 第一步：开始验收 }])
  * $checks (list[AcceptanceCheckpointCheckDuty] * Hint[{ 第二步：逐条勾选，按原清单顺序 }])
  * $judge (AcceptanceCheckpointJudgeDuty * Hint[{ 第三步：逐阶段判定 }])
  * $review (AcceptanceCheckpointReviewDuty * Hint[{ 第四步：判定整份清单 }])
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
