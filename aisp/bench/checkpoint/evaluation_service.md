# 评估服务

## public.viba

只做转发：从 `## 问题` 的 `service` 模块与 `## 接口` 的 `service_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `RunRequest`、`ServiceManifest`、`ServiceRunVerdict`、`ServiceBacklink`，操作 `Submit`、`Query`、`Collect`、`Cancel`。先看 `RunRequest` 与 `Submit`，再顺着 `Query`、`Collect`、`Cancel` 读到 `ServiceRunVerdict` 与 `ServiceBacklink`；`ServiceManifest` 是运行清单，回链与历史可比性都从它出发。

```bash public
import aisp.bench.checkpoint.evaluation_service.types as service
import aisp.bench.checkpoint.evaluation_service.apis as service_api

RunRequest = service.RunRequest
ServiceManifest = service.ServiceManifest
ServiceRunVerdict = service.ServiceRunVerdict
ServiceBacklink = service.ServiceBacklink
Submit = service_api.Submit
Query = service_api.Query
Collect = service_api.Collect
Cancel = service_api.Cancel
```

## 背景

评估集不能只是一堆配方：配方解决"怎么测"，服务解决"谁来跑、跑完放哪、结论怎么回到配方上"。这份文档定义评估服务受理运行请求、执行与调度、出产物与回链所需的类型与操作，让评估集能被持续运行。

## types.viba

问题的形式化分成类型与枚举两类。配置与产物写成了类型：`RunRequest` 是一次运行的完整输入，`Framework` 与 `Load` 是它引用的两个类型，分别描述推理框架与负载；`ServiceManifest` 是运行清单，它的 `$request` 字段是 `RunRequest`，`$files` 字段是 `ServiceArtifactFile` 的列表；`ServiceRunDir` 直接取 `str` 类型，表示 `runs/<run-id>/` 这个运行目录；`ServiceBacklink` 是写回配方的回链，`ServiceVersionSet` 是必须同时记录的版本集合，`ServiceScheduling` 是排队与资源约束，`ServiceCiRun` 是一次 CI 运行。判定与分类写成了枚举：`ServiceRunVerdict` 是一次运行的结论，`passed`、`failed`、`invalid` 是它的三个取值；`ServiceFailureKind` 是失败分类，`ServicePriority` 是队列优先级，`ServiceInternalStage` 是执行中的内部阶段，`ServiceCiTrigger` 是 `ServiceCiRun` 的触发场景，`ServiceMetric` 是服务自身的观测指标，`ServiceOpenQuestion` 是尚未解决的问题。`ServiceBoundary` 的 `$does` 与 `$does_not` 都由枚举构成：`$does` 是 `ServiceResponsibility` 的列表，`$does_not` 是 `ServiceOutOfScope` 的列表；`ServiceBacklink` 的 `$status` 取 `ServiceRunVerdict`，`ServiceScheduling` 的 `$priority_order` 取 `ServicePriority` 的列表。

```bash types
import aisp.bench.checkpoint.ckpt_sample_interface.types as ckpt_sample
import aisp.bench.checkpoint.scaling.types as levels

RunRequest =
  Object
  * $recipe (str * { 配方标识，对应 recipes/<name>/ })
  * $recipe_version (str * { 配方版本，必须与仓库里的一致 })
  * $model (ckpt_sample.Model * { 被评估的模型 })
  * $framework ((Framework | nil) * { 推理框架；训练侧评估给 nil })
  * $level (levels.Level * { 规模档位 })
  * $topology (ckpt_sample.Topology * { 节点数、每节点卡数、网络与存储挂载方式 })
  * $storage (ckpt_sample.StorageLayer * { backend 与 adapter 两层；服务据此注入 AI_INFRA_STORAGE_BACKEND 与 AI_INFRA_STORAGE_ADAPTER })
  * $load (Load * { 负载配置 })
  * $observe (ckpt_sample.ObservationConfig * { 观测配置 })
  * $seed (int * { 随机种子 })

Framework =
  Object
  * $name (str * { 推理框架名：vllm、sglang、deepinfer 等 })
  * $version (str * { 框架版本 })

Load =
  Object
  * $concurrency (int * { 并发请求数 })
  * $duration_s (int * { 持续时长，秒 })
  * $input_len ((int | nil) * { 输入序列长度；训练侧或不适用时给 nil })
  * $output_len ((int | nil) * { 输出序列长度；训练侧或不适用时给 nil })
  * $arrival_interval_ms ((float | nil) * { 请求到达间隔，毫秒；不按固定间隔发时给 nil })
  * $batch_size ((int | nil) * { batch 大小；不适用时给 nil })

ServiceResponsibility =
  Oneof
  | "accept_and_validate" * { 接收运行请求，校验参数 }
  | "prepare_and_execute" * { 按配方准备环境、调度资源、执行 }
  | "collect_and_aggregate" * { 采集、校验、聚合结果 }
  | "write_artifacts_and_manifest" * { 把产物写入对象存储并生成清单 }
  | "write_back_latest_run" * { 把回链写回配方的 latest_run }

ServiceOutOfScope =
  Oneof
  | "decide_coverage" * { 决定评估集该覆盖什么 }
  | "change_recipe_semantics" * { 修改配方里的口径与阈值 }
  | "explain_business_result" * { 解释结论的业务含义 }
  | "retain_raw_trace" * { 长期保存原始 trace；原始 trace 按保留期清理 }
  | "merge_metric_change" * { 自动合并任何口径变更 }

ServiceBoundary =
  Object
  * $does (list[ServiceResponsibility] * { 服务负责的五件事 })
  * $does_not (list[ServiceOutOfScope] * { 服务不负责的五件事 })
  * $rule (str * { 判断标准：服务可以做任何按配方执行的事，不能做任何改变配方语义的事 })

ServiceFailureKind =
  Oneof
  | "environment" * { 环境失败；自动重试 2 次，仍失败则标记为环境问题并通知维护者 }
  | "dependency" * { 依赖失败；依赖缺失或版本不满足，与其它失败分类分开记录，供缺口分析使用 }
  | "code_unrunnable" * { 代码不可跑；不重试，记录到模型清单的缺口 }
  | "insufficient_resource" * { 资源不足；重新排队，不消耗重试次数 }
  | "timeout" * { 超时；记录超时点，保留已采集的度量 }
  | "observation" * { 观测失败；重跑一次，仍失败则标记该次运行无效，不进入对齐统计 }
  | "assertion" * { 断言失败；保留现场，不重试，进入缺口分析 }

ServiceRunVerdict =
  Oneof
  | "passed" * { 通过 }
  | "failed" * { 失败 }
  | "invalid" * { 无效运行：不能算通过，也不能算失败；它没有结论，只是没有数据，统计里必须与通过、失败分开 }

ServiceInternalStage =
  Oneof
  | "validate" * { 校验：校验请求与配方版本，留下校验报告 }
  | "prepare" * { 准备：拉代码、装依赖、准备数据、预热，留下环境清单 }
  | "collect" * { 采集收尾：校验、聚合、写产物与回链，留下度量文件 }

ServicePriority =
  Oneof
  | "regression" * { 回归，队列里优先级最高，不可被抢占 }
  | "new_case" * { 新用例，优先级次之 }
  | "exploration" * { 探索，优先级最低；抢占只针对这一类运行 }

ServiceScheduling =
  Object
  * $priority_order (list[ServicePriority] * { 队列顺序：回归 > 新用例 > 探索；同一优先级内按提交时间排序 })
  * $time_slice_single_rank (bool * { 单卡可被多个 rank 分时复用，同一时刻只允许一个 rank 占用，切换时清空显存 })
  * $isolation (str * { 不同运行不共享工作目录；共享存储的写入路径按 run-id 隔离 })
  * $quota (str * { 按团队配额限制并发与总卡时 })
  * $preemptible (list[ServicePriority] * { 只允许抢占探索类运行，回归类不可抢占 })
  * $high_bandwidth_parallel (int * { 同一存储后端上同时跑的高带宽运行数；硬约束是 1，两个并行跑测出来的是争用下的性能，不是评估结论 })

ServiceRunDir =
  str
  * { 一次运行的目录：runs/<run-id>/，下面是 manifest.json（运行清单：全部输入、版本、拓扑、观测配置）、metrics.json（本次运行的度量值）、alignment.json（对齐结果与容差对比）、report.html（人读报告）、trace/（原始 trace，按保留期清理）、artifacts/（生成的配置、检查点片段、日志） }

ServiceArtifactFile =
  Object
  * $path (str * { 产物文件在运行目录下的相对路径 })
  * $sha256 (str * { 该文件的校验和 })

ServiceManifest =
  Object
  * $request (RunRequest * { 这次运行的全部输入：配方、模型、框架、档位、拓扑、存储两层、负载、观测、种子 })
  * $service_version (str * { 服务版本；执行方式变了它变 })
  * $started_at (str * { 开始时间戳 })
  * $finished_at (str * { 结束时间戳 })
  * $state (ckpt_sample.State * { 结束时的状态；取值只用 ckpt_sample_interface.md 的 State })
  * $files (list[ServiceArtifactFile] * { 产物文件与校验和；manifest.json 是回链的核心 })

ServiceBacklink =
  Object
  * $run_id (str * { 运行标识 })
  * $report_uri (str * { 人读报告的位置 })
  * $metrics_uri (str * { 度量文件的位置 })
  * $sha256 (str * { 度量文件的校验和 })
  * $status (ServiceRunVerdict * { 这次运行的结论；无效运行不能算通过，也不能算失败 })
  * $finished_at (str * { 结束时间戳 })

ServiceVersionSet =
  Object
  * $recipe (str * { 配方版本，存在 recipe.yaml 的 version；流程或口径变了它变 })
  * $metrics (str * { 指标版本，存在 metrics/*/version；度量定义变了它变 })
  * $service (str * { 服务版本，存在 manifest.json 的 service_version；执行方式变了它变 })
  * $framework ((Framework | nil) * { 被评估对象的框架版本，存进 manifest.json；训练侧给 nil })
  * $model (ckpt_sample.Model * { 被评估对象的模型版本，存进 manifest.json })
  * $storage (ckpt_sample.StorageLayer * { 存储两层版本，存进 manifest.json 的 storage；backend 或 adapter 变了它变 })
  * $compatible_metrics (list[str] * { 配方的 compatible_metrics：按指标名声明兼容的版本列表；服务在运行前校验配方、指标、服务三者兼容，不兼容直接拒绝，不允许先跑再说 })

ServiceCiTrigger =
  Oneof
  | "recipe_change" * { 配方改动，提交时触发；跑该配方的最小用例（S0），验证配方可执行 }
  | "framework_upgrade" * { 框架升级，每日触发；跑三个框架的适配用例 }
  | "storage_change" * { 存储后端或适配层变更，变更时触发；跑受影响 backend / adapter 的对齐用例与 SLI 对比 }
  | "regression" * { 回归，每周触发；跑全部 S0 + 抽样 S1，对比基线 }
  | "exploration" * { 探索，持续触发；跑新发现的模型与场景 }

ServiceCiRun =
  Object
  * $trigger (ServiceCiTrigger * { 这次 CI 由哪个场景触发 })
  * $records (list[ckpt_sample.RunRecord] * { 这个场景跑出来的运行记录，每条都要回链 })
  * $small_scale_only (bool * { CI 里只跑小规模；大规模运行走队列人工触发 })
  * $backlink_required (bool * { CI 的结论也要回链，不允许 CI 里跑过但没留记录 })

ServiceMetric =
  Oneof
  | "success_rate" * { 运行成功率 }
  | "queue_duration" * { 平均排队时长 }
  | "run_duration" * { 平均执行时长 }
  | "failure_count" * { 每类失败的数量 }
  | "backlink_completeness" * { 回链完整率 }
  | "observation_overhead" * { 观测开销：开启与关闭观测的指标差异 }
  | "resource_utilization" * { 资源利用率 }

ServiceOpenQuestion =
  Oneof
  | "gpu_memory_cleanup" * { 分时复用单卡时，显存清理不彻底会导致后续 rank OOM，清理策略需要更严格的验证 }
  | "queue_wait_resource_pool" * { 大规模运行的排队时长可能超过一天，是否需要预留资源池 }
  | "fixed_observation" * { 观测配置不同会导致结果不可比，是否强制固定观测配置 }
  | "service_upgrade_rerun" * { 服务版本升级时，历史结果是否需要重跑以保持可比 }
```

运行请求的结构见 [`json_schema/RunRequest.schema.json`](json_schema/RunRequest.schema.json)。请求不允许有"其它"字段；新增字段先改这里的类型，再改服务。

## 基本操作

服务需要五个操作：提交、查询、取消、取产物、写回。提交校验请求与配方、指标、服务三者的版本兼容，不兼容直接拒绝，通过校验的请求按优先级入队，请求交出去就返回，不等样本跑完。查询答一次运行当前的状态、进度与产物位置，只读，完成与否只看状态不看进度。取消让服务停下这次运行，已经写完的产物保留。取产物交出运行清单与人读报告的位置，以及这次运行的度量值与判定。写回把回链写进对应配方的 `latest_run`，只写六个字段，且只能由服务执行。

## apis.viba

```bash apis
import aisp.bench.checkpoint.evaluation_service.types as service
import aisp.bench.checkpoint.ckpt_sample_interface.types as ckpt_sample

Submit =
     ckpt_sample.RunRecord
  <- $request (service.RunRequest * { 这次评估的运行请求：配方与版本、模型、框架、档位、拓扑、存储两层、负载、观测、种子 })
  <- { 提交接口：校验请求与版本，配方、指标、服务三者不兼容直接拒绝，返回状态为 rejected 的记录；通过校验的请求按优先级入队，请求交出去就返回，不等样本跑完，返回的记录此时可能仍在排队或执行中 }

Query =
     ckpt_sample.RunRecord
  <- $run_id (str * { 要查的那次运行 })
  <- { 查一次运行：答当前状态、进度与产物位置。只读，不改变运行；完成与否只看状态，不看进度 }

Collect =
     ckpt_sample.Artifacts
  <- $run_id (str * { 要取产物的那次运行 })
  <- { 取产物：交出运行清单与人读报告的位置，以及这次运行的 SLI 度量与 SLO 判定；原始 trace 按保留期清理 }

Cancel =
     ckpt_sample.RunRecord
  <- $run_id (str * { 要停的那次运行 })
  <- { 取消接口：让服务停下这次运行，已经写完的产物保留，返回的记录状态为 cancelled；已经结束的运行原样交回，不报错 }

Backlink =
     service.ServiceBacklink
  <- $record (ckpt_sample.RunRecord * { 要写回的那次运行 })
  <- $request (service.RunRequest * { 这次运行的请求；配方标识与版本来自这里 })
  <- $status (service.ServiceRunVerdict * { 这次运行的结论；无效运行不能算通过，也不能算失败 })
  <- { 写回配方：把回链写进对应配方的 latest_run，只写 run_id、report_uri、metrics_uri、sha256、status、finished_at 六个字段；写回只能由服务执行，配方里的口径、阈值、流程无权修改 }
```

接口返回的记录是 [ckpt_sample_interface.md](ckpt_sample_interface.md) 的 `RunRecord`：运行标识、状态、进度、产物位置；状态只用那份文档 `State` 的六个取值，本篇不另立状态类型。

命令行与 HTTP 是 Submit、Query、Collect、Cancel 四个操作的薄封装：命令行有 `eval run`、`eval status`、`eval result`、`eval cancel`，HTTP 有 `POST /v1/runs`、`GET /v1/runs/{run-id}`、`GET /v1/runs/{run-id}/artifacts`、`POST /v1/runs/{run-id}/cancel`，行为与接口一致；`Backlink` 由服务在运行结束后自己执行，不对外暴露。

## flow.viba

```bash flow
import aisp.bench.checkpoint.evaluation_service.types as service
import aisp.bench.checkpoint.evaluation_service.apis as service_api
import aisp.bench.checkpoint.ckpt_sample_interface.types as ckpt_sample

ServiceAdmitDuty =
  Object
  * $step (service_api.Submit * { 受理：提交运行请求，拿到 ckpt_sample.RunRecord })
  * $request (service.RunRequest * { 这一步的输入：配方与版本、模型、框架、档位、拓扑、存储两层、负载、观测、种子 })
  * $record (ckpt_sample.RunRecord * { 这一步的产物：运行标识、状态、进度与产物位置 })

ServiceExecuteDuty =
  Object
  * $query (service_api.Query * { 执行中查一次：状态、进度与产物位置 })
  * $cancel (service_api.Cancel * { 执行中取消：停下这次运行，已经写完的产物保留 })
  * $record (ckpt_sample.RunRecord * { 同一条运行记录；状态取自 ckpt_sample.State 的六个取值 })
  * $stages (list[service.ServiceInternalStage] * { 执行中的内部阶段：校验、准备、采集收尾，按顺序；它们不占对外状态 })
  * $scheduling (service.ServiceScheduling * { 排队与资源约束：优先级、分时、隔离、配额、抢占、高带宽串行 })
  * $failure ((service.ServiceFailureKind | nil) * { 失败时的分类；运行正常结束时给 nil })

ServiceDeliverDuty =
  Object
  * $collect (service_api.Collect * { 取产物：运行清单与人读报告的位置，以及 SLI 度量与 SLO 判定 })
  * $artifacts (ckpt_sample.Artifacts * { 这一步的产物：运行清单与人读报告的位置，以及 SLI 度量与 SLO 判定 })
  * $run_dir (service.ServiceRunDir * { 产物目录：runs/<run-id>/；原始 trace 按保留期清理 })
  * $manifest (service.ServiceManifest * { 运行清单：全部输入、版本、拓扑、观测配置与产物校验和 })
  * $status (service.ServiceRunVerdict * { 这次运行的结论：通过、失败或无效；无效运行不能算通过，也不能算失败，统计里必须单独分开 })
  * $backlink (service_api.Backlink * { 写回：把回链写进配方的 latest_run，只写六个字段 })

ServiceRun =
  Object
  * $admit (ServiceAdmitDuty * { 第一步，受理 })
  * $execute (ServiceExecuteDuty * { 第二步，执行与调度 })
  * $deliver (ServiceDeliverDuty * { 第三步，出产物与回链 })

ServiceCiDuty =
  Object
  * $ci (service.ServiceCiRun * { CI 场景：触发条件、跑出来的运行记录、只跑小规模、结论也要回链 })
  * $deliver (ServiceDeliverDuty * { CI 的运行同样要出产物与回链，不允许 CI 里跑过但没留记录 })

ServiceOperation =
  Oneof
  | $manual (ServiceRun * { 人工或队列触发的一次运行：受理、执行、交付三步 })
  | $ci (ServiceCiDuty * { CI 触发的一次运行：只跑小规模，大规模运行走队列人工触发 })

ServiceOverview =
  Object
  * $boundary (service.ServiceBoundary * { 服务负责什么、不负责什么；判据是不能改变配方语义 })
  * $versions (service.ServiceVersionSet * { 必须同时记录的版本：配方、指标、服务、框架与模型、存储两层；缺一条历史结果就不可比 })
  * $scheduling (service.ServiceScheduling * { 排队与资源约束 })
  * $operations (list[ServiceOperation] * { 每次运行要么由人工或队列触发，要么由 CI 触发 })
  * $metrics (list[service.ServiceMetric] * { 服务自身的观测：成功率、排队与执行时长、每类失败数量、回链完整率、观测开销、资源利用率 })
  * $open_questions (list[service.ServiceOpenQuestion] * { 尚未解决的问题：显存清理、排队时长与资源池、观测配置是否固定、服务升级是否重跑 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
