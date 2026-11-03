# 贡献规范

## public

只做转发：从 `## 问题` 的 `contributing` 模块与 `## 接口` 的 `contributing_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `ContributingReview`、`ContributingRecipe`、`ContributingMetricRegistration` 与 `ContributingCheckResult`，操作 `CreateRecipe`、`RegisterMetric`、`WriteDecision` 与 `RunChecks`；先看 `ContributingReview` 与 `ContributingRecipe`，再按 `CreateRecipe`、`RegisterMetric`、`WriteDecision`、`RunChecks` 的顺序读，`ContributingMetricRegistration` 与 `ContributingCheckResult` 分别是登记指标的入参和跑校验的返回项。

```bash contributing_public
import aisp.bench.contributing.contributing as contributing
import aisp.bench.contributing.contributing_api as contributing_api

ContributingReview = contributing.ContributingReview
ContributingRecipe = contributing.ContributingRecipe
ContributingMetricRegistration = contributing.ContributingMetricRegistration
ContributingCheckResult = contributing.ContributingCheckResult
CreateRecipe = contributing_api.CreateRecipe
RegisterMetric = contributing_api.RegisterMetric
WriteDecision = contributing_api.WriteDecision
RunChecks = contributing_api.RunChecks
```

## 背景

本项目的主体是文档与配方，改动的影响面比代码仓库大：一条错误的验收口径会让下游所有评估结论失效。这份文档写给要动手改这个仓库的人，管三件事：新增一个评估集配方、修改一个指标口径、把一次会长期影响口径的取舍记成决策记录。它说明这三件事各要改哪些文件、写哪些字段、跑哪些校验，以及哪些改动可以直接提、哪些必须先走评审。

## contributing

这一节把贡献流程形式化为一组 viba 类型：改动先由枚举 `ContributingChangeKind` 分类，`ContributingReview` 以它的取值作为 `kind`，并记录各项确认与受影响的清单。配方一侧有两个枚举，`ContributingRecipeFileKind` 说明要填哪一份文件，`ContributingRecipeRequiredField` 列出 `recipe.yaml` 里不允许留空的项；`ContributingRecipeFile` 把一份文件的种类、位置与内容绑在一起，`ContributingRecipe` 再聚合文件列表、必填项列表、`notes` 与 `changelog`。指标一侧，`ContributingMetricVersion` 是版本号的别名，`ContributingMetricRegistration` 聚合弃用信息 `ContributingMetricDeprecation` 与一组 `ContributingTolerance`。决策记录与校验结果各是一个类型，`ContributingDecision` 的分类取枚举 `ContributingDecisionKind`，`ContributingCheckResult` 的检查项与执行范围则取枚举 `ContributingCheckItem` 与 `ContributingCheckScope`。

```bash contributing

ContributingChangeKind =
  Oneof
  | "small_change" * { 可以小步改的内容：措辞、链接、排版、英文拼写；已有文档里补充例子、补充已知坑；修正事实错误，例如某个框架的接口已经改名。直接提改动即可，评审看两件事：是否与实际行为一致，是否与其它文档的口径冲突 }
  | "must_review" * { 必须走评审的内容：修改任何指标口径、阈值、验收标准（metrics/、recipes/*/metrics.yaml）；新增或删除一个评估集配方（recipes/）；修改 checkpoint/methodology.md 中保真边界表或 IO pattern 度量项的定义；修改 schemas/；修改 meta-evaluation/playbook-metrics.yaml 的指标定义。改 methodology 那两处等于改三类评估集的共同定义，评审时要说明影响哪些配方、哪些历史结论失效 }

ContributingReview =
  Object
  * $kind (ContributingChangeKind * { 这次改动属于哪一类；两类流程不同，小步改直接提，必须走评审的先评审再提 })
  * $metric_feasibility_confirmed (bool * { 是否已有一位熟悉存储侧的人确认口径可实现；只对必须走评审的改动要求 })
  * $threshold_calibration_confirmed (bool * { 是否已有一位实际跑过评估的人确认阈值有标定依据；只对必须走评审的改动要求 })
  * $affected_recipes (list[str] * { 这次改动影响哪些配方；改 checkpoint/methodology.md 的保真边界表或 IO pattern 度量项定义时必须写 })
  * $invalidated_conclusions (list[str] * { 这次改动让哪些历史结论失效；改 checkpoint/methodology.md 的保真边界表或 IO pattern 度量项定义时必须写 })
  * { 两位评审人的确认缺一项不算评审通过：至少一位熟悉存储侧的人确认口径可实现，至少一位实际跑过评估的人确认阈值有标定依据 }

ContributingRecipeFileKind =
  Oneof
  | "recipe_yaml" * { recipes/<name>/recipe.yaml：bypass、fidelity_boundary、io_pattern_invariants、scaling_plan 四项不允许留空，理由写在 notes 里；目录从 recipes/_template/ 复制得到 }
  | "metrics_yaml" * { recipes/<name>/metrics.yaml：只选 metrics/registry.yaml 已登记的指标；阈值写在 tolerance，键必须是 check 支持的度量项名；需要新指标时先加文档与登记表，再走评审 }
  | "readme" * { recipes/<name>/README.md：目标、输入、输出、步骤、验收标准、负责人；步骤要能照着做，不写"参考某某实现" }
  | "checks" * { recipes/<name>/checks/：本配方专属校验，由该配方自己的 CI 任务运行；通用校验放 aisp/bench/checks/，scripts/run_checks.py 只跑通用校验 }

ContributingRecipeFile =
  Object
  * $kind (ContributingRecipeFileKind * { 哪一份 })
  * $path (str * { 位置：recipes/<name>/recipe.yaml、recipes/<name>/metrics.yaml、recipes/<name>/README.md、recipes/<name>/checks/ })
  * $content (str * { 这一份必须写清的内容；按 kind 的说明逐项写，写完再跑校验 })

ContributingRecipeRequiredField =
  Oneof
  | "bypass" * { recipe.yaml 的 bypass：不允许留空 }
  | "fidelity_boundary" * { recipe.yaml 的 fidelity_boundary：不允许留空 }
  | "io_pattern_invariants" * { recipe.yaml 的 io_pattern_invariants：不允许留空 }
  | "scaling_plan" * { recipe.yaml 的 scaling_plan：不允许留空 }

ContributingRecipe =
  Object
  * $name (str * { 评估集名；目录名用小写连字符，例如 recipes/checkpoint/ })
  * $files (list[ContributingRecipeFile] * { 配方的四份内容：recipe.yaml、metrics.yaml、README.md、checks/；从 recipes/_template/ 复制得到，逐份填写 })
  * $required_fields (list[ContributingRecipeRequiredField] * { recipe.yaml 里不允许留空的四项；四项都要有取值 })
  * $notes (str * { recipe.yaml 的 notes：四项取值的理由写在这里 })
  * $changelog (str * { CHANGELOG.md：在 Unreleased 下加的一行 })

ContributingMetricVersion = str * { 指标口径的版本号；改口径时新口径用新版本号 }

ContributingMetricDeprecation =
  Object
  * $deprecated_version (ContributingMetricVersion * { 被弃用的版本 })
  * $reason (str * { 旧口径为什么不可用；写在 metrics/<name>.md 里保留的旧口径一节 })
  * $replacement_version (ContributingMetricVersion * { 新口径的版本号 })
  * { 能新增指标就不改旧指标；必须改旧指标时才用这一项，旧口径在 metrics/<name>.md 里保留一节，标注弃用版本与原因 }

ContributingTolerance =
  Object
  * $key (str * { 度量项名；键必须是 check 支持的度量项名 })
  * $value (float * { 阈值 })
  * $file (str * { 阈值只写在 recipes/<name>/metrics.yaml 的 tolerance；check 脚本读取同一份文件，禁止在代码或文档里另留一份执行值 })

ContributingMetricRegistration =
  Object
  * $name (str * { 指标名；对应 metrics/<name>.md 与 metrics/registry.yaml 里的登记项 })
  * $doc (str * { 指标文档 metrics/<name>.md：口径写在这里，改口径时旧口径保留一节 })
  * $version (ContributingMetricVersion * { 当前版本 })
  * $deprecation ((ContributingMetricDeprecation | nil) * { 改的是旧指标时写弃用信息；新增指标给 nil })
  * $tolerance (list[ContributingTolerance] * { 阈值，一项一个度量项名；只写在 recipes/<name>/metrics.yaml 的 tolerance })
  * $compatible_metrics (list[ContributingMetricVersion] * { 配方的 compatible_metrics 里为该指标列出的版本；改口径时要同步更新所有引用该指标的 recipes/*/metrics.yaml })
  * { 只选 metrics/registry.yaml 已登记的指标；需要新指标时先在 metrics/ 写文档、在 metrics/registry.yaml 登记，再走评审 }

ContributingDecisionKind =
  Oneof
  | "bypass_choice" * { 选择了某种旁路手段而排除了另一种 }
  | "scaling_invariant" * { 定义了新的 scaling 不变量，或放弃某个不变量 }
  | "version_binding" * { 评估集版本与评估服务版本如何绑定 }
  | "incomparable_change" * { 任何会导致历史结果不可比的改动 }

ContributingDecision =
  Object
  * $number (int * { 编号，递增 })
  * $slug (str * { 短描述；文件名是 NNNN-短描述.md，放在 decisions/ 下 })
  * $kind (ContributingDecisionKind * { 这条记录属于哪一类必须写 ADR 的情况；日常改动不写在这里 })
  * $background (str * { 背景：为什么要做这个决定 })
  * $candidates (list[str] * { 候选：被考虑过的选项，一项一个 })
  * $decision (str * { 决定：选了哪个 })
  * $consequences (str * { 后果：这个决定带来什么 })
  * { 模板见 decisions/README.md；写清楚背景、候选、决定、后果，不写过程流水账 }

ContributingCheckScope =
  Oneof
  | "general" * { 通用校验：放 aisp/bench/checks/，由 scripts/run_checks.py 跑，只跑这一部分 }
  | "recipe" * { 本配方专属校验：放 recipes/<name>/checks/，由该配方自己的 CI 任务跑 }

ContributingCheckItem =
  Oneof
  | "required_fields_not_empty" * { recipe.yaml 的 bypass、fidelity_boundary、io_pattern_invariants、scaling_plan 四项都不留空，理由写在 notes 里 }
  | "metric_registered" * { metrics.yaml 里的指标都在 metrics/registry.yaml 登记过 }
  | "tolerance_supported_key" * { tolerance 的键都是 check 支持的度量项名 }
  | "tolerance_single_copy" * { 阈值只出现在 recipes/<name>/metrics.yaml 的 tolerance，代码与文档里没有第二份执行值 }
  | "examples_expectation" * { 本地运行 python3 scripts/run_checks.py 时含 selftest 负例，examples/ 与 examples/invalid/ 都要符合预期 }
  | "two_reviewers" * { 必须走评审的改动有两位评审人的确认：一位熟悉存储侧的人确认口径可实现，一位实际跑过评估的人确认阈值有标定依据 }
  | "no_internal_details" * { 文档里没有具体集群规模、卡数、节点数、机房位置；没有内部系统名、内部框架名、内部服务地址、内部存储桶名；没有客户与业务模型清单、未公开的模型参数与发布计划；没有具体的人名与组织名。需要描述规模时用档位（单机、双机、百卡、千卡、万卡、十万卡），需要举例时用 example/ 这类占位标识；已经写进去的具体数字直接删，不留"某规模"这样的模糊替代 }

ContributingCheckResult =
  Object
  * $item (ContributingCheckItem * { 哪一项检查 })
  * $scope (ContributingCheckScope * { 这一项由谁跑：通用校验由 scripts/run_checks.py 跑，配方专属校验由该配方自己的 CI 任务跑 })
  * $detail (str * { 没有通过时写清缺的是什么；通过时写检查到的文件与目录 })
```

## 基本操作

新增一个配方，先把 `recipes/_template/` 复制成 `recipes/<name>/`，目录名用小写连字符，例如 `recipes/checkpoint/`，然后填四份内容：`recipe.yaml` 的 `bypass`、`fidelity_boundary`、`io_pattern_invariants`、`scaling_plan` 四项不允许留空、理由写在 `notes` 里；`metrics.yaml` 只选 `metrics/registry.yaml` 已登记的指标，阈值写在 `tolerance`、键必须是 check 支持的度量项名；`README.md` 写目标、输入、输出、步骤、验收标准与负责人，步骤要能照着做，不写"参考某某实现"；本配方专属校验放 `recipes/<name>/checks/`，由该配方自己的 CI 任务运行，通用校验放 `aisp/bench/checks/`，`scripts/run_checks.py` 只跑通用校验。需要新指标时，先在 `metrics/` 写文档、在 `metrics/registry.yaml` 登记，再走评审；必须改旧口径时，在 `metrics/<name>.md` 里保留旧口径一节并标注弃用版本与原因，新口径用新版本号，同步更新所有引用该指标的 `recipes/*/metrics.yaml` 与配方的 `compatible_metrics`。会长期影响口径的取舍写成决策记录：编号递增，文件名 `NNNN-短描述.md`，写清背景、候选、决定、后果，不写过程流水账。最后在 `CHANGELOG.md` 的 `Unreleased` 下加一行，本地运行 `python3 scripts/run_checks.py`（含 `selftest` 负例），`examples/` 与 `examples/invalid/` 都要符合预期。

## contributing_api

```bash contributing_api
import aisp.bench.contributing.contributing as contributing

CreateRecipe =
     contributing.ContributingRecipe
  <- $name (str * { 评估集名；目录名用小写连字符，例如 recipes/checkpoint/ })
  <- $files (list[contributing.ContributingRecipeFile] * { 四份内容：recipe.yaml、metrics.yaml、README.md、checks/ })
  <- $notes (str * { recipe.yaml 里四项取值的理由 })
  <- { 建配方：把 recipes/_template/ 复制成 recipes/<name>/，写进四份内容，并在 CHANGELOG.md 的 Unreleased 下加一行；返回写好的配方。bypass、fidelity_boundary、io_pattern_invariants、scaling_plan 四项任何一项留空都不算建好配方 }

RegisterMetric =
     contributing.ContributingMetricRegistration
  <- $metric (contributing.ContributingMetricRegistration * { 要登记或改口径的指标：指标名、文档位置、版本、弃用信息、阈值与 compatible_metrics })
  <- $registered (list[str] * { metrics/registry.yaml 里已登记的指标名；只有在这个列表里的指标才能选 })
  <- { 登记指标：核对指标已在 metrics/registry.yaml 登记、阈值只写在 recipes/<name>/metrics.yaml 的 tolerance；改旧口径时保留旧口径一节并标注弃用版本与原因，新口径用新版本号；返回登记后的条目，并同步更新所有引用该指标的 recipes/*/metrics.yaml 与 compatible_metrics }

WriteDecision =
     contributing.ContributingDecision
  <- $decision (contributing.ContributingDecision * { 编号、短描述、类别、背景、候选、决定、后果 })
  <- { 写决策：按 decisions/README.md 的模板写进 decisions/NNNN-短描述.md，编号递增；只有必须写 ADR 的四类情况才走这一步，日常改动不写 }

RunChecks =
     list[contributing.ContributingCheckResult]
  <- $items (list[contributing.ContributingCheckItem] * { 这次要检查的项 })
  <- $scope (contributing.ContributingCheckScope * { 跑通用校验还是本配方专属校验 })
  <- { 跑校验：逐项检查，含 selftest 负例，examples/ 与 examples/invalid/ 都要符合预期；返回没有通过的项，空列表表示全部通过 }
```

## contributing_flow

```bash contributing_flow
import aisp.bench.contributing.contributing as contributing

ContributingStep =
  Oneof
  | $create_recipe (contributing.ContributingRecipe * { 第一步，建配方：调 contributing_api.CreateRecipe；复制 recipes/_template/ 到 recipes/<name>/，填四份内容，在 CHANGELOG.md 的 Unreleased 下加一行；产物是写好的配方 })
  | $register_metric (contributing.ContributingMetricRegistration * { 第二步，登记指标：调 contributing_api.RegisterMetric；只选 metrics/registry.yaml 已登记的指标，改旧口径时保留旧口径一节并写弃用版本与原因；产物是登记后的指标条目 })
  | $write_decision (contributing.ContributingDecision * { 第三步，写决策：调 contributing_api.WriteDecision；只有必须写 ADR 的四类情况才有这一步，写清背景、候选、决定、后果；产物是写下的决策记录 })
  | $run_checks (list[contributing.ContributingCheckResult] * { 第四步，跑校验：调 contributing_api.RunChecks；含 selftest 负例，examples/ 与 examples/invalid/ 都要符合预期；产物是没有通过的检查项，空列表表示全部通过 })

ContributingFlow =
  Object
  * $review (contributing.ContributingReview * { 这次改动属于哪一类、要不要两位评审人的确认；小步改直接提，必须走评审的先评审再提 })
  * $steps (list[ContributingStep] * { 四个操作按建配方 → 登记指标 → 写决策 → 跑校验 的顺序；这次不涉及的操作跳过，每一步的产物就是这次改动留下的东西 })
  * { 一次改动由两样东西组成：评审分类决定走哪条流程，步骤按顺序留下配方、指标条目、决策记录与校验结果 }
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
