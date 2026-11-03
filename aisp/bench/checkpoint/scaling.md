# Scaling：不变量、逐级验证与外推

## public

只做转发：从 `## 问题` 的 `scaling` 模块与 `## 接口` 的 `scaling_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `ScalingRunPlan`、`ScalingInvariantSet`、`ScalingLevelRun`、`ScalingExtrapolation`，操作 `ChooseDimension`、`PickInvariant`、`ScaleUp`、`Extrapolate`；先看 `ScalingRunPlan` 与 `ChooseDimension`，再由 `PickInvariant` 交回 `ScalingInvariantSet`、由 `ScaleUp` 交回 `ScalingLevelRun`，逐级结果汇进 `Extrapolate` 交回的 `ScalingExtrapolation`。

```viba scaling_public
import scaling
import scaling_api

ScalingRunPlan = scaling.ScalingRunPlan
ScalingInvariantSet = scaling.ScalingInvariantSet
ScalingLevelRun = scaling.ScalingLevelRun
ScalingExtrapolation = scaling.ScalingExtrapolation
ChooseDimension = scaling_api.ChooseDimension
PickInvariant = scaling_api.PickInvariant
ScaleUp = scaling_api.ScaleUp
Extrapolate = scaling_api.Extrapolate
```

## 背景

三类评估集共用这套方法。它回答的问题是：在小规模上测出来的结论，凭什么能用到十万卡；评估集的上限按十万卡设计。放大过程中数据本身、系统与策略同时在变，不把哪些应该保持不变、哪些一定会变写清楚，放大之后测到的差异就无法区分是存储扛不住还是配置变了。

## scaling

问题形式化为 `scaling` 模块：取值只能落在有限集合里的概念写成 Oneof 枚举，`ScalingDimension` 是放大维度，`ScalingInvariantExample` 是不变量示例，`ScalingExtrapolationRule` 是外推规则，`ScalingWriteMode` 是写入模式，`ScalingNonlinearSource` 是放大中非线性变化的来源，`ScalingOpenQuestion` 是尚无答案的开放问题。需要成组记录的概念写成 Object 类型：`ScalingRunPlan` 的 `$dimension` 取这次放大的一个 `ScalingDimension`、`$fixed` 是其余四个维度的 `ScalingFixedDimension` 列表，`ScalingFixedDimension` 记一个被固定的维度与固定成的值。不变量这条链上，`ScalingInvariantCandidate` 是候选度量项，判断通过的写成 `ScalingInvariant`，`ScalingInvariantSet` 的 `$invariants` 收最终选定的 `ScalingInvariant` 列表，`$variables`、`$references` 与 `$unmeasurable` 分别记变量、参考项与测不到的候选。`ScalingLevelRun` 记一级放大的结果，其 `$level` 取 `levels.Level`、`$dimension` 取 `ScalingDimension`；`ScalingExtrapolation` 记一次外推，其 `$from_level` 与 `$to_level` 取 `levels.Level`、`$rules` 是 `ScalingExtrapolationRule` 的列表、`$timing` 是 `ScalingTiming`、`$nonlinear_sources` 是 `ScalingNonlinearSource` 的列表，`ScalingTiming` 的 `$mode` 取 `ScalingWriteMode`；`ScalingLevelReport` 记每一级的报告，其 `$level` 取 `levels.Level`。

```viba scaling
import levels

ScalingDimension =
  Oneof
  | "model_scale" * { 模型规模：参数量、层数、隐藏维度、KV 头数；影响单请求数据量与单分片大小 }
  | "cluster_size" * { 集群规模：节点数、卡数、每节点卡数；影响并发度、聚合带宽与元数据请求数 }
  | "parallel_strategy" * { 并行策略：DP / TP / PP / EP 的组合与度数；影响分片方式、通信分组与每 rank 负载 }
  | "load" * { 负载：并发请求数、序列长度、到达间隔、请求分布；影响读写比、突发模式与缓存命中率 }
  | "storage_backend" * { 存储后端：文件系统、对象存储、分层缓存；影响请求大小上限、元数据成本与一致性代价 }

ScalingFixedDimension =
  Object
  * $dimension (ScalingDimension * { 被固定住的那个维度 })
  * $value (str * { 固定成什么值，例如节点数、每节点卡数或并行度数；随该级报告记录 })

ScalingRunPlan =
  Object
  * $dimension (ScalingDimension * { 这一次唯一放大的维度；同时放大两个维度得到的结论无法归因 })
  * $fixed (list[ScalingFixedDimension] * { 其余四个维度的固定值；四个都要列，并且记录 })

ScalingInvariantCandidate =
  Object
  * $metric (str * { 候选度量项的名字，从 methodology.md 的度量项里挑出与本次评估目标相关的项 })
  * $definition (str * { 这个度量项怎么算，写清分子、分母或统计口径 })
  * $varies_with_dimension (bool * { 是否随目标维度变化；会变的量是变量，不是不变量 })
  * $measurable (bool * { 是否能被测量；测不到的不能当不变量 })
  * $change_invalidates (bool * { 变了是否意味着结论失效；变了也不影响结论的只是参考项 })
  * $tolerance (str * { 不变量允许的波动范围，必须可计算；例如 L1 距离不超过 0.1 })

ScalingInvariant =
  Object
  * $name (str * { 不变量名称，写进配方的 metrics.yaml })
  * $definition (str * { 定义：量的是什么 })
  * $computation (str * { 计算方式：从哪些原始数据、按什么公式算出来 })
  * $tolerance (str * { 容差：允许的波动范围，必须可计算 })
  * $verdict (str * { 判定规则：实测值在什么条件下判为保持，什么条件下判为失效 })

ScalingInvariantExample =
  Oneof
  | "per_rank_request_size" * { checkpoint 评估集示例：每 rank 请求大小分布，即该 rank 单次 checkpoint 内所有写请求的字节数直方图；容差 L1 距离不超过 0.1；由分片策略决定，参数规模放大时每片大小按比例放大，直方图的相对分布稳定 }
  | "bytes_per_parameter" * { checkpoint 评估集示例：每参数字节数，即一次 checkpoint 写入总字节除以参数量；容差相对误差不超过 2%；由精度、优化器状态与分片冗余决定，与规模无关 }
  | "per_rank_write_concurrency" * { checkpoint 评估集示例：单 rank 写入并发度，即单 rank 同时在途的写请求数；容差中位数相对误差不超过 15%；由框架的写入并发配置决定 }

ScalingInvariantSet =
  Object
  * $invariants (list[ScalingInvariant] * { 最终选定的不变量，经验范围是每条评估集 3 到 6 条；选得太多验证成本高且互相矛盾，选得太少外推没有依据 })
  * $variables (list[str] * { 会随目标维度变化的量，作为变量记录并画曲线 })
  * $references (list[str] * { 变了也不影响结论、只作参考的项 })
  * $unmeasurable (list[str] * { 测不到的候选，不能当不变量 })

ScalingLevelRun =
  Object
  * $level (levels.Level * { 这一级是 S0 到 S5 里的哪一档 })
  * $dimension (ScalingDimension * { 这一级沿哪个维度放大 })
  * $samples (int * { 这一级的采样点数量；不必与其它级相同 })
  * $complete_measurement (bool * { 这一级是否拿到完整度量；不允许只测了带宽 })
  * $invariants_kept (bool * { 选定的不变量是否都在容差内保持 })
  * $focus (str * { 这一级的重点；存储后端若在 S2 已饱和，S3 到 S5 的重点从测请求特征改为测排队与尾延迟，配方里预先写明 })
  * $attribution (str * { 偏差归因：哪些来自系统、哪些来自配置变化；没有偏差写 none，不留空 })

ScalingExtrapolationRule =
  Oneof
  | "aggregate_bandwidth" * { 聚合带宽等于单 rank 带宽乘以 rank 数，只在存储侧未饱和时成立；饱和之后增加 rank 不会增加聚合带宽，只会增加排队与尾延迟 }
  | "data_bytes" * { 数据字节数随参数量线性增长 }
  | "metadata_operations" * { 元数据操作数随分片数与文件数增长，与总字节无关；分片数随集群规模增长时，元数据可能比数据先到上限。两条曲线分开算、分开报告，合成一条会掩盖真正的瓶颈 }
  | "timing_overlap" * { 同步写入时训练停顿、IO 独占；异步写入与计算重叠，实际带宽需求是写入量除以重叠窗口长度。计算被旁路后窗口变短、测量值偏高，必须按真实计算时长折算 }
  | "tail_latency" * { 大规模评估关心 P99 与 P999，不关心平均值；尾延迟随规模超线性增长，来源包括排队、重传与元数据热点，不能按平均值外推 }

ScalingWriteMode =
  Oneof
  | "sync" * { 同步写入：写入期间训练停顿，IO 是独占的 }
  | "async" * { 异步写入：写入与计算重叠，实际带宽需求是写入量除以重叠窗口长度；计算被旁路后窗口变短，测量值会偏高 }

ScalingTiming =
  Object
  * $mode (ScalingWriteMode * { 这次评估的写入模式 })
  * $bandwidth_demand (float * { 实际带宽需求：同步写入按写入量除以写入窗口，异步写入按写入量除以重叠窗口 })
  * $real_compute_median_s (float * { 真实运行测得的计算时长中位数，秒；折算旁路运行的写入时间轴时用它 })
  * $stretch_rule (str * { 时序与重叠的折算规则：把旁路运行的写入时间轴拉伸到真实长度；规则写进配方 })

ScalingNonlinearSource =
  Oneof
  | "storage_saturation" * { 表现：带宽走平、尾延迟陡增；排查：单 rank 带宽随规模曲线 }
  | "metadata_hotspot" * { 表现：小请求耗时随规模急剧上升；排查：按操作类型拆分延迟 }
  | "network_congestion" * { 表现：跨节点流量抖动、重传增加；排查：网络计数器与重传率 }
  | "cache_hit_drop" * { 表现：实际打到远端的请求变多；排查：分层统计命中率 }
  | "load_imbalance" * { 表现：部分 rank 长时间空闲、部分饱和；排查：每 rank 的请求量分布 }
  | "scheduling_jitter" * { 表现：长尾请求集中在少数节点；排查：按节点拆分尾延迟 }
  | "failure_recovery" * { 表现：重启后短时间 IO 放大；排查：恢复窗口内的请求序列 }

ScalingExtrapolation =
  Object
  * $from_level (levels.Level * { 外推的起点：已有实测的最高一级 })
  * $to_level (levels.Level * { 外推目标；十万卡是 S5 })
  * $rules (list[ScalingExtrapolationRule] * { 这次外推用到的规则；数据与元数据分开算、分开报告 })
  * $saturated (bool * { 存储侧是否已饱和；判断看单 rank 带宽随 rank 数增长的曲线，开始走平的那一点就是饱和点 })
  * $saturation_point (str * { 饱和点在哪；饱和之后一律用排队模型描述，不用线性外推；未饱和写 none })
  * $timing (ScalingTiming * { 时序折算：同步还是异步，以及旁路窗口怎么按真实计算时长折算 })
  * $tail_latency (str * { P99 与 P999 的外推结论；尾延迟随规模超线性增长，不能按平均值外推 })
  * $nonlinear_sources (list[ScalingNonlinearSource] * { 已排查的非线性来源；放大中出现超线性变化时先排查这些来源，再下结论 })
  * $prediction (str * { 下一级的预测值 })
  * $basis (str * { 预测依据 })

ScalingLevelReport =
  Object
  * $level (levels.Level * { 这份报告对应哪一级 })
  * $config (str * { 该级的完整配置：模型、并行、拓扑、存储后端、负载 })
  * $invariants (str * { 声明的不变量表，以及实测值与容差的对比 })
  * $variables (str * { 变量表，以及实测值随规模的变化曲线 })
  * $attribution (str * { 偏差归因：哪些偏差来自系统，哪些来自配置变化 })
  * $next_prediction (str * { 下一级的预测值与预测依据 })
  * $backlink (str * { 报告放在对象存储，仓库里只写回链 })

ScalingOpenQuestion =
  Oneof
  | "sample_points" * { 中间规模的采样点怎么选：目前按每级不超过上一级的 4 倍经验取值，没有理论依据；千卡到万卡这一级跨了约 10 倍，是已知的例外 }
  | "simulation_substitute" * { 十万卡规模的真实运行成本过高，是否允许用部分模拟加部分真实的方式替代，替代的可信度如何界定 }
  | "backend_specific_rules" * { 不同存储后端的外推规则不通用，是否需要按后端各写一份 }
  | "single_dimension_exception" * { 并行策略在放大过程中往往同时变化，只沿一个维度放大的要求在实际中难以满足，需要明确的例外规则 }
```

档位枚举保留在原有的 levels 模块；scaling 模块与其它文档都引用它。

```viba levels
Level =
  Oneof
  | "S0" * { 单机，最小参数规模。对齐基准；度量项在容差内 }
  | "S1" * { 单机多卡或双机。引入并行切分与多 rank 并发；不变量保持 }
  | "S2" * { 数十至百卡。引入网络与共享存储的争用；不变量保持，偏差有归因 }
  | "S3" * { 千卡。引入调度与故障恢复；不变量保持，偏差有归因 }
  | "S4" * { 万卡。实测上限；不变量保持，偏差有归因 }
  | "S5" * { 十万卡。外推目标；不变量保持，外推结论登记 }
```

## 基本操作

需要四个操作。选维度：从模型规模、集群规模、并行策略、负载、存储后端里选一个放大，其余四个固定并记录，同时放大两个维度得到的结论无法归因。定不变量：从 [`methodology.md`](methodology.md) 的度量项里挑候选，逐个判断会不会随目标维度变化、能不能被测量、变了是否意味着结论失效，再定可计算的容差，最终留下 3 到 6 条。逐级验证：按 S0 到 S5 的阶梯一级一级跑，至少四级，每级都要拿到完整度量、重新验证不变量并给偏差归因，不允许从最小规模直接跳到十万卡。外推：先判断存储侧是否饱和，数据与元数据分开算，处理时序与重叠，也就是同步或异步写入的时间折算，再处理 P99、P999 尾延迟，给出下一级的预测值与预测依据。每一级都要写报告，报告包含完整配置、不变量对比、变量曲线、偏差归因与下一级预测，报告放对象存储，仓库里只写回链。

## scaling_api

```viba scaling_api
import levels
import scaling

ChooseDimension =
     scaling.ScalingRunPlan
  <- $dimension (scaling.ScalingDimension * { 这次要放大的维度；五个维度里选一个，其余四个固定并记录 })
  <- $fixed (list[scaling.ScalingFixedDimension] * { 其余四个维度的固定值；四个都要列，同时放大两个维度得到的结论无法归因 })
  <- { 选维度：从模型规模、集群规模、并行策略、负载、存储后端五个维度里选一个放大，固定并记录其余四个；返回这次评估的放大计划 }

PickInvariant =
     scaling.ScalingInvariantSet
  <- $dimension (scaling.ScalingDimension * { 目标维度；判断候选会不会随它变化 })
  <- $candidates (list[scaling.ScalingInvariantCandidate] * { 候选度量项：从 methodology.md 的度量项里挑出与本次评估目标相关的项，每项带定义、三个判断与容差 })
  <- { 定不变量：逐个候选判断会不会随目标维度变化、能不能被测量、变了是否意味着结论失效，再定可计算的容差；会变的是变量，变了不影响结论的只是参考项；最终留下 3 到 6 条不变量，每条写进配方的 metrics.yaml，包含名称、定义、计算方式、容差、判定规则；返回不变量集合，以及变量、参考项与测不到的候选 }

ScaleUp =
     scaling.ScalingLevelRun
  <- $level (levels.Level * { 要跑到的那一级；阶梯至少四级，当前按六级执行 })
  <- $plan (scaling.ScalingRunPlan * { 这次放大的维度与其余四个固定值；一次评估只沿这一个维度放大，其余四个保持固定 })
  <- $invariants (list[scaling.ScalingInvariant] * { 每一级都要重新验证的不变量 })
  <- $samples (int * { 这一级的采样点数量；不必与其它级相同 })
  <- { 放大一级：不允许从最小规模直接跳到十万卡；这一级要拿到完整度量，不允许只测了带宽；验证不变量是否都在容差内，偏差要有归因；若存储后端在 S2 已饱和，S3 到 S5 的重点改为测排队与尾延迟，配方里要预先写明；返回这一级的结果 }

Extrapolate =
     scaling.ScalingExtrapolation
  <- $runs (list[scaling.ScalingLevelRun] * { 已经跑过的逐级结果，至少四级 })
  <- $target (levels.Level * { 外推目标；十万卡是 S5 })
  <- $timing (scaling.ScalingTiming * { 时序折算：同步还是异步，以及真实计算时长中位数 })
  <- { 外推：先看单 rank 带宽随 rank 数增长的曲线判断存储侧是否饱和，走平之后一律用排队模型；数据字节数与元数据操作数分开算、分开报告；按真实计算时长折算旁路窗口；P99 与 P999 不按平均值外推；放大中出现超线性变化时先排查七个非线性来源，再给下一级的预测值与预测依据；返回这次外推的结果 }
```

## scaling_flow

scaling_flow 把维度、不变量、逐级验证、外推与报告串成一个整体：一份放大计划贯穿所有级，一组不变量在每一级重新验证，逐级结果汇到一次外推，每一级的结果写成一份报告。

```viba scaling_flow
import levels
import scaling
import scaling_api

ScalingChooseDuty =
  Object
  * $step (scaling_api.ChooseDimension * { 选维度：一次只沿一个维度放大，其余四个固定并记录 })
  * $plan (scaling.ScalingRunPlan * { 产物：这次放大的维度与四个固定值 })

ScalingInvariantDuty =
  Object
  * $step (scaling_api.PickInvariant * { 定不变量：按候选、可测性、结论影响、容差逐步筛 })
  * $set (scaling.ScalingInvariantSet * { 产物：3 到 6 条不变量，以及变量、参考项与测不到的候选 })

ScalingLevelDuty =
  Object
  * $step (scaling_api.ScaleUp * { 放大一级：拿到完整度量，重新验证不变量，给偏差归因 })
  * $run (scaling.ScalingLevelRun * { 产物：这一级的结果与侧重点 })

ScalingExtrapolateDuty =
  Object
  * $step (scaling_api.Extrapolate * { 外推：判断饱和，数据与元数据分开算，处理时序与尾延迟 })
  * $result (scaling.ScalingExtrapolation * { 产物：目标级的预测值与预测依据 })

ScalingReportDuty =
  Object
  * $report (scaling.ScalingLevelReport * { 每一级一份报告：配置、不变量、变量、偏差归因、下一级预测；报告放对象存储，仓库只写回链 })

ScalingFlow =
  Object
  * $ladder (list[levels.Level] * { 阶梯 S0 到 S5；至少四级，当前按六级执行；不允许从最小规模直接跳到十万卡 })
  * $choose (ScalingChooseDuty * { 第一步：选维度 })
  * $invariants (ScalingInvariantDuty * { 第二步：定不变量 })
  * $level_runs (list[ScalingLevelDuty] * { 第三步：逐级验证，每级一条 })
  * $extrapolate (ScalingExtrapolateDuty * { 第四步：外推到目标级；输入是逐级验证的结果 })
  * $reports (list[ScalingReportDuty] * { 第五步：每一级一份报告 })
  * $open_questions (list[scaling.ScalingOpenQuestion] * { 尚无答案的开放问题 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
