# 存储表现：SLI、SLO 与存储版本对比

## 背景

同一份负载换一个存储版本之后，要能说清差多少、往哪个方向差，并且把差异归到 backend 还是 adapter 这一层。重保子集（评估集里选定要达标的那部分负载）还要能说清是否达标，阈值由使用方在部署评估集时给出。这份文档定义存储版本比较与重保判定各自需要的记录、窗口、阈值与判定结果，以及跨存储版本比较时使用的噪声带。

## 问题

```viba performance
import levels
import types

PerformanceSampleKey = str * { 负载身份：hash(recipe, model id + commit, framework, load, topology, level)；同一份负载换存储版本时它不变 }

PerformanceSliUri = str * { 一份 sli.json 的位置：sli/<sample_key>/<storage_id>/<run-id>.json }

PerformanceStorageId = str * { 存储版本身份：backend.name@version+config_hash / adapter.name@version+config_hash；换存储版本时它变，同一份负载的 sample_key 不变 }

PerformanceStorageLayer =
  Object
  * $component (types.Component * { 这一层组件的名字、版本与源码 commit；环境变量只传名字，不传版本 })
  * $config_ref (str * { 这一层组件配置的引用；name、version、config_ref 一起写进运行清单，配置哈希由这份配置算出 })

PerformanceStorageVersion =
  Object
  * $backend (PerformanceStorageLayer * { 纯存储系统这一层：GPFS、HDFS、Alluxio、Ceph、JuiceFS；服务在样本进程里注入 AI_INFRA_STORAGE_BACKEND，值是组件名，样本必须读取它，未设置直接报错退出，不允许默认值 })
  * $adapter (PerformanceStorageLayer * { AI Infra 存储传输适配层这一层：mooncake、torchstore、bytecheckpoint；服务注入 AI_INFRA_STORAGE_ADAPTER；每个样本必须同时声明 backend 与 adapter 两者，运行请求的 storage.backend 与 storage.adapter 都要填 })

PerformanceWorkload =
  Oneof
  | "checkpoint" * { 目前只有这一类负载能跑 }
  | "dataset" * { 待做，还没有实现 }
  | "kvcache" * { 待做，还没有实现 }

PerformanceWarmup =
  Oneof
  | $fraction (float * { 按比例丢弃，例如前 10%，比例写进配方 })
  | $rounds (int * { 按轮数丢弃，例如前 N 轮，轮数写进配方 })

PerformanceWindow =
  Object
  * $warmup (PerformanceWarmup * { 预热丢掉的规则 })
  * $steady_start (str * { 稳态窗口起点，时间戳；起点与终点按应用层的打点算 })
  * $steady_end (str * { 稳态窗口终点，时间戳 })
  * $cv (float * { 窗口内吞吐变异系数；大于 10% 判不稳 })

PerformanceAttributionKind =
  Oneof
  | "throughput" * { 吞吐：写入或读取期间的字节速率 }
  | "iops" * { IOPS：每秒 IO 操作数 }
  | "latency_percentile" * { 延迟分位；P99 至少 10⁴ 次请求、P999 至少 10⁵ 次，样本不足时只报区间 }
  | "queue_depth" * { 排队深度：设备或客户端队列里积压的请求数 }
  | "saturation" * { 饱和度：资源离上限还有多远 }
  | "rank_fairness" * { rank 间公平性：各 rank 分到的份额是否相当 }
  | "error_and_retry" * { 错误与重试：失败请求与重试的次数 }
  | "metadata_op_rate" * { 元数据 op rate：每秒元数据操作数 }
  | "window_stability" * { 窗口稳定性：窗口内的指标是否平稳 }
  | "ceiling_efficiency" * { 相对上限的效率：实测值达到上限的多少 }

PerformanceAttribution =
  Object
  * $kind (PerformanceAttributionKind * { 哪一种底层 SLI })
  * $value (float * { 这项底层 SLI 的测量值 })

PerformanceEvidence =
  Object
  * $manifest (str * { 运行清单的位置：输入、版本、拓扑、观测配置 })
  * $io_pattern (str * { IO pattern 记录的位置 })
  * $raw_data (str * { 原始数据的位置 })
  * $sha256 (str * { 原始数据的校验和 })

PerformanceSliRecord =
  Object
  * $sample_key (PerformanceSampleKey * { 负载身份，跨存储版本稳定 })
  * $run_id (str * { 运行标识；留存时写入 PerformanceSliUri 对应的路径，全部保留、不覆盖 })
  * $workload (PerformanceWorkload * { 跑的哪类负载 })
  * $storage (PerformanceStorageVersion * { backend 与 adapter 两层的 name、version、config_ref；storage_id 由这两层拼成 })
  * $window (PerformanceWindow * { 预热、稳态起止、变异系数 })
  * $metrics (list[types.CkptSli] * { 每个样本每次运行都测的 SLI 值，每项一条，没有阈值；SLI 覆盖全部样本 })
  * $attribution (list[PerformanceAttribution] * { 底层 SLI，解释 metrics 里的值为什么是这个值；不参与 SLO 判定，也不单独作为结论 })
  * $evidence (PerformanceEvidence * { manifest、io-pattern、原始数据位置与 sha256；报告只引用，不入库 })

PerformanceNoiseBand =
  Object
  * $k (float * { 倍数 k：带宽度等于 k 乘以重复运行的变异系数 })
  * $cv (float * { 同一存储版本重复运行算出的变异系数 })
  * $repeats (int * { 重复运行次数；同一配置至少 3 次，报告 min / median / max，极差大于 10% 判不可比 })
  * $calibration_ref (str * { 标定记录的位置；k 与次数写在这里，噪声带不是固定百分比 })

PerformanceComparisonVerdict =
  Oneof
  | "提升" * { 差值落在噪声带外，改动后更好 }
  | "退化" * { 差值落在噪声带外，改动后更差 }
  | "不可比" * { 差值落在噪声带内，或者任一侧运行不稳 }

PerformanceMetricDelta =
  Object
  * $before (types.CkptSli * { 改动前那一次的这项 SLI })
  * $after (types.CkptSli * { 改动后那一次的同一项 SLI })
  * $absolute (float * { 绝对差，按指标自己的单位 })
  * $relative (float * { 相对差 })
  * $noise_band (PerformanceNoiseBand * { 这一项指标自己的噪声带；差值落在带内就判不可比 })
  * $verdict (PerformanceComparisonVerdict * { 这一项指标的结论；比较报告只说哪边好、差多少，不做通过或不通过 })

PerformanceLayer =
  Oneof
  | "backend" * { 纯存储系统这一层；storage.backend 变了就归这一层 }
  | "adapter" * { AI Infra 存储传输适配层这一层；storage.adapter 变了就归这一层 }

PerformanceStorageComparison =
  Object
  * $sample_key (PerformanceSampleKey * { 两次运行必须是同一个负载身份，才谈得上比 })
  * $before (PerformanceStorageId * { 改动前的存储版本，对应一份 sli.json })
  * $after (PerformanceStorageId * { 改动后的存储版本，对应另一份 sli.json；与 before 的 storage_id 不同 })
  * $deltas (list[PerformanceMetricDelta] * { 逐指标算出的绝对差与相对差 })
  * $changed_layers (list[PerformanceLayer] * { 哪几层变了：只允许一层不同，或者两层都不同但结论按层分别归因；两层一起变却只报一个总账，等于没测 })

PerformanceThresholdProvenanceKind =
  Oneof
  | "requirement" * { 需求文档 }
  | "baseline" * { 基线测量 }
  | "ceiling" * { 上限与效率目标 }

PerformanceThresholdProvenance =
  Object
  * $kind (PerformanceThresholdProvenanceKind * { 阈值来源属于哪一种；只能是需求文档、基线测量、上限与效率目标三者之一 })
  * $ref (str * { 来源的编号，例如需求编号 })
  * $date (str * { 来源的日期，例如 2026-10-30 })

PerformanceThresholdScope =
  Object
  * $backend (list[str] * { 对哪些 backend 组件名成立，例如 gpfs })
  * $adapter (list[str] * { 对哪些 adapter 组件名成立，例如 torchstore })
  * $topology (list[levels.Level] * { 对哪些规模档位成立，例如 S0 到 S2 })

PerformanceComparator =
  Oneof
  | "<=" * { 不超过阈值 }
  | ">=" * { 不低于阈值 }

PerformanceSloThreshold =
  Object
  * $version (str * { 阈值版本；阈值带版本，改动走评审，判定结果引用这个版本 })
  * $metric (str * { 判哪个指标，例如 ttft_p99_ms })
  * $comparator (PerformanceComparator * { 往哪个方向比 })
  * $target (float * { 阈值；部署方填写，仓库不提供数字 })
  * $unit (str * { 阈值单位，例如 ms })
  * $provenance (PerformanceThresholdProvenance * { 阈值从哪来；没有来源的阈值不允许用于判定 })
  * $valid_for (PerformanceThresholdScope * { 阈值在哪些存储与规模档上成立；超出这个范围判不可比 })
  * $review_due (str * { 复审日期，例如 2027-01-30；过期判不可比 })

PerformanceSloVerdict =
  Oneof
  | "pass" * { 达标：实测值满足 comparator 与 target，且置信区间没有跨过阈值 }
  | "fail" * { 不达标：实测值不满足 comparator 与 target，且置信区间没有跨过阈值 }
  | "inconclusive" * { 不可比：置信区间跨过阈值，或者阈值过期、超出 valid_for 范围、存储版本变更未重标 }

PerformanceSloResult =
  Object
  * $sample_key (PerformanceSampleKey * { 被选择器选中的样本 })
  * $slo_ref (str * { 所用的阈值版本与条目；判定结果写进 slo-result.json })
  * $metric (str * { 判定的指标 })
  * $target (float * { 阈值 })
  * $observed (float * { 实测的 SLI 值 })
  * $verdict (PerformanceSloVerdict * { 判定结果 })
  * $sli_uri (PerformanceSliUri * { 对应 sli.json 的回链 })
```

## 基本操作

解决这个问题需要四个操作。测一次 SLI：在这份负载与这个存储版本上跑一次，丢弃预热、在稳态窗口内测量，得到各项 SLI 值、底层归因与证据，写成一条记录。留存：把这条记录写到按负载与存储版本分出的位置，全部保留、不覆盖。比较两个版本：取同一份负载、两个不同存储版本的两条记录，逐指标算绝对差与相对差，对照噪声带得出结论，并指出哪几层变了。按阈值判定：只对重保子集里被选中的样本，用 SLI 值对照部署方给的阈值，得出达标、不达标或不可比。

## 接口

```viba performance_api
import performance

Measure =
     performance.PerformanceSliRecord
  <- $sample_key (performance.PerformanceSampleKey * { 要测的那份负载的身份；同一份负载换存储版本时它不变 })
  <- $storage (performance.PerformanceStorageVersion * { 这次要测的存储版本：backend 与 adapter 两层都要声明 })
  <- { 测一次 SLI：在这份负载与这个存储版本上跑一次，丢弃预热，在至少 60 秒或固定字节数的稳态窗口内测量；同一后端同一时刻只跑一个高带宽样本，开关观测各跑一次且关键指标变化不超过 3%。返回一条 SLI 记录，里面是各项 SLI 值、底层归因与证据，没有阈值 }

Retain =
     performance.PerformanceSliUri
  <- $record (performance.PerformanceSliRecord * { 要留存的那条 SLI 记录 })
  <- { 留存：把记录写成一份 sli.json，全部保留、不覆盖，保留期至少覆盖比较窗口，默认一年；只留最新一份就无法回答换后端前后差多少。返回写入的位置 }

Compare =
     performance.PerformanceStorageComparison
  <- $before (performance.PerformanceSliRecord * { 改动前那一次的 SLI 记录 })
  <- $after (performance.PerformanceSliRecord * { 改动后那一次的 SLI 记录；与 before 必须是同一个 sample_key、不同的 storage_id })
  <- $calibration (str * { 噪声带标定记录的位置；同一存储版本重复运行导出的 k 与次数写在这里 })
  <- { 比较两个存储版本：逐指标算绝对差与相对差，与噪声带比较，结论三选一（提升、退化、不可比），并指出哪几层变了。只回答哪边好、差多少，不做通过或不通过 }

Judge =
     performance.PerformanceSloResult
  <- $record (performance.PerformanceSliRecord * { 被选择器选中的那次运行的 SLI 记录 })
  <- $threshold (performance.PerformanceSloThreshold * { 部署方给的阈值条目：方向、目标值、来源、适用范围、复审日期 })
  <- { 按阈值判定：判定只走 SLO，用 SLI 值对照阈值，置信区间跨过阈值判不可比；阈值过期、超出 valid_for 范围、存储版本变更未重标一律判不可比。返回一条 slo-result，引用所用的阈值版本与 SLI 回链 }
```

## 组织

```viba performance_flow
import performance
import performance_api

PerformanceSampleDuty =
  Object
  * $measure (performance_api.Measure * { 测一次 SLI：拿到一条 performance.PerformanceSliRecord })
  * $retain (performance_api.Retain * { 留存：把这条记录写成一份 sli.json，全部保留、不覆盖 })

PerformanceVersionDuty =
  Object
  * $before (performance_api.Measure * { 改动前那一次运行 })
  * $after (performance_api.Measure * { 改动后那一次运行；与 before 是同一个 sample_key })
  * $compare (performance_api.Compare * { 比较两个存储版本：拿到 performance.PerformanceStorageComparison })

PerformanceSubsetDuty =
  Object
  * $measure (performance_api.Measure * { 判定前先测出被选中样本的 SLI })
  * $judge (performance_api.Judge * { 按阈值判定：拿到 performance.PerformanceSloResult })

PerformanceDuty =
  Oneof
  | $every_sample (PerformanceSampleDuty * { 每个样本每次运行都做：测 SLI、留存；SLI 覆盖全部样本 })
  | $two_versions (PerformanceVersionDuty * { 换存储版本时做：同一份负载的两个版本各测一次，再比较；报告只说哪边好、差多少 })
  | $protected_subset (PerformanceSubsetDuty * { 重保子集：只有选择器选中的样本判定，其余样本只产 SLI })
```

IO pattern 的度量项定义在 [`methodology.md`](methodology.md)，本篇消费它的输出；放大到多级规模时的不变量与外推规则由 [`scaling.md`](scaling.md) 处理。判定阈值属于部署配置，不在本项目；选择器写在部署的 `slo.yaml` 里，配方本身不存阈值。评估集自身是否可信（对齐、覆盖、scaling 一致性）由 `metrics/` 定义。

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
