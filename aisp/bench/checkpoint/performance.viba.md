# 存储表现：SLI 与 SLO

## 背景

一次运行测出来的指标叫 SLI，按阈值判定叫 SLO；这里定义这两类记录，样本接口用这一份。

## types.viba

一条运行量出来的指标，每个指标一个具名类型，`CkptSli` 把它们收成一个取值一个的枚举。

```bash types
CkptSli =
  Oneof
  | $check_point_duration_sli (CheckPointDurationMetric * { 一次 checkpoint 从开始写到元数据可见的时长，秒 })
  | $training_stall_sli (TrainingStallMetric * { 训练被写入阻塞的时长；异步写入扣掉与计算重叠的部分，秒 })
  | $restore_duration_sli (RestoreDurationMetric * { 从 checkpoint 恢复到可以继续训练的时长，秒 })
  | $write_throughput_sli (WriteThroughputMetric * { 写入期间按 rank 聚合的吞吐，字节每秒 })
  | $metadata_commit_sli (MetadataCommitMetric * { 分片元数据提交到可见的时长，毫秒 })
  | $write_latency_p99_sli (WriteLatencyP99Metric * { 单个写请求的 P99，毫秒 })

CheckPointDurationMetric = float * { 一次 checkpoint 从开始写到元数据可见的时长，秒 }

TrainingStallMetric = float * { 训练被写入阻塞的时长；异步写入扣掉与计算重叠的部分，秒 }

RestoreDurationMetric = float * { 从 checkpoint 恢复到可以继续训练的时长，秒 }

WriteThroughputMetric = float * { 写入期间按 rank 聚合的吞吐，字节每秒 }

MetadataCommitMetric = float * { 分片元数据提交到可见的时长，毫秒 }

WriteLatencyP99Metric = float * { 单个写请求的 P99，毫秒 }

```

## slo.viba

阈值判定，`MetricLE` / `MetricGE` 是对照方式，`CkptSlo` 把六个指标各收一个取值。

```bash slo
import aisp.bench.checkpoint.performance.types as sli

CkptSlo =
  Oneof
  | $check_point_duration_slo (MetricLE[sli.CheckPointDurationMetric] * { 写入时长不超过部署方给的阈值 })
  | $training_stall_slo (MetricLE[sli.TrainingStallMetric] * { 训练停顿不超过部署方给的阈值 })
  | $restore_duration_slo (MetricLE[sli.RestoreDurationMetric] * { 恢复时长不超过部署方给的阈值 })
  | $write_throughput_slo (MetricGE[sli.WriteThroughputMetric] * { 写入吞吐不低于部署方给的阈值 })
  | $metadata_commit_slo (MetricLE[sli.MetadataCommitMetric] * { 元数据提交时长不超过部署方给的阈值 })
  | $write_latency_p99_slo (MetricLE[sli.WriteLatencyP99Metric] * { 写请求 P99 不超过部署方给的阈值 })

MetricLE[Value] =
  Object
  * $actual Value
  * $threshold Value

MetricGE[Value] =
  Object
  * $actual Value
  * $threshold Value
```

## 基本操作

1. 测量：一次运行跑完，从它记下的观测里算出六个指标，每项一条 `CkptSli`。
2. 判定：把每条指标的取值填进对应的 `CkptSlo`，与部署方给的阈值比较，答通过、失败或不可比。

## apis.viba

```bash apis
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample
import aisp.bench.checkpoint.performance.types as sli
import aisp.bench.checkpoint.performance.slo as slo

Measure =
     list[sli.CkptSli]
  <- $run (ckpt_sample.RunRecord * { 一次已经跑完、观测已开的运行 })
  <- {
    从这次运行记下的观测里算出六个指标：写入时长、训练停顿、恢复时长、写入吞吐、元数据提交、写请求 P99；返回每项一条，没有阈值
  }

Judge =
     list[slo.CkptSlo]
  <- $sli (list[sli.CkptSli] * { 这次测得的指标 })
  <- $policy (str * { 部署方给的阈值；每个指标一个，缺哪个就判不了哪个 })
  <- {
    逐指标填进对应的 CkptSlo，与阈值比较：落在阈值内答通过，否则答失败；阈值缺失时答不可比
  }
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
