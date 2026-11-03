# checkpoint 样本接口

一份 RunSpec 进，一条 RunRecord 出。一次运行 = 一条样本 × 一个存储版本。

## public

只做转发：从 ckpt_sample 与 ckpt_sample_api 里 import，再把要发布的名字重新绑定一次。具体定义在下面两节里。

```viba public
import ckpt_sample
import ckpt_sample_api

Start = ckpt_sample_api.Start
Stop = ckpt_sample_api.Stop
Query = ckpt_sample_api.Query
Execute = ckpt_sample_api.Execute
GetLevel = ckpt_sample_api.GetLevel
RunSpec = ckpt_sample.RunSpec
RunRecord = ckpt_sample.RunRecord
Artifacts = ckpt_sample.Artifacts
CkptSli = ckpt_sample.CkptSli
CkptSlo = ckpt_sample.CkptSlo
SampleConfigBase = ckpt_sample.SampleConfigBase
```

## ckpt_sample_api

```viba ckpt_sample_api
import ckpt_sample
import levels

Start =
     ckpt_sample.RunRecord
  <- $spec (ckpt_sample.RunSpec * { 这次评估的运行请求 })
  <- { 提交接口：请求交出去就返回，不等样本跑完。校验请求，按配置起一个样本进程，把运行标识与当前状态交回来；此时状态可能仍在排队或执行中，产物位置可能还缺 }

Stop =
     ckpt_sample.RunRecord
  <- $run_id (str * { 要停的那次运行 })
  <- { 取消接口：让服务停下这次运行，已经写完的产物保留。返回的记录状态为 cancelled；已经结束的运行原样交回，不报错 }

Query =
     ckpt_sample.RunRecord
  <- $run_id (str * { 要查的那次运行 })
  <- { 查一次运行：答当前状态、进度与产物位置。只读，不改变运行；完成与否只看状态，不看进度 }

Execute =
     ckpt_sample.Artifacts
  <- $spec (ckpt_sample.RunSpec * { 同一份运行请求 })
  <- { 执行接口：同一份请求同步跑到结束，返回时四份产物已经写完。它由 Start 在后台触发；Start 只拿到标识与状态，拿不到产物本身 }

GetLevel =
     levels.Level
  <- $config (ckpt_sample.SampleConfigBase * { 样本配置 })
  <- { 导出属性：按节点数与每节点卡数落到 S0 到 S5 的哪一级，阈值由配方的 scaling 阶梯给 }
```

## ckpt_sample

```viba ckpt_sample
import observation

RunRecord =
  Object
  * $run_id (str * { 服务分配的运行标识，查状态、取产物都用它 })
  * $state (State * { 这次运行现在在哪一步 })
  * $progress (WorkProgress * { 已完成的工作量占总量的多少，单位由配置定 })
  * $artifacts (Artifacts * { 产物的位置；没跑完时相应字段缺 })

RunSpec =
  Object
  * $sample (str * { 跑哪个样本程序，写 name@version })
  * $config (str * { 样本 repo 里那份配置的名字；那份配置必须含 SampleConfigBase 的字段 })
  * $storage (StorageLayer * { 这次要评的存储两层 })
  * $seed (int * { 随机种子，决定同一请求重跑的一致性 })

StorageLayer =
  Object
  * $backend (Component * { 纯存储系统，例如 GPFS、Ceph })
  * $adapter (Component * { 存储传输适配层，例如 torchstore })

Component =
  Object
  * $name (str * { 组件名 })
  * $version (str * { 组件版本 })
  * $git_commit_id ((str | nil) * { 组件源码的 commit；只发版本不发源码时给 nil })

State =
  Oneof
  | $queued (QueueProgress * { 排队中，还没开始跑 })
  | $running (nil * { 正在执行 })
  | $completed (nil * { 正常结束 })
  | $failed (Failure * { 执行失败，带分类与说明 })
  | $rejected (Failure * { 请求不合法，没进队列 })
  | $cancelled (nil * { 被取消 })

QueueProgress =
  Object
  * $pos (int * { 在队列里排第几位 })
  * $len (int * { 队列里一共几个 })

WorkProgress =
  Object
  * $done (int * { 已完成的工作量 })
  * $total (int * { 总工作量；还没算出来时是 0 })

Artifacts =
  Object
  * $manifest (str * { 运行清单：输入、版本、拓扑、观测配置，服务写 })
  * $metrics (list[CkptSli] * { 这次运行的 SLI：每项一条，没有阈值 })
  * $slo (list[CkptSlo] * { 每个 SLI 指标的判定，阈值由部署方给 })
  * $report (str * { 人读报告的位置 })

CkptSlo =
  Oneof
  | $check_point_duration_slo (MetricLE[CheckPointDurationMetric] * { 写入时长不超过部署方给的阈值 })
  | $training_stall_slo (MetricLE[TrainingStallMetric] * { 训练停顿不超过部署方给的阈值 })
  | $restore_duration_slo (MetricLE[RestoreDurationMetric] * { 恢复时长不超过部署方给的阈值 })
  | $write_throughput_slo (MetricGE[WriteThroughputMetric] * { 写入吞吐不低于部署方给的阈值 })
  | $metadata_commit_slo (MetricLE[MetadataCommitMetric] * { 元数据提交时长不超过部署方给的阈值 })
  | $write_latency_p99_slo (MetricLE[WriteLatencyP99Metric] * { 写请求 P99 不超过部署方给的阈值 })

CkptSli =
  Oneof
  | $check_point_duration_sli (CheckPointDurationMetric * { 一次 checkpoint 从开始写到元数据可见的时长，秒 })
  | $training_stall_sli (TrainingStallMetric * { 训练被写入阻塞的时长；异步写入扣掉与计算重叠的部分，秒 })
  | $restore_duration_sli (RestoreDurationMetric * { 从 checkpoint 恢复到可以继续训练的时长，秒 })
  | $write_throughput_sli (WriteThroughputMetric * { 写入期间按 rank 聚合的吞吐，字节每秒 })
  | $metadata_commit_sli (MetadataCommitMetric * { 分片元数据提交到可见的时长，毫秒 })
  | $write_latency_p99_sli (WriteLatencyP99Metric * { 单个写请求的 P99，毫秒 })

MetricLE[Value] =
  Object
  * $actual Value
  * $threshold Value

MetricGE[Value] =
  Object
  * $actual Value
  * $threshold Value

CheckPointDurationMetric = float * { 一次 checkpoint 从开始写到元数据可见的时长，秒 }

TrainingStallMetric = float * { 训练被写入阻塞的时长；异步写入扣掉与计算重叠的部分，秒 }

RestoreDurationMetric = float * { 从 checkpoint 恢复到可以继续训练的时长，秒 }

WriteThroughputMetric = float * { 写入期间按 rank 聚合的吞吐，字节每秒 }

MetadataCommitMetric = float * { 分片元数据提交到可见的时长，毫秒 }

WriteLatencyP99Metric = float * { 单个写请求的 P99，毫秒 }

Failure =
  Object
  * $kind (str * { 失败分类：environment、dependency、timeout、observation、assertion 等 })
  * $detail (str * { 具体说明 })
SampleConfigBase =
  Object
  * $model (Model * { 被评估的模型 })
  * $topology (Topology * { 节点、卡、网络、挂载 })
  * $observe (ObservationConfig * { 观测设置 })

Model =
  Object
  * $id (str * { 模型标识，例如 HuggingFace 的 repo id })
  * $git_commit_id (str * { 代码 commit，钉死到具体一份代码 })

Topology =
  Object
  * $nodes (int * { 节点数 })
  * $gpus_per_node (int * { 每节点卡数 })
  * $network (str * { 网络类型：rdma、tcp、none })
  * $mount (str * { 存储挂载方式：local-nvme、nfs、fuse })

ObservationConfig =
  Object
  * $enabled (bool * { 是否开观测 })
  * $sample_rate (float * { 采样率，0 到 1 })
  * $layers (list[observation.ObservationLayer] * { 采集层；至少两层，其中必须含 sys })

```

## json schema

接口里的每个类型各有一份 JSON Schema，放在 [`json_schema/`](json_schema/) 下，文件名是类型名加 `.schema.json`。函数没有对应的 JSON 值，不生成文件。

这些文件由 `scripts/export_json_schema.py` 从文档里的 viba 代码块生成，不要手改。
