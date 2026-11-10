# Diff Minner：SLI 与差距判定

## 需求背景

Diff Minner 对比同一份负载在 EFS 与 GPFS 上的表现，回答三个问题：采哪些指标，什么差距才算明显差于，以及怎样采集才能把差距归因到存储。dataset、ckpt 与 kvcache 三类负载共用这一套配对比较与证据口径，所以指标、运行证据、判定结果与比较操作从这里发布。


## public.viba

```bash public
import aisp.bench.diff_minner.types as diff
import aisp.bench.diff_minner.apis as diff_api

MetricName = diff.MetricName
Statistic = diff.Statistic
CacheState = diff.CacheState
StorageSide = diff.StorageSide
Payload = diff.Payload
FileSize = diff.FileSize
DatasetPayload = diff.DatasetPayload
CheckpointPayload = diff.CheckpointPayload
KvCachePayload = diff.KvCachePayload
Environment = diff.Environment
EnvironmentPair = diff.EnvironmentPair
SampleWindow = diff.SampleWindow
WindowShape = diff.WindowShape
IoOperation = diff.IoOperation
StorageScenario = diff.StorageScenario
MetadataFileKind = diff.MetadataFileKind
InterferenceRecord = diff.InterferenceRecord
InterferencePair = diff.InterferencePair
SideAdmissionEvidence = diff.SideAdmissionEvidence
AdmissionEvidence = diff.AdmissionEvidence
StabilityPolicy = diff.StabilityPolicy
GapPolicy = diff.GapPolicy
NoiseMeasurement = diff.NoiseMeasurement
NoiseBaseline = diff.NoiseBaseline
PairedMetricRound = diff.PairedMetricRound
MetricSeries = diff.MetricSeries
ComparisonGroup = diff.ComparisonGroup
Interval = diff.Interval
ThresholdKind = diff.ThresholdKind
GapGates = diff.GapGates
MetricComparison = diff.MetricComparison
Comparison = diff.Comparison
Defect = diff.Defect
ComparisonResult = diff.ComparisonResult
CandidateReview = diff.CandidateReview
ClassifiedComparison = diff.ClassifiedComparison
CompareGroup = diff_api.CompareGroup
```

## types.viba

一个 `ComparisonGroup` 是同一份 payload 的一个完整比较格，包含应用指标、用于归因的存储原生指标与逐轮双侧准入证据。每个 `MetricSeries` 是一个指标在同一档位下的至少五轮配对原始值。任一应用感知指标（主或辅助）同时越过三道门槛，比较格就进入候选池；原生指标的越线结果只用于解释和归因。

```bash types
MetricName =
  Oneof
  | "dataset_samples_per_gpu" * { 每卡样本吞吐，samples/s/GPU；主指标，越低越差 }
  | "dataset_first_batch_wait" * { 首个 batch 等待时长，秒；主指标，越高越差 }
  | "dataset_gpu_io_wait" * { GPU IO wait 占比；辅助指标，越高越差 }
  | "dataset_epoch_duration" * { epoch 总时长，秒；辅助指标，越高越差 }
  | "dataset_job_startup" * { 作业启动到开训时长，秒；辅助指标，越高越差 }
  | "ckpt_save_stall" * { 单次保存对训练的同步阻塞时长，秒；主指标，越高越差 }
  | "ckpt_load" * { checkpoint load 时长，秒；主指标，越高越差 }
  | "ckpt_save_duration" * { 保存总时长，秒；辅助指标，越高越差 }
  | "ckpt_write_bandwidth" * { 写带宽，GiB/s；辅助指标，越低越差 }
  | "ckpt_failure_recovery" * { 故障恢复总时长，秒；辅助指标，越高越差 }
  | "kv_ttft" * { TTFT，秒；主指标，报均值与 P99，越高越差 }
  | "kv_fetch_segment" * { KV 取回传输段延迟，秒；主指标，脱离计算段单独计时，越高越差 }
  | "kv_tpot" * { TPOT，秒；辅助指标，越高越差 }
  | "kv_effective_hit_rate" * { 有效命中率；取回路径不比重算更快的命中不计收益，辅助指标，越低越差 }
  | "kv_qps" * { 推理请求 QPS；辅助指标，越低越差 }
  | "storage_sequential_read_bandwidth" * { 顺序读带宽，GiB/s；越低越差 }
  | "storage_random_read_bandwidth" * { 随机读带宽，GiB/s；越低越差 }
  | "storage_write_bandwidth" * { 写带宽，GiB/s；越低越差 }
  | "storage_random_read_iops" * { 4 KiB 随机读 IOPS；越低越差 }
  | "storage_random_write_iops" * { 4 KiB 随机写 IOPS；越低越差 }
  | "storage_io_latency" * { IO 延迟，秒；按 operation 与 statistic 报分布，越高越差 }
  | "metadata_create_qps" * { create QPS；越低越差 }
  | "metadata_stat_qps" * { stat QPS；越低越差 }
  | "metadata_unlink_qps" * { unlink QPS；越低越差 }
  | "metadata_open_qps" * { open QPS；越低越差 }
  | "metadata_readdir_qps" * { readdir QPS；越低越差 }
  | "metadata_create_latency" * { create 延迟，秒；按 statistic 报分布，越高越差 }
  | "metadata_stat_latency" * { stat 延迟，秒；按 statistic 报分布，越高越差 }
  | "metadata_unlink_latency" * { unlink 延迟，秒；按 statistic 报分布，越高越差 }
  | "metadata_open_latency" * { open 延迟，秒；按 statistic 报分布，越高越差 }
  | "metadata_readdir_latency" * { readdir 延迟，秒；按 statistic 报分布，越高越差 }
  | "interference_read_bandwidth" * { 背景写压力下的读带宽，GiB/s；越低越差 }
  | "interference_read_latency" * { 背景写压力下的读延迟，秒；至少报 P99，越高越差 }

Statistic =
  Oneof
  | "mean" * { 测量窗内均值；文档中的 avg 也用这个取值 }
  | "p50" * { 测量窗内 P50 }
  | "p99" * { 测量窗内 P99 }
  | "p999" * { 测量窗内 P999 }

CacheState =
  Oneof
  | "cold" * { 每轮都重新挂载并清空页缓存与客户端缓存，只取清缓存后的首轮 }
  | "hot" * { 每轮测量前完整预读同一 payload；与冷态分开报，不混入同一组统计 }

StorageSide =
  Oneof
  | "efs"
  | "gpfs"

Payload =
  Oneof
  | $dataset (DatasetPayload * { dataset 的完整形状参数 })
  | $ckpt (CheckpointPayload * { ckpt 的完整形状参数 })
  | $kvcache (KvCachePayload * { kvcache 的完整形状参数 })

FileSize =
  Oneof
  | $fixed_bytes (int * { 所有文件相同的字节数 })
  | $distribution (str * { 混合文件大小的完整分布产物位置，不用平均大小代替 })

DatasetPayload =
  Object
  * $file_count (int * { 文件总数 })
  * $file_size (FileSize * { 单文件大小或完整大小分布 })
  * $files_per_rank (int * { 每 rank 文件数 })
  * $random_read (bool * { 是否随机读取 })

CheckpointPayload =
  Object
  * $model_parameters (int * { 模型参数量 })
  * $sharding (str * { 分片方式与每 rank 分片大小 })
  * $save_frequency_steps (int * { 每多少训练步保存一次 })
  * $async_write (bool * { 是否异步写 })

KvCachePayload =
  Object
  * $bytes_per_token (int * { KV 每 token 字节数 })
  * $context_length (int * { 上下文长度，token 数 })
  * $hit_rate (float * { 命中率，0 到 1 })
  * $block_size_bytes (int * { KV 块字节数 })
  * $concurrent_sessions (int * { 并发会话数 })

Environment =
  Object
  * $machine_model (str * { 机型 })
  * $cpu_model (str * { CPU 型号 })
  * $nic_model (str * { 网卡型号 })
  * $nic_count (int * { 网卡数量 })
  * $disk_model (str * { 盘型号 })
  * $disk_count (int * { 盘数量 })
  * $filesystem_version (str * { 文件系统版本；两侧分别记录 })
  * $adapter (str * { 存储适配层 name@version；两侧必须一致 })
  * $mount_options (str * { 完整挂载参数 })
  * $client_count (int * { 客户端数 })
  * $iodepth (int * { IO 队列深度；存储原生微基准固定为 16 })
  * $direct (bool * { 是否绕过页缓存；存储原生微基准固定为 true })

EnvironmentPair =
  Object
  * $efs (Environment * { EFS 侧环境 })
  * $gpfs (Environment * { GPFS 侧环境；除文件系统实现、版本与必需挂载差异外，其余控制项逐项对齐 })

WindowShape =
  Object
  * $duration_s (float * { 两侧相同的有效采样时长；存储原生微基准固定为 120 秒 })
  * $warmup_discard_s (float * { 两侧相同的预热丢弃时长；冷热状态由 CacheState 单独区分 })

SampleWindow =
  Object
  * $shape (WindowShape * { 本轮有效采样与预热窗口形状 })
  * $efs_started_at (str * { EFS 有效测量开始时间，ISO 8601 })
  * $efs_ended_at (str * { EFS 有效测量结束时间，ISO 8601 })
  * $gpfs_started_at (str * { GPFS 有效测量开始时间，ISO 8601 })
  * $gpfs_ended_at (str * { GPFS 有效测量结束时间，ISO 8601 })

IoOperation =
  Oneof
  | "sequential_read"
  | "random_read"
  | "sequential_write"
  | "random_write"

MetadataFileKind =
  Oneof
  | "empty" * { 空文件 }
  | "real_small" * { 真实小文件 }

StorageScenario =
  Object
  * $operation ((IoOperation | nil) * { 带宽、IOPS、IO 延迟与混部指标必填；元数据与应用指标给 nil })
  * $block_size ((str | nil) * { 带宽、IOPS、IO 延迟与混部指标分档：4KiB、128KiB、1MiB、64MiB；其他指标给 nil })
  * $streams ((int | nil) * { 带宽、IOPS、IO 延迟与混部指标的并发流数：单流填 1，并发流至少 10；其他指标给 nil })
  * $metadata_file_kind ((MetadataFileKind | nil) * { 元数据指标必填，空文件与真实小文件分开比较；其余指标给 nil })
  * $background_write_mb_s_per_disk ((float | nil) * { 混部干扰指标必填：0、256、512 三档；其余指标给 nil })

InterferenceRecord =
  Object
  * $configured_mb_s_per_disk (float * { 本轮配置的背景写目标速率，MB/s/盘 })
  * $actual_mb_s_per_disk (float * { 本轮实测背景写速率，MB/s/盘 })
  * $disk_count (int * { 背景写实际作用的盘数 })
  * $started_at (str * { 背景写开始时间，ISO 8601 })
  * $ended_at (str * { 背景写结束时间，ISO 8601 })
  * $evidence_uri (str * { 背景写作业、配置与原始计数的产物位置 })

InterferencePair =
  Object
  * $efs (InterferenceRecord * { EFS 测量窗内的背景写证据 })
  * $gpfs (InterferenceRecord * { GPFS 测量窗内的背景写证据 })

SideAdmissionEvidence =
  Object
  * $content_match (bool * { 读写后逐字节或校验和比对是否一致 })
  * $checksum_algorithm ((str | nil) * { 使用校验和时填写算法与覆盖范围；逐字节比对给 nil })
  * $content_evidence_uri (str * { 预期与实际摘要比对或逐字节比对的证据位置 })
  * $checkpoint_recovery ((bool | nil) * { ckpt 必填：完整训练状态是否可恢复；其他负载给 nil })
  * $mlperf_storage_version ((str | nil) * { ckpt 必填：采用的 MLPerf Storage 版本；其他负载给 nil })
  * $training_state_evidence_uri ((str | nil) * { ckpt 必填：完整状态清单、全 rank 恢复与可继续训练的证明；其他负载给 nil })
  * $error_rate (float * { 测量窗内错误率 })
  * $timeout_rate (float * { 测量窗内超时率 })
  * $throttle_count (int * { 测量窗内限流次数 })
  * $retry_count (int * { 测量窗内重试次数 })
  * $stability_window_s (float * { 连续长压观察窗，秒；必须等于实际起止时间之差 })
  * $stability_started_at (str * { 长压观察开始时间，ISO 8601 })
  * $stability_ended_at (str * { 长压观察结束时间，ISO 8601；观察窗须覆盖本轮对应侧有效测量窗 })
  * $performance_decay (float * { 连续长压下的性能衰减，相对值 })
  * $periodic_jitter (float * { 连续长压下的周期抖动，相对值 })
  * $stability_series_uri (str * { 错误、超时、限流、重试与长压性能时间序列的位置 })

AdmissionEvidence =
  Object
  * $efs (SideAdmissionEvidence * { EFS 侧正确性与稳定性证据 })
  * $gpfs (SideAdmissionEvidence * { GPFS 基线侧正确性与稳定性证据 })

StabilityPolicy =
  Object
  * $min_window_s (float * { 最短连续长压观察窗，秒；源文档未给数值，必须由评测方提供 })
  * $max_error_rate (float * { 允许的最大错误率 })
  * $max_timeout_rate (float * { 允许的最大超时率 })
  * $max_throttle_count (int * { 允许的最大限流次数 })
  * $max_retry_count (int * { 允许的最大重试次数 })
  * $max_performance_decay (float * { 允许的最大性能衰减 })
  * $max_periodic_jitter (float * { 允许的最大周期抖动 })

GapPolicy =
  Object
  * $version (str * { 判定口径版本；首版为 diff-minner-v1，调阈值或统计算法后换版本 })
  * $mean_threshold (float * { 均值类实际意义阈值；首版 0.10 })
  * $tail_threshold (float * { P99、P999 尾延迟实际意义阈值；首版 0.20 })
  * $metadata_qps_threshold (float * { 元数据 QPS 实际意义阈值；首版 0.15 })
  * $bootstrap_resamples (int * { 配对 bootstrap 重抽样次数；首版 10000 })
  * $bootstrap_seed (int * { 非负随机种子；与固定生成器及抽样算法一起保证结果可复算 })
  * $stability (StabilityPolicy * { 正确性与稳定性准入阈值；源文档未给数值，必须由评测方提供 })
  * $interference_tolerance_mb_s_per_disk (float * { 实测背景写速率相对目标档允许的最大绝对偏差；源文档未给数值，必须由评测方提供 })
  * $calibration_evidence_uri ((str | nil) * { 首版给 nil；回调版本必填候选池分布、人工保留结果与调阈依据的位置 })

NoiseMeasurement =
  Object
  * $measured_on (str * { 自比测量日期，ISO 8601 日期；与 started_at 日期一致 })
  * $value (float * { 本侧本轮该统计量的原始值 })
  * $started_at (str * { 有效测量开始时间，ISO 8601 })
  * $ended_at (str * { 有效测量结束时间，ISO 8601 })
  * $interference ((InterferenceRecord | nil) * { 混部指标必填；其余指标给 nil })
  * $evidence_uri (str * { 本次自比原始输出、缓存处理与环境证据的位置 })

NoiseBaseline =
  Object
  * $side (StorageSide * { 哪一侧文件系统的自比基线；每个指标两侧都要有 })
  * $payload (Payload * { 与正式比较的完整 payload 相同 })
  * $metric (MetricName * { 与待比较指标相同 })
  * $statistic (Statistic * { 与待比较统计量相同 })
  * $cache_state (CacheState * { 与待比较冷热状态相同 })
  * $storage_scenario ((StorageScenario | nil) * { 与待比较场景相同；应用指标给 nil })
  * $environment (Environment * { 自比侧环境；须与正式轮次对应侧一致 })
  * $window (WindowShape * { 与正式轮次相同的采样窗口形状 })
  * $measurements (list[NoiseMeasurement] * { 至少两个不同日期，每个日期至少两次测量 })
  * $between_round_differences (list[float] * { 同日按时间相邻测量的相对差，由 measurements 复算 })
  * $between_day_differences (list[float] * { 按日期排序后相邻测量日的日中位数相对差，由 measurements 复算 })
  * $band (float * { 两个相对差列表所有元素绝对值的最大值；不得直接填写预期值 })
  * $evidence_uri (str * { 自比差值、日 median 与噪声带的计算结果位置 })

PairedMetricRound =
  Object
  * $index (int * { 配对轮次，从 1 开始连续编号 })
  * $efs_value (float * { 本轮 EFS 原始值 })
  * $gpfs_value (float * { 本轮 GPFS 原始值 })
  * $first (StorageSide * { 本轮先跑哪一侧；首轮随机，之后逐轮轮换 })
  * $environments (EnvironmentPair * { 本轮两侧环境对照 })
  * $window (SampleWindow * { 本轮两侧采样窗及实际起止时间 })
  * $interference ((InterferencePair | nil) * { 混部指标必填；其余指标给 nil })
  * $admission (AdmissionEvidence * { 本轮两侧正确性与稳定性证据；相同长压窗可覆盖多轮 })
  * $evidence_uri (str * { 本轮两侧原始输出、trace 与缓存处理记录的位置 })

MetricSeries =
  Object
  * $metric (MetricName * { 要比较的指标 })
  * $statistic (Statistic * { 要比较的统计量 })
  * $storage_scenario ((StorageScenario | nil) * { 存储原生指标必填；应用感知指标给 nil })
  * $order_seed (int * { 首轮先后顺序的随机种子 })
  * $rounds (list[PairedMetricRound] * { 至少五轮配对原始值；每轮先跑侧逐轮交替 })
  * $noise (list[NoiseBaseline] * { EFS 与 GPFS 各一条；指标、统计量、冷热与场景必须一致 })

ComparisonGroup =
  Object
  * $group_id (str * { 完整比较格标识；只绑定 payload 与冷热状态 })
  * $run_id (str * { 本次比较运行的唯一标识；重复执行同一 group_id 时必须更换 })
  * $payload (Payload * { 两侧共用的同一份 payload；分支同时确定负载类型 })
  * $cache_state (CacheState * { 本组只含一种冷热状态 })
  * $series (list[MetricSeries] * { 完整应用指标集与该负载必需的原生子集；各序列自行绑定场景，以 metric、statistic、storage_scenario 唯一 })

Interval =
  Object
  * $lower (float * { 区间下界 })
  * $upper (float * { 区间上界 })

ThresholdKind =
  Oneof
  | "mean" * { 均值类及未单独特定的统计量，使用 mean_threshold }
  | "tail_latency" * { P99 或 P999，使用 tail_threshold }
  | "metadata_qps" * { 五种元数据操作的 QPS，使用 metadata_qps_threshold }

GapGates =
  Object
  * $statistical (bool * { 方向化配对差值的 95% 置信区间整体位于有害侧且不包含零 })
  * $practical (bool * { 有害方向的相对差达到实际意义阈值 })
  * $above_noise (bool * { 有害方向的相对差严格大于两侧实测噪声带的较大值 })

MetricComparison =
  Object
  * $series (MetricSeries * { 本指标的完整输入证据 })
  * $efs_median (float * { EFS 各轮原始值的中位数 })
  * $gpfs_median (float * { GPFS 各轮原始值的中位数 })
  * $efs_mad (float * { EFS 各轮原始值的中位数绝对偏差，作为离散度 })
  * $gpfs_mad (float * { GPFS 各轮原始值的中位数绝对偏差，作为离散度 })
  * $paired_difference_ci (Interval * { 方向化配对差值中位数的非参数 bootstrap 95% 置信区间 })
  * $relative_gap ((float | nil) * { 以 GPFS 中位数绝对值为分母的有害方向相对差；GPFS 中位数为零时给 nil })
  * $threshold_kind (ThresholdKind * { 本指标使用的实际意义阈值类别 })
  * $applied_threshold (float * { 从 GapPolicy 取到的实际阈值 })
  * $noise_band (float * { 两侧 NoiseBaseline.band 的较大值 })
  * $gates ((GapGates | nil) * { 三道门槛各自的结果；相对差不可计算时给 nil })
  * $uncomparable_reason ((str | nil) * { 相对差不可计算时说明零分母等原因；可计算时给 nil })
  * $material_diff (bool * { 三个 gate 全为 true；gates 为 nil 时必须为 false，任一应用指标均可触发候选 })

Comparison =
  Object
  * $group (ComparisonGroup * { 完整比较格：payload、冷热、所有指标原始值、环境与逐轮准入证据 })
  * $policy (GapPolicy * { 本次使用的阈值、统计算法与准入口径 })
  * $metrics (list[MetricComparison] * { 每个输入指标一份统计与越线结果 })
  * $candidate (bool * { 至少一个应用感知指标的 material_diff 为 true；原生指标不能独立触发候选 })
  * $completed_at (str * { 比较完成时间，ISO 8601；重复运行时据此选最新结果 })

Defect =
  Object
  * $group (ComparisonGroup * { 保留完整输入证据 })
  * $policy (GapPolicy * { 本次准入规则 })
  * $reasons (list[str] * { EFS 各失败轮次及原因，至少一项 })
  * $baseline_valid (bool * { GPFS 各轮准入是否全部通过；false 表示不能归因到 EFS })

ComparisonResult =
  Oneof
  | $compared (Comparison * { 两侧准入通过且证据完整，已完成性能比较 })
  | $defect (Defect * { EFS 任一轮正确性或稳定性实测不达标；不做性能排名，baseline_valid 记录基线是否有效 })
  | $incomplete (list[str] * { 缺证据、仅 GPFS 基线失败或环境不可比等原因；退回重测，不进分类 })

CandidateReview =
  Object
  * $kept (bool * { 人工分类是否保留为有效问题 })
  * $reason (str * { 保留或剔除的原因 })
  * $reviewer (str * { 分类人 })
  * $reviewed_at (str * { 分类时间，ISO 8601 })

ClassifiedComparison =
  Object
  * $comparison (Comparison * { candidate 为 true 的完整比较格 })
  * $review (CandidateReview * { 人工分类结论；kept 为 true 才计为有效对比 })
```

## 指标集

### 应用感知指标

每个负载先采主指标，辅助指标用于解释业务影响。主辅标签不改变候选资格：任一应用感知指标三门全过都触发候选，存储原生指标不能独立触发。kvcache 必须把 `kv_fetch_segment` 从端到端 TTFT 中拆出，不能只报 TTFT。

| 负载 | 主指标 | 辅助指标 |
| --- | --- | --- |
| dataset | `dataset_samples_per_gpu`、`dataset_first_batch_wait` | `dataset_gpu_io_wait`、`dataset_epoch_duration`、`dataset_job_startup` |
| ckpt | `ckpt_save_stall`、`ckpt_load` | `ckpt_save_duration`、`ckpt_write_bandwidth`、`ckpt_failure_recovery` |
| kvcache | `kv_ttft` 的 mean 与 p99、`kv_fetch_segment` | `kv_tpot`、`kv_effective_hit_rate`、`kv_qps` |

计时与聚合边界固定如下：

- `dataset_samples_per_gpu`：有效测量窗内完成的样本数，除以该窗墙钟秒数与 GPU 数。`dataset_first_batch_wait` 从数据加载器启动到各 rank 首个 batch 就绪，取所有 rank 的最大值。
- `ckpt_save_stall`：训练因同步保存而暂停的墙钟时长，从训练停止推进到保存所需状态可见且训练可继续；异步写只计不能与训练重叠的阻塞段。
- `ckpt_load`：从发起 checkpoint load 到所有 rank 的模型与优化器状态反序列化完成；不含故障检测、进程调度与重新建队。
- `ckpt_save_duration`：从保存请求发起到所有 rank 分片提交并可被新进程读取，包含异步写的后台完成段。`ckpt_write_bandwidth` 用同一窗口的实际 checkpoint 字节数除以该时长。
- `ckpt_failure_recovery`：从故障注入到所有 rank 恢复并可继续训练，包含检测、重启与 load。
- `kv_ttft`：从服务收到请求到返回首个输出 token，按请求报 mean 与 P99。`kv_fetch_segment` 从首个 KV 读请求发起到最后一个 KV 块可供计算使用，不含 prefill 计算。
- `kv_effective_hit_rate`：KV 取回路径耗时小于对应重算耗时的命中数，除以全部命中数；没有收益的命中不进入分子。全部命中数为零时该轮记 0，表示没有有效命中收益；后续零分母按指标级不可比规则处理。

### 存储原生指标

存储带宽、IOPS、`storage_io_latency` 与混部读指标必须同时带操作类型、块大小和并发；读写分开。元数据的五种操作分别报 QPS 与延迟，空文件与真实小文件分开，不填块大小与并发。混部干扰按每盘背景写限速 0、256、512 MB/s 三档分别报读带宽与读 P99。原生差距用于归因，不能独立触发候选。

| 组 | 指标 | 固定分档 |
| --- | --- | --- |
| 带宽 | 三种 `storage_*_bandwidth` 的 mean | 4KiB、128KiB、1MiB、64MiB；单流与至少一个 streams>=10 档 |
| IOPS | 两种 `storage_random_*_iops` 的 mean | 4KiB；单流与至少一个 streams>=10 档 |
| 延迟 | `storage_io_latency` | mean、p50、p99、p999；四种操作、四种块大小、两类并发分别报 |
| 元数据 | 五种 `metadata_*_qps` 的 mean 与五种 `metadata_*_latency` 的 mean、p50、p99、p999 | empty 与 real_small |
| 混部干扰 | `interference_read_bandwidth` 的 mean、`interference_read_latency` 的 p99 | 两种读操作、四种块大小、两类并发；0、256、512 MB/s/盘 |

带宽名与操作必须对应：顺序读、随机读、写带宽分别至少覆盖 sequential_read、random_read、sequential_write。IOPS 名分别绑定 random_read 与 random_write。块大小只用 4KiB、128KiB、1MiB、64MiB；并发必须包含 streams=1 和至少一个 streams>=10 的固定档。元数据场景不填块大小与并发。

存储原生微基准固定 `direct=true`、`iodepth=16`、每轮有效采样 120 秒。应用负载也使用相同的两侧采样窗与预热丢弃策略，但不套用 FIO 的块大小和并发分档。

每个比较格必须有所属负载的完整应用指标集，以及下表的原生子集。子集表限定 operation 或 block_size 时，只覆盖这些组合以及上表要求的统计量和并发档；未限定的维度按上表完整覆盖固定分档。额外采集的原生指标也遵守相同分档，不能用单一档位代替已声明矩阵。

| 负载 | 必需原生子集 |
| --- | --- |
| dataset | 两种读带宽；五种元数据 QPS 与延迟，覆盖 readdir |
| ckpt | 写带宽；sequential_write 与 random_write 的 `storage_io_latency`；混部读带宽与读 P99；逐轮恢复正确性 |
| kvcache | 4KiB 随机读 IOPS；4KiB random_read 的 `storage_io_latency`；混部读带宽与读 P99；`kv_fetch_segment` 应用指标 |

指标与统计量的合法组合固定如下，其他组合返回 `incomplete`：

| 指标 | 允许的 Statistic |
| --- | --- |
| `kv_ttft` | mean、p99；两者都必需 |
| `storage_io_latency` | mean、p50、p99、p999；固定矩阵要求四者齐全 |
| 五种 `metadata_*_latency` | mean、p50、p99、p999；固定矩阵要求四者齐全 |
| `interference_read_latency` | p99 |
| 其他全部指标 | mean |

### 正确性与稳定性

每轮分别核两侧 `content_match`。`content_match` 为 false 时该轮该侧准入失败。ckpt 还要求 `checkpoint_recovery` 为 true，并按记录的 MLPerf Storage 版本验证完整训练状态可恢复。错误率、超时率、限流、重试、长压性能衰减或周期抖动越过 `StabilityPolicy` 时该侧准入失败。同轮两侧 `stability_window_s` 必须相同且不小于 `StabilityPolicy.min_window_s`。没有已确认 EFS defect 时，窗口不同或缺任一轮证据返回 `incomplete`；窗口不同不得归因 EFS。

EFS 任一轮实测失败都返回结构化 `defect` 并保留失败原因；GPFS 全通过时 `baseline_valid=true`，GPFS 也有实测失败时为 false。只有 GPFS 失败而 EFS 全通过时返回 `incomplete`。缺陷样本不参与性能排名，权重高于一般性能差距。

## 基本操作

只有一个操作：比较一个完整比较格。先扫描实测缺陷，再核证据完整性与环境可比性，最后做统计判定。

1. 扫描所有已提供轮次的双侧准入证据。EFS 任一轮实测失败就返回 `defect`，不得因 GPFS 同时失败或其他证据缺失而丢弃；`baseline_valid=true` 仅表示 GPFS 所需证据完整且全部通过。没有 EFS 实测失败而仅 GPFS 失败时返回 `incomplete`。
2. 核 `group_id` 只对应同一 payload 与冷热状态，`run_id` 唯一，各序列以 `(metric, statistic, storage_scenario)` 唯一。应用指标的场景为 nil，原生指标各自绑定场景，不要求两类场景相同。
3. 核所属负载的完整应用指标集、必需原生子集、固定分档和合法统计量组合。每个指标至少五轮配对值，轮号连续，首轮由 `order_seed` 随机决定，之后严格 AB/BA 轮换。
4. 核两侧窗口形状、环境控制项、原始产物与缓存处理。每侧实际起止时间之差必须等于 `shape.duration_s`，原生微基准必须为 120 秒；两侧有效窗不得重叠，实际先后顺序必须与 `first` 一致。文件系统实现、版本与必需挂载差异必须留档，其他控制项不一致则退回重测。同轮两侧长压窗时长必须相同且达到 `min_window_s`，实际起止时间之差必须等于该时长，并分别覆盖本轮对应侧有效测量窗。
5. 每条序列必须有 EFS、GPFS 各一条噪声基线。核 payload、指标、统计量、冷热、场景、对应侧环境与窗口形状完全一致。原始测量至少覆盖两个日期且每日至少两次，同一基线的测量窗不得重叠，每次起止时间之差等于窗口时长，缓存处理证据符合冷热状态，最晚测量早于对应侧首轮正式测量。同日按 `started_at` 排序后的相邻值计算轮间差；先取每日中位数，再按日期排序后的相邻测量日计算日间差。相对差固定为 `abs(后值 - 前值) / abs(前值)`，前值为零时该基线无效并返回 `incomplete`。两个差值列表必须可由 `measurements` 逐项复算，`band` 等于两个列表全部元素绝对值的最大值。
6. 混部序列的正式轮次与噪声原始测量都必须有对应侧 `InterferenceRecord`。正式轮次两侧配置目标相同并等于场景档位，盘数一致，背景写起止时间完整覆盖对应侧有效测量窗；噪声记录遵守相同目标、速率与时间覆盖规则，盘数与对应侧正式轮次一致。目标为 0 时实测必须为 0；非零档的实测值与目标绝对差不得超过 `interference_tolerance_mb_s_per_disk`。非混部序列的 interference 必须为 nil。缺任一项返回 `incomplete`。
7. 两侧分别报中位数与 MAD。逐轮把原始差值统一到“正值表示 EFS 更差”的方向，按配对索引做 percentile bootstrap，对差值中位数给出 95% 置信区间，不假设正态分布。生成器固定为 `numpy.random.Generator(numpy.random.PCG64(seed))`；每次用 `integers(0, n, size=n)` 抽取配对索引，双侧共用同一索引。对 bootstrap 中位数序列用 `numpy.percentile(..., [2.5, 97.5], method="linear")` 取区间。重抽样次数与种子来自 `GapPolicy`。
8. 越高越差的指标，`relative_gap = (EFS 中位数 - GPFS 中位数) / abs(GPFS 中位数)`；越低越差的指标反向计算。GPFS 中位数为零时仍保留原始值、中位数、MAD 与配对 CI，但 `relative_gap` 和 `gates` 为 nil，`material_diff=false`，并填写 `uncomparable_reason`。该项不否决整组，其他有效应用指标仍可触发候选。
9. 元数据 QPS 先用元数据阈值；P99 与 P999 再用尾延迟阈值；其余组合用均值类阈值。每个指标的三道门槛取合取得到 `material_diff`。至少一个应用感知指标 `material_diff=true` 就把比较格置为 `candidate=true`；原生指标不能独立触发，同组多个命中不拆成多个候选。
10. 候选比较格交人工分类。报告窗为 `[start, end)`。同一 `policy.version` 下按 `group_id` 去重：先取 `completed_at < end` 的最新 `compared` 运行；最新运行 `candidate=false` 时该组不计。否则取该 `run_id` 下 `reviewed_at < end` 的最新复核，仅当该复核落在 `[start, end)` 且 `kept=true` 时计入分子。单位时间有效对比数 = 计入的 `group_id` 数 / 报告窗墙钟小时。晚到复核计入实际复核窗口，窗口后的新运行或复核不改写历史窗口；历史记录保留。

源文档未指定离散度、置信区间算法、相对差分母与噪声带算法，本契约分别固定为 MAD、配对中位数的 PCG64 percentile bootstrap 与 linear 分位数、GPFS 中位数绝对值，以及同日相邻轮差、相邻测量日的日中位数差和两类差值绝对值的最大值。全部命中为零时有效命中率记 0，以及复核按 `reviewed_at` 所属窗口计分，也是本契约的补充口径。稳定性数值阈值与背景写速率容差由版本化 `GapPolicy` 提供，不填伪造默认值。

首版 `GapPolicy.version` 为 `diff-minner-v1`，三道实际意义阈值分别为 0.10、0.20、0.15，bootstrap 为 10000 次。跑满一周后可按候选池与人工分类分布调阈值；调阈值必须换版本并填写 `calibration_evidence_uri`，保留旧版本原始运行与历史判定。

## apis.viba

```bash apis
import aisp.bench.diff_minner.types as diff

CompareGroup =
     diff.ComparisonResult
  <- $group (diff.ComparisonGroup * { 同一份 payload 的完整比较格，含应用指标、必需原生子集、至少五轮配对值与逐轮双侧准入证据 })
  <- $policy (diff.GapPolicy * { 实际意义阈值、稳定性阈值、背景写容差与 bootstrap 参数 })
  <- {
    EFS 任一轮实测失败返回 defect，并记录 baseline_valid；否则先核证据完整性、环境一致性与双侧准入，仅 GPFS 失败或证据不完整返回 incomplete。逐指标计算中位数、MAD、方向化配对差值中位数的非参数 bootstrap 95% 置信区间、有害方向相对差与三道门槛；零分母只把该项标为不可比，至少一个应用感知指标三门全过才返回 candidate=true 的 compared
  }
```
