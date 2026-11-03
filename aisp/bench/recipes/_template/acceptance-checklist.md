# 验收清单模板

## public

只做转发：从 `## 问题` 的 `acceptance_template` 模块与 `## 接口` 的 `acceptance_template_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `AcceptanceTemplate`、`AcceptanceTemplateItem`、`AcceptanceTemplateRecord`、`AcceptanceTemplateGateReview` 与 `AcceptanceTemplateAdmission`，操作 `CheckItem`、`ReviewGate` 与 `EnterGate`；先看 `AcceptanceTemplate` 与 `AcceptanceTemplateItem`，再看 `CheckItem` 与 `AcceptanceTemplateRecord`，最后看 `ReviewGate`、`AcceptanceTemplateGateReview`、`EnterGate` 与 `AcceptanceTemplateAdmission`。

```viba acceptance_template_public
import acceptance_template
import acceptance_template_api

AcceptanceTemplate = acceptance_template.AcceptanceTemplate
AcceptanceTemplateItem = acceptance_template.AcceptanceTemplateItem
AcceptanceTemplateRecord = acceptance_template.AcceptanceTemplateRecord
AcceptanceTemplateGateReview = acceptance_template.AcceptanceTemplateGateReview
AcceptanceTemplateAdmission = acceptance_template.AcceptanceTemplateAdmission
CheckItem = acceptance_template_api.CheckItem
ReviewGate = acceptance_template_api.ReviewGate
EnterGate = acceptance_template_api.EnterGate
```

## 背景

这份文档是验收清单模板，按 G0 到 G4 五道门逐条列出要勾的验收项。每道门都要勾，未勾选的门不允许进入下一道门；勾选时附上回链或证据位置。

## 问题

问题形式化为 `acceptance_template` 模块，概念分成类型与枚举两类。清单结构写成 Object 类型：`AcceptanceTemplate` 是整份验收清单，`$gates` 收按 G0 到 G4 排列的 `AcceptanceTemplateGateChecklist`，每个 `AcceptanceTemplateGateChecklist` 把 `gates.Gate` 的一个取值与这道门的 `AcceptanceTemplateItem` 的列表配成一对；`AcceptanceTemplateRecord` 的 `$checks` 收已经勾过的 `AcceptanceTemplateCheck`，`AcceptanceTemplateGateReview` 汇总某道门里已勾选与未勾选的验收项，并给出这道门是否勾完的判定。取值只能落在有限集合里的概念写成 Oneof 枚举：`AcceptanceTemplateItem` 是可勾的验收项，`AcceptanceTemplateCheckState` 是未勾选与已勾选两种状态，`AcceptanceTemplateEvidence` 是回链或证据位置，`AcceptanceTemplateAdmission` 是进入某道门的结果。关联落在字段上：`AcceptanceTemplateCheck` 的 `$item` 取 `AcceptanceTemplateItem`、`$state` 取 `AcceptanceTemplateCheckState`，`AcceptanceTemplateCheckState` 的 `$checked` 分支携带一个 `AcceptanceTemplateEvidence`；`AcceptanceTemplateAdmission` 的 `$allowed` 分支携带允许进入的那道 `gates.Gate`，`$blocked` 分支携带造成拒绝的 `AcceptanceTemplateGateReview` 列表。

```viba acceptance_template
import gates

AcceptanceTemplateItem =
  Oneof
  | "g0_runs_without_bypass" * { G0 能跑：不旁路的状态下，目标代码能跑完一次前向或一次预填充 }
  | "g0_run_config_recorded" * { G0 能跑：运行配置已记录（模型 commit、框架版本、依赖 lock、拓扑） }
  | "g0_minimal_config_repeatable" * { G0 能跑：最小可运行配置已写成文件，能重复执行 }
  | "g1_bypass_runs_same_flow" * { G1 旁路可跑：旁路实现后能跑完与 G0 相同的流程 }
  | "g1_fidelity_boundary_filled" * { G1 旁路可跑：recipe.yaml 的 fidelity_boundary 已逐行填写，无空字段 }
  | "g1_storage_and_transfer_not_l0" * { G1 旁路可跑：存储与传输路径的 fidelity 均不为 L0 }
  | "g1_known_bias_direction" * { G1 旁路可跑：known_bias 已写明偏差方向 }
  | "g2_real_and_bypass_runs" * { G2 小规模对齐：真实运行与旁路运行各完成一次，观测配置相同 }
  | "g2_byte_deviation_within_one_percent_or_explained" * { G2 小规模对齐：应用层与系统层总字节数偏差 ≤ 1%，或偏差已解释 }
  | "g2_observation_overhead_within_three_percent" * { G2 小规模对齐：观测开销单独测量，关键指标变化 ≤ 3% }
  | "g2_all_alignment_items_within_tolerance_or_attributed" * { G2 小规模对齐：全部对齐分项在容差内，或偏差已归因并经评审 }
  | "g2_alignment_report_linked" * { G2 小规模对齐：对齐报告已上传并回链 }
  | "g3_complete_metrics_each_level" * { G3 逐级 scaling：每一级都有完整度量，不是只测带宽 }
  | "g3_invariant_adjacent_deviation_within_tolerance" * { G3 逐级 scaling：每条不变量的相邻级偏差在容差内 }
  | "g3_no_monotonic_regression" * { G3 逐级 scaling：无不变量单调恶化 }
  | "g3_nonlinearity_investigated" * { G3 逐级 scaling：非线性来源已排查，偏差归因已写 }
  | "g3_next_level_prediction_written" * { G3 逐级 scaling：下一级预测值与预测依据已写 }
  | "g4_latest_run_written" * { G4 结论登记：latest_run 已由评估服务写入，回链三要素齐全 }
  | "g4_coverage_matrix_updated" * { G4 结论登记：覆盖度矩阵已更新 }
  | "g4_remaining_biases_logged" * { G4 结论登记：未解决的偏差已登记进 playbook/pitfalls.md }
  | "g4_versions_consistent" * { G4 结论登记：配方版本、指标版本、服务版本一致且可查 }

AcceptanceTemplateEvidence =
  Oneof
  | $backlink (str * { 勾选时附上的回链 })
  | $evidence_location (str * { 勾选时附上的证据位置 })

AcceptanceTemplateCheckState =
  Oneof
  | $unchecked (nil * { 未勾选；未勾选的门不允许进入下一道门 })
  | $checked (AcceptanceTemplateEvidence * { 已勾选，并附上回链或证据位置 })

AcceptanceTemplateCheck =
  Object
  * $item (AcceptanceTemplateItem * { 勾的是哪一条验收项 })
  * $state (AcceptanceTemplateCheckState * { 这条验收项是否已经勾选；勾选时带上的回链或证据位置 })

AcceptanceTemplateRecord =
  Object
  * $checks (list[AcceptanceTemplateCheck] * { 已经勾过的验收项各一条；没有勾的项不在这里，按未勾选处理 })

AcceptanceTemplateGateChecklist =
  Object
  * $gate (gates.Gate * { 这道门；五道门按 G0 到 G4 的顺序推进 })
  * $items (list[AcceptanceTemplateItem] * { 这道门要勾的验收项，按清单原顺序；每项一条，逐条勾选 })

AcceptanceTemplate =
  Object
  * $gates (list[AcceptanceTemplateGateChecklist] * { 五道门与各自的验收项，按 G0 到 G4 排列；每道门都要勾 })

AcceptanceTemplateGateReview =
  Object
  * $gate (gates.Gate * { 复核的是哪一道门 })
  * $checked (list[AcceptanceTemplateItem] * { 这道门里已经勾选的验收项 })
  * $unchecked (list[AcceptanceTemplateItem] * { 这道门里还没勾选的验收项；有任意一条时这道门不算勾完，不允许进入下一道门 })
  * $complete (bool * { 这道门是否全部勾选；为 true 才允许进入下一道门 })

AcceptanceTemplateAdmission =
  Oneof
  | $allowed (gates.Gate * { 允许进入这道门；它前面的每一道门都已全部勾选 })
  | $blocked (list[AcceptanceTemplateGateReview] * { 不允许进入：前面存在未勾完的门，每道这样的门一条复核结果 })
```

## 基本操作

解决这个问题需要三个操作。每道门都要勾，未勾选的门不允许进入下一道门。勾选（CheckItem）：把一条验收项记为已勾选，并附上回链或证据位置，写进勾选记录。复核（ReviewGate）：对照某道门的验收项，列出已勾选与未勾选的项，并判定这道门是否全部勾选。进入（EnterGate）：按 G0 到 G4 的顺序申请进入一道门，G0 直接允许，其余门要求前面的每一道门都已勾完，有未勾完的门就拒绝并交回这些门的复核结果。

## 接口

```viba acceptance_template_api
import acceptance_template
import gates

CheckItem =
     acceptance_template.AcceptanceTemplateRecord
  <- $record (acceptance_template.AcceptanceTemplateRecord * { 当前已登记的全部勾选记录 })
  <- $item (acceptance_template.AcceptanceTemplateItem * { 要勾的那一条验收项 })
  <- $evidence (acceptance_template.AcceptanceTemplateEvidence * { 勾选时附上的回链或证据位置 })
  <- { 勾选一条验收项：把这一项记为已勾选，并附上回链或证据位置，写进勾选记录；返回更新后的勾选记录。所属门是否勾完由复核判定 }

ReviewGate =
     acceptance_template.AcceptanceTemplateGateReview
  <- $checklist (acceptance_template.AcceptanceTemplateGateChecklist * { 要复核的那道门与这道门的验收项 })
  <- $record (acceptance_template.AcceptanceTemplateRecord * { 当前已登记的全部勾选记录 })
  <- { 复核一道门：对照这道门的验收项，列出已勾选与未勾选的项，并判定这道门是否全部勾选；有任意一条未勾选时 complete 为 false，不允许进入下一道门 }

EnterGate =
     acceptance_template.AcceptanceTemplateAdmission
  <- $template (acceptance_template.AcceptanceTemplate * { 五道门与各自的验收项，按 G0 到 G4 排列 })
  <- $record (acceptance_template.AcceptanceTemplateRecord * { 当前已登记的全部勾选记录 })
  <- $gate (gates.Gate * { 要进入的那道门 })
  <- { 进入一道门：G0 直接允许；其余门要求它前面的每一道门 complete，有未勾完的门就拒绝，并交回这些门的复核结果 }
```

## 组织

```viba acceptance_template_flow
import acceptance_template
import acceptance_template_api

AcceptanceTemplateCheckStep =
  Object
  * $step (acceptance_template_api.CheckItem * { 勾选：把一条验收项记为已勾选，并附上回链或证据位置 })
  * $check (acceptance_template.AcceptanceTemplateCheck * { 这一步的产物：一条勾选记录 })

AcceptanceTemplateReviewStep =
  Object
  * $step (acceptance_template_api.ReviewGate * { 复核：对照某道门的验收项，判定这道门是否全部勾选 })
  * $review (acceptance_template.AcceptanceTemplateGateReview * { 这一步的产物：已勾选与未勾选的项，以及这道门是否全部勾选 })

AcceptanceTemplateEnterStep =
  Object
  * $step (acceptance_template_api.EnterGate * { 进入：按门的顺序申请进入，拒绝时交回未勾完的门的复核结果 })
  * $admission (acceptance_template.AcceptanceTemplateAdmission * { 这一步的产物：允许进入，或拒绝并给出前面未勾完的门的复核结果 })

AcceptanceTemplateFlow =
  Object
  * $template (acceptance_template.AcceptanceTemplate * { 问题定义：五道门与各自的验收项，按 G0 到 G4 排列 })
  * $record (acceptance_template.AcceptanceTemplateRecord * { 已经登记的全部勾选记录 })
  * $check (AcceptanceTemplateCheckStep * { 第一步：勾选一条验收项 })
  * $review (AcceptanceTemplateReviewStep * { 第二步：复核这道门是否全部勾选 })
  * $enter (AcceptanceTemplateEnterStep * { 第三步：按顺序进入下一道门 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
