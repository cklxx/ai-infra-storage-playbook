# 定位与原则

## public

只做转发：从 `## 问题` 的 `principles` 模块与 `## 接口` 的 `principles_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `PrinciplesSpec`、`PrinciplesSuccessCriterion`、`PrinciplesAcceptance`、`PrinciplesReviewVerdict` 与 `PrinciplesGapRoute`，操作 `AcceptGate`、`ReviewChange` 与 `RouteGap`；先看入口 `PrinciplesSpec` 与验收操作 `AcceptGate`，再看 `ReviewChange`、`RouteGap` 各自交回的 `PrinciplesReviewVerdict` 与 `PrinciplesGapRoute`。

```bash principles_public
import aisp.bench.checkpoint.principles.principles as principles
import aisp.bench.checkpoint.principles.principles_api as principles_api

PrinciplesSpec = principles.PrinciplesSpec
PrinciplesSuccessCriterion = principles.PrinciplesSuccessCriterion
PrinciplesAcceptance = principles.PrinciplesAcceptance
PrinciplesReviewVerdict = principles.PrinciplesReviewVerdict
PrinciplesGapRoute = principles.PrinciplesGapRoute
AcceptGate = principles_api.AcceptGate
ReviewChange = principles_api.ReviewChange
RouteGap = principles_api.RouteGap
```

## 背景

本项目是生成评估集的 playbook：一套配方、指标与流程，产出 AI Infra 存储与传输侧的评估集。一次性的测跑只能回答当前实现有多快，回答不了覆盖是否够、结论是否可外推、覆盖度是否在随时间衰减，所以需要一套持续维护的 benchmark。评估集提供覆盖与外推依据，评估服务负责持续运行，扩展机制负责覆盖度不衰减——三者缺一，闭环就断。

## principles

问题的形式化以 `PrinciplesSpec` 这个 Object 类型为入口：定位、持续维护 benchmark 的理由、评估集关系、边界、硬原则、成功判据与角色分工分别收进 `$positioning`（`PrinciplesPositioning`）、`$benchmark`（`PrinciplesContinuousBenchmark`）、`$eval_sets`（`PrinciplesEvalSetRelation`）、`$scope`（`PrinciplesScope`）、`$hard_principles`（`PrinciplesHardPrinciple` 的列表）、`$success_criteria`（`PrinciplesSuccessCriterion` 的列表）与 `$roles`（`PrinciplesRoles`）七个字段。`PrinciplesSpec` 的中间字段继续展开成 Object 类型：`PrinciplesPositioning` 的 `$parts`、`$questions`、`$output` 分别是 `PrinciplesPart`、`PrinciplesQuestion` 的列表与单个 `PrinciplesEvalSet`；`PrinciplesContinuousBenchmark` 的 `$reasons` 是 `PrinciplesBenchmarkReason` 的列表，`$loop` 是 `PrinciplesClosedLoop`，后者的 `$parts`、`$stages`、`$human` 分别取 `PrinciplesLoopPart`、`PrinciplesLoopStage` 与 `PrinciplesHumanInLoop`，而 `PrinciplesHumanInLoop` 的 `$automatic`、`$reviewed` 又分别取 `PrinciplesAutomatedStep`、`PrinciplesReviewSubject`；`PrinciplesEvalSetRelation` 的 `$source` 是 `PrinciplesModelCodeLibrary`，`$derived` 是 `PrinciplesEvalSet`；`PrinciplesScope` 的 `$included`、`$excluded` 分别是 `PrinciplesIncludedWork`、`PrinciplesExcludedWork` 的列表，`PrinciplesRoles` 的 `$roles`、`$rules` 分别是 `PrinciplesRole`、`PrinciplesRoleRule` 的列表。取值只能落在有限集合里的概念写成 Oneof 枚举：`PrinciplesPart`、`PrinciplesQuestion`、`PrinciplesBenchmarkReason` 表示本项目的组成部分、本项目回答的问题与持续维护 benchmark 的理由，`PrinciplesLoopPart`、`PrinciplesLoopStage`、`PrinciplesAutomatedStep`、`PrinciplesReviewSubject` 表示闭环的组成部分、阶段、自动步骤与人审事项，`PrinciplesEvalSet`、`PrinciplesIncludedWork`、`PrinciplesExcludedWork` 表示评估集类别与范围的两侧，`PrinciplesHardPrinciple`、`PrinciplesSuccessCriterion`、`PrinciplesRole`、`PrinciplesRoleRule` 表示硬原则、成功判据、角色与角色规则，`PrinciplesAcceptVerdict`、`PrinciplesReviewDecision`、`PrinciplesGapKind` 表示验收结论、评审结论与缺口来源。`PrinciplesAcceptance`、`PrinciplesReviewVerdict` 与 `PrinciplesGapRoute` 不在 `PrinciplesSpec` 的字段里，它们复用同一批枚举：`PrinciplesAcceptance` 的 `$eval_set`、`$verdict` 分取 `PrinciplesEvalSet`、`PrinciplesAcceptVerdict`，`$missing` 是 `PrinciplesSuccessCriterion` 的列表，`PrinciplesReviewVerdict` 的 `$subject`、`$decision` 分取 `PrinciplesReviewSubject`、`PrinciplesReviewDecision`，`PrinciplesGapRoute` 的 `$gap` 是 `PrinciplesGap`、`$stages` 是 `PrinciplesLoopStage` 的列表，`PrinciplesGap` 的 `$kind` 取 `PrinciplesGapKind`。

```bash principles
PrinciplesSpec =
  Object
  * $positioning (PrinciplesPositioning * { 定位：本项目是什么、产出什么、回答哪三个问题 })
  * $benchmark (PrinciplesContinuousBenchmark * { 为什么做一套持续维护的 benchmark：一次性的测跑回答不了的三个问题，以及三部分闭环 })
  * $eval_sets (PrinciplesEvalSetRelation * { 三类评估集的关系：模型代码收集库是前置原料库，checkpoint 评估集从库里取样构建 })
  * $scope (PrinciplesScope * { 边界：本项目管什么、不管什么 })
  * $hard_principles (list[PrinciplesHardPrinciple] * { 三条硬原则：计算可以假，IO 必须真；小规模要能对齐，大规模要能外推；结果只回链，不入库 })
  * $success_criteria (list[PrinciplesSuccessCriterion] * { 成功判据：一个评估集算建成了，需要同时满足的五条 })
  * $roles (PrinciplesRoles * { 角色分工，以及兼任与评审回避的规则 })

PrinciplesPositioning =
  Object
  * $parts (list[PrinciplesPart] * { 本项目是生成评估集的 playbook：一套配方、指标与流程 })
  * $output (PrinciplesEvalSet * { 产出：AI Infra 存储与传输侧的评估集 })
  * $questions (list[PrinciplesQuestion] * { 它回答的三个问题：测什么、怎么测、测完怎么让下一版测得更多 })

PrinciplesPart =
  Oneof
  | "recipes" * { 配方：recipes/ 下的配方文件，依赖在 recipe.yaml 里显式声明 }
  | "metrics" * { 指标：口径、阈值、验收标准与校验脚本 }
  | "process" * { 流程：闭环里从评估集到回归的步骤 }

PrinciplesQuestion =
  Oneof
  | "what" * { 测什么 }
  | "how" * { 怎么测 }
  | "next" * { 测完怎么让下一版测得更多 }

PrinciplesContinuousBenchmark =
  Object
  * $reasons (list[PrinciplesBenchmarkReason] * { 一次性的测跑只能回答当前实现有多快，回答不了这三个问题；这三个问题也是需要一套持续维护的 benchmark 的原因 })
  * $loop (PrinciplesClosedLoop * { 三部分闭环：评估集、评估服务、扩展机制 })

PrinciplesBenchmarkReason =
  Oneof
  | "coverage" * { 覆盖是否够：真实模型代码产生的 IO 是长尾的；少数几个旗舰模型覆盖不到分片写入、小文件元数据、跨节点 KV 搬运这些会打垮存储的场景 }
  | "extrapolation" * { 结论是否可外推：单机测出来的结论在十万卡上未必成立，因为聚合带宽、元数据放大、并行策略都在变 }
  | "decay" * { 覆盖度是否在衰减：新模型、新推理框架出现后，bench 若没有机制发现缺口并生成新版本，覆盖度会随时间下降 }

PrinciplesClosedLoop =
  Object
  * $parts (list[PrinciplesLoopPart] * { 闭环的三部分；三者缺一，闭环就断 })
  * $stages (list[PrinciplesLoopStage] * { 闭环按顺序经过的五个阶段；最后一个阶段回到第一个 })
  * $human (PrinciplesHumanInLoop * { 闭环里人的位置：哪些步骤自动，哪些改动要人审核 })

PrinciplesLoopPart =
  Oneof
  | "eval_set" * { 评估集：提供覆盖与外推依据 }
  | "eval_service" * { 评估服务：负责持续运行 }
  | "extension" * { 扩展机制：负责覆盖度不衰减；由 playbook 执行，评估集本身不变 }

PrinciplesLoopStage =
  Oneof
  | "current_set" * { 当前版本的评估集（覆盖度矩阵） }
  | "service_run" * { 评估服务：跑用例 → 产出 IO pattern 与结论 }
  | "gap_analysis" * { 缺口分析：新架构 / 新框架 / 新并行策略 / 未覆盖的 IO 特征 }
  | "new_version" * { playbook 生成新版本：新用例、新配方、新适配层 }
  | "regression" * { 回归：旧用例结论是否仍然成立；结果回到当前版本的评估集 }

PrinciplesHumanInLoop =
  Object
  * $automatic (list[PrinciplesAutomatedStep] * { 自动做的三件事：发现缺口、生成候选用例、回归 })
  * $reviewed (list[PrinciplesReviewSubject] * { 人审核的三类事项：口径变更、阈值调整、任何会让历史结论不可比的改动 })

PrinciplesAutomatedStep =
  Oneof
  | "find_gaps" * { 自动发现缺口 }
  | "generate_candidates" * { 自动生成候选用例 }
  | "regress" * { 自动回归 }

PrinciplesReviewSubject =
  Oneof
  | "metric_change" * { 口径变更 }
  | "threshold_change" * { 阈值调整 }
  | "incomparable_change" * { 任何会让历史结论不可比的改动 }

PrinciplesEvalSetRelation =
  Object
  * $source (PrinciplesModelCodeLibrary * { 前置原料库：模型代码收集库 })
  * $derived (PrinciplesEvalSet * { 从原料库取样构建的评估集：checkpoint 存储评估集（训练侧） })
  * $recipe (str * { 声明这条依赖的配方文件：recipes/checkpoint/recipe.yaml })
  * $dependency (str * { 配方里必须写的依赖：depends_on: recipes/model_code_collection })
  * $pending (list[PrinciplesEvalSet] * { dataset 与 kvcache 评估集待做（TODO） })

PrinciplesModelCodeLibrary =
  Object
  * $inference_models (str * { 推理模型代码，1000+，尽量配对训练代码 })
  * $diversity (str * { 结构去重后的多样性覆盖 })
  * $mock_group (str * { mock process group 可跑性验证 })

PrinciplesEvalSet =
  Oneof
  | "checkpoint" * { checkpoint 存储评估集（训练侧）；从模型代码收集库取样构建 }
  | "dataset" * { dataset 评估集；待做（TODO） }
  | "kvcache" * { kvcache 评估集；待做（TODO） }

PrinciplesScope =
  Object
  * $included (list[PrinciplesIncludedWork] * { 本项目管什么 })
  * $excluded (list[PrinciplesExcludedWork] * { 本项目不管什么，每条带原因 })

PrinciplesIncludedWork =
  Oneof
  | "model_code" * { 模型代码的收集、去重、可跑性验证方法 }
  | "checkpoint" * { 训练侧 checkpoint 的存储评估方法；dataset 与 kvcache 待做（TODO） }
  | "bypass" * { 旁路计算、保留 IO 的通用方法，以及保真程度的登记方式 }
  | "scaling" * { 小规模对齐与 scaling 外推的方法 }
  | "service" * { 评估服务的接口、调度、结果回链规范 }
  | "extension" * { playbook 扩展评估集的触发条件、缺口分析、审核边界 }
  | "metrics" * { 指标口径、阈值、验收标准与校验脚本 }

PrinciplesExcludedWork =
  Oneof
  | "performance_tuning" * { 模型训练与推理的性能调优。原因：那是被评估对象，不是评估设施 }
  | "kernel_optimization" * { 计算 kernel 优化。原因：与存储传输侧的 IO 无关 }
  | "hardware_selection" * { 存储硬件选型。原因：硬件选型的输入来自评估结论，选型决策不在这里做 }
  | "production_ops" * { 生产集群运维。原因：评估集群与生产集群是两套环境 }
  | "report_archival" * { 一次性 benchmark 报告的归档。原因：报告是运行产物，只回链，不入库 }
  | "raw_assets" * { 原始数据集、模型权重、checkpoint。原因：体积与权限都不适合放进仓库 }

PrinciplesHardPrinciple =
  Oneof
  | "fake_compute_real_io" * { 计算可以假，IO 必须真。评估的目的是存储传输侧；计算部分（forward、backward、optimizer、prefill、decode）对 IO 的贡献只有「什么时候发起」和「发起多少」，不贡献请求本身的特征，所以计算可以被旁路。但发起 IO 的那条代码路径必须保持原样：真实的数据加载、真实的 checkpoint 写入、真实的通信原语调用。旁路了哪些、保留了什么、带来了什么偏差，逐项登记在配方的「保真边界表」里；没有登记表的配方视为未完成 }
  | "align_then_extrapolate" * { 小规模要能对齐，大规模要能外推。小规模上跑出来的 IO pattern 必须能和同等规模的真实运行对上，否则后面的外推没有依据；大规模结论必须由逐级验证得到，不允许从小规模直接跳到十万卡给结论。外推的依据是 scaling 不变量：一组在放大过程中应保持稳定的 IO 特征；不变量选得对不对，决定了外推结论是否可信 }
  | "link_only" * { 结果只回链，不入库。仓库里永远只有配方、指标、阈值、校验脚本、模板，以及指向外部产物的 URI、sha256、状态；任何一次运行的大报告、trace、日志、产物都放在对象存储或 CI artifact 里。判断标准：删掉外部存储里的所有产物，本项目应当仍然完整、仍然能重新跑出结论；如果删不掉，说明仓库里混进了不该放的东西 }

PrinciplesSuccessCriterion =
  Oneof
  | "reproducible" * { 配方能被另一个人照着跑通，不需要口口相传的隐含步骤 }
  | "aligned" * { 小规模结果与真实运行在声明的容差内对齐 }
  | "scaling_validated" * { scaling 不变量在每一级都验证过，且偏差有归因 }
  | "gaps_registered" * { 覆盖度矩阵上有明确的空白格子，且空白格子被登记为待补，而不是被忽略 }
  | "loop_proven" * { 至少一个真实缺口是由评估服务发现、并驱动 playbook 生成新版本补上的；这条衡量的是闭环是否真的转起来了 }

PrinciplesRoles =
  Object
  * $roles (list[PrinciplesRole] * { 四类角色 })
  * $rules (list[PrinciplesRoleRule] * { 兼任与评审回避的规则 })

PrinciplesRole =
  Oneof
  | "recipe_maintainer" * { 配方维护者：负责单个评估集的正确性与可复现性 }
  | "metric_maintainer" * { 指标维护者：负责 metrics/ 的口径一致，历史结果可比 }
  | "service_maintainer" * { 服务维护者：负责评估服务的调度、结果存储、回链完整性 }
  | "reviewer" * { 评审者：负责口径可实现、阈值有依据、结论可外推 }

PrinciplesRoleRule =
  Oneof
  | "allow_concurrent" * { 角色可以由同一人兼任 }
  | "no_self_review" * { 改口径的人不能是自己评审自己 }

PrinciplesAcceptance =
  Object
  * $eval_set (PrinciplesEvalSet * { 被验收的评估集 })
  * $verdict (PrinciplesAcceptVerdict * { 建成或未建成 })
  * $missing (list[PrinciplesSuccessCriterion] * { 未满足的成功判据；建成时为空 })

PrinciplesAcceptVerdict =
  Oneof
  | "built" * { 五条成功判据全部满足，这个评估集算建成 }
  | "not_built" * { 至少一条成功判据未满足，这个评估集还不算建成 }

PrinciplesReviewVerdict =
  Object
  * $subject (PrinciplesReviewSubject * { 这次评审针对的改动 })
  * $role (PrinciplesRole * { 承担评审的角色：评审者，负责口径可实现、阈值有依据、结论可外推 })
  * $decision (PrinciplesReviewDecision * { 评审结论：允许或禁止 })

PrinciplesReviewDecision =
  Oneof
  | "allowed" * { 评审通过：评审者不是提出改动的人 }
  | "self_review_forbidden" * { 评审不通过：改口径的人不能是自己评审自己 }

PrinciplesGap =
  Object
  * $cell ((str | nil) * { 缺口在覆盖度矩阵上的位置：空白格子；没有具体格子时给 nil })
  * $kind (PrinciplesGapKind * { 缺口从哪来：新架构、新框架、新并行策略、未覆盖的 IO 特征 })
  * $discovered_by_service (bool * { 这个缺口是不是由评估服务发现的；成功判据要求至少一个真实缺口由评估服务发现、并驱动 playbook 生成新版本 })

PrinciplesGapKind =
  Oneof
  | "new_architecture" * { 新架构 }
  | "new_framework" * { 新框架 }
  | "new_parallel_strategy" * { 新并行策略 }
  | "uncovered_io_feature" * { 未覆盖的 IO 特征 }

PrinciplesGapRoute =
  Object
  * $gap (PrinciplesGap * { 要回流的缺口 })
  * $stages (list[PrinciplesLoopStage] * { 缺口在闭环里经过的阶段：从缺口分析开始，经 playbook 生成新版本、回归，最后回到当前版本的评估集 })
```

## 基本操作

验收（AcceptGate）判断一个评估集算不算建成：按成功判据逐条对照，五条全部满足才算建成，缺哪条返回哪条。

1. 评审（ReviewChange）时按 no_self_review 规则检查评审者：角色可以由同一人兼任，但改口径的人不能是自己评审自己。
2. 回流（RouteGap）把缺口交回闭环：缺口从覆盖度矩阵的空白格子或新架构、新框架、新并行策略、未覆盖的 IO 特征进入，经缺口分析、playbook 生成新版本、回归，回到当前版本的评估集。

## principles_api

```bash principles_api
import aisp.bench.checkpoint.principles.principles as principles

AcceptGate =
     principles.PrinciplesAcceptance
  <- $eval_set (principles.PrinciplesEvalSet * { 被判断是否算建成的评估集 })
  <- $satisfied (list[principles.PrinciplesSuccessCriterion] * { 已经满足的成功判据；未列出的判据视为未满足 })
  <- { 验收：拿五条成功判据逐条对照。五条全部满足才算建成；返回结论与缺的判据 }

ReviewChange =
     principles.PrinciplesReviewVerdict
  <- $subject (principles.PrinciplesReviewSubject * { 要评审的改动：口径变更、阈值调整、任何会让历史结论不可比的改动 })
  <- $author (str * { 提出改动的人 })
  <- $reviewer (str * { 准备评审这次改动的人 })
  <- { 评审：这次改动由评审者评审，并按 no_self_review 规则检查评审者是不是提出改动的人。同一个人提出又评审时返回 self_review_forbidden，否则返回 allowed，同时带上这次评审针对的改动与承担评审的角色 }

RouteGap =
     principles.PrinciplesGapRoute
  <- $gap (principles.PrinciplesGap * { 要回流的缺口：覆盖度矩阵上的空白格子，或新架构、新框架、新并行策略、未覆盖的 IO 特征 })
  <- { 回流：把缺口交给闭环。缺口从缺口分析进入，经 playbook 生成新版本、回归，最后回到当前版本的评估集；返回缺口与它经过的阶段 }
```

## principles_flow

```bash principles_flow
import aisp.bench.checkpoint.principles.principles as principles
import aisp.bench.checkpoint.principles.principles_api as principles_api

PrinciplesAcceptDuty =
  Object
  * $step (principles_api.AcceptGate * { 验收：判断一个评估集算不算建成 })
  * $criteria (list[principles.PrinciplesSuccessCriterion] * { 这一步逐条比对的五条成功判据 })

PrinciplesReviewDuty =
  Object
  * $step (principles_api.ReviewChange * { 评审：判断一次改动由谁来评、能不能评 })
  * $subjects (list[principles.PrinciplesReviewSubject] * { 这一步覆盖的三类改动：口径变更、阈值调整、任何会让历史结论不可比的改动 })

PrinciplesRouteDuty =
  Object
  * $step (principles_api.RouteGap * { 回流：把缺口交回闭环 })
  * $stages (list[principles.PrinciplesLoopStage] * { 缺口在闭环里经过的阶段 })

PrinciplesFlow =
  Object
  * $spec (principles.PrinciplesSpec * { 问题定义：定位、为什么做持续维护的 benchmark、评估集关系、边界、硬原则、成功判据、角色 })
  * $loop (principles.PrinciplesClosedLoop * { 闭环：评估集、评估服务、扩展机制三部分缺一就断 })
  * $accept (PrinciplesAcceptDuty * { 第一项职责：验收一个评估集算不算建成 })
  * $review (PrinciplesReviewDuty * { 第二项职责：评审口径、阈值与不可比改动 })
  * $route (PrinciplesRouteDuty * { 第三项职责：把缺口回流到闭环 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
