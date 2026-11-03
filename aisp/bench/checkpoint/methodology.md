# 核心方法论：旁路计算，保真 IO

## public

只做转发：从 `## 问题` 的 `methodology` 模块与 `## 接口` 的 `methodology_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `MethodologySpec`、`MethodologyBypassPlan`、`MethodologyBoundaryTable`、`MethodologyTolerance`，操作 `PlanBypass`、`RecordBoundary`、`Observe`、`Align`；先看 `MethodologySpec` 与 `PlanBypass`，再看 `RecordBoundary` 交回的 `MethodologyBoundaryTable` 与 `Observe`、`Align` 判定用的 `MethodologyTolerance`。

```viba methodology_public
import methodology
import methodology_api

MethodologySpec = methodology.MethodologySpec
MethodologyBypassPlan = methodology.MethodologyBypassPlan
MethodologyBoundaryTable = methodology.MethodologyBoundaryTable
MethodologyTolerance = methodology.MethodologyTolerance
PlanBypass = methodology_api.PlanBypass
RecordBoundary = methodology_api.RecordBoundary
Observe = methodology_api.Observe
Align = methodology_api.Align
```

## 背景

本文是整套方法的唯一出处：旁路、保真等级、保真边界表、IO pattern 度量项、对齐判定、阶段门只在这里定义一次；三类评估集的配方引用本文的章节，只写各自的差异。本文解决"评估集怎么建、怎么判它可信"。存储在一个样本上的表现（SLI）怎么测、重保子集怎么判（SLO）、两个存储版本怎么比，见 [`storage-performance.md`](storage-performance.md)，两篇的分工不要混。

## methodology

问题形式化为五个模块：`methodology` 汇总整套方法；`gates`、`bypass`、`fidelity`、`observation` 分别定义阶段门、旁路手段与保真等级、保真边界表、观测层。对象类型 `MethodologySpec`、`MethodologyBypassPlan`、`MethodologyBypassPremise`、`MethodologyBoundaryTable`、`MethodologyObservation`、`MethodologyAlignment`、`MethodologyScaling`、`MethodologyReproduction`、`MethodologyTolerance` 与 `MethodologyToleranceCalibration` 分别表示整套方法的汇总、旁路方案、旁路前提、保真边界表、一次采集、一次对齐判定、一级放大、可复现条件、一项容差与这项容差的标定记录。取值只能落在有限集合里的概念写成 `Oneof` 枚举：`MethodologyMetric`、`MethodologyToleranceStatistic`、`MethodologyAttributionCause`、`MethodologyScaleRule`、`MethodologyReproducibilityItem` 与 `MethodologyFailureMode` 分别表示 IO pattern 度量项、对齐统计量、偏差归因、scaling 规则、可复现项与失效模式。`MethodologySpec` 的九个字段分别引用这些类型：`$gates`、`$bypass_methods`、`$fidelity_boundaries`、`$observation_layers` 分别是 `gates.Gate`、`bypass.BypassMethod`、`fidelity.FidelityBoundary`、`observation.ObservationLayer` 的列表，`$metrics`、`$tolerances`、`$scale_rules`、`$failure_modes` 分别是 `MethodologyMetric`、`MethodologyTolerance`、`MethodologyScaleRule`、`MethodologyFailureMode` 的列表，`$reproduction` 是 `MethodologyReproduction`；`MethodologyBypassPlan` 的 `$method` 与 `$fidelity` 分别取 `bypass.BypassMethod` 与 `bypass.FidelityLevel` 的一个取值，`MethodologyTolerance` 的 `$metric` 与 `$statistic` 分别取 `MethodologyMetric` 与 `MethodologyToleranceStatistic` 的一个取值。

```viba methodology
import bypass
import fidelity
import gates
import levels
import observation

MethodologySpec =
  Object
  * $gates (list[gates.Gate] * { 五道阶段门，G0 到 G4；每个配方都必须按这五道门推进，每道门有明确的产出 })
  * $bypass_methods (list[bypass.BypassMethod] * { 四种旁路手段，成本与保真度递增；BypassMethod 写的是请求序列的保真等级，不含时序 })
  * $fidelity_boundaries (list[fidelity.FidelityBoundary] * { 保真边界表；每个配方必须填写，没有这张表视为未完成 })
  * $observation_layers (list[observation.ObservationLayer] * { 三层观测；至少要两层交叉核对 })
  * $metrics (list[MethodologyMetric] * { IO pattern 的度量项，所有评估集共用的词汇表；每条评估集配方从中挑 3–6 项作为 scaling 不变量，其余作为参考项；挑得太多无法验证，挑得太少外推没有依据 })
  * $tolerances (list[MethodologyTolerance] * { 对齐容差；实际判定用配方 metrics.yaml 里的 tolerance，这里的初始容差只是标定起点 })
  * $scale_rules (list[MethodologyScaleRule] * { scaling 的两条规则：先对齐再放大，每一级重新验证不变量 })
  * $reproduction (MethodologyReproduction * { 可复现需要固定的七项；缺任何一项，结论都只能算某次运行的观测，不能算评估结论 })
  * $failure_modes (list[MethodologyFailureMode] * { 六种失效模式及其现象与处置 })

MethodologyMetric =
  Oneof
  | "request_size_distribution" * { 每个 IO 请求字节数的直方图，按 4 KiB 起对数分桶；采集方式：应用层 hook 或存储客户端日志 }
  | "read_write_ratio" * { 读写比，两个口径：按字节数、按请求数；采集方式：应用层 hook 或存储客户端日志 }
  | "sequentiality" * { 相邻请求的逻辑偏移差与请求大小的比值；1 表示完全顺序；采集方式：应用层 hook }
  | "concurrency" * { 同时在途的请求数分布，中位数、P95、峰值；采集方式：应用层 hook 或队列深度采样 }
  | "queue_depth" * { 设备或客户端队列的排队请求数；采集方式：系统层采样 }
  | "timing" * { 每秒请求数与每秒字节数的时间序列，突发窗口长度与峰值；采集方式：系统层计数 }
  | "hotness" * { 按数据块统计的访问次数分布，Top-K 占比、Gini 系数；采集方式：应用层 hook，按偏移聚合 }
  | "lifetime" * { 同一数据块从首次写入到被读取或被驱逐的时长；采集方式：应用层 hook }
  | "cross_node_traffic" * { 每个 rank 的出/入字节数、对端节点分布、通信与存储的时间重叠；采集方式：网络计数器 + 应用层 hook }

MethodologyToleranceStatistic =
  Oneof
  | "bucket_frequency_l1" * { 请求大小分布：分桶频率的 L1 距离，初始容差 ≤ 0.10 }
  | "byte_ratio_relative_error" * { 读写比：字节口径的相对误差，初始容差 ≤ 5% }
  | "concurrency_median_relative_error" * { 并发度：中位数相对误差，初始容差 ≤ 10% }
  | "concurrency_p95_relative_error" * { 并发度：P95 相对误差，初始容差 ≤ 20% }
  | "peak_window_bytes_relative_error" * { 时序：峰值窗口内的字节数相对误差，初始容差 ≤ 10% }
  | "top_k_share_absolute_difference" * { 热度：Top-K 占比的绝对差，初始容差 ≤ 0.05 }
  | "sequential_request_share_absolute_difference" * { 顺序性：顺序请求占比的绝对差，初始容差 ≤ 0.05 }

MethodologyTolerance =
  Object
  * $metric (MethodologyMetric * { 这个容差对应哪个度量项，例如请求大小分布、读写比、并发度、时序、热度、顺序性 })
  * $statistic (MethodologyToleranceStatistic * { 对齐指标：按哪个统计量判定；初始容差见取值说明 })
  * $initial (float * { 初始容差数值；标定前视为待验证，实际判定用配方 metrics.yaml 里的 tolerance })
  * $calibration ((MethodologyToleranceCalibration | nil) * { 这一项容差的标定记录；标定前给 nil，实际判定前必须补上。checkpoint 写入的请求大小由分片策略决定，容差应更紧 })

MethodologyToleranceCalibration =
  Object
  * $recipe (str * { 标定结果写进哪个配方的 metrics.yaml，例如 recipes/checkpoint })
  * $date (str * { 标定日期 })
  * $baseline (str * { 所用基准 })

MethodologyAttributionCause =
  Oneof
  | "observation_overhead" * { 第 1 项：观测开销改变了 pattern；先关掉观测对比 }
  | "local_buffer_or_merge" * { 第 2 项：本地缓冲或合并改变了请求的边界；检查文件系统页缓存、写入缓冲、批量提交 }
  | "bypass_timing" * { 第 3 项：旁路改变了时序；计算耗时为 0，写入挤在一起，单卡串行跑 rank 导致并发降低 }
  | "allocator" * { 第 4 项：allocator 差异；meta device 不分配真实内存，allocator 行为、对齐、碎片都不同 }
  | "cache_warmup" * { 第 5 项：冷热缓存差异；首次运行与重复运行差别很大，必须固定预热策略 }
  | "communication_mock" * { 第 6 项：通信 mock 丢失了 rank 间同步，并发度与交织时序失真 }

MethodologyAlignment =
  Object
  * $within_tolerance (bool * { 选定度量项是否全部落在配方 metrics.yaml 标定的容差内 })
  * $attribution (list[MethodologyAttributionCause] * { 差异超过容差时按枚举顺序逐项排除；归因结论写进配方的 README.md，不要只留在聊天记录里 })

MethodologyScaleRule =
  Oneof
  | "alignment_first" * { 对齐通过之前，不允许进入 scaling；在对不齐的小规模上放大，只会把偏差放大 }
  | "revalidate_each_level" * { 每一级 scaling 都要重新验证不变量；跳级得到的结论没有依据 }

MethodologyScaling =
  Object
  * $level (levels.Level * { 这次放大到的档位，级别的定义见 scaling.md })
  * $invariants_kept (bool * { 这一级的不变量是否都在容差内保持 })
  * $attribution (str * { 偏差归因；没有偏差写 none，不留空 })

MethodologyBypassPremise =
  Object
  * $io_path_unchanged (bool * { 存储与传输侧的评估对象是 IO；计算对 IO 的贡献只有三件事：什么时候发起、一次发起多少、以什么并发度发起。把计算换成不产生真实计算的实现，只要发起 IO 的代码路径没有被替换，IO 请求序列依然能代表真实运行；计算本身的数值正确性、算子实现、kernel 性能都不进入评估结论。为 false 时旁路结果不能代表真实运行 })
  * $timing_bias (str * { 旁路计算后时序一定被压缩，例如用 meta device 后 forward 瞬间返回，原本被计算掩盖的 checkpoint 写入会挤在一起；写清这个偏差把哪个指标往哪个方向推，必要时在旁路实现里注入与真实计算等长的延迟。没有偏差写 none，不留空 })

MethodologyBypassPlan =
  Object
  * $method (bypass.BypassMethod * { 四种旁路手段里选一种，成本与保真度递增 })
  * $fidelity (bypass.FidelityLevel * { 这种手段的请求序列保真等级；L2 是大多数场景的默认目标，L3 只用于对齐基准，不用于批量运行 })
  * $premise (MethodologyBypassPremise * { 旁路结果能代表真实运行的前提 })

MethodologyBoundaryTable =
  Object
  * $rows (list[fidelity.FidelityBoundary] * { 每个被旁路的代码路径一行，写到函数级；每个配方必须填写，没有这张表视为未完成 })

MethodologyObservation =
  Object
  * $layers (list[observation.ObservationLayer] * { 这次开了哪几层；三层里至少要两层交叉核对 })
  * $byte_skew (float * { 应用层与系统层统计的总字节数偏差比例；超过 1% 必须先解释，再使用任何 pattern 结论 })
  * $explanation (str * { 偏差超过 1% 时的解释；解释不清时先怀疑观测本身：采样丢点、缓冲未刷、统计口径把元数据算进或漏出。没有偏差写 none，不留空 })
  * $overhead (float * { 观测开销：开启与关闭观测各跑一次，关键指标的变化比例；超过 3% 时降低采样率或改用系统层 })

MethodologyReproducibilityItem =
  Oneof
  | "model_code" * { 模型代码：记录仓库地址与 commit，不只记录 model id }
  | "config" * { 配置：记录完整配置文件与哈希 }
  | "dependencies" * { 依赖：记录 lock 文件与镜像版本 }
  | "topology" * { 拓扑：记录 rank 数、每节点卡数、网络拓扑、存储挂载方式 }
  | "warmup" * { 预热：记录预热方式与预热轮数 }
  | "observation" * { 观测：记录观测开关、采样率、观测本身的开销 }
  | "randomness" * { 随机性：数据顺序、shuffle 种子、请求注入顺序全部固定 }

MethodologyReproduction =
  Object
  * $fixed (list[MethodologyReproducibilityItem] * { 已固定的项；一次评估要能被别人重跑出同样的结论，七项都要固定 })
  * $missing (list[MethodologyReproducibilityItem] * { 还缺的项；缺任何一项，结论都只能算某次运行的观测，不能算评估结论 })

MethodologyFailureMode =
  Oneof
  | "observation_overhead" * { 现象：开观测后吞吐下降、请求变小；处置：降采样，改用系统层，单独测量开销 }
  | "buffer_merge" * { 现象：应用层看到 4 KiB 写，设备层看到 1 MiB 写；处置：以系统层为准，应用层只用于逻辑归属 }
  | "timing_compression" * { 现象：旁路后写入全部挤在最后；处置：在旁路里注入等时延迟，或按真实时间轴采样 }
  | "single_device_serial" * { 现象：并发度远低于真实；处置：用多进程、多流模拟并发，或明确登记为已知偏差 }
  | "cache_difference" * { 现象：首轮与次轮差异大；处置：固定预热，报告只取稳态窗口 }
  | "communication_mock" * { 现象：rank 间不同步，交织时序消失；处置：关键路径改用真实通信，或把该路径排除在结论之外 }
```

对齐的判定是：在选定的度量项上，旁路运行与同等规模的真实运行，其统计量落在声明的容差内。实际判定用配方 `metrics.yaml` 里的 `tolerance`，类型里的初始容差只是标定起点；容差需要按评估集标定，checkpoint 写入的请求大小由分片策略决定，容差应更紧。

```viba gates
Gate =
  Oneof
  | "G0" * { 能跑：目标代码在不旁路的情况下能跑完一次前向或一次预填充；产出可运行的最小配置 }
  | "G1" * { 旁路可跑：旁路实现后能跑完同样流程，且 IO 路径未被替换；产出保真边界表 }
  | "G2" * { 小规模对齐：选定度量项在容差内；产出对齐报告的回链 }
  | "G3" * { 逐级 scaling：每一级的不变量都在容差内，偏差有归因；产出 scaling 报告的回链 }
  | "G4" * { 结论登记：回链三要素齐全，覆盖率矩阵更新；产出 recipe.yaml 的 latest_run }
```

G1 到 G4 的判定记录写进 `recipe.yaml`，不写进文档正文。

```viba bypass
BypassMethod =
  Oneof
  | "meta_device" * { 张量只保留 dtype 与逻辑尺寸，不分配显存/内存。请求序列 L2；成本极低；用于需要真实控制流的全部计算 }
  | "module_mock" * { 替换指定模块的 forward/step，返回预先约定的张量。请求序列 L2；成本低；用于只关心某几条 IO 路径、其余整段旁路 }
  | "cpu_offload" * { 计算在 CPU 上用极小规模真实执行。请求序列 L2；成本中；用于需要真实 kernel 调用顺序、但不需要 GPU }
  | "real_small_scale" * { 不做旁路，直接小规模真实运行。请求序列 L3；成本高；用于标定其它手段的偏差 }

FidelityLevel =
  Oneof
  | "L0" * { 只保证调用到同一对外接口，内部实现已被替换，例如用自己的写入器替代框架的 checkpoint 实现 }
  | "L1" * { 代码路径相同，但请求在本地被缓冲或合并，请求的大小与偏移已经改变 }
  | "L2" * { 代码路径与请求序列相同，每条请求与真实运行一一对应 }
  | "L3" * { 在 L2 之上，时序与并发也与真实运行一致，跨节点传输是真实的 }
```

`BypassMethod` 写的是请求序列的保真等级，不含时序。旁路计算后时序一定被压缩：原本散布在整个训练步里的写入会挤到末尾。时序按 [`scaling.md`](scaling.md) 的「时序与重叠」折算，必要时在旁路实现里注入与真实计算等长的延迟；请求序列与时序必须分开评估。L2 是大多数场景的默认目标：它保证发了哪些请求，不保证什么时候发；L3 只用于对齐基准，不用于批量运行。

```viba fidelity
import bypass

Bypassed =
  Oneof
  | "yes" * { 整条路径被旁路，走的是替代实现 }
  | "no" * { 路径没有被旁路，走真实实现 }
  | "partial" * { 路径部分被旁路；必须写清部分的范围边界，例如「写入路径真实，元数据提交被 mock」 }

FidelityBoundary =
  Object
  * $path (str * { 被登记的代码路径或模块，写到函数级，例如 torch.distributed.checkpoint.save })
  * $bypassed (Bypassed * { 是否被旁路；partial 时必须写清部分的范围边界，例如「写入路径真实，元数据提交被 mock」 })
  * $method ((bypass.BypassMethod | nil) * { 用哪种手段旁路的；bypassed 为 no 时给 nil })
  * $fidelity (bypass.FidelityLevel * { 请求序列的保真等级；IO 路径一律不允许 L0，写 L0 说明评估对象已被替换，该路径的结论无效 })
  * $kept (str * { 保留了哪些，必须具体，例如「每个 rank 的独立分片写入」 })
  * $known_bias (str * { 这个偏差把哪个指标往哪个方向推高或压低；答不出方向的说明还没理解它。没有偏差写 none，不留空 })
```

每个配方必须填写，没有这张表视为未完成。行结构见 [`json_schema/FidelityBoundary.schema.json`](json_schema/FidelityBoundary.schema.json)。

```viba observation
ObservationLayer =
  Oneof
  | "app" * { 在数据加载器、写入器、block manager 外面包一层。拿得到请求的逻辑含义、偏移、大小、调用栈；看不到合并后的真实请求 }
  | "sys" * { 块设备 trace、文件系统客户端统计、网络计数器。拿得到真实下发的请求、排队、重传；丢失逻辑归属，难以按 rank 拆分 }
  | "storage" * { 存储服务端的请求日志与指标。拿得到服务端视角的吞吐、尾延迟、元数据操作；采样率与聚合粒度受限 }
```

三层观测至少要两层交叉核对：应用层统计的总字节数与系统层统计的总字节数，偏差超过 1% 必须先解释；解释不清时先怀疑观测本身，再使用任何 pattern 结论。观测开销单独测量：开启与关闭观测各跑一次，关键指标变化超过 3% 时降低采样率或改用系统层。

## 基本操作

先准备旁路（`PlanBypass`）：从四种手段里选一种，确认发起 IO 的代码路径没有被替换，登记时序偏差，必要时在旁路实现里注入与真实计算等长的延迟。再记录保真边界表（`RecordBoundary`）：每个被旁路的路径一行，IO 路径的保真等级不得是 L0。采集（`Observe`）至少开两层观测并交叉核对：应用层与系统层的总字节偏差超过 1% 要先解释，观测开销超过 3% 要降低采样率或改用系统层。对齐（`Align`）取不做旁路的同规模真实运行与旁路运行，在选定度量项上比较统计量，判定是否落在配方 `metrics.yaml` 标定的容差内；超出容差按归因顺序逐项排除，结论写进配方的 `README.md`。对齐通过后逐级放大（`Scale`），每一级重新验证不变量，跳级得到的结论没有依据。最后固定可复现条件（`Reproduce`）：模型代码、配置、依赖、拓扑、预热、观测、随机性七项，缺任何一项，结论都只能算某次运行的观测。

## methodology_api

```viba methodology_api
import bypass
import fidelity
import levels
import methodology
import observation

PlanBypass =
     methodology.MethodologyBypassPlan
  <- $method (bypass.BypassMethod * { 从四种旁路手段里选一种；它决定请求序列的保真等级 })
  <- $fidelity (bypass.FidelityLevel * { 请求序列的保真等级；L2 是大多数场景的默认目标，L3 只用于对齐基准，不用于批量运行 })
  <- $premise (methodology.MethodologyBypassPremise * { 旁路依赖的前提：发起 IO 的代码路径没有被替换，时序偏差已登记 })
  <- { 准备旁路：选定手段与保真等级，确认 IO 路径不变，登记时序偏差；时序按 scaling.md 的「时序与重叠」折算，必要时在旁路实现里注入与真实计算等长的延迟。返回旁路方案 }

RecordBoundary =
     methodology.MethodologyBoundaryTable
  <- $rows (list[fidelity.FidelityBoundary] * { 每个被旁路的代码路径一行，写到函数级；bypassed 为 partial 时写清部分的范围边界 })
  <- { 记录保真边界表：每个配方必须填写，没有这张表视为未完成；IO 路径的保真等级不得是 L0，写 L0 说明评估对象已被替换，该路径的结论无效。返回填好的表 }

Observe =
     methodology.MethodologyObservation
  <- $layers (list[observation.ObservationLayer] * { 这次开了哪几层；三层里至少两层交叉核对 })
  <- $app_bytes (float * { 应用层统计的总字节数 })
  <- $sys_bytes (float * { 系统层统计的总字节数 })
  <- $explanation (str * { 偏差超过 1% 时的解释；没有偏差写 none，不留空 })
  <- $overhead (float * { 开启与关闭观测各跑一次，关键指标的变化比例 })
  <- { 采集：三层观测至少开两层并交叉核对；应用层与系统层的总字节数偏差超过 1% 必须先解释，再使用任何 pattern 结论；观测开销超过 3% 时降低采样率或改用系统层。返回这次采集的观测结果 }

Align =
     methodology.MethodologyAlignment
  <- $real (methodology.MethodologyObservation * { 不做旁路的同规模真实运行，按 Observe 采集 })
  <- $bypass (methodology.MethodologyObservation * { 与真实运行同规模的旁路运行，也按 Observe 采集 })
  <- $tolerances (list[methodology.MethodologyTolerance] * { 配方 metrics.yaml 标定的容差；不是本文的初始容差 })
  <- { 小规模对齐：在选定的度量项上比较两次运行的统计量，判定是否落在容差内；差异超过容差时按 MethodologyAttributionCause 的顺序逐项排除，归因结论写进配方的 README.md。返回对齐判定 }

Scale =
     methodology.MethodologyScaling
  <- $level (levels.Level * { 这次放大到的档位；级别的定义见 scaling.md })
  <- $invariants (list[methodology.MethodologyMetric] * { 这一级要重新验证的不变量；对齐通过之前不允许进入 scaling })
  <- { 逐级放大：总则见 scaling.md；对齐通过之前不允许进入 scaling，每一级都要重新验证不变量，跳级得到的结论没有依据；偏差要有归因。返回这一级的结果 }

Reproduce =
     methodology.MethodologyReproduction
  <- $fixed (list[methodology.MethodologyReproducibilityItem] * { 已经固定的项；七项都要固定 })
  <- { 固定可复现条件：模型代码、配置、依赖、拓扑、预热、观测、随机性；返回固定的项与还缺的项。缺任何一项，结论都只能算某次运行的观测，不能算评估结论 }
```

## methodology_flow

```viba methodology_flow
import methodology
import methodology_api

MethodologyPrepareDuty =
  Object
  * $step (methodology_api.PlanBypass * { 准备旁路：对应门 G1，门 G0 是它的前提；先跑通不旁路的流程，再选旁路手段，保持 IO 路径不变 })
  * $plan (methodology.MethodologyBypassPlan * { 这一步的产物：旁路手段、请求序列保真等级、前提与时序偏差 })

MethodologyBoundaryDuty =
  Object
  * $step (methodology_api.RecordBoundary * { 记录保真边界：对应门 G1；每个配方必须填写 })
  * $table (methodology.MethodologyBoundaryTable * { 这一步的产物：保真边界表的行 })

MethodologyObserveDuty =
  Object
  * $step (methodology_api.Observe * { 采集：至少两层观测交叉核对；为门 G2 的对齐提供观测结果 })
  * $observation (methodology.MethodologyObservation * { 这一步的产物：观测层、字节偏差、解释与观测开销 })

MethodologyAlignDuty =
  Object
  * $step (methodology_api.Align * { 小规模对齐：与同规模真实运行对比选定度量项；对应门 G2 })
  * $alignment (methodology.MethodologyAlignment * { 这一步的产物：容差判定与偏差归因 })

MethodologyScaleDuty =
  Object
  * $step (methodology_api.Scale * { 逐级放大：每一级重新验证不变量；对应门 G3 })
  * $scaling (methodology.MethodologyScaling * { 这一步的产物：这一级的不变量保持情况与偏差归因 })

MethodologyReproduceDuty =
  Object
  * $step (methodology_api.Reproduce * { 固定可复现条件：结论登记前必须完成；缺任何一项，结论只能算某次运行的观测 })
  * $reproduction (methodology.MethodologyReproduction * { 这一步的产物：已固定的项与还缺的项 })

MethodologyFlow =
  Object
  * $spec (methodology.MethodologySpec * { 问题定义：阶段门、旁路、保真、观测、度量项、容差、scaling 规则、可复现与失效模式 })
  * $prepare (MethodologyPrepareDuty * { 第一步：准备旁路 })
  * $boundary (MethodologyBoundaryDuty * { 第二步：记录保真边界 })
  * $observe (MethodologyObserveDuty * { 第三步：采集并交叉核对观测 })
  * $align (MethodologyAlignDuty * { 第四步：小规模对齐 })
  * $scale (MethodologyScaleDuty * { 第五步：逐级放大 })
  * $reproduce (MethodologyReproduceDuty * { 第六步：固定可复现条件 })
```

Scaling 的总则见 [`scaling.md`](scaling.md)。

配方只写差异：`recipes/model-code-collection` 只写语料不变量与可跑性验证，`recipes/checkpoint` 只写 meta device 旁路与并行配置；共性的步骤、判定规则引用本文的章节标题加路径，不复制。新规则先写进本文，再改配方；配方里与本文冲突的表述以本文为准，并修正配方。改本文等于改三类评估集的共同定义，评审要求与改指标口径相同：说明影响哪些配方、哪些历史结论失效，并在 `CHANGELOG.md` 记录。

更多已知问题与开放问题见 [`pitfalls.md`](pitfalls.md)。

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
