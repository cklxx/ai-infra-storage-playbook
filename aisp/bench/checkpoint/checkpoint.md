# Checkpoint 存储评估

## public

只做转发：从 `## 问题` 的 `checkpoint` 模块与 `## 接口` 的 `checkpoint_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `CheckpointSpec`、`CheckpointFidelity` 与 `CheckpointConclusion`，操作 `PrepareBypass`、`RecordBoundary`、`Align`、`ScaleUp` 与 `Register`；先看 `CheckpointSpec` 与 `PrepareBypass`，再按 `RecordBoundary`、`Align`、`ScaleUp`、`Register` 的顺序读到 `CheckpointFidelity` 与 `CheckpointConclusion`。

```bash checkpoint_public
import aisp.bench.checkpoint.checkpoint.checkpoint as checkpoint
import aisp.bench.checkpoint.checkpoint.checkpoint_api as checkpoint_api

CheckpointSpec = checkpoint.CheckpointSpec
CheckpointFidelity = checkpoint.CheckpointFidelity
CheckpointConclusion = checkpoint.CheckpointConclusion
PrepareBypass = checkpoint_api.PrepareBypass
RecordBoundary = checkpoint_api.RecordBoundary
Align = checkpoint_api.Align
ScaleUp = checkpoint_api.ScaleUp
Register = checkpoint_api.Register
```

## 背景

训练侧的存储评估，评估对象是 checkpoint 的写入与读取。目标是在真实存储与传输路径上测出训练任务产生的 IO 行为，并把结论从单卡、小参数规模外推到十万卡。本篇只写这两条路径的特殊之处，旁路与保真的总则见 [`methodology.md`](methodology.md)。

## checkpoint

checkpoint 存储评估的形式化分成类型与枚举两类。`CheckpointSpec` 是入口的 Object 类型，把评估对象 `CheckpointSubject`、旁路方案 `CheckpointBypassPlan` 与保真边界 `CheckpointFidelity` 分别收成 `$subject`、`$bypass` 与 `$fidelity` 三个字段，把阶段门、小规模对齐、放大维度、外推规则与验收项收成 `$gates`、`$alignment`、`$scaling`、`$extrapolation`、`$acceptance` 五个列表字段；`CheckpointFidelity` 的每一行是 `fidelity.FidelityBoundary`。可选项写成 Oneof 枚举：`CheckpointGate`、`CheckpointAlignmentStep`、`CheckpointScalingDimension`、`CheckpointExtrapolationRule` 与 `CheckpointAcceptanceItem` 依次是 `CheckpointSpec` 的 `$gates`、`$alignment`、`$scaling`、`$extrapolation` 与 `$acceptance` 的元素类型；`CheckpointWriteFeature` 与 `CheckpointReadFeature` 是写入侧与读取侧要记录的特征，`CheckpointBypassStep` 与 `CheckpointBypassConstraint` 是旁路的一个步骤与一条约束，分别构成 `CheckpointSubject` 的 `$write_features`、`$read_features` 与 `CheckpointBypassPlan` 的 `$steps`、`$constraints`。对齐、放大、结论、登记与并行配置各有自己的类型：`CheckpointAlignment` 记对齐步骤与容差判定，`CheckpointScalingRun` 记逐级放大的每一级，其中 `$dimension` 取 `CheckpointScalingDimension` 的一个取值，`CheckpointConclusion` 的 `$alignment` 取 `CheckpointAlignment`、`$scaling` 取 `CheckpointScalingRun` 的列表，另收验收项与回链，`CheckpointRegistration` 记结论与覆盖矩阵的更新状态，`CheckpointParallel` 记 DP/TP/PP/EP 四个度数。

```bash checkpoint
import aisp.bench.checkpoint.methodology.fidelity as fidelity
import aisp.bench.checkpoint.scaling.levels as levels
import aisp.bench.checkpoint.ckpt_sample_interface.ckpt_sample as ckpt_sample

CheckpointSpec =
  Object
  * $subject (CheckpointSubject * { 评估对象：训练框架的 checkpoint 写入与读取两条路径，以及必须记录的写入侧与读取侧特征 })
  * $bypass (CheckpointBypassPlan * { 旁路 forward / backward / optimizer 的五步做法与四条约束；checkpoint 写入完全不改 })
  * $fidelity (CheckpointFidelity * { 保真边界表：本评估集的五条必填行；完整实例见 recipes/checkpoint/recipe.yaml })
  * $gates (list[CheckpointGate] * { 六个步骤的阶段门，按原顺序：G0、G1、G2、G3-a、G3-b、G4 })
  * $alignment (list[CheckpointAlignmentStep] * { 小规模对齐的四个步骤；基准是不做旁路的同规模真实运行 })
  * $scaling (list[CheckpointScalingDimension] * { scaling 的五个维度，每个维度带应保持的不变量与预期变化的变量 })
  * $extrapolation (list[CheckpointExtrapolationRule] * { 三条外推规则：聚合带宽、元数据操作、每参数字节数 })
  * $acceptance (list[CheckpointAcceptanceItem] * { 五项验收：IO pattern 对齐度、scaling 一致性、保真度、可复现、覆盖 })

CheckpointSubject =
  Object
  * $implementation (ckpt_sample.Component * { 训练框架的分布式检查点实现，记录名字与版本；checkpoint 的 IO 由它决定，不由模型代码决定，换一个实现结论就变了 })
  * $sharding (str * { 分片方案：按 DP 切、按 TP 切、按 PP 切、ZeRO 分片、参数与优化器状态分开存；它直接决定每个 rank 写多少、写几次、写多大块 })
  * $write_features (list[CheckpointWriteFeature] * { 写入侧必须记录的特征，每项一条 })
  * $read_features (list[CheckpointReadFeature] * { 读取侧（恢复训练）单独记录的特征，每项一条 })

CheckpointWriteFeature =
  Oneof
  | "total_bytes" * { 写入总字节；决定单次 checkpoint 的带宽需求 }
  | "shard_count_and_size" * { 分片数与每片大小；决定并发度与请求大小分布 }
  | "write_concurrency" * { 写入并发度；决定存储侧的峰值压力 }
  | "sync_or_async" * { 同步写入还是异步写入；异步写入会把 IO 与计算重叠，时序完全不同 }
  | "compression" * { 是否压缩、压缩算法与分段；改变请求大小与 CPU 开销 }
  | "metadata_commit" * { 元数据提交方式；大量小文件与少量大文件的压力点完全不同 }
  | "write_period" * { 写入周期；checkpoint 间隔决定平均带宽与突发占比 }

CheckpointReadFeature =
  Oneof
  | "overlap_with_training_start" * { 读取是否与训练启动重叠 }
  | "per_rank_parallel_read" * { 读取是否按 rank 并发读 }
  | "hash_verification" * { 读取是否校验哈希 }

CheckpointParallel =
  Object
  * $dp (int * { 数据并行的度数，按真实配置设置 })
  * $tp (int * { 张量并行的度数，按真实配置设置 })
  * $pp (int * { 流水并行的度数，按真实配置设置 })
  * $ep (int * { 专家并行的度数，按真实配置设置 })

CheckpointBypassStep =
  Oneof
  | "meta_model" * { 用 torch.device("meta") 构建模型：参数与缓冲区只保留 dtype 与逻辑尺寸，不分配真实内存 }
  | "meta_forward" * { 前向：输入也放在 meta device 上，前向照常执行；计算不发生，但控制流、模块调用顺序、张量的逻辑尺寸全部真实 }
  | "placeholder_backward" * { 反向：直接对 meta 张量调 backward() 会因为没有真实存储而失败；按训练框架的用法构造梯度的占位实现，保证 param.grad 存在且尺寸正确 }
  | "mock_optimizer" * { optimizer：替换为只更新占位张量的 mock，保留 state_dict() 的键结构与分片逻辑；检查点写入依赖 state_dict() 的键与分片，不能简化成空实现 }
  | "unchanged_checkpoint_write" * { 检查点写入：完全不改，走框架原有实现 }

CheckpointBypassConstraint =
  Oneof
  | "model_code_source" * { 模型代码必须来自 recipes/model_code_collection，且是训练侧可用的实现；推理代码不能直接拿来跑预训练 }
  | "parallel_strategy" * { 并行策略（DP/TP/PP/EP）必须按真实配置设置；旁路只去掉计算，不去掉并行切分 }
  | "parameter_init" * { 参数初始化：meta device 不需要真实初始化，但若框架在初始化阶段就写盘（例如初始化检查点），该路径必须保留 }
  | "mixed_precision" * { 混合精度：dtype 必须与真实训练一致，否则写入字节数直接错 }

CheckpointBypassPlan =
  Object
  * $steps (list[CheckpointBypassStep] * { 旁路的五步做法，按原顺序执行 })
  * $constraints (list[CheckpointBypassConstraint] * { 旁路必须满足的四条约束 })

CheckpointFidelity =
  Object
  * $forward_backward (fidelity.FidelityBoundary * { 必填行：path=forward / backward；bypassed=yes；method=meta_device；fidelity=L2；kept=模块调用顺序、张量逻辑尺寸、梯度键结构；known_bias=计算耗时为 0，写入时序可能被压缩 })
  * $optimizer_step (fidelity.FidelityBoundary * { 必填行：path=optimizer.step；bypassed=yes；method 记作占位更新；fidelity=L1；kept=state_dict() 的键结构与分片；known_bias=优化器状态不真实变化 })
  * $parallel_split (fidelity.FidelityBoundary * { 必填行：path=并行切分与通信分组；bypassed=no；method=nil；fidelity=L2；kept=DP/TP/PP/EP 的分组与分片；known_bias=通信内容被 mock 时同步丢失 })
  * $checkpoint_write (fidelity.FidelityBoundary * { 必填行：path=checkpoint 写入与元数据提交；bypassed=no；method=nil；fidelity=L2；kept=真实写入调用、真实文件系统或对象存储；known_bias=无 })
  * $checkpoint_read (fidelity.FidelityBoundary * { 必填行：path=checkpoint 读取与恢复；bypassed=no；method=nil；fidelity=L2；kept=真实读取调用、真实校验；known_bias=无 })

CheckpointGate =
  Oneof
  | "G0" * { 第 1 步的通过条件：能跑；选模型、选训练框架与并行配置，跑通一次不旁路的训练若干步 }
  | "G1" * { 第 2 步的通过条件：旁路可跑，保真边界表填完；接入 meta device 与占位 optimizer，保持 IO 路径不变 }
  | "G2" * { 第 3 步的通过条件：选定度量项在容差内；小集群小参数规模运行，与真实小规模运行对比 IO pattern }
  | "G3-a" * { 第 4 步的通过条件：不变量保持，偏差有归因；固定并行策略，放大参数量 }
  | "G3-b" * { 第 5 步的通过条件：不变量保持，偏差有归因；固定参数量，先到万卡（S4），再外推到十万卡（S5） }
  | "G4" * { 第 6 步的通过条件：回链三要素齐全；登记结论与回链，更新覆盖矩阵 }

CheckpointAlignmentStep =
  Oneof
  | "minimal_config" * { 取最小可用配置：单机 8 卡或更小，参数量最小的一档 }
  | "real_and_bypass_runs" * { 一次真实运行，一次旁路运行，两次都开观测 }
  | "compare_metrics" * { 对比 methodology.md 列出的度量项，按配方 metrics.yaml 里标定的容差判定 }
  | "attribute_deviations" * { 差异超过容差时按 methodology.md 的归因顺序排查 }

CheckpointAlignment =
  Object
  * $steps (list[CheckpointAlignmentStep] * { 对齐的四个步骤，按原顺序 })
  * $within_tolerance (bool * { 选定度量项是否全部落在配方 metrics.yaml 标定的容差内；超出容差时按 methodology.md 的归因顺序排查 })

CheckpointScalingDimension =
  Oneof
  | "parameter_count" * { 参数量上升；不变量：每 rank 的写入请求大小分布、读写比；变量：写入总字节、分片数 }
  | "cluster_size" * { 集群规模上升；不变量：单 rank 的请求大小与并发度；变量：聚合带宽、元数据操作总数、峰值持续时间 }
  | "data_parallel" * { DP 上升；不变量：每片大小、单 rank 写入顺序；变量：分片数、元数据请求数 }
  | "tensor_pipeline_parallel" * { TP/PP 上升；不变量：计算与写入的时间重叠关系；变量：每片大小、片内偏移 }
  | "expert_parallel" * { EP 上升；不变量：单专家分片的写入模式；变量：专家分片数与分布 }

CheckpointExtrapolationRule =
  Oneof
  | "aggregate_bandwidth" * { 聚合带宽 ≈ 单 rank 带宽 × 并发 rank 数，只在存储侧未饱和时成立；超过存储侧上限后，外推必须改用排队模型，并用中间规模实测校正 }
  | "metadata_operations" * { 元数据操作数随分片数线性增长，不随总字节增长；分片数放大到数万卡量级时，元数据可能先饱和 }
  | "parameter_bytes" * { 写入总字节随参数量线性增长，但优化器状态与梯度的比例固定，所以每参数字节数是不变量 }

CheckpointScalingRun =
  Object
  * $dimension (CheckpointScalingDimension * { 这一次放大的维度，取值见 CheckpointScalingDimension；第 4 步放大参数量，第 5 步放大集群规模 })
  * $target ((levels.Level | nil) * { 放大集群规模时的目标档位，先到万卡（S4），再外推到十万卡（S5）；只放大参数量时给 nil })
  * $invariants_kept (bool * { 选定的不变量是否都在容差内保持 })
  * $attribution (str * { 偏差归因；没有偏差写 none，不留空 })

CheckpointAcceptanceItem =
  Oneof
  | "io_pattern_alignment" * { 口径见 metrics/io_pattern_alignment.md；它是 G2 的门槛 }
  | "scaling_consistency" * { 口径见 metrics/scaling_consistency.md；每一级都要算 }
  | "fidelity" * { 保真边界表中 IO 路径不得出现 L0；人工评审 }
  | "reproducibility" * { 配置、commit、拓扑、预热、观测全部登记；人工评审 }
  | "coverage" * { 参数量分桶 × 集群规模 × 并行策略 的已覆盖格子数；自动统计 }

CheckpointConclusion =
  Object
  * $alignment (CheckpointAlignment * { 小规模对齐的结果；这一步的成本高于其它步骤，但它是外推结论的唯一依据，不能跳过 })
  * $scaling (list[CheckpointScalingRun] * { 逐级 scaling 的结果，每一级一条；参数规模放大会改变分片与每片大小，集群规模放大会改变并发与聚合带宽，两者的失效方式不同，不能合并 })
  * $acceptance (list[CheckpointAcceptanceItem] * { 这份结论覆盖的五项验收 })
  * $backlink (str * { 结论的回链；回链三要素齐全才允许登记 })

CheckpointRegistration =
  Object
  * $conclusion (CheckpointConclusion * { 已登记的结论 })
  * $coverage_updated (bool * { 覆盖矩阵是否已更新 })
```

## 基本操作

先跑通一次不旁路的训练若干步，再准备旁路：用 meta device 构建模型，前向照常执行，反向与 optimizer 换成占位实现，checkpoint 写入完全不改。旁路跑通后记录保真边界表，五条必填行一条不能少，IO 路径的保真等级不得是 L0。再取最小可用配置做一次真实运行和一次旁路运行，两次都开观测，对比 `methodology.md` 列出的度量项，按配方 `metrics.yaml` 里标定的容差判定是否对齐。对齐通过后逐级放大：先固定并行策略放大参数量，再固定参数量放大集群规模，每一级都要验证不变量并给偏差归因。最后登记结论与回链，更新覆盖矩阵。

## checkpoint_api

```bash checkpoint_api
import aisp.bench.checkpoint.checkpoint.checkpoint as checkpoint
import aisp.bench.checkpoint.methodology.fidelity as fidelity
import aisp.bench.checkpoint.scaling.levels as levels
import aisp.bench.checkpoint.ckpt_sample_interface.ckpt_sample as ckpt_sample

PrepareBypass =
     checkpoint.CheckpointBypassPlan
  <- $model (ckpt_sample.Component * { 模型代码；必须来自 recipes/model_code_collection，且是训练侧可用的实现 })
  <- $implementation (ckpt_sample.Component * { 训练框架的分布式检查点实现，记录名字与版本 })
  <- $parallel (checkpoint.CheckpointParallel * { 并行策略 DP/TP/PP/EP 的度数，按真实配置设置；旁路只去掉计算，不去掉并行切分 })
  <- $dtype (str * { 混合精度：dtype 必须与真实训练一致，否则写入字节数直接错 })
  <- { 准备旁路：先跑通一次不旁路的训练若干步（门 G0），再用 meta device 构建模型，前向照常执行，反向与 optimizer 换成占位实现，checkpoint 写入完全不改；返回五步做法与四条约束 }

RecordBoundary =
     checkpoint.CheckpointFidelity
  <- $forward_backward (fidelity.FidelityBoundary * { 必填行 forward / backward：旁路手段、保真等级、保留项与已知偏差 })
  <- $optimizer_step (fidelity.FidelityBoundary * { 必填行 optimizer.step：占位更新保留了 state_dict() 的键结构与分片 })
  <- $parallel_split (fidelity.FidelityBoundary * { 必填行并行切分与通信分组：分组与分片保持真实，通信被 mock 时登记同步丢失 })
  <- $checkpoint_write (fidelity.FidelityBoundary * { 必填行 checkpoint 写入与元数据提交：真实写入调用、真实文件系统或对象存储 })
  <- $checkpoint_read (fidelity.FidelityBoundary * { 必填行 checkpoint 读取与恢复：真实读取调用、真实校验 })
  <- { 记录保真边界表：五条必填行一条不能少；IO 路径的保真等级不得是 L0，否则该路径的结论无效；返回填好的表 }

Align =
     checkpoint.CheckpointAlignment
  <- $real (ckpt_sample.RunRecord * { 不做旁路的同规模真实运行；用最小可用配置，开观测 })
  <- $bypass (ckpt_sample.RunRecord * { 与真实运行同规模的旁路运行，也开观测 })
  <- { 小规模对齐：对比 methodology.md 列出的度量项，按配方 metrics.yaml 标定的容差判定；差异超过容差时按 methodology.md 的归因顺序排查；返回四个步骤与判定 }

ScaleUp =
     checkpoint.CheckpointScalingRun
  <- $dimension (checkpoint.CheckpointScalingDimension * { 这一次放大的维度，取值见 CheckpointScalingDimension；一次只沿一个维度放大 })
  <- $target ((levels.Level | nil) * { 放大集群规模时的目标档位，先到万卡（S4），再外推到十万卡（S5）；只放大参数量时给 nil })
  <- { 放大一级：先固定并行策略放大参数量，再固定参数量放大集群规模，两步不能合并；每一级都要验证不变量，偏差要有归因；返回这一级的结果 }

Register =
     checkpoint.CheckpointRegistration
  <- $conclusion (checkpoint.CheckpointConclusion * { 要登记的结论：小规模对齐与逐级 scaling 的结果，按验收项判定，回链三要素齐全 })
  <- { 登记结论与回链，更新覆盖矩阵；返回登记后的结论与覆盖矩阵的更新状态 }
```

## checkpoint_flow

```bash checkpoint_flow
import aisp.bench.checkpoint.checkpoint.checkpoint as checkpoint
import aisp.bench.checkpoint.checkpoint.checkpoint_api as checkpoint_api

CheckpointPrepareDuty =
  Object
  * $step (checkpoint_api.PrepareBypass * { 旁路准备：对应第 1、2 步；先跑通不旁路的训练若干步，再接入 meta device 与占位 optimizer，保持 IO 路径不变 })
  * $subject (checkpoint.CheckpointSubject * { 这一步的输入：检查点实现、分片方案与要记录的读写特征 })
  * $plan (checkpoint.CheckpointBypassPlan * { 这一步的产物：五步做法与四条约束 })

CheckpointBoundaryDuty =
  Object
  * $step (checkpoint_api.RecordBoundary * { 记录保真边界：五条必填行齐全；对应第 2 步的门 G1 })
  * $boundary (checkpoint.CheckpointFidelity * { 这一步的产物：五条必填的保真边界行 })

CheckpointAlignDuty =
  Object
  * $step (checkpoint_api.Align * { 小规模对齐：与同规模真实运行对比 IO pattern；对应第 3 步的门 G2 })
  * $alignment (checkpoint.CheckpointAlignment * { 这一步的产物：四个对齐步骤与容差判定 })

CheckpointScaleDuty =
  Object
  * $step (checkpoint_api.ScaleUp * { 逐级放大：先放大参数量，再放大集群规模；对应第 4、5 步的门 G3-a 与 G3-b })
  * $scaling (list[checkpoint.CheckpointScalingRun] * { 这一步的产物：逐级 scaling 的结果，每一级一条 })

CheckpointRegisterDuty =
  Object
  * $step (checkpoint_api.Register * { 登记结论与回链，更新覆盖矩阵；对应第 6 步的门 G4 })
  * $registration (checkpoint.CheckpointRegistration * { 这一步的产物：登记后的结论与覆盖矩阵的更新状态 })

CheckpointFlow =
  Object
  * $spec (checkpoint.CheckpointSpec * { 问题定义：评估对象、旁路、保真、阶段门、对齐、scaling、验收 })
  * $prepare (CheckpointPrepareDuty * { 第一步：准备旁路 })
  * $boundary (CheckpointBoundaryDuty * { 第二步：记录保真边界 })
  * $align (CheckpointAlignDuty * { 第三步：小规模对齐 })
  * $scale (CheckpointScaleDuty * { 第四、五步：逐级放大 })
  * $register (CheckpointRegisterDuty * { 第六步：登记结论 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
