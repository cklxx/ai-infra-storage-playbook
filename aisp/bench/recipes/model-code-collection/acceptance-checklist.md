# 模型代码收集：验收清单

## 背景

这份文档是模型代码收集配方的验收清单，按 G0 能跑、G1 旁路可跑、G2 小规模对齐、G3 逐级 scaling、G4 结论登记五道门列出 15 条验收项。它回答这套配方在每个阶段要满足什么条件才算完成，验收时按门逐条核对。

## 问题

```viba acceptance_collection
import gates

AcceptanceCollectionItem =
  Oneof
  | "g0_candidate_manifest_at_three_times_target" * Hint[{ G0 能跑：候选清单已生成，数量达到目标数量的 3 倍 }]
  | "g0_one_model_runnable_pipeline_completed" * Hint[{ G0 能跑：至少一个模型完成下载、可跑性验证全流程 }]
  | "g0_workspace_images_grouped_by_transformers_major" * Hint[{ G0 能跑：工作区镜像按 transformers 主版本分组完成 }]
  | "g1_mock_process_group_verified" * Hint[{ G1 旁路可跑：mock 进程组已实现，且用已知能跑的模型验证过 mock 返回值正确 }]
  | "g1_fidelity_boundary_filled_with_comm_l1" * Hint[{ G1 旁路可跑：fidelity_boundary 已填写，通信路径标注为 L1 }]
  | "g1_time_sharing_schedule_recorded" * Hint[{ G1 旁路可跑：分时占用的调度方式已记录，标明并发为 1 }]
  | "g2_downstream_metric_versions_match" * Hint[{ G2 小规模对齐：本配方不做 IO 对齐；下游配方引用时的指标版本一致 }]
  | "g2_coverage_script_passed_on_50_models" * Hint[{ G2 小规模对齐：覆盖度计算脚本在 50 个模型的子集上跑通 }]
  | "g3_scaling_deferred_to_scaling_plan" * Hint[{ G3 逐级 scaling：本配方不适用；语料规模扩展由 scaling_plan 的 S0–S2 覆盖 }]
  | "g4_manifest_uploaded_with_sha256" * Hint[{ G4 结论登记：清单已上传，sha256 已记录 }]
  | "g4_coverage_gaps_prioritized" * Hint[{ G4 结论登记：覆盖度清单已生成，缺口已按优先级排序 }]
  | "g4_unknown_code_role_counted_as_gap" * Hint[{ G4 结论登记：无法判定代码角色的样本已计入缺口 }]
  | "g4_unpaired_training_counted_as_gap" * Hint[{ G4 结论登记：未配对训练代码的样本已计入缺口 }]
  | "g4_acceptance_targets_met" * Hint[{ G4 结论登记：可跑率、架构族覆盖、规模覆盖、配对率均达到验收目标 }]
  | "g4_rerun_files_and_sha256_identical" * Hint[{ G4 结论登记：重跑一次，文件集合与 sha256 完全一致 }]

AcceptanceCollectionGate =
  Object
  * $gate (gates.Gate * Hint[{ 阶段门，取值 G0 到 G4；G0 能跑、G1 旁路可跑、G2 小规模对齐、G3 逐级 scaling、G4 结论登记 }])
  * $items (list[AcceptanceCollectionItem] * Hint[{ 这道门的验收项，按原清单顺序 }])

AcceptanceCollectionChecklist =
  Object
  * $target_count (int * Hint[{ 目标数量；候选清单的数量要达到它的 3 倍 }])
  * $gates (list[AcceptanceCollectionGate] * Hint[{ G0 到 G4 五道门，按原清单顺序；G0 有 3 条、G1 有 3 条、G2 有 2 条、G3 有 1 条、G4 有 6 条，共 15 条验收项 }])

AcceptanceCollectionCoverageRun =
  Object
  * $subset_size (int * Hint[{ 这次跑的子集大小；本配方要求 50 个模型 }])
  * $passed (bool * Hint[{ 脚本在这个子集上是否跑通 }])

AcceptanceCollectionItemResult =
  Object
  * $item (AcceptanceCollectionItem * Hint[{ 这条验收项 }])
  * $passed (bool * Hint[{ 这条验收项是否通过；通过时把原清单这一项的方框勾上 }])

AcceptanceCollectionGateResult =
  Object
  * $gate (gates.Gate * Hint[{ 这次验收的门 }])
  * $items (list[AcceptanceCollectionItemResult] * Hint[{ 这道门每条验收项的判定，按原清单顺序 }])
  * $passed (bool * Hint[{ 这道门是否通过；items 全部通过时为真 }])
```

## 基本操作

先验收 G0 能跑：核对候选清单的数量达到目标数量的 3 倍，至少一个模型走完下载与可跑性验证全流程，工作区镜像按 transformers 主版本分好组。再验收 G1 旁路可跑：mock 进程组要已实现并用已知能跑的模型验证过返回值，fidelity_boundary 要填好且通信路径标为 L1，分时占用的调度方式要记录且并发为 1。G2 只核对两件事：本配方不做 IO 对齐、下游配方引用时的指标版本一致，覆盖度计算脚本在 50 个模型的子集上跑通。G3 在本配方不适用，确认语料规模扩展由 scaling_plan 的 S0–S2 覆盖即可。最后验收 G4 结论登记：清单上传并记下 sha256，覆盖度清单的缺口按优先级排好，无法判定代码角色与未配对训练代码的样本都计入缺口，可跑率、架构族覆盖、规模覆盖、配对率达标，重跑一次文件集合与 sha256 完全一致。

## 接口

```viba acceptance_collection_api
import acceptance_collection
import collection
import fidelity
import levels

CheckRunnable =
     acceptance_collection.AcceptanceCollectionGateResult
  <- $entries (list[collection.CollectionManifestEntry] * Hint[{ 候选清单的全部记录；数量要达到目标数量的 3 倍 }])
  <- $target_count (int * Hint[{ 目标数量；候选数量要达到它的 3 倍 }])
  <- Hint[{ 验收 G0 能跑：候选清单数量达到目标数量的 3 倍；至少一条记录同时有下载的文件与可跑性结论；每条记录的工作区都记下 transformers 主版本，分组完成。返回这三条验收项的逐条判定与门的结论 }]

CheckBypass =
     acceptance_collection.AcceptanceCollectionGateResult
  <- $known_runnable (collection.CollectionManifestEntry * Hint[{ 已知能跑的模型；用它跑一次 mock 进程组，核对 mock 返回值 }])
  <- $mock (collection.CollectionRunnableRecord * Hint[{ 这次 mock 进程组验证的记录；backend 为 mock，concurrency 标明为 1 }])
  <- $boundary (list[fidelity.FidelityBoundary] * Hint[{ fidelity_boundary 的全部边界行；通信路径那行的 fidelity 要标注为 L1 }])
  <- Hint[{ 验收 G1 旁路可跑：mock 进程组已实现且用已知能跑的模型验证过返回值正确；fidelity_boundary 已填写且通信路径标注为 L1；分时占用的调度方式已记录且并发为 1。返回这三条验收项的逐条判定与门的结论 }]

CheckAlignment =
     acceptance_collection.AcceptanceCollectionGateResult
  <- $metric_versions (dict[str, str] * Hint[{ 下游配方引用时的指标版本；键是指标名，值是版本，要与本配方 metrics.yaml 里的一致 }])
  <- $coverage (acceptance_collection.AcceptanceCollectionCoverageRun * Hint[{ 覆盖度计算脚本这次运行：子集大小与是否跑通；子集取 50 个模型 }])
  <- Hint[{ 验收 G2 小规模对齐：本配方不做 IO 对齐，只核对下游配方引用时的指标版本一致；覆盖度计算脚本在 50 个模型的子集上跑通。返回这两条验收项的逐条判定与门的结论 }]

CheckScaling =
     acceptance_collection.AcceptanceCollectionGateResult
  <- $plan_levels (list[levels.Level] * Hint[{ scaling_plan 里覆盖语料规模扩展的档位；本配方要求是 S0 到 S2 }])
  <- Hint[{ 验收 G3 逐级 scaling：本配方不适用，语料规模扩展由 scaling_plan 的 S0–S2 覆盖；传入的档位是 S0 到 S2 时这一条通过。返回这条验收项的判定与门的结论 }]

CheckRegistration =
     acceptance_collection.AcceptanceCollectionGateResult
  <- $manifest (collection.CollectionManifest * Hint[{ 已上传的清单；sha256 已记录 }])
  <- $coverage (collection.CollectionCoverage * Hint[{ 覆盖度清单；缺口已按优先级排序，无法判定代码角色与未配对训练代码的样本已计入 }])
  <- $rerun (collection.CollectionManifest * Hint[{ 重跑一次得到的清单；文件集合与 sha256 要和上一次完全一致 }])
  <- Hint[{ 验收 G4 结论登记：清单已上传且 sha256 已记录；覆盖度清单已生成且缺口按优先级排序；无法判定代码角色与未配对训练代码的样本都计入缺口；可跑率、架构族覆盖、规模覆盖、配对率均达到验收目标；重跑一次文件集合与 sha256 完全一致。返回这六条验收项的逐条判定与门的结论 }]
```

## 组织

```viba acceptance_collection_flow
import acceptance_collection
import acceptance_collection_api

AcceptanceCollectionStep =
  Oneof
  | $g0 (acceptance_collection_api.CheckRunnable * Hint[{ 门 G0 能跑：候选清单、下载与可跑性验证、工作区镜像三条验收项 }])
  | $g1 (acceptance_collection_api.CheckBypass * Hint[{ 门 G1 旁路可跑：mock 进程组、fidelity_boundary、分时占用三条验收项 }])
  | $g2 (acceptance_collection_api.CheckAlignment * Hint[{ 门 G2 小规模对齐：下游指标版本一致、覆盖度脚本在 50 个模型子集跑通两条验收项 }])
  | $g3 (acceptance_collection_api.CheckScaling * Hint[{ 门 G3 逐级 scaling：本配方不适用，语料规模扩展由 scaling_plan 的 S0–S2 覆盖 }])
  | $g4 (acceptance_collection_api.CheckRegistration * Hint[{ 门 G4 结论登记：清单上传与 sha256、缺口排序、两类缺口、四项指标、重跑一致六条验收项 }])

AcceptanceCollectionFlow =
  Object
  * $checklist (acceptance_collection.AcceptanceCollectionChecklist * Hint[{ 验收清单：目标数量与 G0 到 G4 五道门的验收项 }])
  * $steps (list[AcceptanceCollectionStep] * Hint[{ 五道门的验收操作，按 G0 到 G4 的顺序 }])
  * $results (list[acceptance_collection.AcceptanceCollectionGateResult] * Hint[{ 每道门各一份判定，按 G0 到 G4 的顺序；items 是这道门各条验收项的结果 }])
  * $accepted (bool * Hint[{ 这套配方是否通过验收；五道门的判定全部通过时为真 }])
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
