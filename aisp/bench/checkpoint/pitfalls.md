# 已知坑与开放问题

## public

只做转发：从 `## 问题` 的 `pitfalls` 模块与 `## 接口` 的 `pitfalls_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布七个名字：类型 `PitfallEntry`、`PitfallCategory`、`Pitfall`、`PitfallStatus`，操作 `RegisterPitfall`、`JudgeResolved`、`OpenQuestion`；先看 `PitfallEntry` 与 `RegisterPitfall`，再看 `JudgeResolved` 与 `OpenQuestion`。

```bash pitfalls_public
import aisp.bench.checkpoint.pitfalls.pitfalls as pitfalls
import aisp.bench.checkpoint.pitfalls.pitfalls_api as pitfalls_api

PitfallCategory = pitfalls.PitfallCategory
Pitfall = pitfalls.Pitfall
PitfallStatus = pitfalls.PitfallStatus
PitfallEntry = pitfalls.PitfallEntry
RegisterPitfall = pitfalls_api.RegisterPitfall
JudgeResolved = pitfalls_api.JudgeResolved
OpenQuestion = pitfalls_api.OpenQuestion
```

## 背景

这份文档记录评估里反复踩到的坑、还在排查的问题，以及还没有答案的问题：每条坑写清现象、原因、处置、状态，每条开放问题写清影响范围与当前处置方式。新增条目按已有字段填写，不留空；已经解决的问题不删除，状态改为"已解决"并写明解决方式。dataset 与 kvcache 还没有定义，只留 TODO。

## pitfalls

问题形式化为一份坑登记表。一条登记记录写成 `PitfallEntry` 这个 Object 类型，六个字段分别收下分类、具体坑、现象、原因、处置与状态。`PitfallCategory`、`Pitfall`、`PitfallStatus` 与 `PitfallOpenQuestion` 都是 Oneof 枚举：`PitfallCategory` 给出条目所属的类别，`Pitfall` 的每个取值对应一条已知坑，`PitfallStatus` 给出 `$status` 字段的取值，`PitfallOpenQuestion` 承接未解决的坑挂出的开放问题。分类、具体坑与状态不是自由文本，分别取自 `PitfallCategory`、`Pitfall` 与 `PitfallStatus` 的取值。

```bash pitfalls
PitfallCategory =
  Oneof
  | "methodology" * { 方法论层面的坑：观测开销污染结论、应用层与系统层对不上、时序被压缩、单卡串行导致并发失真、冷热缓存差异、旁路后显存不释放 }
  | "model_code" * { 模型代码收集的坑：依赖地狱、可跑性验证被当成性能验证、mock 通信原语返回错张量、结构去重误杀、训练代码配对造假、许可证缺失 }
  | "checkpoint" * { checkpoint 评估的坑：meta device 与分布式检查点不兼容、异步检查点时序失真、分片元数据代价被低估、优化器状态被简化掉 }
  | "dataset_kvcache" * { dataset 与 kvcache：还没有定义，只留 TODO }
  | "evaluation_service" * { 评估服务的坑：并行运行互相干扰、回链缺失、无效运行混入统计、版本漂移 }

Pitfall =
  Oneof
  | "observation_overhead" * { 观测开销污染结论。现象：开观测后吞吐下降 5%–20%，请求变小。原因：采样与写日志本身消耗 CPU 与 IO。处置：单独测量开销；超过 3% 就降采样或改用系统层。状态：已定规则，未量化 }
  | "layer_mismatch" * { 应用层与系统层对不上。现象：应用层统计 4 KiB 写，设备层看到 1 MiB 写。原因：页缓存与写入缓冲合并了请求。处置：以系统层为准，应用层只用于逻辑归属。状态：已定规则 }
  | "timing_compressed" * { 时序被压缩。现象：旁路后写入全部集中在末尾。原因：计算耗时为 0，原本被计算掩盖的写入挤在一起。处置：注入等时延迟，或按真实计算时长折算时间轴。状态：部分解决 }
  | "serial_ranks" * { 单卡串行导致并发失真。现象：并发度远低于真实运行。原因：rank 分时占用同一张卡。处置：明确登记为已知偏差，关键结论用多进程重测。状态：已定规则 }
  | "cold_warm_cache" * { 冷热缓存差异。现象：首轮与次轮指标差 2 倍以上。原因：页缓存与存储侧缓存未预热。处置：固定预热轮数，只取稳态窗口。状态：已定规则 }
  | "bypass_memory_leak" * { 旁路后显存不释放。现象：连续运行多个 rank 后 OOM。原因：meta device 仍有少量真实分配，清理不彻底。处置：每个 rank 独立进程，退出即释放。状态：部分解决 }
  | "dependency_hell" * { 依赖地狱。现象：不同模型要求不同的 transformers 版本，装不下。原因：建模代码随框架版本改写。处置：按主版本分组，建多个镜像。状态：已定规则 }
  | "runnability_as_performance" * { 可跑性验证被当成性能验证。现象：用分时串行跑出来的耗时做结论。原因：分时运行时并发为 1。处置：在清单里标明并发为 1，耗时字段不用于结论。状态：已定规则 }
  | "mock_comm_wrong_tensor" * { mock 通信原语返回错张量。现象：代码在后续计算里崩，失败被误判为不可跑。原因：mock 返回值的 dtype 或张量维度不对。处置：验收 mock 实现本身：先用已知能跑的模型验证。状态：已解决 }
  | "dedup_false_positive" * { 结构去重误杀。现象：两个不同架构被判为重复。原因：只用配置字段做指纹，漏掉代码层差异。处置：加入代码层特征；阈值待标定。状态：部分解决 }
  | "fake_pairing" * { 训练代码配对造假。现象：配对了但根本不是同一模型。原因：按组织与时间就近配对。处置：配对必须有证据，证据不足记 unpaired。状态：已定规则 }
  | "missing_license" * { 许可证缺失。现象：部分模型没有许可证。原因：上传者未声明。处置：单独标记，不默认纳入。状态：已定规则 }
  | "meta_device_incompatible" * { meta device 与分布式检查点不兼容。现象：state_dict() 的键与真实运行不一致。原因：不同版本对 meta 参数的处理不同。处置：按版本维护适配说明，先在最小配置上核对键结构。状态：开放 }
  | "async_checkpoint_timing" * { 异步检查点时序失真。现象：异步写入测不出重叠效果。原因：计算耗时为 0，没有可重叠的窗口。处置：按真实计算时长拉伸时间轴。状态：开放 }
  | "shard_metadata_cost" * { 分片元数据代价被低估。现象：小规模正常，放大后元数据先饱和。原因：元数据操作数随分片数增长。处置：元数据与数据分开外推。状态：已定规则 }
  | "optimizer_state_dropped" * { 优化器状态被简化掉。现象：写入字节数偏小。原因：mock 的 optimizer 没有保留状态张量。处置：保留 state_dict() 的键与分片结构。状态：已定规则 }
  | "parallel_run_interference" * { 并行运行互相干扰。现象：两次运行都测得偏慢。原因：同一存储后端被两个高带宽用例争用。处置：同后端高带宽用例串行。状态：已定规则 }
  | "missing_backlink" * { 回链缺失。现象：有运行没记录，结论无法追溯。原因：服务失败时没写回链。处置：失败也要写回链，状态记为 failed。状态：已定规则 }
  | "invalid_run_counted" * { 无效运行混入统计。现象：通过率虚高。原因：观测失败、超时的运行被当成通过。处置：无效运行单独统计。状态：已定规则 }
  | "version_drift" * { 版本漂移。现象：结论变了，但说不清是哪一层变了。原因：四条版本没同时记录。处置：清单里四条版本必填，服务启动时校验。状态：已定规则 }

PitfallStatus =
  Oneof
  | "resolved" * { 已解决：问题已经解决，写明解决方式 }
  | "partially_resolved" * { 部分解决：问题只解决了一部分 }
  | "open" * { 开放：问题还没有解决 }
  | "rule_fixed" * { 已定规则：处置已经定成规则，条目仍留在表里 }
  | "rule_fixed_unquantified" * { 已定规则，未量化：处置已经定成规则，但还没有量化到每次运行 }

PitfallEntry =
  Object
  * $category (PitfallCategory * { 这条坑属于哪一类；新增条目时在 Pitfall 里加一个对应类别的取值，其余字段不留空 })
  * $pitfall (Pitfall * { 这条记录写的是哪一条已知坑 })
  * $symptom (str * { 现象：要能被别人观察到，不写"感觉不对" })
  * $cause (str * { 原因：写已经查明的；没查明的写"原因未明"，并把条目同时挂成开放问题 })
  * $disposition (str * { 处置：写当下实际执行的动作，不写"应该加强" })
  * $status (PitfallStatus * { 状态：取自 PitfallStatus；已经解决的问题不删除条目，状态改为"已解决"并写明解决方式 })

PitfallOpenQuestion =
  Oneof
  | "observation_overhead_per_run" * { 观测开销如何量化到每次运行。影响：结论可信度。当前处置：每次运行都测开关差值，暂不设硬门槛 }
  | "fingerprint_threshold" * { 结构指纹的权重与阈值。影响：去重质量。当前处置：先用 0.15，等人工标注样本标定 }
  | "code_feature_extraction" * { 代码层特征的稳定提取。影响：跨版本兼容。当前处置：解析器容忍失败，失败样本进人工队列 }
  | "hundred_thousand_gpu_cost" * { 十万卡规模的真实运行成本。影响：外推可信度。当前处置：用 S3/S4 实测 + 排队模型，结论标注可信度等级 }
  | "intermediate_scale_points" * { 中间规模采样点怎么选。影响：外推依据。当前处置：按每级不超过 4 倍经验取值 }
  | "async_timing_factor" * { 异步写入的时序折算系数。影响：带宽需求高估。当前处置：用真实计算时长中位数折算，系数记录在配方里 }
  | "unified_framework_semantics" * { 三个框架的统一语义抽象。影响：多框架适配。当前处置：适配层只统一分配/读写/传输/驱逐四类事件 }
  | "exemption_review_cycle" * { 豁免格子的复核周期。影响：覆盖度真实性。当前处置：每季度复核一次 }
  | "case_retirement_rule" * { 用例退役规则。影响：维护成本。当前处置：连续两个版本周期无结论的用例进入退役候选 }
  | "auto_candidate_equivalence" * { 自动候选与已有用例的等价判定。影响：覆盖质量。当前处置：入集前人工比对结构距离与负载配置 }
```

## 基本操作

要维护这份登记表，需要三个操作。

1. 第一个操作登记一条坑：按分类收下这条坑，写清现象、原因、处置与状态，字段不留空。
2. 第二个操作判断一条坑是否已解决：只有状态为"已解决"才算解决，已经解决的问题保留条目，不删除。
3. 第三个操作把未解决的坑挂成开放问题：写明它对应的问题、影响范围与当前处置方式，已解决的坑不挂。

## pitfalls_api

```bash pitfalls_api
import aisp.bench.checkpoint.pitfalls.pitfalls as pitfalls

RegisterPitfall =
     pitfalls.PitfallEntry
  <- $category (pitfalls.PitfallCategory * { 这条坑属于哪一类 })
  <- $pitfall (pitfalls.Pitfall * { 登记的是哪一条已知坑 })
  <- $symptom (str * { 现象：要能被别人观察到，不写"感觉不对" })
  <- $cause (str * { 原因：写已经查明的；没查明的写"原因未明"，并把条目同时挂成开放问题 })
  <- $disposition (str * { 处置：写当下实际执行的动作，不写"应该加强" })
  <- $status (pitfalls.PitfallStatus * { 状态：取自 PitfallStatus；已经解决的问题不删除条目，状态改为"已解决"并写明解决方式 })
  <- { 登记接口：收下一条坑的现象、原因、处置与状态，按分类把条目补全后交回；新增条目按已有字段填写，不留空 }

JudgeResolved =
     bool
  <- $entry (pitfalls.PitfallEntry * { 要判断的那条坑 })
  <- { 判断接口：看这条坑的状态，只有状态为已解决才交回 true；其余状态都交回 false，条目继续留在表里 }

OpenQuestion =
     pitfalls.PitfallOpenQuestion
  <- $entry (pitfalls.PitfallEntry * { 已登记、且 JudgeResolved 判为未解决的那条坑 })
  <- { 挂问题接口：把一条未解决的坑挂到它对应的开放问题上，交回那个问题的内容；PitfallOpenQuestion 里已有对应问题时取那一条，没有时按同样的写法加一个取值，写明影响范围与当前处置方式 }
```

## pitfalls_flow

```bash pitfalls_flow
import aisp.bench.checkpoint.pitfalls.pitfalls as pitfalls
import aisp.bench.checkpoint.pitfalls.pitfalls_api as pitfalls_api

PitfallStep =
  Oneof
  | $register (pitfalls_api.RegisterPitfall * { 第一步：登记一条坑，收下分类、现象、原因、处置与状态 })
  | $judge (pitfalls_api.JudgeResolved * { 第二步：判断刚登记的这条坑是否已解决，只有已解决才算解决 })
  | $open_question (pitfalls_api.OpenQuestion * { 第三步：把未解决的坑挂成开放问题，写明影响范围与当前处置方式 })

PitfallDuty =
  Object
  * $steps (list[PitfallStep] * { 三个操作按登记 → 判断 → 挂问题的顺序串成一轮；判断为未解决的才走第三步 })
  * $entries (list[pitfalls.PitfallEntry] * { 登记过的坑；已经解决的也不删除，状态留在条目里 })
  * $questions (list[pitfalls.PitfallOpenQuestion] * { 未解决的坑挂出来的开放问题；已解决的坑不进入这里 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
