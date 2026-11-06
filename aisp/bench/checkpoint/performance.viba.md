# 存储表现：SLI 与 SLO

## 需求背景

一次运行测出来的指标叫 SLI，按阈值判定叫 SLO。判定要有统一口径：一次运行只测三项指标，每项从哪个时刻算到哪个时刻、用哪个统计量、怎么和部署方给的阈值比较。运行记录、判定操作与读文档的人都按这一份走，所以 `CkptSli`、`CkptSlo` 与判定操作从这里发布。含义说不清的指标不进这份清单。

## public.viba

```bash public
import aisp.bench.checkpoint.performance.types as performance
import aisp.bench.checkpoint.performance.slo as slo
import aisp.bench.checkpoint.performance.apis as performance_api

CkptSli = performance.CkptSli
CheckPointDurationMetric = performance.CheckPointDurationMetric
RestoreDurationMetric = performance.RestoreDurationMetric
WriteLatencyP99Metric = performance.WriteLatencyP99Metric
CkptSlo = slo.CkptSlo
CkptSloPolicy = slo.CkptSloPolicy
Judge = performance_api.Judge
JudgePolicy = performance_api.JudgePolicy
```

## types.viba

一条运行量出来的指标，每项一个具名类型，`CkptSli` 把它们收成一个取值一个的枚举。三项分别覆盖写入路径、读取路径与请求尾延迟；写入总字节与写入时长能算出的量不再单列。

```bash types
CkptSli =
  Oneof
  | $check_point_duration_sli (CheckPointDurationMetric * { 一次 checkpoint 的写入时长，秒 })
  | $restore_duration_sli (RestoreDurationMetric * { 一次恢复的时长，秒 })
  | $write_latency_p99_sli (WriteLatencyP99Metric * { 数据写请求的尾延迟 P99，毫秒 })

CheckPointDurationMetric = float * { 墙钟写入时长，秒：从 rank 0 发出第一条数据写请求起，到最后一个 rank 的元数据提交被一个新进程读到时止；不含预热段，不含两次 checkpoint 之间的训练时间 }

RestoreDurationMetric = float * { 墙钟恢复时长，秒：从 rank 0 发出第一条读请求起，到所有 rank 都报告参数与优化器状态就绪、可以继续训练时止；读前必须丢掉页缓存与客户端缓存，否则测到的是内存带宽 }

WriteLatencyP99Metric = float * { 数据写请求的应用层时延 P99，毫秒：单个请求从应用层提交到收到完成回调；只统计数据写请求，不统计元数据请求；全部 rank 的请求合并后取 P99 }
```

## slo.viba

阈值判定，`MetricLE` 是对照方式，`CkptSlo` 把三项指标各收一个取值；`CkptSloPolicy` 是部署方给出的三项阈值，没给的项判不了。

```bash slo
import aisp.bench.checkpoint.performance.types as sli

CkptSlo =
  Oneof
  | $check_point_duration_slo (MetricLE[sli.CheckPointDurationMetric] * { 写入时长不超过部署方给的阈值 })
  | $restore_duration_slo (MetricLE[sli.RestoreDurationMetric] * { 恢复时长不超过部署方给的阈值 })
  | $write_latency_p99_slo (MetricLE[sli.WriteLatencyP99Metric] * { 写请求 P99 不超过部署方给的阈值 })

MetricLE[Value] =
  Object
  * $actual Value
  * $threshold Value
  * $passed (bool * { actual 不超过 threshold 时为 true })

CkptSloPolicy =
  Object
  * $check_point_duration_s ((float | nil) * { 写入时长阈值，秒；没给就判不了这一项 })
  * $restore_duration_s ((float | nil) * { 恢复时长阈值，秒；没给就判不了这一项 })
  * $write_latency_p99_ms ((float | nil) * { 写请求 P99 阈值，毫秒；没给就判不了这一项 })
```

## 基本操作

两个操作。`Judge` 是原动作：`$policy` 仍是字符串，按部署方给的阈值表名字判。`JudgePolicy` 是新增动作：直接接 `CkptSloPolicy`，三项阈值逐项给。两者都只有通过运行校验的运行才进。

## apis.viba

```bash apis
import aisp.bench.checkpoint.performance.types as sli
import aisp.bench.checkpoint.performance.slo as slo

Judge =
     list[slo.CkptSlo]
  <- $sli (list[sli.CkptSli] * { 这次测得的指标 })
  <- $policy (str * { 部署方给的阈值；每个指标一个，缺哪个就判不了哪个 })
  <- {
    逐指标填进对应的 CkptSlo，与阈值比较：落在阈值内 passed 为 true，否则为 false；阈值缺失的指标不进返回列表，读作不可比
  }

JudgePolicy =
     list[slo.CkptSlo]
  <- $sli (list[sli.CkptSli] * { 这次测得的指标 })
  <- $policy (slo.CkptSloPolicy * { 部署方给的阈值；某个指标没给阈值，这一项就不进返回列表，读作不可比 })
  <- {
    逐指标填进对应的 CkptSlo，与阈值比较：落在阈值内 passed 为 true，否则为 false；阈值缺失的指标不进返回列表，读作不可比
  }
```
