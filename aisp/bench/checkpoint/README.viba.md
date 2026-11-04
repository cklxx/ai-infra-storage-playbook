# checkpoint bench

## 需求背景

bench 要回答一个问题：在一批真实的模型代码上，checkpoint 写入与读取对存储提出什么要求。回答它需要一条完整的链：收代码、挑样本、跑一次、判阈值、比版本、补缺口。这条链上的名字都从这里发布，别的文档只从这里取。

## public.viba

先看 `Bench`，再看 `Collect`、`PickSamples`、`Execute`、`Judge`、`Compare`、`FindGaps` 六个操作；样本与运行直接用 `sample` 的 `RunSpec` 与 `RunRecord`，这里不另立一份。

```bash public
import aisp.bench.checkpoint.sample.public as sample
import aisp.bench.checkpoint.readme.types as ckpt_bench
import aisp.bench.checkpoint.readme.apis as ckpt_bench_api

Bench = ckpt_bench.Bench
RunSpec = sample.RunSpec
RunRecord = sample.RunRecord
Collect = ckpt_bench_api.Collect
PickSamples = ckpt_bench_api.PickSamples
Execute = ckpt_bench_api.Execute
Judge = ckpt_bench_api.Judge
Compare = ckpt_bench_api.Compare
FindGaps = ckpt_bench_api.FindGaps
```

## types.viba

bench 由一个语料、一批样本、几套存储与它们跑出来的运行组成；一条样本是一条 `RunSpec`，一次运行是一条 `RunRecord`。这里只定义 bench 自己的东西：整体 `Bench` 与缺口 `Gap`。

```bash types
import aisp.bench.checkpoint.sample.public as sample

Bench =
  Object
  * $corpus (list[sample.Model] * { 真实模型代码，从平台上收，按 id + commit 钉死 })
  * $samples (list[sample.RunSpec] * { 从语料里挑出的用例：模型代码 + 并行配置 + 负载 })
  * $storages (list[sample.StorageLayer] * { 被评的存储两层 })
  * $runs (list[sample.RunRecord] * { 每条样本在每个存储版本上跑一次 })
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
import aisp.bench.checkpoint.sample.public as sample
import aisp.bench.checkpoint.performance.public as sli
import aisp.bench.checkpoint.readme.types as ckpt_bench
import aisp.bench.checkpoint.ckpt_bypass_plan.public as ckpt_bypass_plan_api
import aisp.bench.checkpoint.measures.public as measures_api
import aisp.bench.checkpoint.observation.public as observation_api
import aisp.bench.checkpoint.scaling.public as scaling_api
import aisp.bench.checkpoint.model_code_collection.public as collection_api
import aisp.bench.metrics.coverage.public as coverage_api

Collect =
     list[sample.Model]
  <- {
    从平台抓模型代码，按结构去重，跑一遍确认能跑
  }
  <- $fetch (collection_api.Fetch * { 抓取：它按来源与筛选条件取 model id，只下代码与配置，逐个文件记 sha256 与许可证；它交回的清单记录是这一批候选，去重与可跑性还是 nil })
  <- $dedup (collection_api.Dedup * { 去重：候选清单交给它分组，同架构且代码层关键调用序列一致的只留一个代表，其余不再进可跑性验证 })
  <- $probe (collection_api.ProbeRunnable * { 跑一遍：留下的每条记录由它起单 rank 进程跑一次前向或一次预填充，跑不起来的在这里被剔掉；剩下的记录才作为 Model 交回 })

PickSamples =
     list[sample.RunSpec]
  <- $corpus (list[sample.Model] * { 可用的模型代码 })
  <- $coverage (coverage_api.CoverageManifest * { 覆盖度清单：配方声明的轴与已有格子 })
  <- {
    按要覆盖的格子挑模型，配好并行与负载
  }
  <- $compute (coverage_api.ComputeCoverage * { 清单交给它算出缺口清单与优先级；这次挑哪些模型，按它交回的缺口清单走 })
  <- $level (scaling_api.GetLevel * { 每条用例的拓扑交给它落到 S0 到 S5 的哪一级；并行配置与负载按它交回的档位配 })

Execute =
     sample.RunRecord
  <- $spec (sample.RunSpec * { 一条用例 })
  <- {
    旁路计算，保留 checkpoint 写入与读取，跑一次，记 IO 与 SLI
  }
  <- $prepare (ckpt_bypass_plan_api.PrepareBypass * { 它交回的五步做法与四条约束决定这次怎么旁路：模型在 meta device 上建，反向与 optimizer 换占位，checkpoint 写入原样保留 })
  <- $collect (observation_api.Collect * { 开跑前先让它开观测，trace 才有来源；它交回实际开的层，少于两层这次运行就不算数 })
  <- $measure (sample.Measure * { 跑完把这条记录交给它，它把 trace 折算成六项 SLI，填进 Artifacts.metrics })
  <- $run (sample.Execute * { 请求交给它同步跑到结束；它交回的四份产物就是这条运行记录的产物 })

Judge =
     list[sli.CkptSlo]
  <- $sli (list[sli.CkptSli] * { 这次测得的指标 })
  <- $policy (str * { 部署方给的阈值 })
  <- {
    逐指标对照阈值，给出通过 / 失败 / 不可比
  }
  <- $judge (sli.Judge * { 把 Artifacts.metrics 交给它，它逐项配阈值判出 CkptSlo，成为 Artifacts.slo；这一步只决定用哪份阈值 })

Compare =
     str
  <- $a (sample.RunRecord * { 旧存储版本的运行 })
  <- $b (sample.RunRecord * { 新存储版本的运行 })
  <- {
    同一份负载，逐指标比差值，只允许存储两层里有一层不同；返回比较结果的位置
  }
  <- $compare (measures_api.CompareTolerance * { 两个版本同名的每项指标各调它一次，它按这一项的统计量判定两个值是否落在容差内；有一项超差，两个版本就不可比 })

FindGaps =
     list[ckpt_bench.Gap]
  <- $runs (list[sample.RunRecord] * { 已有的运行 })
  <- $corpus (list[sample.Model] * { 语料 })
  <- {
    看哪些模型族、规模、负载还没有样本，登记成缺口
  }
  <- $coverage (coverage_api.ComputeCoverage * { 算覆盖率：它交回的缺口清单已经按优先级排好；这里只把缺口转成 Gap 登记 })
```
