# checkpoint bench

## public

先看 `Bench`、`Sample`、`Run` 三个类型，再看 `Execute`、`Judge`、`Compare` 三个操作。

```viba ckpt_bench_public
import ckpt_bench
import ckpt_bench_api

Bench = ckpt_bench.Bench
Sample = ckpt_bench.Sample
Run = ckpt_bench.Run
Execute = ckpt_bench_api.Execute
Judge = ckpt_bench_api.Judge
Compare = ckpt_bench_api.Compare
```

## 背景

在一批真实的模型代码上，量 checkpoint 写入与读取对存储的要求，并把结论从单机外推到十万卡。

## ckpt_bench

bench 由一个语料、一批样本、几套存储与它们跑出来的运行组成；一条样本是一条用例，一次运行 = 一条样本 × 一个存储版本。

```viba ckpt_bench
import ckpt_sample
import io_pattern
import performance

Bench =
  Object
  * $corpus (list[ckpt_sample.Model] * { 真实模型代码，从平台上收，按 id + commit 钉死 })
  * $samples (list[Sample] * { 从语料里挑出的用例：模型代码 + 并行配置 + 负载 })
  * $storages (list[ckpt_sample.StorageLayer] * { 被评的存储两层 })
  * $runs (list[Run] * { 每条样本在每个存储版本上跑一次 })
  * $gaps (list[Gap] * { 没覆盖到、需要补的地方 })

Sample =
  Object
  * $model (ckpt_sample.Model * { 跑哪份代码 })
  * $parallel (str * { DP / TP / PP / EP 怎么切 })
  * $load (str * { batch、序列长度、checkpoint 间隔 })

Run =
  Object
  * $io (io_pattern.IoPatternRecord * { 这次运行发出的读写请求：大小、偏移、并发、时序 })
  * $sli (list[performance.PerformanceSliRecord] * { 从这次运行量出来的指标 })
  * $slo (list[performance.PerformanceSloResult] * { 部署方给了阈值的判定 })
  * $manifest (str * { 输入、版本、拓扑的记录在哪 })

Gap =
  Object
  * $what (str * { 哪个模型族、哪种负载没有覆盖 })
  * $why (str * { 为什么该补 })
```

## 基本操作

收代码、选样本、按存储跑一次、量指标并判阈值、比两个存储版本、把没覆盖的登记成缺口。

## ckpt_bench_api

```viba ckpt_bench_api
import ckpt_bench
import ckpt_sample
import performance

Collect =
     list[ckpt_sample.Model]
  <- { 从平台抓模型代码，按结构去重，跑一遍确认能跑 }

PickSamples =
     list[ckpt_bench.Sample]
  <- $corpus (list[ckpt_sample.Model] * { 可用的模型代码 })
  <- $shape (str * { 这次要覆盖的结构与规模 })
  <- { 按要覆盖的格子挑模型，配好并行与负载 }

Execute =
     ckpt_bench.Run
  <- $sample (ckpt_bench.Sample * { 一条用例 })
  <- $storage (ckpt_sample.StorageLayer * { 一个存储版本 })
  <- { 旁路计算，保留 checkpoint 写入与读取，跑一次，记 IO 与 SLI }

Judge =
     list[performance.PerformanceSloResult]
  <- $sli (list[performance.PerformanceSliRecord] * { 这次量出来的指标 })
  <- $policy (performance.PerformanceSloThreshold * { 部署方给的阈值 })
  <- { 逐指标对照阈值，给出通过 / 失败 / 不可比 }

Compare =
     performance.PerformanceStorageComparison
  <- $a (ckpt_bench.Run * { 旧存储版本的运行 })
  <- $b (ckpt_bench.Run * { 新存储版本的运行 })
  <- { 同一份负载，逐指标比差值，只允许存储两层里有一层不同 }

FindGaps =
     list[ckpt_bench.Gap]
  <- $runs (list[ckpt_bench.Run] * { 已有的运行 })
  <- $corpus (list[ckpt_sample.Model] * { 语料 })
  <- { 看哪些模型族、规模、负载还没有样本，登记成缺口 }
```

## ckpt_bench_flow

六个操作按顺序串起来，就是这套 bench 的一圈。

```viba ckpt_bench_flow
import ckpt_bench_api

Duty =
  Object
  * $collect (ckpt_bench_api.Collect * { 收代码 })
  * $pick (ckpt_bench_api.PickSamples * { 选样本 })
  * $execute (ckpt_bench_api.Execute * { 跑一次 })
  * $judge (ckpt_bench_api.Judge * { 判阈值 })
  * $compare (ckpt_bench_api.Compare * { 比版本 })
  * $find_gaps (ckpt_bench_api.FindGaps * { 补缺口 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
