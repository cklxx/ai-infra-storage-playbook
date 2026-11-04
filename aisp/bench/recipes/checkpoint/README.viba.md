# Checkpoint 存储评估配方

## public.viba

只做转发：从 `## 问题` 的 `recipe_checkpoint` 模块与 `## 接口` 的 `recipe_checkpoint_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `RecipeCheckpointSpec`、`RecipeCheckpointBypass` 与 `RecipeCheckpointProducts`，操作 `RunBaseline`、`PrepareBypass`、`Align`、`Scale` 与 `Register`；先看 `RecipeCheckpointSpec` 与 `RecipeCheckpointBypass`，再按 `RunBaseline`、`PrepareBypass`、`Align`、`Scale`、`Register` 的顺序读到 `RecipeCheckpointProducts`。

```bash public
import aisp.bench.checkpoint.checkpoint.types as checkpoint
import aisp.bench.recipes.checkpoint.readme.types as recipe_checkpoint
import aisp.bench.recipes.checkpoint.readme.apis as recipe_checkpoint_api

RecipeCheckpointSpec = recipe_checkpoint.RecipeCheckpointSpec
RecipeCheckpointBypass = recipe_checkpoint.RecipeCheckpointBypass
RecipeCheckpointProducts = recipe_checkpoint.RecipeCheckpointProducts
RunBaseline = recipe_checkpoint_api.RunBaseline
PrepareBypass = recipe_checkpoint_api.PrepareBypass
Align = recipe_checkpoint_api.Align
Scale = recipe_checkpoint_api.Scale
Register = recipe_checkpoint_api.Register
```

## 背景

训练侧存储评估，评估对象是训练框架的 checkpoint 写入与读取两条路径，计算部分被旁路。目标是在真实存储与传输路径上测出训练任务产生的 IO 特征，不在合成负载上测，并把结论从单机小参数外推到十万卡。方法说明见 [`checkpoint/checkpoint.viba.md`](../../checkpoint/checkpoint.viba.md)。

## types.viba

问题形式化为 `recipe_checkpoint` 模块，概念分成类型与枚举两类：承载字段的结构写成对象类型，取值只能落在有限集合里的词汇写成 Oneof 枚举。`RecipeCheckpointSpec` 是入口类型，五个字段分别收下输入 `RecipeCheckpointInput`、配置要求 `RecipeCheckpointConfig`、`RecipeCheckpointStage` 的列表、产出 `RecipeCheckpointProducts` 与 `RecipeCheckpointAcceptanceItem` 的列表；`RecipeCheckpointInput` 用 `RecipeCheckpointVersionedName` 描述框架、storage.backend 与 storage.adapter，用 `RecipeCheckpointParallel` 描述四个并行度数，`RecipeCheckpointConfig` 的并行策略覆盖与写入方式分别取 `RecipeCheckpointParallelLead` 与 `RecipeCheckpointWriteMode` 这两个枚举的列表。步骤、阶段门与验收项写成枚举：`RecipeCheckpointStep` 给出六个步骤，`checkpoint.CheckpointGate` 给出六个阶段门，`RecipeCheckpointAcceptanceItem` 给出验收项，`RecipeCheckpointStage` 把 `RecipeCheckpointStep` 的一个取值与 `checkpoint.CheckpointGate` 的一个取值配成一对；`RecipeCheckpointBypass` 由 `RecipeCheckpointBypassStep` 的列表、`fidelity.FidelityBoundary` 的列表与一条 `ckpt_sample.RunRecord` 组成。判定与放大的结果各有类型：`RecipeCheckpointAlignment` 由 `RecipeCheckpointAlignmentItem` 的列表与一个 `bool` 结论组成，`RecipeCheckpointScaling` 由 `RecipeCheckpointParameterScaling` 与 `RecipeCheckpointClusterScaling` 组成，两者的检查分别取 `RecipeCheckpointParameterScalingCheck` 与 `RecipeCheckpointClusterScalingCheck` 的列表，并各带一个 `checkpoint.CheckpointGate`；`RecipeCheckpointRegistration` 记录登记结果，`RecipeCheckpointProducts` 的四个字段都是 `str`，给出四份产出的位置。

```bash types
import aisp.bench.checkpoint.checkpoint.types as checkpoint
import aisp.bench.checkpoint.fidelity.types as fidelity
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample

RecipeCheckpointInput =
  Object
  * $model_code (str * { 模型代码：取自 recipes/model_code_collection 的语料 })
  * $framework (RecipeCheckpointVersionedName * { 所用的训练框架及版本 })
  * $parallel (RecipeCheckpointParallel * { 并行配置：DP、TP、PP、EP 的度数 })
  * $dataset_layout (str * { 数据集布局：与真实训练一致的目录结构与文件切分 })
  * $storage_backend (RecipeCheckpointVersionedName * { storage.backend：纯存储系统，例如 GPFS、Ceph、JuiceFS })
  * $storage_adapter (RecipeCheckpointVersionedName * { storage.adapter：存储传输适配层，例如 torchstore、bytecheckpoint })

RecipeCheckpointVersionedName =
  Object
  * $name (str * { 组件名 })
  * $version (str * { 组件版本 })

RecipeCheckpointParallel =
  Object
  * $dp (int * { 数据并行的度数，按真实配置设置 })
  * $tp (int * { 张量并行的度数，按真实配置设置 })
  * $pp (int * { 流水并行的度数，按真实配置设置 })
  * $ep (int * { 专家并行的度数，按真实配置设置 })

RecipeCheckpointBypassStep =
  Oneof
  | "meta_model" * { 模型用 torch.device("meta") 构建 }
  | "meta_forward" * { 前向用 meta 输入执行 }
  | "placeholder_backward" * { 反向用占位梯度，保证 param.grad 存在且尺寸正确 }
  | "placeholder_optimizer" * { optimizer 换成占位更新，保留 state_dict() 的键结构与分片 }
  | "unchanged_checkpoint_io" * { checkpoint 写入与读取不改 }

RecipeCheckpointBypass =
  Object
  * $steps (list[RecipeCheckpointBypassStep] * { 旁路做法，按原顺序：构建模型、前向、反向、optimizer、checkpoint 写入与读取 })
  * $fidelity_boundary (list[fidelity.FidelityBoundary] * { 保真边界表；第 2 步的通过条件是它填完 })
  * $run (ckpt_sample.RunRecord * { 旁路后跑完与第 1 步相同流程的运行记录；取得 G1 })

RecipeCheckpointConfig =
  Object
  * $parallel_coverage (list[RecipeCheckpointParallelLead] * { 并行策略：至少覆盖 DP 主导、TP 主导、PP 主导、EP 各一组 })
  * $checkpoint_implementation (RecipeCheckpointVersionedName * { checkpoint 实现：记录实现名与版本；不同实现不混在一份结论里 })
  * $write_modes (list[RecipeCheckpointWriteMode] * { 写入方式：同步与异步分别测，不合并 })
  * $data_layout (str * { 数据布局：与真实训练一致；样本量可以缩小，文件切分与格式不能改 })
  * $warmup_rounds (int * { 预热：固定轮数，报告只取稳态窗口 })

RecipeCheckpointParallelLead =
  Oneof
  | "dp_led" * { DP 主导的一组 }
  | "tp_led" * { TP 主导的一组 }
  | "pp_led" * { PP 主导的一组 }
  | "ep" * { EP 的一组 }

RecipeCheckpointWriteMode =
  Oneof
  | "sync" * { 同步写入 }
  | "async" * { 异步写入 }

RecipeCheckpointStep =
  Oneof
  | "select_and_run" * { 第 1 步：选一个最小可用模型（语料里参数量最小的一档），按真实并行配置跑通若干训练步，不旁路 }
  | "bypass" * { 第 2 步：接入旁路；模型用 meta device 构建，前向用 meta 输入，反向用占位梯度，optimizer 换成占位更新，checkpoint 写入与读取不改 }
  | "alignment" * { 第 3 步：同一配置跑两遍，一次真实、一次旁路，观测配置相同，按 metrics.yaml 的容差判定分项 }
  | "scale_parameters" * { 第 4 步：固定集群规模与并行策略，把参数量放大一级 }
  | "scale_cluster" * { 第 5 步：固定参数量，把集群规模放到万卡，再外推到十万卡 }
  | "register" * { 第 6 步：回链写入 latest_run，更新覆盖度矩阵，未解决的偏差进坑表 }


RecipeCheckpointStage =
  Object
  * $step (RecipeCheckpointStep * { 六个步骤之一 })
  * $gate (checkpoint.CheckpointGate * { 这一步的通过条件；按步骤顺序对应 G0、G1、G2、G3-a、G3-b、G4 })

RecipeCheckpointProducts =
  Object
  * $io_pattern (str * { IO pattern 记录的位置；记录与 schemas/io-pattern.schema.json 一致；产物全部放对象存储 })
  * $alignment_report (str * { 对齐报告的位置：真实运行与旁路运行的分项对比；产物全部放对象存储 })
  * $scaling_report (str * { scaling 报告的位置：逐级不变量对比与偏差归因；产物全部放对象存储 })
  * $backlink (str * { 回链：recipe.yaml 的 latest_run；仓库只保留回链 })

RecipeCheckpointAcceptanceItem =
  Oneof
  | "alignment" * { 对齐分项：全部分项在容差内，或有条件通过且偏差已归因 }
  | "per_parameter_bytes" * { 每参数字节数：计算值与观测值的相对误差 ≤ 2% }
  | "scaling_consistency" * { scaling 一致性：每级相邻偏差在容差内，无单调恶化 }
  | "coverage" * { 覆盖：并行策略、集群规模、参数量三个轴上的已覆盖格子数达标 }
  | "reproducibility" * { 可复现：配置、commit、拓扑、预热、观测全部登记 }

RecipeCheckpointAlignmentItem =
  Object
  * $metric (str * { 分项名称，按 metrics.yaml 的度量项 })
  * $within_tolerance (bool * { 这一项是否在容差内 })
  * $conditional (bool * { 这一项是否属于有条件通过 })
  * $attribution (str * { 这一项的偏差归因；不通过项按 checkpoint/methodology.viba.md 的归因顺序排查，结论写进本目录的 notes 或方法文档的坑表 })

RecipeCheckpointAlignment =
  Object
  * $items (list[RecipeCheckpointAlignmentItem] * { 分项对比，每项一条 })
  * $within_tolerance (bool * { 全部分项是否在容差内或有条件通过 })

RecipeCheckpointParameterScalingCheck =
  Oneof
  | "per_rank_request_size_distribution" * { 每 rank 写入请求大小分布是否保持 }
  | "per_parameter_bytes" * { 每参数字节数是否保持 }
  | "shard_count_and_size" * { 分片数与每片大小的变化是否符合预期 }

RecipeCheckpointParameterScaling =
  Object
  * $checks (list[RecipeCheckpointParameterScalingCheck] * { 第 4 步的三项检查 })
  * $gate (checkpoint.CheckpointGate * { 通过条件 G3-a })

RecipeCheckpointClusterScalingCheck =
  Oneof
  | "single_rank_request_size_and_concurrency" * { 单 rank 请求大小与并发度是否保持 }
  | "aggregate_bandwidth_knee" * { 聚合带宽是否出现饱和拐点 }
  | "metadata_saturation" * { 元数据操作数是否先于数据字节数饱和 }
  | "tail_latency" * { 尾延迟是否超线性增长 }

RecipeCheckpointClusterScaling =
  Object
  * $checks (list[RecipeCheckpointClusterScalingCheck] * { 第 5 步的四项检查 })
  * $attribution (str * { 偏差归因；G3-b 的通过条件要求偏差有归因 })
  * $gate (checkpoint.CheckpointGate * { 通过条件 G3-b })

RecipeCheckpointScaling =
  Object
  * $parameters (RecipeCheckpointParameterScaling * { 第 4 步：固定集群规模与并行策略，把参数量放大一级 })
  * $cluster (RecipeCheckpointClusterScaling * { 第 5 步：固定参数量，把集群规模放到万卡，再外推到十万卡 })

RecipeCheckpointRegistration =
  Object
  * $backlink (str * { 回链已写入 recipe.yaml 的 latest_run })
  * $coverage_updated (bool * { 覆盖度矩阵是否已更新 })
  * $unresolved_deviations (list[str] * { 未解决的偏差；进坑表 })

RecipeCheckpointSpec =
  Object
  * $input (RecipeCheckpointInput * { 输入：模型代码、训练框架与版本、并行配置、数据集布局、storage.backend 与 storage.adapter })
  * $config (RecipeCheckpointConfig * { 配置要求：并行策略覆盖、checkpoint 实现、写入方式、数据布局、预热 })
  * $stages (list[RecipeCheckpointStage] * { 六个阶段，按原顺序 })
  * $products (RecipeCheckpointProducts * { 产出：IO pattern 记录、对齐报告、scaling 报告、回链 })
  * $acceptance (list[RecipeCheckpointAcceptanceItem] * { 五项验收目标 })
```

## 基本操作

先跑通一次不旁路的训练（`RunBaseline`）：选语料里参数量最小的一档模型，按真实并行配置跑若干训练步，取得 G0。

1. 然后接入旁路（`PrepareBypass`）：模型用 meta device 构建，前向用 meta 输入，反向用占位梯度，optimizer 换成占位更新，checkpoint 写入与读取不改，旁路后跑完同一流程并填完保真边界表，取得 G1。
2. 对齐通过后逐级放大（`Scale`）：先固定集群规模与并行策略放大参数量，按 G3-a 判定三项检查；再固定参数量把集群规模放到万卡、外推到十万卡，按 G3-b 判定四项检查，偏差要有归因。
3. 最后登记（`Register`）：回链写入 [`recipe.yaml`](recipe.yaml) 的 `latest_run`，更新覆盖度矩阵，未解决的偏差进坑表，取得 G4。

## apis.viba

```bash apis
import aisp.bench.recipes.checkpoint.readme.types as recipe_checkpoint
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample

RunBaseline =
     ckpt_sample.RunRecord
  <- $input (recipe_checkpoint.RecipeCheckpointInput * { 配方输入：模型代码、训练框架与版本、并行配置、数据集布局、storage.backend 与 storage.adapter })
  <- $config (recipe_checkpoint.RecipeCheckpointConfig * { 配置要求：并行策略覆盖、checkpoint 实现、写入方式、数据布局、预热 })
  <- $steps (int * { 这次要跑的训练步数；第 1 步要求跑通若干训练步 })
  <- { 第 1 步选型与跑通：选一个最小可用模型（语料里参数量最小的一档），按真实并行配置跑若干训练步，不旁路；取得 G0，即跑完一次前向、一次反向、一次 optimizer.step 与一次 checkpoint 写入。返回这次运行的记录 }

PrepareBypass =
     recipe_checkpoint.RecipeCheckpointBypass
  <- $baseline (ckpt_sample.RunRecord * { 第 1 步跑通的不旁路运行；G0 已通过 })
  <- { 第 2 步接入旁路：模型用 torch.device("meta") 构建，前向用 meta 输入执行，反向用占位梯度保证 param.grad 存在且尺寸正确，optimizer 换成占位更新并保留 state_dict() 的键结构与分片，checkpoint 写入与读取不改。返回旁路做法、填完的保真边界表与这次旁路运行记录；取得 G1 }

Align =
     recipe_checkpoint.RecipeCheckpointAlignment
  <- $real (ckpt_sample.RunRecord * { 不做旁路的运行；与旁路运行同一配置，观测配置相同 })
  <- $bypass (ckpt_sample.RunRecord * { 旁路运行；与真实运行同一配置，观测配置相同 })
  <- { 第 3 步小规模对齐：同一配置跑两遍，一次真实、一次旁路，观测配置相同；按 metrics.yaml 的容差判定分项，不通过的项按 checkpoint/methodology.viba.md 的归因顺序排查；全部在容差内或有条件通过取得 G2。返回分项对比与判定 }

Scale =
     recipe_checkpoint.RecipeCheckpointScaling
  <- $input (recipe_checkpoint.RecipeCheckpointInput * { 配方输入：模型代码、训练框架与版本、并行配置、数据集布局、storage.backend 与 storage.adapter })
  <- $config (recipe_checkpoint.RecipeCheckpointConfig * { 配置要求：并行策略覆盖、checkpoint 实现、写入方式、数据布局、预热 })
  <- $alignment (recipe_checkpoint.RecipeCheckpointAlignment * { 通过 G2 的小规模对齐结果 })
  <- $parameter_target (str * { 第 4 步放大一级后的参数量目标；固定集群规模与并行策略 })
  <- $cluster_targets (list[str] * { 第 5 步的集群规模目标：先到万卡，再外推到十万卡；固定参数量 })
  <- { 第 4、5 步逐级放大：先固定集群规模与并行策略把参数量放大一级，检查每 rank 写入请求大小分布、每参数字节数、分片数与每片大小的变化，取得 G3-a；再固定参数量把集群规模放到万卡、外推到十万卡，检查单 rank 请求大小与并发度、聚合带宽饱和拐点、元数据操作是否先于数据字节数饱和、尾延迟是否超线性增长，取得 G3-b，偏差要有归因。返回两级放大的结果 }

Register =
     recipe_checkpoint.RecipeCheckpointRegistration
  <- $alignment (recipe_checkpoint.RecipeCheckpointAlignment * { 小规模对齐结果；G2 })
  <- $scaling (recipe_checkpoint.RecipeCheckpointScaling * { 两级放大结果；G3-a 与 G3-b })
  <- $products (recipe_checkpoint.RecipeCheckpointProducts * { 四份产出：IO pattern 记录、对齐报告、scaling 报告、回链 })
  <- { 第 6 步登记：把回链写入 recipe.yaml 的 latest_run，更新覆盖度矩阵，未解决的偏差进坑表；取得 G4。返回登记结果 }
```

## flow.viba

`recipe_checkpoint_flow` 把输入、配置、五个操作与四份产出串成一次完整评估：五个操作覆盖六个步骤，阶段门按原顺序判定。

```bash flow
import aisp.bench.recipes.checkpoint.readme.types as recipe_checkpoint
import aisp.bench.recipes.checkpoint.readme.apis as recipe_checkpoint_api
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample

RecipeCheckpointBaselineDuty =
  Object
  * $step (recipe_checkpoint_api.RunBaseline * { 第 1 步选型与跑通：取得 G0 })
  * $run (ckpt_sample.RunRecord * { 产物：不旁路运行的记录 })

RecipeCheckpointBypassDuty =
  Object
  * $step (recipe_checkpoint_api.PrepareBypass * { 第 2 步接入旁路：取得 G1 })
  * $result (recipe_checkpoint.RecipeCheckpointBypass * { 产物：旁路做法、保真边界表与旁路运行记录 })

RecipeCheckpointAlignDuty =
  Object
  * $step (recipe_checkpoint_api.Align * { 第 3 步小规模对齐：取得 G2 })
  * $alignment (recipe_checkpoint.RecipeCheckpointAlignment * { 产物：分项对比与容差判定 })

RecipeCheckpointScaleDuty =
  Object
  * $step (recipe_checkpoint_api.Scale * { 第 4、5 步逐级放大：取得 G3-a 与 G3-b })
  * $scaling (recipe_checkpoint.RecipeCheckpointScaling * { 产物：参数规模与集群规模两级放大的结果 })

RecipeCheckpointRegisterDuty =
  Object
  * $step (recipe_checkpoint_api.Register * { 第 6 步登记：取得 G4 })
  * $registration (recipe_checkpoint.RecipeCheckpointRegistration * { 产物：回链、覆盖度矩阵更新状态、未解决的偏差 })

RecipeCheckpointFlow =
  Object
  * $spec (recipe_checkpoint.RecipeCheckpointSpec * { 问题定义：输入、配置要求、六个阶段、产出与验收目标 })
  * $baseline (RecipeCheckpointBaselineDuty * { 第 1 步 })
  * $bypass (RecipeCheckpointBypassDuty * { 第 2 步 })
  * $alignment (RecipeCheckpointAlignDuty * { 第 3 步 })
  * $scaling (RecipeCheckpointScaleDuty * { 第 4、5 步 })
  * $registration (RecipeCheckpointRegisterDuty * { 第 6 步 })
  * $products (recipe_checkpoint.RecipeCheckpointProducts * { 四份产出：IO pattern 记录、对齐报告、scaling 报告、回链；产物全部放对象存储，仓库只保留回链 })
  * $acceptance (list[recipe_checkpoint.RecipeCheckpointAcceptanceItem] * { 五项验收目标 })
```

验收里的 SLO 指标与判定顺序见 [`checkpoint/performance.viba.md`](../../checkpoint/performance.viba.md) 的 3.1 节。负责人见 [`recipe.yaml`](recipe.yaml) 的 `owner`；开放问题见 [`checkpoint/checkpoint.viba.md`](../../checkpoint/checkpoint.viba.md) 的「开放问题」。

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
