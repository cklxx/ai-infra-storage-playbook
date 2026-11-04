# 度量项与容差

## public.viba

```bash public
import aisp.bench.checkpoint.measures.types as measures

MethodologySpec = measures.MethodologySpec
```

## types.viba

```bash types
import aisp.bench.checkpoint.bypass.types as bypass
import aisp.bench.checkpoint.fidelity.types as fidelity
import aisp.bench.checkpoint.gates.types as gates
import aisp.bench.checkpoint.scaling.types as levels
import aisp.bench.checkpoint.observation.types as observation

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

## apis.viba
