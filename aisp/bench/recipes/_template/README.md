# 配方模板

## public

只做转发：从 `## 问题` 的 `recipe_template` 模块与 `## 接口` 的 `recipe_template_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布七个名字：类型 `RecipeTemplateSpec`、`RecipeTemplateDirectory` 与 `RecipeTemplateRequirement`，操作 `CopyTemplate`、`FillPlaceholders`、`CheckRequirements` 与 `ScaffoldRecipe`；先看 `RecipeTemplateSpec` 与 `RecipeTemplateDirectory`，再按 `CopyTemplate`、`FillPlaceholders`、`CheckRequirements` 的顺序读到 `RecipeTemplateRequirement` 的六条硬要求，`ScaffoldRecipe` 一次完成前三个操作。

```bash recipe_template_public
import aisp.bench.recipes._template.readme.recipe_template as recipe_template
import aisp.bench.recipes._template.readme.recipe_template_api as recipe_template_api

RecipeTemplateSpec = recipe_template.RecipeTemplateSpec
RecipeTemplateDirectory = recipe_template.RecipeTemplateDirectory
RecipeTemplateRequirement = recipe_template.RecipeTemplateRequirement
CopyTemplate = recipe_template_api.CopyTemplate
FillPlaceholders = recipe_template_api.FillPlaceholders
CheckRequirements = recipe_template_api.CheckRequirements
ScaffoldRecipe = recipe_template_api.ScaffoldRecipe
```

## 背景

本文解决新建配方时从哪里开始的问题：复制本目录到 `recipes/<评估集名>/`，逐项替换尖括号内的占位内容，复制后不要保留尖括号。它说明配方目录里六个文件各管什么、`recipe.yaml` 与 `metrics.yaml` 要填哪些字段，以及复制脚手架之后必须满足的硬要求。

## recipe_template

问题的形式化分成类型与枚举两类。`RecipeTemplateSpec` 是入口的 Object 类型，`$template` 取一个 `RecipeTemplateDirectory`，`$requirements` 与 `$steps` 分别是 `RecipeTemplateRequirement` 与 `RecipeTemplateScaffoldStep` 的列表。配方目录里的每个文件各自写成一个类型：`RecipeTemplateDirectory` 的 `$recipe`、`$metrics`、`$readme`、`$acceptance_checklist` 分别取 `RecipeTemplateRecipeYaml`、`RecipeTemplateMetricsYaml`、`RecipeTemplateReadme`、`RecipeTemplateAcceptanceChecklist`，`RecipeTemplateRecipeYaml` 再展开出 `RecipeTemplateInvariant`、`RecipeTemplateScalingPlan` 与 `fidelity.FidelityBoundary`，`RecipeTemplateMetricsYaml` 的 `$metrics` 是 `RecipeTemplateMetric` 的列表。取值只能落在有限集合里的概念写成 Oneof 枚举：`RecipeTemplateRequirement` 的六个取值是填写的硬要求，`RecipeTemplateScaffoldStep` 的四个取值是脚手架的步骤，`RecipeTemplateBuildStage` 的三个取值是配方入口的阶段；`RecipeTemplateCheckReport` 的 `$passed` 与 `$failed` 都以 `RecipeTemplateRequirement` 为元素类型，`RecipeTemplateScaffold` 把复制出的 `RecipeTemplateDirectory` 与一份 `RecipeTemplateCheckReport` 配在一起。

```bash recipe_template
import aisp.bench.checkpoint.methodology.fidelity as fidelity
import aisp.bench.checkpoint.methodology.gates as gates

RecipeTemplateSpec =
  Object
  * $template (RecipeTemplateDirectory * { 模板目录：六个文件各自的内容与读者 })
  * $requirements (list[RecipeTemplateRequirement] * { 填写的硬要求；复制后逐条检查 })
  * $steps (list[RecipeTemplateScaffoldStep] * { 复制脚手架的步骤：手动路径按复制目录、替换占位内容、检查硬要求的顺序执行；脚本路径用 new_recipe.py 一步完成复制、基础替换与检查 })

RecipeTemplateDirectory =
  Object
  * $name (str * { 评估集名；对应 recipes/<评估集名>/，模板里是尖括号占位，复制后不要保留尖括号 })
  * $recipe (RecipeTemplateRecipeYaml * { recipe.yaml：元信息、旁路范围、保真边界、不变量、scaling 计划、兼容的指标版本；评估服务与校验脚本读取 })
  * $metrics (RecipeTemplateMetricsYaml * { metrics.yaml：选用的指标、参数、阈值；评估服务与对齐判定读取 })
  * $readme (RecipeTemplateReadme * { README.md：目标、输入、输出、步骤、验收、负责人；人看 })
  * $acceptance_checklist (RecipeTemplateAcceptanceChecklist * { acceptance_checklist.md：阶段门 G0–G4 的勾选项；评审看 })
  * $checks (list[str] * { checks/：本配方专属校验脚本；CI 看 })
  * $build (list[RecipeTemplateBuildStage] * { build.py：配方入口，prepare / run / collect 三个阶段；实现者看 })

RecipeTemplateRecipeYaml =
  Object
  * $meta (dict[str, str] * { 元信息；评估服务与校验脚本读取 })
  * $bypass_scope (list[str] * { 旁路范围；评估服务与校验脚本读取 })
  * $fidelity_boundary (list[fidelity.FidelityBoundary] * { 保真边界；凡是存储与传输路径，fidelity 不允许是 L0 })
  * $io_pattern_invariants (list[RecipeTemplateInvariant] * { 不变量；写 3–6 条，每条都要有可计算的定义与容差 })
  * $scaling_plan (RecipeTemplateScalingPlan * { scaling 计划；至少两级，且必须写明固定哪些维度、放大哪个维度 })
  * $compatible_metrics (dict[str, list[str]] * { 指标名到兼容版本的映射；必须覆盖 metrics.yaml 里实际使用的版本 })
  * $latest_run ((str | nil) * { 最近一次运行；初始为 null，由评估服务在首次运行后写入，不要手填 })

RecipeTemplateReadme =
  Object
  * $objective (str * { 目标 })
  * $inputs (str * { 输入 })
  * $outputs (str * { 输出 })
  * $steps (str * { 步骤 })
  * $acceptance (str * { 验收 })
  * $owner (str * { 负责人 })

RecipeTemplateAcceptanceChecklist =
  Object
  * $items (list[RecipeTemplateChecklistItem] * { 阶段门 G0–G4 的勾选项；评审逐项勾选 })

RecipeTemplateChecklistItem =
  Object
  * $gate (gates.Gate * { 这一项对应哪个阶段门，G0 到 G4 })
  * $checked (bool * { 是否已勾选 })

RecipeTemplateBuildStage =
  Oneof
  | "prepare" * { 配方入口的第一个阶段：prepare }
  | "run" * { 配方入口的第二个阶段：run }
  | "collect" * { 配方入口的第三个阶段：collect }

RecipeTemplateScalingPlan =
  Object
  * $levels (list[str] * { 至少两级，每一级一条 })
  * $fixed_dimensions (list[str] * { 固定哪些维度 })
  * $varied_dimension (str * { 放大哪个维度 })

RecipeTemplateInvariant =
  Object
  * $definition (str * { 可计算的定义 })
  * $tolerance (str * { 容差；与定义一起判定这一条不变量是否保持 })

RecipeTemplateMetricsYaml =
  Object
  * $metrics (list[RecipeTemplateMetric] * { 选用的指标；评估服务与对齐判定读取 })

RecipeTemplateMetric =
  Object
  * $name (str * { 指标名；compatible_metrics 按这个名列版本 })
  * $version (str * { 这个指标实际使用的版本；必须被 compatible_metrics 覆盖 })
  * $params (dict[str, str] * { 参数；评估服务与对齐判定读取 })
  * $tolerance (dict[str, float] * { 阈值；只写在 metrics.yaml 的 tolerance，不要在别处再抄一份 })

RecipeTemplateRequirement =
  Oneof
  | "fidelity_boundary_no_l0" * { fidelity_boundary 中凡是存储与传输路径，fidelity 不允许是 L0 }
  | "io_pattern_invariants_3_to_6" * { io_pattern_invariants 写 3–6 条，每条都要有可计算的定义与容差 }
  | "scaling_plan_at_least_two_levels" * { scaling_plan 至少两级，且必须写明固定哪些维度、放大哪个维度 }
  | "compatible_metrics_cover_used_versions" * { compatible_metrics 按指标名列出版本，且必须覆盖 metrics.yaml 里实际使用的版本 }
  | "tolerance_only_in_metrics" * { 阈值只写在 metrics.yaml 的 tolerance，不要在别处再抄一份 }
  | "latest_run_null_until_first_run" * { latest_run 初始为 null，由评估服务在首次运行后写入，不要手填 }

RecipeTemplateScaffoldStep =
  Oneof
  | "copy_directory" * { 复制本目录到 recipes/<评估集名>/ }
  | "replace_placeholders" * { 逐项替换尖括号内的占位内容，复制后不要保留尖括号 }
  | "check_requirements" * { 检查新目录是否满足填写的硬要求 }
  | "run_new_recipe_script" * { 运行 python3 scripts/new_recipe.py <评估集名>；脚本完成复制与基础替换，并检查新目录是否满足硬要求 }

RecipeTemplateCheckReport =
  Object
  * $passed (list[RecipeTemplateRequirement] * { 已满足的硬要求 })
  * $failed (list[RecipeTemplateRequirement] * { 未满足的硬要求；为空表示全部满足 })

RecipeTemplateScaffold =
  Object
  * $directory (RecipeTemplateDirectory * { 复制出的配方目录 recipes/<评估集名>/ })
  * $report (RecipeTemplateCheckReport * { 新目录的硬要求检查结果 })
```

## 基本操作

复制脚手架的四个操作是复制目录、替换占位内容、检查硬要求、运行生成脚本。先把本目录复制到 `recipes/<评估集名>/`，得到配方目录的六个文件。再逐项替换尖括号内的占位内容，复制后不要保留尖括号。检查 `recipe.yaml` 与 `metrics.yaml` 的硬要求：`fidelity_boundary` 中存储与传输路径的 `fidelity` 不得是 `L0`，`io_pattern_invariants` 写 3–6 条且每条都有可计算的定义与容差，`scaling_plan` 至少两级并写明固定哪些维度、放大哪个维度，`compatible_metrics` 按指标名列出版本且覆盖 `metrics.yaml` 实际使用的版本，阈值只写在 `metrics.yaml` 的 `tolerance`，`latest_run` 初始为 `null`。也可以直接运行 `python3 scripts/new_recipe.py <评估集名>`，由脚本完成复制与基础替换并检查新目录是否满足硬要求。

## recipe_template_api

```bash recipe_template_api
import aisp.bench.recipes._template.readme.recipe_template as recipe_template

CopyTemplate =
     recipe_template.RecipeTemplateDirectory
  <- $template (recipe_template.RecipeTemplateDirectory * { 模板目录：六个文件各自的内容与读者 })
  <- $name (str * { 评估集名；对应 recipes/<评估集名>/，复制后不要保留尖括号 })
  <- { 复制本目录到 recipes/<评估集名>/；返回复制出的目录。此时 recipe.yaml 与 metrics.yaml 仍是模板内容，需要逐项替换尖括号内的占位内容 }

FillPlaceholders =
     recipe_template.RecipeTemplateDirectory
  <- $directory (recipe_template.RecipeTemplateDirectory * { 复制出的配方目录；尖括号占位内容还没替换 })
  <- $values (dict[str, str] * { 尖括号占位符到实际内容的映射；逐项替换 })
  <- { 逐项替换尖括号内的占位内容；复制后不要保留尖括号；返回替换完成的配方目录 }

CheckRequirements =
     recipe_template.RecipeTemplateCheckReport
  <- $recipe (recipe_template.RecipeTemplateRecipeYaml * { 待检查的 recipe.yaml })
  <- $metrics (recipe_template.RecipeTemplateMetricsYaml * { 待检查的 metrics.yaml；阈值只写在这里的 tolerance })
  <- { 按填写的硬要求逐条检查 recipe.yaml 与 metrics.yaml；返回已满足与未满足的条目，未满足列表为空才算通过 }

ScaffoldRecipe =
     recipe_template.RecipeTemplateScaffold
  <- $name (str * { 评估集名；脚本用它替换 recipes/<评估集名>/ 里的尖括号 })
  <- { 运行 python3 scripts/new_recipe.py <评估集名>；脚本完成复制与基础替换，并检查新目录是否满足硬要求；返回复制出的配方目录与检查结果 }
```

## recipe_template_flow

```bash recipe_template_flow
import aisp.bench.recipes._template.readme.recipe_template as recipe_template
import aisp.bench.recipes._template.readme.recipe_template_api as recipe_template_api

RecipeTemplateCopyDuty =
  Object
  * $step (recipe_template_api.CopyTemplate * { 复制：把本目录复制到 recipes/<评估集名>/ })
  * $directory (recipe_template.RecipeTemplateDirectory * { 这一步的产物：复制出的配方目录 })

RecipeTemplateFillDuty =
  Object
  * $step (recipe_template_api.FillPlaceholders * { 替换：逐项替换尖括号内的占位内容 })
  * $directory (recipe_template.RecipeTemplateDirectory * { 这一步的产物：不保留尖括号的配方目录 })

RecipeTemplateCheckDuty =
  Object
  * $step (recipe_template_api.CheckRequirements * { 检查：硬要求逐条判定 })
  * $report (recipe_template.RecipeTemplateCheckReport * { 这一步的产物：已满足与未满足的条目 })

RecipeTemplateScriptDuty =
  Object
  * $step (recipe_template_api.ScaffoldRecipe * { 脚本路径：运行 python3 scripts/new_recipe.py <评估集名>，一次完成复制与基础替换并检查新目录 })
  * $scaffold (recipe_template.RecipeTemplateScaffold * { 这一步的产物：配方目录与检查结果 })

RecipeTemplateFlow =
  Object
  * $spec (recipe_template.RecipeTemplateSpec * { 问题定义：模板目录、六个文件、recipe.yaml 与 metrics.yaml 的字段、填写的硬要求、复制脚手架的步骤 })
  * $copy (RecipeTemplateCopyDuty * { 第一步：复制本目录 })
  * $fill (RecipeTemplateFillDuty * { 第二步：替换尖括号内的占位内容 })
  * $check (RecipeTemplateCheckDuty * { 第三步：检查硬要求 })
  * $script (RecipeTemplateScriptDuty * { 另一条路径：用 scripts/new_recipe.py 一次完成复制、基础替换与检查 })
  * $result (recipe_template.RecipeTemplateScaffold * { 最终产物：配方目录与硬要求检查结果；手动路径由前三步得到，脚本路径由 ScaffoldRecipe 一次得到 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
