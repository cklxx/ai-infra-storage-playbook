# 模型代码收集配方

## 背景

本配方收集 1000 个以上可跑的推理模型代码、尽量配对训练代码，生产另外两个配方的原料：一份可复现、去重后、验证过能跑的 LLM 模型代码语料。给定清单与 commit，语料要能在新机器上重建出同样的文件集合；结构族、规模量级、注意力变体的覆盖矩阵要能计算。方法说明见 [`playbook/model-code-collection.md`](../../playbook/model-code-collection.md)，开放问题见同一篇文档的「开放问题」。

## 问题

```viba recipe_collection
RecipeCollectionInputKind =
  Oneof
  | "platform_model_list" * { 平台模型列表，来源是 HuggingFace Hub 模型接口；必需 }
  | "org_model_list" * { 机构模型清单，来源是组织主页、自有模型清单；可选 }
  | "dependency_image" * { 依赖镜像，按 transformers 主版本分组；必需 }
  | "gpu_resource" * { GPU 资源，可被分时占用的单卡；必需 }

RecipeCollectionInput =
  Object
  * $kind (RecipeCollectionInputKind * { 哪一路输入 })
  * $required (bool * { 是否必需；机构模型清单是可选输入，其余三路必需 })

RecipeCollectionOutputKind =
  Oneof
  | "model_code" * { 模型代码：对象存储 models/<org>/<name>/<commit>/，只含代码与配置，不含权重 }
  | "manifest" * { 清单：对象存储 manifests/model-code-<version>.json，结构见 schemas/model-manifest.schema.json }
  | "coverage_manifest" * { 覆盖度清单：对象存储 coverage/model-code-<version>.json，结构见 schemas/coverage.schema.json }
  | "latest_run" * { 回链：本目录 recipe.yaml 的 latest_run，由评估服务写入 }

RecipeCollectionOutput =
  Object
  * $kind (RecipeCollectionOutputKind * { 哪一份产物 })
  * $location (str * { 产物位置：对象存储路径，或本目录 recipe.yaml 的 latest_run 字段 })

RecipeCollectionCandidateFilter =
  Oneof
  | "pipeline_tag" * { 按 pipeline_tag 筛选候选 }
  | "library_name" * { 按 library_name 筛选候选 }
  | "downloads" * { 按下载量筛选候选 }
  | "created_at" * { 按创建时间筛选候选 }

RecipeCollectionCandidate =
  Object
  * $model_id (str * { 模型标识，取自平台模型列表接口 })
  * $org (str * { 模型所属组织 })
  * $license (str * { 许可证 })
  * $tags (list[str] * { 模型的 tags })
  * $created_at (str * { 模型的创建时间 })

RecipeCollectionWorkspace =
  Object
  * $framework_major (str * { transformers 主版本；候选按主版本分组，每组一个工作区镜像 })
  * $dependencies (str * { 一套独立依赖 })
  * $disk_quota (str * { 固定的磁盘配额 })
  * $cleanup (str * { 固定的清理规则 })
  * $downloader (str * { 下载器，按白名单取文件 })

RecipeCollectionCandidateSet =
  Object
  * $target (int * { 目标数量：可跑模型数的下限，初始目标 1000 })
  * $stop_at (int * { 停止抓取的数量：目标数量的 3 倍；多抓的部分用于补偿下载失败与去重淘汰 })
  * $candidates (list[RecipeCollectionCandidate] * { 候选清单；每个候选记 model id、组织、许可证、tags、创建时间 })
  * $workspaces (list[RecipeCollectionWorkspace] * { 按 transformers 主版本分组的工作区 })

RecipeCollectionCodeFile =
  Object
  * $path (str * { 文件在模型目录里的相对路径 })
  * $sha256 (str * { 文件内容的 sha256；下载后计算 })

RecipeCollectionFetchFailureKind =
  Oneof
  | "network" * { 网络失败 }
  | "permission" * { 权限不足 }
  | "not_found" * { 文件不存在 }
  | "license_not_accepted" * { 许可未接受 }

RecipeCollectionFetchFailure =
  Object
  * $kind (RecipeCollectionFetchFailureKind * { 四类失败中的哪一类 })
  * $detail (str * { 具体说明 })

RecipeCollectionDownload =
  Object
  * $files (list[RecipeCollectionCodeFile] * { 按白名单取到的代码与配置，不含权重；白名单见方法文档的「只取代码与配置」；下载后校验文件数与清单一致 })
  * $commit (str * { 仓库的当前 commit；下载时记录 })
  * $failures (list[RecipeCollectionFetchFailure] * { 失败按网络、权限、不存在、许可未接受四类分别记录 })

RecipeCollectionCodeRole =
  Oneof
  | "inference" * { 推理代码 }
  | "pretrain" * { 预训练代码 }
  | "both" * { 推理代码与预训练代码都有 }
  | "unknown" * { 证据不足以判定时写这个值，不要猜；计入覆盖缺口 }

RecipeCollectionFingerprint =
  Object
  * $config (list[str] * { 配置层特征 })
  * $code (list[str] * { 代码层特征 })

RecipeCollectionDedupDecision =
  Oneof
  | "kept" * { 保留；按最大边际覆盖保留代表样本 }
  | "dropped" * { 丢弃；组内加权距离小于阈值的重复样本 }

RecipeCollectionDedupRecord =
  Object
  * $group (str * { 架构族分组 })
  * $decision (RecipeCollectionDedupDecision * { 保留还是丢弃 })
  * $dropped_by ((str | nil) * { 丢弃时指向代表样本的 model id；保留时给 nil })

RecipeCollectionRunnableState =
  Oneof
  | "yes" * { 能跑 }
  | "no" * { 不能跑 }
  | "partial" * { 部分跑通 }

RecipeCollectionRunnableFailure =
  Object
  * $kind (str * { 失败分类；超时单独归类 })
  * $step (str * { 失败发生在哪一步 })
  * $summary (str * { 错误摘要 })

RecipeCollectionRunnableRecord =
  Object
  * $state (RecipeCollectionRunnableState * { 结果：yes / no / partial })
  * $ranks (int * { rank 数，固定值，默认 2 })
  * $timeout_min (int * { 超时，统一设为 10 分钟；超时单独归类 })
  * $failures (list[RecipeCollectionRunnableFailure] * { 失败步骤与错误摘要；超时单独归类 })

RecipeCollectionTrainingStatus =
  Oneof
  | "paired" * { 配上了训练代码 }
  | "external" * { 训练代码在外链里；配对规则见方法文档的四条规则 }
  | "unpaired" * { 配不上；配对证据不足时一律写这个值 }

RecipeCollectionTrainingPairing =
  Object
  * $status (RecipeCollectionTrainingStatus * { paired_training.status })
  * $ref ((str | nil) * { 训练代码的引用；unpaired 时给 nil })

RecipeCollectionCorpusEntry =
  Object
  * $candidate (RecipeCollectionCandidate * { 候选：model id、组织、许可证、tags、创建时间 })
  * $download ((RecipeCollectionDownload | nil) * { 取到的代码与配置；还没下载时给 nil })
  * $code_role ((RecipeCollectionCodeRole | nil) * { 代码角色；还没判定时给 nil })
  * $code_role_evidence (str * { 判定 code_role 的证据；判定顺序与证据等级见方法文档的「区分推理代码与预训练代码」；证据不足时 code_role 写 unknown })
  * $fingerprint ((RecipeCollectionFingerprint | nil) * { 配置层与代码层特征；还没提取时给 nil })
  * $dedup ((RecipeCollectionDedupRecord | nil) * { 去重决定，写进清单的 dedup 字段；还没去重时给 nil })
  * $runnable ((RecipeCollectionRunnableRecord | nil) * { 可跑性结论；还没验证时给 nil })
  * $training ((RecipeCollectionTrainingPairing | nil) * { 训练代码配对结论；还没配对时给 nil })

RecipeCollectionCoverageDimension =
  Oneof
  | "architecture_family" * { 结构族：覆盖矩阵按架构族分格 }
  | "scale" * { 规模量级：覆盖矩阵按 6 个量级分桶分格 }
  | "attention_variant" * { 注意力变体：覆盖矩阵按 6 类注意力变体分格 }

RecipeCollectionCoverageCell =
  Object
  * $dimension (RecipeCollectionCoverageDimension * { 这一格按哪个维度分 })
  * $bucket (str * { 这一格是哪个桶：结构族名、量级分桶或注意力变体 })
  * $count (int * { 这个桶里有几个模型 })

RecipeCollectionGapKind =
  Oneof
  | "empty_cell" * { 覆盖矩阵里的空白格子 }
  | "unknown_code_role" * { code_role 为 unknown 的模型；计入覆盖缺口 }

RecipeCollectionGap =
  Object
  * $kind (RecipeCollectionGapKind * { 缺的是哪一类 })
  * $detail (str * { 具体缺什么 })

RecipeCollectionCoverage =
  Object
  * $cells (list[RecipeCollectionCoverageCell] * { 覆盖矩阵的每一格：结构族、规模量级、注意力变体 })
  * $gaps (list[RecipeCollectionGap] * { 缺口清单；语料版本升级前必须由负责人确认 })

RecipeCollectionAcceptanceMetric =
  Oneof
  | "runnable_model_count" * { 可跑模型数：runnable=yes 且 dedup.decision=kept 的模型数；目标 ≥ 1000 }
  | "runnable_rate" * { 可跑率：runnable=yes 的模型占全部保留样本的比例；目标 ≥ 85% }
  | "architecture_family_coverage" * { 架构族覆盖：至少 3 个样本的架构族数；目标 ≥ 20 }
  | "scale_coverage" * { 规模覆盖：6 个量级分桶，每桶 ≥ 10；目标全部满足 }
  | "attention_variant_coverage" * { 注意力变体覆盖：6 类变体各 ≥ 5；目标全部满足 }
  | "training_pairing_rate" * { 训练代码配对率：paired 与 external 的占比；目标 ≥ 40% }
  | "reproducible_corpus" * { 语料可复现：重跑后文件集合与 sha256 完全一致；目标 100% }

RecipeCollectionAcceptance =
  Object
  * $metrics (list[RecipeCollectionAcceptanceMetric] * { 七项验收指标：可跑模型数、可跑率、架构族覆盖、规模覆盖、注意力变体覆盖、训练代码配对率、语料可复现 })
  * $checker (str * { 覆盖矩阵与缺口清单的计算脚本：checks/check_coverage.py })
  * $checklist (str * { 逐项确认的验收清单：acceptance-checklist.md })
  * $owner (str * { 负责人；见本目录 recipe.yaml 的 owner 字段；语料版本升级前必须由负责人确认覆盖缺口清单 })

RecipeCollectionAcceptanceItem =
  Object
  * $metric (RecipeCollectionAcceptanceMetric * { 哪一项指标 })
  * $actual (str * { 这项的实际值 })
  * $passed (bool * { 是否达到目标；目标写在 RecipeCollectionAcceptanceMetric 的取值说明里 })

RecipeCollectionAcceptanceReport =
  Object
  * $items (list[RecipeCollectionAcceptanceItem] * { 七项指标各一条 })
  * $coverage (RecipeCollectionCoverage * { 覆盖矩阵与缺口清单 })
  * $passed (bool * { 七项全部达标才为 true })
```

## 基本操作

先抓取候选并建立工作区：调用平台模型列表接口，按 `pipeline_tag`、`library_name`、下载量与创建时间筛选，每个候选记 model id、组织、许可证、tags、创建时间；候选数量达到目标数量的 3 倍后停止抓取，多抓的部分用于补偿下载失败与去重淘汰；再按 `transformers` 主版本把候选分组，每组一个工作区镜像，工作区里放一套独立依赖、固定的磁盘配额与清理规则、一个按白名单取文件的下载器。接着下载代码与配置并判定代码角色：白名单见方法文档的「只取代码与配置」，下载后计算每个文件的 `sha256`、记录仓库的当前 commit、校验文件数与清单一致，失败按网络、权限、不存在、许可未接受四类分别记录；对每个模型产出 `code_role` 与 `code_role_evidence`，证据不足时写 `unknown`，不要猜，`unknown` 计入覆盖缺口。然后提取配置层与代码层特征做结构指纹，按架构族分组，组内计算加权距离，按最大边际覆盖保留代表样本，去重决定写进清单的 `dedup` 字段；阈值初始值 0.15，标定前不对外引用去重率。再做可跑性验证：用固定 rank 数（默认 2）初始化 mock 的进程组，每个 rank 单独起进程、分时占用同一张卡、跑一次前向，输入维度用配置允许的小值；记录 `yes` / `no` / `partial` 与失败步骤、错误摘要，超时统一设为 10 分钟并单独归类。随后按方法文档的四条规则配对训练代码，产出 `paired_training.status`（`paired` / `external` / `unpaired`）与 `ref`，配对证据不足时一律 `unpaired`。最后统计覆盖度并验收：用 `checks/check_coverage.py` 计算覆盖矩阵与缺口清单，按 [`acceptance-checklist.md`](acceptance-checklist.md) 逐项确认可跑模型数、可跑率、架构族覆盖、规模覆盖、注意力变体覆盖、训练代码配对率、语料可复现七项指标；语料版本升级前必须由负责人确认覆盖缺口清单，负责人见 [`recipe.yaml`](recipe.yaml) 的 `owner` 字段。

## 接口

```viba recipe_collection_api
import recipe_collection

CollectCandidates =
     recipe_collection.RecipeCollectionCandidateSet
  <- $target (int * { 目标可跑模型数；初始目标 1000，停止抓取的数量按它的 3 倍算 })
  <- $filters (list[recipe_collection.RecipeCollectionCandidateFilter] * { 抓取时用的筛选条件：pipeline_tag、library_name、下载量、创建时间 })
  <- { 抓取候选并建立工作区：调用平台模型列表接口，按筛选条件过滤，每个候选记 model id、组织、许可证、tags、创建时间；候选数量达到目标数量的 3 倍后停止抓取，多抓的部分用于补偿下载失败与去重淘汰。按 transformers 主版本把候选分组，每组一个工作区镜像，工作区里放一套独立依赖、固定的磁盘配额与清理规则、一个按白名单取文件的下载器。返回候选清单与工作区 }

FetchCode =
     recipe_collection.RecipeCollectionCorpusEntry
  <- $candidate (recipe_collection.RecipeCollectionCandidate * { 要下载的候选 })
  <- $workspace (recipe_collection.RecipeCollectionWorkspace * { 这个候选所在 transformers 主版本的工作区；下载与判定都在里面做 })
  <- { 下载代码与配置并判定代码角色：按方法文档「只取代码与配置」的白名单取文件，下载后计算每个文件的 sha256、记录仓库的当前 commit、校验文件数与清单一致；失败按网络、权限、不存在、许可未接受四类分别记录。对每个模型产出 code_role 与 code_role_evidence，证据不足时写 unknown，不要猜，unknown 计入覆盖缺口。返回一条语料条目，带上候选、下载结果、代码角色与证据 }

DedupCorpus =
     list[recipe_collection.RecipeCollectionCorpusEntry]
  <- $entries (list[recipe_collection.RecipeCollectionCorpusEntry] * { 已经下载并判定过代码角色的语料条目 })
  <- $threshold (float * { 组内加权距离的阈值，初始值 0.15；标定前不对外引用去重率 })
  <- { 结构指纹与去重：提取配置层与代码层特征，按架构族分组，组内计算加权距离，按最大边际覆盖保留代表样本；去重决定写进条目的 dedup 字段。返回同一批条目，每条写上指纹与去重决定；kept 的条目进入可跑性验证，dropped 的条目留在清单里 }

ProbeRunnable =
     recipe_collection.RecipeCollectionCorpusEntry
  <- $entry (recipe_collection.RecipeCollectionCorpusEntry * { 要验证的那条语料；去重丢弃的条目不再验证 })
  <- { 可跑性验证：用固定 rank 数（默认 2）初始化 mock 的进程组，每个 rank 单独起进程、分时占用同一张卡、跑一次前向，输入维度用配置允许的小值；记录 yes / no / partial 与失败步骤、错误摘要，超时统一设为 10 分钟并单独归类。返回同一条语料，写上 runnable 结论 }

PairTrainingCode =
     recipe_collection.RecipeCollectionCorpusEntry
  <- $entry (recipe_collection.RecipeCollectionCorpusEntry * { 要配对的语料条目；用它的 code_role 与结构指纹 })
  <- { 训练代码配对：按方法文档的四条规则配对，产出 paired_training.status（paired / external / unpaired）与 ref；配对证据不足时一律 unpaired。返回同一条语料，写上 training 结论 }

CheckAcceptance =
     recipe_collection.RecipeCollectionAcceptanceReport
  <- $entries (list[recipe_collection.RecipeCollectionCorpusEntry] * { 已经下载、去重、验证、配对过的全部语料条目 })
  <- $acceptance (recipe_collection.RecipeCollectionAcceptance * { 验收口径：七项指标、覆盖度计算脚本、验收清单与负责人 })
  <- { 覆盖度统计与验收：用 checks/check_coverage.py 计算覆盖矩阵与缺口清单，按验收清单逐项确认七项指标；返回每项指标的实际值与是否达标，以及覆盖矩阵与缺口清单，七项全部达标才算验收通过 }
```

## 组织

```viba recipe_collection_flow
import recipe_collection
import recipe_collection_api

RecipeCollectionFlow =
  Object
  * $inputs (list[recipe_collection.RecipeCollectionInput] * { 四路输入：平台模型列表与机构模型清单供抓取候选，依赖镜像与 GPU 资源供下载与可跑性验证；机构模型清单可选 })
  * $collect_candidates (recipe_collection_api.CollectCandidates * { 抓取候选并建立工作区：候选达到目标数量的 3 倍后停止，按 transformers 主版本分组 })
  * $fetch_code (recipe_collection_api.FetchCode * { 下载代码与配置并判定代码角色：只取代码与配置，失败分四类，证据不足写 unknown })
  * $dedup_corpus (recipe_collection_api.DedupCorpus * { 结构指纹与去重：按架构族分组，组内加权距离，按最大边际覆盖保留代表样本 })
  * $probe_runnable (recipe_collection_api.ProbeRunnable * { 可跑性验证：mock 进程组，固定 rank 数，分时占用单卡，超时 10 分钟 })
  * $pair_training_code (recipe_collection_api.PairTrainingCode * { 训练代码配对：按方法文档的四条规则，证据不足一律 unpaired })
  * $check_acceptance (recipe_collection_api.CheckAcceptance * { 覆盖度统计与验收：算覆盖矩阵与缺口清单，判七项指标 })
  * $candidates (recipe_collection.RecipeCollectionCandidateSet * { 抓取候选的产物：候选清单与工作区 })
  * $corpus (list[recipe_collection.RecipeCollectionCorpusEntry] * { 语料的全部条目：一条一个模型，带下载结果、代码角色、指纹、去重决定、可跑性结论与训练代码配对 })
  * $coverage (recipe_collection.RecipeCollectionCoverage * { 覆盖矩阵与缺口清单 })
  * $acceptance_report (recipe_collection.RecipeCollectionAcceptanceReport * { 七项验收指标的实际值与判定 })
  * $outputs (list[recipe_collection.RecipeCollectionOutput] * { 四份产出：模型代码、清单、覆盖度清单、回链；模型代码与两份清单放对象存储，回链由评估服务写进 recipe.yaml 的 latest_run })
  * { 六步按字段顺序走：抓取候选并建立工作区、下载并判定代码角色、去重、验证可跑、配对训练代码、覆盖统计与验收；语料是这份配方的产物，清单、覆盖度清单与回链都从语料算出来；语料版本升级前由负责人确认覆盖缺口清单 }
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
