# 度量项与容差

## 需求背景

对齐要有尺子：度量项、统计量与容差。判定两个数是否落在容差内要用这一份定义，所以本篇发布度量项、容差与比较操作。

## public.viba

```bash public
import aisp.bench.checkpoint.measures.types as measures
import aisp.bench.checkpoint.measures.apis as measures_api

MethodologyMetric = measures.MethodologyMetric
MethodologyToleranceStatistic = measures.MethodologyToleranceStatistic
MethodologyTolerance = measures.MethodologyTolerance
MethodologyToleranceCalibration = measures.MethodologyToleranceCalibration
CompareTolerance = measures_api.CompareTolerance
```

## types.viba

```bash types
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
  * $recipe (str * { 标定结果写进哪个配方的 metrics.yaml，例如 checkpoint 这个评估集 })
  * $date (str * { 标定日期 })
  * $baseline (str * { 所用基准 })
```

## 基本操作

只有一个操作：比一个度量项。给出一项的容差与两个数值，按这一项的统计量判定是否落在容差内。

## apis.viba

```bash apis
import aisp.bench.checkpoint.measures.types as measures

CompareTolerance =
     bool
  <- $tolerance (measures.MethodologyTolerance * { 这一项的统计量与容差 })
  <- $observed (float * { 旁路运行测得的数值 })
  <- $expected (float * { 真实运行测得的数值 })
  <- {
    按这一项的统计量比较两个数：落在容差内答 true；超出时按这一项的统计量逐项排查，结论写进配方目录，不留在聊天记录里
  }
```
