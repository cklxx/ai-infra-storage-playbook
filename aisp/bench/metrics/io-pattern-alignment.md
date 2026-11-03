# IO pattern 对齐度

## 背景

旁路运行必须与同等规模的真实运行在 IO 上对齐，旁路实现才算成立；这份文档定义对齐度怎么记录、怎么算、怎么判。对齐度不是一个数，而是一组分项：分项由配方的 `metrics.yaml` 用 `items` 与 `tolerance` 声明，check 脚本只算声明过的项，逐项判定，全部通过才算对齐。它是阶段门 G2 的门槛。

## 问题

```viba io_pattern
import observation

IoPatternSpec =
  Object
  * $runs (list[IoPatternRunRole] * { 要比对的两侧：旁路运行与同等规模的真实运行 })
  * $record (IoPatternRecord * { 记录结构：一次运行产出的 IO pattern 记录；记录必须声明至少两层采集来源且包含 sys })
  * $items (list[IoPatternMetricItem] * { 度量项：配方 metrics.yaml 用 items 声明，只算声明过的项 })
  * $tolerance (list[IoPatternTolerance] * { 容差：配方 metrics.yaml 的 tolerance，逐项一条，由评审把关 })
  * $verdict (IoPatternVerdict * { 判定：全部在阈值内是对齐通过，否则按归因与记录状态给出有条件通过、不通过或不可比 })

IoPatternRunRole =
  Oneof
  | "real" * { 同等规模的真实运行；相对误差的分母取这一侧的值 }
  | "bypass" * { 旁路运行；要与真实运行在选定度量项上对齐 }

IoPatternWindow =
  Object
  * $start (str * { 稳态窗口起点；两侧窗口从稳态开始，长度相同 })
  * $end (str * { 稳态窗口终点；与 start 一起确定窗口长度 })

IoPatternTotals =
  Object
  * $read_bytes (int * { 读请求的总字节数；应用层逐请求求和与系统层统计的偏差超过 1% 时，对齐度结论作废 })
  * $write_bytes (int * { 写请求的总字节数；应用层逐请求求和与系统层统计的偏差超过 1% 时，对齐度结论作废 })
  * $read_ops (int * { 读请求的总数；用于按请求数口径计算读写比 })
  * $write_ops (int * { 写请求的总数；用于按请求数口径计算读写比 })

IoPatternHistogram =
  Object
  * $bucket_edges (list[int] * { 请求大小直方图的分桶边界，按 4 KiB 起对数分桶；两边必须相同 })
  * $counts (list[int] * { 每个桶里的请求数；归一化后算 L1 距离 })

IoPatternConcurrency =
  Object
  * $p50 (float * { 并发度中位数；判 concurrency_p50 时用 })
  * $p95 (float * { 并发度 P95；判 concurrency_p95 时用 })
  * $max (float * { 并发度最大值；判 concurrency_max 时用 })

IoPatternHotness =
  Object
  * $top_k (int * { Top-K 的 K，按数据块统计访问次数 })
  * $top_k_share (float * { Top-K 块访问次数占总访问次数的比例；判 hotness 时用 })

IoPatternTiming =
  Object
  * $peak_bytes_per_second (float * { 每秒峰值字节数；判 timing_peak 时用 })

IoPatternRecord =
  Object
  * $run_id (str * { 运行标识 })
  * $recipe (str * { 产出这条记录的配方名 })
  * $window (IoPatternWindow * { 采集窗口；两侧必须从稳态开始且长度相同 })
  * $sources (list[observation.ObservationLayer] * { 采集来源；至少两层且必须含 sys，否则不能用于对齐判定 })
  * $totals (IoPatternTotals * { 读写总量，按字节与请求数两个口径 })
  * $request_size_histogram (IoPatternHistogram * { 请求大小直方图；两侧 bucket_edges 必须相同 })
  * $concurrency ((IoPatternConcurrency | nil) * { 并发度分布；声明 concurrency 分项时需要，没有采集给 nil })
  * $sequentiality_ratio ((float | nil) * { 顺序请求占比；声明 sequentiality 分项时需要，没有采集给 nil })
  * $hotness ((IoPatternHotness | nil) * { 块访问热度；声明 hotness 分项时需要，没有采集给 nil })
  * $observation_overhead_ratio ((float | nil) * { 开启观测与关闭观测相比关键指标的变化比例；超过 3% 时时序结论无效，没有测量给 nil })
  * $tokens_generated ((int | nil) * { 本次运行生成的 token 数；声明 per_token_kv_bytes 分项时需要，没有采集给 nil })
  * $timing ((IoPatternTiming | nil) * { 每秒字节数峰值；声明 timing_peak 分项时需要，没有采集给 nil })

IoPatternMetricItem =
  Oneof
  | "request_size_distribution" * { 两组直方图归一化后的 L1 距离；单位是距离 0–2；两边的 bucket_edges 必须相同；初始参考阈值 0.10 }
  | "read_write_ratio_bytes" * { 按字节口径的读写比相对误差；单位是比例；初始参考阈值 5% }
  | "read_write_ratio_ops" * { 按请求数口径的读写比相对误差；单位是比例；初始参考阈值 10% }
  | "concurrency_p50" * { 并发度 P50 的相对误差；单位是比例；初始参考阈值 10% }
  | "concurrency_p95" * { 并发度 P95 的相对误差；单位是比例；初始参考阈值 20% }
  | "concurrency_max" * { 并发度最大值的相对误差；单位是比例；初始参考阈值表没有给这一项，容差以配方 metrics.yaml 为准 }
  | "sequentiality" * { 顺序请求占比的绝对差；单位是绝对差；初始参考阈值 0.05 }
  | "hotness" * { Top-K 块访问占比的绝对差；单位是绝对差；初始参考阈值 0.05 }
  | "per_token_kv_bytes" * { 每 token KV 写入字节的相对误差；单位是比例；需要记录 tokens_generated；初始参考阈值 1% }
  | "timing_peak" * { 每秒峰值字节数的相对误差；单位是比例；需要记录 timing.peak_bytes_per_second；初始参考阈值 10% }

IoPatternUnit =
  Oneof
  | "distance" * { 距离，0–2；request_size_distribution 用 }
  | "ratio" * { 比例；两个读写比、三个并发度、每 token KV 字节与峰值时序用 }
  | "absolute" * { 绝对差；顺序性与热度用 }

IoPatternMetricResult =
  Object
  * $item (IoPatternMetricItem * { 这一项是哪个度量项 })
  * $value (float * { 这一项算出的差值：L1 距离、相对误差或绝对差，按 item 的定义算 })
  * $unit (IoPatternUnit * { 这一项的单位，由 item 决定 })

IoPatternComparison =
  Object
  * $real (IoPatternRecord * { 同等规模的真实运行记录；相对误差的分母取这一侧的值 })
  * $bypass (IoPatternRecord * { 旁路运行记录 })
  * $items (list[IoPatternMetricResult] * { 只算配方 metrics.yaml 用 items 声明过的度量项，逐项一条 })
  * $comparable (bool * { 两侧窗口相同、直方图 bucket_edges 相同、记录合法时才可比；不可比时不给结论 })
  * $incomparable_reason ((str | nil) * { 不可比的原因：窗口不同、bucket_edges 不同或记录非法；可比时给 nil })

IoPatternToleranceSource =
  Oneof
  | "reference" * { 直接使用初始参考阈值 }
  | "calibrated" * { 标定值高于参考值，改用标定值 }

IoPatternCalibration =
  Object
  * $repeats (int * { 标定时同一配置做 5 次真实运行 })
  * $max_pairwise_difference (float * { 5 次真实运行两两之间的最大差异，作为容差下限 })
  * $date (str * { 标定日期 })
  * $baseline_ref (str * { 基准运行的回链 })

IoPatternTolerance =
  Object
  * $item (IoPatternMetricItem * { 这一条容差对应的度量项 })
  * $reference ((float | nil) * { 初始参考阈值；concurrency_max 的参考阈值表没有给这一项，给 nil })
  * $limit (float * { 这次判定实际使用的阈值；标定值高于参考值时取标定值，否则取参考值 })
  * $source (IoPatternToleranceSource * { 实际阈值取自参考值还是标定值 })
  * $calibration ((IoPatternCalibration | nil) * { 标定记录；没有标定给 nil })

IoPatternDeviationDirection =
  Oneof
  | "above" * { 旁路运行的值高于真实运行 }
  | "below" * { 旁路运行的值低于真实运行 }
  | "unknown" * { 偏差方向不明 }

IoPatternAttribution =
  Object
  * $item (IoPatternMetricItem * { 哪一项超出阈值 })
  * $explained (bool * { 归因是否已写清；归因不明时判不通过 })
  * $direction (IoPatternDeviationDirection * { 偏差方向：旁路值相对真实值是高还是低 })
  * $controllable (bool * { 偏差方向是否可控；有条件通过要求归因已写清且方向可控 })
  * $detail (str * { 归因的具体说明 })

IoPatternLimitation =
  Oneof
  | "looks_like_only" * { 只能判定像不像，不能判定对不对；两侧同时漏采同一类请求时，仍会判为对齐 }
  | "timing_observation_sensitive" * { 时序分项对观测开销敏感；开销本身超过 3% 时，时序结论无效 }
  | "scale_up_not_guaranteed" * { 小规模上对齐，不保证放大后仍对齐；放大后的偏差由 scaling 一致性负责 }

IoPatternExplanation =
  Object
  * $attributions (list[IoPatternAttribution] * { 每一项超出阈值的归因，逐项一条 })
  * $timing_valid (bool * { 观测开销不超过 3% 时时序结论有效；超过 3% 时时序分项结论无效 })
  * $limitations (list[IoPatternLimitation] * { 这条结论的已知限制，按原文档列出 })

IoPatternVerdict =
  Oneof
  | "对齐通过" * { 全部声明项在阈值内 }
  | "有条件通过" * { 任一项超出，归因已写清、偏差方向可控；需评审确认 }
  | "不通过" * { 任一项超出，归因不明 }
  | "不可比" * { 阈值缺失、记录非法、观测失败；重跑 }

IoPatternToleranceCheck =
  Object
  * $item (IoPatternMetricItem * { 这一项是哪个度量项 })
  * $value (float * { 这一项算出的差值 })
  * $limit (float * { 这一项实际使用的阈值 })
  * $within (bool * { 差值是否不超过阈值 })

IoPatternJudgement =
  Object
  * $verdict (IoPatternVerdict * { 最终结论：对齐通过、有条件通过、不通过或不可比 })
  * $checks (list[IoPatternToleranceCheck] * { 逐项对照阈值的结果 })
  * $explanation (IoPatternExplanation * { 判定所依据的归因与已知限制 })
```

## 基本操作

解决这个问题需要四个操作。采集：在旁路运行与同等规模的真实运行上，从应用层 hook 记录每次请求的偏移、大小、时间戳与方向，从系统层取设备或客户端的请求统计，并记录 `tokens_generated` 与 `timing.peak_bytes_per_second`；记录必须声明至少两层采集来源且包含 `sys`，应用层与系统层的总字节数偏差超过 1% 时先解释偏差。比较：两侧使用相同的时间窗口，只计算配方 `metrics.yaml` 用 `items` 声明过的度量项，逐项算差值；直方图的 `bucket_edges` 不一致时判为不可比，不给结论。归因：对超出容差的项写清原因，并说明偏差方向是否可控；观测开销超过 3% 时时序分项结论无效。判定：按 `tolerance` 里的阈值逐项对照，全部在阈值内是对齐通过，任一项超出但归因已写清且偏差方向可控是有条件通过（需评审确认），归因不明是不通过，阈值缺失、记录非法或观测失败是不可比并重跑。

## 接口

```viba io_pattern_api
import io_pattern
import observation
import types

Collect =
     io_pattern.IoPatternRecord
  <- $run (types.RunRecord * { 要采集的那次运行：旁路运行或同等规模的真实运行 })
  <- $role (io_pattern.IoPatternRunRole * { 这次运行是哪一侧 })
  <- $layers (list[observation.ObservationLayer] * { 采集层；至少两层且必须含 sys，否则不能用于对齐判定 })
  <- $warmup_rounds (int * { 丢弃前 N 轮，N 写进配方参数 })
  <- { 采集：从应用层 hook 取每次请求的偏移、大小、时间戳、方向，从系统层取设备或客户端的请求统计，存储侧的请求日志有则用于三方核对，按配方声明汇总成记录；应用层与系统层的总字节数偏差超过 1% 时先解释偏差。返回一条记录 }

Compare =
     io_pattern.IoPatternComparison
  <- $real (io_pattern.IoPatternRecord * { 同等规模的真实运行记录；相对误差的分母取这一侧的值 })
  <- $bypass (io_pattern.IoPatternRecord * { 旁路运行记录 })
  <- $items (list[io_pattern.IoPatternMetricItem] * { 配方 metrics.yaml 用 items 声明过的度量项；只算这些项 })
  <- { 比较：两侧使用相同时间窗口，逐项算差值；直方图 bucket_edges 不一致时判为不可比，不给结论。返回逐项差值与可比性 }

Judge =
     io_pattern.IoPatternJudgement
  <- $comparison (io_pattern.IoPatternComparison * { 比较结果：逐项差值与可比性 })
  <- $tolerances (list[io_pattern.IoPatternTolerance] * { 配方 metrics.yaml 的 tolerance；声明项缺少阈值时判不可比 })
  <- $explanation (io_pattern.IoPatternExplanation * { 比较结果的归因与已知限制；归因不明判不通过 })
  <- { 判定：逐项对照阈值。全部在阈值内是对齐通过；任一项超出但归因已写清且偏差方向可控是有条件通过，需评审确认；归因不明是不通过；阈值缺失、记录非法或观测失败是不可比，重跑。返回判定 }

Explain =
     io_pattern.IoPatternExplanation
  <- $comparison (io_pattern.IoPatternComparison * { 比较结果：哪些项超出阈值 })
  <- $tolerances (list[io_pattern.IoPatternTolerance] * { 容差声明；用来找出超出阈值的项 })
  <- { 归因：对超出阈值的每一项写清原因与偏差方向是否可控，并列出已知限制；观测开销超过 3% 时时序分项结论无效。返回归因 }
```

## 组织

```viba io_pattern_flow
import io_pattern
import io_pattern_api

IoPatternCollectDuty =
  Object
  * $real (io_pattern_api.Collect * { 采集真实运行：同等规模、开观测；返回一条真实运行记录 })
  * $bypass (io_pattern_api.Collect * { 采集旁路运行：与真实运行同规模、也开观测；返回一条旁路运行记录 })
  * $records (list[io_pattern.IoPatternRecord] * { 两条记录：真实运行与旁路运行；两侧窗口长度相同 })

IoPatternCompareDuty =
  Object
  * $compare (io_pattern_api.Compare * { 比较两条记录：只算声明项，逐项算差值 })
  * $comparison (io_pattern.IoPatternComparison * { 比较结果；不可比时不给结论 })

IoPatternExplainDuty =
  Object
  * $explain (io_pattern_api.Explain * { 归因：对超出项写清原因与偏差方向 })
  * $explanation (io_pattern.IoPatternExplanation * { 归因结果与已知限制 })

IoPatternJudgeDuty =
  Object
  * $judge (io_pattern_api.Judge * { 判定：按配方 tolerance 逐项对照 })
  * $judgement (io_pattern.IoPatternJudgement * { 判定结果：对齐通过、有条件通过、不通过或不可比 })

IoPatternFlow =
  Object
  * $spec (io_pattern.IoPatternSpec * { 问题定义：记录结构、度量项、容差、判定 })
  * $collect (IoPatternCollectDuty * { 采集：两侧各一条记录 })
  * $compare (IoPatternCompareDuty * { 比较：逐项算差值 })
  * $explain (IoPatternExplainDuty * { 归因：超出项的原因与偏差方向 })
  * $judge (IoPatternJudgeDuty * { 判定：逐项对照容差，得出最终结论 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
