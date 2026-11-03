# playbook 与 bench 评估集

## public

只做转发：从 `## 问题` 的 `bench` 模块与 `## 接口` 的 `bench_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `BenchSpec`、`BenchStorageVersion`、`BenchEvalSet`、`BenchRun` 与 `BenchCheckReport`，操作 `RunBench`、`CheckRepo` 与 `ExtendBench`；先看 `BenchSpec` 与 `RunBench`，存储两层看 `BenchStorageVersion`，评估集与校验结果看 `BenchEvalSet` 与 `BenchCheckReport`。

```bash bench_public
import aisp.bench.readme.bench as bench
import aisp.bench.readme.bench_api as bench_api

BenchSpec = bench.BenchSpec
BenchStorageVersion = bench.BenchStorageVersion
BenchEvalSet = bench.BenchEvalSet
BenchRun = bench.BenchRun
BenchCheckReport = bench.BenchCheckReport
RunBench = bench_api.RunBench
CheckRepo = bench_api.CheckRepo
ExtendBench = bench_api.ExtendBench
```

## 背景

本项目是 **playbook**：生成、运行与校验 AI Infra 存储传输侧评估集的程序；它的产物是 **bench**，即两类带版本的静态评估集——模型代码收集与 checkpoint 存储评估。评估用**真实模型代码产生的 IO**，测存储与传输在训练、推理、集群规模下的行为；评估集本身不会变化，让它变化的是这里的配方、指标与扩展流程。dataset 与 kvcache 待做（TODO）；完整指标表、SLO 的配置结构与版本比较方法见 [`checkpoint/performance.md`](checkpoint/performance.md)。

## bench

问题的形式化以 `BenchSpec` 这个 Object 类型为入口：评估对象、存储版本、评估集、指标与目录结构分别收进 `$subjects`（`BenchSubject` 的列表）、`$storage`（`BenchStorageVersion`）、`$eval_sets`（`BenchEvalSet` 的列表）、`$metrics`（`BenchMetricSet` 的列表）与 `$layout`（`BenchLayout`）五个字段。其中四项继续展开成 Object 类型：`BenchStorageVersion` 的 `$layers` 是 `BenchStorageLayer` 的列表，后者用 `$kind` 取 `BenchStorageLayerKind`、用 `$component` 取 `ckpt_sample.Component`；`BenchEvalSet` 的 `$subject` 取 `BenchSubject`，`$entry` 取 `BenchEvalSetEntry` 或 `nil`；`BenchMetricSet` 的 `$subject` 与 `$tier` 分取 `BenchSubject` 与 `BenchMetricTier`，`BenchLayout` 的 `$areas` 取 `BenchRepoArea` 的列表。`BenchRun` 与 `BenchCheckReport` 不在 `BenchSpec` 的字段里：前者由 `BenchRunArtifacts` 与 `BenchBacklink` 组成，后者收拢一次校验的结果。取值只能落在有限集合里的概念写成 Oneof 枚举：`BenchSubject` 表示评估对象，`BenchStorageLayerKind` 表示存储一层的种类，`BenchMetricTier` 表示指标层级，`BenchRepoArea` 表示仓库里要列出的目录与文件，`BenchCheckScope` 表示校验范围，`BenchGapKind` 表示覆盖缺口；`BenchStorageVersion` 的 `$changed_layers`、`BenchEvalSet` 与 `BenchMetricSet` 的 `$subject` 都引用这些枚举类型。

```bash bench
import aisp.bench.checkpoint.ckpt_sample_interface.ckpt_sample as ckpt_sample

BenchSpec =
  Object
  * $subjects (list[BenchSubject] * { 评估对象：模型代码（原料）与 checkpoint；dataset 与 kvcache 是 TODO })
  * $storage (BenchStorageVersion * { 存储两层：backend 与 adapter，每个样本同时声明 })
  * $eval_sets (list[BenchEvalSet] * { 评估集：两类带版本的静态评估集；dataset 与 kvcache 是 TODO })
  * $metrics (list[BenchMetricSet] * { 指标两层：SLI 与 SLO；每个评估对象分别有这两层 })
  * $layout (BenchLayout * { 目录结构：根目录下的目录与文件 })

BenchSubject =
  Oneof
  | "model_code_collection" * { 模型代码（原料）：语料够不够多、够不够全、能不能跑；它不产出 IO 数据，是 checkpoint 评估的原料 }
  | "checkpoint" * { checkpoint：训练侧 checkpoint 写入与读取两条真实路径；回答一次写多久、训练被停多久 }
  | "dataset" * { TODO：尚未定义 }
  | "kvcache" * { TODO：尚未定义 }

BenchStorageLayerKind =
  Oneof
  | "backend" * { 纯存储系统：GPFS、HDFS、Alluxio、Ceph、JuiceFS；运行时由服务注入 AI_INFRA_STORAGE_BACKEND }
  | "adapter" * { AI Infra 存储传输适配层：mooncake、torchstore、bytecheckpoint；运行时由服务注入 AI_INFRA_STORAGE_ADAPTER }

BenchStorageLayer =
  Object
  * $kind (BenchStorageLayerKind * { 这一层是 backend 还是 adapter })
  * $component (ckpt_sample.Component * { 这一层的组件名、版本与源码 commit })
  * $env (str * { 运行时注入的环境变量名：backend 是 AI_INFRA_STORAGE_BACKEND，adapter 是 AI_INFRA_STORAGE_ADAPTER })

BenchStorageVersion =
  Object
  * $layers (list[BenchStorageLayer] * { 每个样本同时声明 backend 与 adapter 两层；未设置对应的环境变量时样本必须报错退出，不允许默认值 })
  * $manifest (str * { 运行清单的位置：两层的版本与配置都写在这份清单里 })
  * $changed_layers (list[BenchStorageLayerKind] * { 比较两个存储版本时只允许一层不同；两层都变则按层分别归因 })

BenchEvalSetEntry =
  Object
  * $version (str * { 评估集的版本；构建完成后不变，扩展时由 playbook 生成新版本 })
  * $measures (str * { 测什么：模型代码收集测语料是否够多、够全、能跑；checkpoint 测训练侧 checkpoint 写读的 IO })
  * $cases_from (str * { 用例从哪来：模型代码收集取 HuggingFace 等平台的 model id；checkpoint 取模型代码收集产出的训练代码与训练框架 })
  * $outputs (list[str] * { 产出：模型代码收集是清单（manifest）与覆盖矩阵；checkpoint 是 IO pattern 记录、SLI 记录、对齐结果与 scaling 结果 })
  * $recipe_dir (str * { 配方目录：模型代码收集是 recipes/model_code_collection/，checkpoint 是 recipes/checkpoint/ })

BenchEvalSet =
  Object
  * $subject (BenchSubject * { 这个评估集评哪个对象：模型代码（原料）或 checkpoint；dataset 与 kvcache 是 TODO })
  * $entry ((BenchEvalSetEntry | nil) * { 已有评估集的版本、测什么、用例来源、产出与配方目录；dataset 与 kvcache 尚未定义，给 nil })

BenchMetricTier =
  Oneof
  | "sli" * { 每个样本每次运行都记录，全量留存，用来比较两个存储版本；没有阈值 }
  | "slo" * { 只对重保子集判定；阈值由使用方在部署评估集时指定，仓库不提供数字 }

BenchMetricSet =
  Object
  * $subject (BenchSubject * { 这组指标评哪个评估对象 })
  * $tier (BenchMetricTier * { 这一组是 SLI 还是 SLO })
  * $metrics (list[str] * { 这组指标的指标名；SLI 记 checkpoint_duration_s、training_stall_s、restore_duration_s、metadata_commit_ms，或可跑率、架构族覆盖、训练代码配对率；SLO 只对重保子集判定，阈值由使用方在部署评估集时指定，仓库不提供数字；dataset 与 kvcache 为 TODO })

BenchRepoArea =
  Oneof
  | "playbook" * { 跨评估集的方法论与评估集的方法 }
  | "checkpoint/json_schema" * { 文档里 viba 类型的 JSON Schema，每个类型一份，由 scripts/export_json_schema.py 生成 }
  | "recipes" * { 评估集的可执行配方，一个评估集一个目录；_template 是新配方的脚手架 }
  | "metrics" * { 指标定义与登记表 }
  | "checks" * { 校验脚本：指标与仓库规范的可执行实现 }
  | "schemas" * { recipe、metrics、io-pattern、run-spec、sli、slo 的 JSON Schema }
  | "scripts" * { 维护脚本：新建配方、批量校验 }
  | "meta-evaluation" * { 评估这套 playbook 自身：指标、方法、问卷 }
  | "decisions" * { 关键取舍的决策记录（ADR） }
  | "examples" * { 最小可跑样例与负例 }
  | "requirements.txt" * { 校验脚本的依赖 }
  | "CONTRIBUTING.md" * { 新增配方、修改指标、记录决策的流程 }
  | "CHANGELOG.md" * { 手册自身的版本变更 }

BenchLayout =
  Object
  * $root (str * { 根目录 aisp/bench/，playbook 与 bench 评估集都在这一个目录下 })
  * $areas (list[BenchRepoArea] * { 根目录下的目录与文件；requirements.txt、CONTRIBUTING.md、CHANGELOG.md 是文件，其余是目录 })
  * $method_docs (list[str] * { checkpoint/ 下的文档：principles.md、methodology.md、model_code_collection.md、checkpoint.md、ckpt_sample_interface.md、scaling.md、evaluation_service.md、extension.md、pitfalls.md、performance.md、appendix_glossary.md })
  * $recipe_dirs (list[str] * { recipes/ 下的目录：_template/、model_code_collection/、checkpoint/ })

BenchRunArtifacts =
  Object
  * $manifest (str * { 运行清单的位置：本次运行的全部输入、版本、拓扑、存储两层版本 })
  * $sli (str * { 本次运行的 SLI 文件位置；全量留存，跨存储版本比较用 })
  * $metrics (str * { 本次运行的度量值文件位置 })
  * $alignment (str * { 与真实运行的对齐结果文件位置 })
  * $report (str * { 人读报告的位置 })

BenchBacklink =
  Object
  * $uri (str * { 产物在对象存储里的位置 })
  * $sha256 (str * { 产物的校验和 })
  * $state (str * { 回链里记录的状态；仓库里只留 URI、sha256、状态三要素 })
  * { 回链写进配方的 latest_run，仓库里只留 URI、sha256、状态三要素；产物本身在对象存储 }

BenchRun =
  Object
  * $run_id (str * { 服务分配的运行标识，查状态、取产物都用它 })
  * $state (ckpt_sample.State * { 这次运行现在在哪一步 })
  * $artifacts (BenchRunArtifacts * { runs/<run-id>/ 下的五份产物 })
  * $backlink (BenchBacklink * { 写进配方 latest_run 的回链 })

BenchCheckScope =
  Oneof
  | "repo" * { 只跑 scripts/validate_repo.py：检查配方、指标登记表与 schema 的一致性 }
  | "full" * { 跑 scripts/run_checks.py：在上面那项之外，加上 selftest 与 examples/ 样例 }

BenchCheckReport =
  Object
  * $exit_code (int * { 0 通过、1 不通过、2 缺依赖；缺依赖不算通过 })
  * $failed (list[str] * { 没有通过的检查项，写清是哪一项、为什么 })
  * $missing_dependencies (list[str] * { 缺的依赖；这时退出码是 2 })

BenchGapKind =
  Oneof
  | "new_model" * { 新模型出现，当前评估集没有覆盖 }
  | "new_framework" * { 新框架出现，当前评估集没有覆盖 }
  | "new_parallel_strategy" * { 新并行策略出现，当前评估集没有覆盖 }
```

## 基本操作

跑一次评估：准备一份运行请求，定下跑哪个样本、用哪份配置、评哪两层存储、用什么随机种子，交给评估服务按配方执行。

1. 校验仓库：在 `aisp/bench` 下安装 `requirements.txt` 的依赖，先跑 `scripts/validate_repo.py` 检查配方、指标登记表与 schema 的一致性，再跑 `scripts/run_checks.py` 在同一套检查之外加上 selftest 与 `examples/` 样例；退出码 0 通过、1 不通过、2 缺依赖，缺依赖不算通过，阈值只从 `recipes/*/metrics.yaml` 读。
2. 扩展评估集：评估集是静态产物，不会自己变化；新模型、新框架或新并行策略出现后，由 playbook 发现覆盖缺口并生成新版本，流程见 [`checkpoint/extension.md`](checkpoint/extension.md)，新增或修改配方前先读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## bench_api

```bash bench_api
import aisp.bench.readme.bench as bench
import aisp.bench.checkpoint.ckpt_sample_interface.ckpt_sample as ckpt_sample

RunBench =
     bench.BenchRun
  <- $spec (ckpt_sample.RunSpec * { 一份运行请求：跑哪个样本、用哪份配置、评哪两层存储、用什么随机种子 })
  <- { 跑一次评估：把请求交给评估服务，按配方执行；产出 runs/<run-id>/ 下的运行清单、SLI、度量值、对齐结果与人读报告；仓库里只在配方的 latest_run 留回链。返回运行标识与状态、五份产物与回链 }

CheckRepo =
     bench.BenchCheckReport
  <- $scope (bench.BenchCheckScope * { 校验范围：repo 只检查配方、指标登记表与 schema 的一致性；full 在这之外加 selftest 与 examples/ 样例 })
  <- { 校验仓库：scope 为 repo 时跑 scripts/validate_repo.py，检查配方、指标登记表与 schema 的一致性；scope 为 full 时跑 scripts/run_checks.py，在前面那项之外加上 selftest 与 examples/ 样例；退出码 0 通过、1 不通过、2 缺依赖，缺依赖不算通过；阈值只从 recipes/*/metrics.yaml 读。返回退出码、没有通过的检查项与缺的依赖 }

ExtendBench =
     bench.BenchEvalSet
  <- $current (bench.BenchEvalSet * { 当前版本的评估集 })
  <- $gaps (list[bench.BenchGapKind] * { 这次发现的覆盖缺口：新模型、新框架、新并行策略 })
  <- { 扩展评估集：评估集是静态产物，不会自己变化；由 playbook 发现覆盖缺口并生成新版本。返回新版本的评估集 }
```

## bench_flow

三个操作串成一条闭环：跑一次评估产出五份产物与回链，校验仓库确认配方、指标与 schema 一致，发现覆盖缺口后扩展评估集、生成新版本；新版本回到评估集，产物留在对象存储，仓库里只留回链。

```bash bench_flow
import aisp.bench.readme.bench as bench
import aisp.bench.readme.bench_api as bench_api

BenchRunDuty =
  Object
  * $run (bench_api.RunBench * { 跑一次评估：一份运行请求进，一份运行结果出；产物写对象存储 })
  * $artifacts (bench.BenchRunArtifacts * { 五份产物：运行清单、SLI、度量值、对齐结果、人读报告 })
  * $backlink (bench.BenchBacklink * { 仓库里只留回链：URI、sha256、状态 })

BenchCheckDuty =
  Object
  * $scope (bench.BenchCheckScope * { 校验范围：只查仓库一致性，或连 selftest 与 examples/ 样例一起跑 })
  * $report (bench_api.CheckRepo * { 校验仓库：退出码 0 通过、1 不通过、2 缺依赖；缺依赖不算通过 })

BenchExtendDuty =
  Object
  * $gaps (list[bench.BenchGapKind] * { 这次发现的覆盖缺口：新模型、新框架、新并行策略 })
  * $next (bench_api.ExtendBench * { 扩展评估集：由 playbook 生成新版本，返回新版本的评估集 })

BenchStep =
  Oneof
  | $run (BenchRunDuty * { 第一个操作：跑一次评估 })
  | $check (BenchCheckDuty * { 第二个操作：校验仓库 })
  | $extend (BenchExtendDuty * { 第三个操作：扩展评估集 })

BenchFlow =
  Object
  * $spec (bench.BenchSpec * { 问题定义：评估对象、存储两层、评估集、指标两层、目录结构 })
  * $steps (list[BenchStep] * { 三个操作，按跑一次评估、校验仓库、扩展评估集的顺序 })
  * $backlink (bench.BenchBacklink * { 每次运行结束后，仓库里只留回链；产物本身在对象存储 })
```

评估方法见 [`checkpoint/methodology.md`](checkpoint/methodology.md)，评估服务见 [`checkpoint/evaluation_service.md`](checkpoint/evaluation_service.md)，扩展流程见 [`checkpoint/extension.md`](checkpoint/extension.md)。判断这套 bench 能不能用见 [`checkpoint/principles.md`](checkpoint/principles.md) 与 [`metrics/coverage.md`](metrics/coverage.md)，验收结论的口径与实现见 [`metrics/`](metrics/README.md) 与 [`checks/README.md`](checks/README.md)，评估这套 playbook 自身见 [`meta-evaluation/method.md`](meta-evaluation/method.md)，领域词见 [`checkpoint/appendix_glossary.md`](checkpoint/appendix_glossary.md)。

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
