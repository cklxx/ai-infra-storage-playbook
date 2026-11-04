# checkpoint bench

## public.viba

先看 `Bench`，再看 `Execute`、`Judge`、`Compare` 三个操作；样本与运行直接用 `ckpt_sample` 的 `RunSpec` 与 `RunRecord`，这里不另立一份。

```bash public
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample
import aisp.bench.checkpoint.readme.types as ckpt_bench
import aisp.bench.checkpoint.readme.apis as ckpt_bench_api

Bench = ckpt_bench.Bench
RunSpec = ckpt_sample.RunSpec
RunRecord = ckpt_sample.RunRecord
Execute = ckpt_bench_api.Execute
Judge = ckpt_bench_api.Judge
Compare = ckpt_bench_api.Compare
```

## 背景

在一批真实的模型代码上，测量 checkpoint 写入与读取对存储的要求，并把结论从单机外推到十万卡。

## types.viba

bench 由一个语料、一批样本、几套存储与它们跑出来的运行组成；一条样本是一条 `RunSpec`，一次运行是一条 `RunRecord`。这里只定义 bench 自己的东西：整体 `Bench` 与缺口 `Gap`。

```bash types
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample

Bench =
  Object
  * $corpus (list[ckpt_sample.Model] * { 真实模型代码，从平台上收，按 id + commit 钉死 })
  * $samples (list[ckpt_sample.RunSpec] * { 从语料里挑出的用例：模型代码 + 并行配置 + 负载 })
  * $storages (list[ckpt_sample.StorageLayer] * { 被评的存储两层 })
  * $runs (list[ckpt_sample.RunRecord] * { 每条样本在每个存储版本上跑一次 })
  * $gaps (list[Gap] * { 没覆盖到、需要补的地方 })

Gap =
  Object
  * $what (str * { 哪个模型族、哪种负载没有覆盖 })
  * $why (str * { 为什么该补 })
```

## 基本操作

1. 收代码：从平台抓模型代码，按结构去重，跑一遍确认能跑。
2. 选样本：按要覆盖的格子挑模型，配好并行与负载，形成 `RunSpec`。
3. 跑一次：旁路计算，保留 checkpoint 写入与读取，跑完拿到一条 `RunRecord`。
4. 判阈值：用 `CkptSli` 的指标对照部署方给的阈值，得出通过、失败或不可比。
5. 比版本：同一份负载换一个存储版本，逐指标比差值，只允许存储两层里有一层不同。
6. 补缺口：看哪些模型族、规模、负载还没有样本，登记成 `Gap`。

## apis.viba

```bash apis
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample
import aisp.bench.checkpoint.performance.types as sli
import aisp.bench.checkpoint.performance.slo as slo
import aisp.bench.checkpoint.readme.types as ckpt_bench

Collect =
     list[ckpt_sample.Model]
  <- { 从平台抓模型代码，按结构去重，跑一遍确认能跑 }

PickSamples =
     list[ckpt_sample.RunSpec]
  <- $corpus (list[ckpt_sample.Model] * { 可用的模型代码 })
  <- $shape (str * { 这次要覆盖的结构与规模 })
  <- { 按要覆盖的格子挑模型，配好并行与负载 }

Execute =
     ckpt_sample.RunRecord
  <- $spec (ckpt_sample.RunSpec * { 一条用例 })
  <- { 旁路计算，保留 checkpoint 写入与读取，跑一次，记 IO 与 SLI }

Judge =
     list[slo.CkptSlo]
  <- $sli (list[sli.CkptSli] * { 这次测得的指标 })
  <- $policy (str * { 部署方给的阈值 })
  <- { 逐指标对照阈值，给出通过 / 失败 / 不可比 }

Compare =
     str
  <- $a (ckpt_sample.RunRecord * { 旧存储版本的运行 })
  <- $b (ckpt_sample.RunRecord * { 新存储版本的运行 })
  <- { 同一份负载，逐指标比差值，只允许存储两层里有一层不同；返回比较结果的位置 }

FindGaps =
     list[ckpt_bench.Gap]
  <- $runs (list[ckpt_sample.RunRecord] * { 已有的运行 })
  <- $corpus (list[ckpt_sample.Model] * { 语料 })
  <- { 看哪些模型族、规模、负载还没有样本，登记成缺口 }
```

## flow.viba

```bash flow
import aisp.bench.checkpoint.readme.apis as api

Duty =
  Object
  * $collect (api.Collect * { 收代码 })
  * $pick (api.PickSamples * { 选样本 })
  * $execute (api.Execute * { 跑一次 })
  * $judge (api.Judge * { 判阈值 })
  * $compare (api.Compare * { 比版本 })
  * $find_gaps (api.FindGaps * { 补缺口 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
