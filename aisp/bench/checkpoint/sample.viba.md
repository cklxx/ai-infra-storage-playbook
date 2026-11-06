# checkpoint 样本接口

## 需求背景

一条样本要能被描述、被执行、被记录：`RunSpec` 说明它跑什么程序、用哪份配置、评哪两层存储、用什么种子、预热多少步、超时多久，`RunRecord` 记下它跑到哪一步、产物在哪里；执行与测量两个操作把样本跑起来并填好这条记录。这些名字是所有下游文档共用的词汇，所以从这里发布成 public。

## public.viba

```bash public
import aisp.bench.checkpoint.sample.types as sample
import aisp.bench.checkpoint.sample.apis as sample_api

RunRecord = sample.RunRecord
RunSpec = sample.RunSpec
StorageLayer = sample.StorageLayer
Component = sample.Component
State = sample.State
QueueProgress = sample.QueueProgress
WorkProgress = sample.WorkProgress
Artifacts = sample.Artifacts
Failure = sample.Failure
Model = sample.Model
SampleConfigBase = sample.SampleConfigBase
Topology = sample.Topology
ObservationConfig = sample.ObservationConfig
Execute = sample_api.Execute
Measure = sample_api.Measure
```

## types.viba

```bash types
import aisp.bench.checkpoint.performance.public as sli
import aisp.bench.checkpoint.observation.public as observation

RunRecord =
  Object
  * $run_id (str * { 运行标识，查状态、取产物都用它 })
  * $protocol_version (str * { 这次运行实际执行的协议版本；与当前协议不同就不参与比较 })
  * $state (State * { 这次运行现在在哪一步 })
  * $progress (WorkProgress * { 已完成的工作量占总量的多少，单位由配置定 })
  * $artifacts (Artifacts * { 产物的位置；没跑完时相应字段缺 })

RunSpec =
  Object
  * $sample (str * { 跑哪个样本程序，写 name@version })
  * $config (SampleConfigBase * { 样本 repo 里那份配置；下方列出的字段必须写全 })
  * $storage (StorageLayer * { 这次要评的存储两层 })
  * $seed (int * { 随机种子，决定同一请求重跑的一致性 })
  * $warmup_steps (int * { 测量前跑多少步预热；与协议一致 })
  * $timeout_s (float * { 本次运行超时，秒；与协议一致 })
  * $protocol_version (str * { 这次运行按哪一版协议执行；由 Bench 的协议填入 })

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
  * $manifest (str * { 运行清单：输入、版本、拓扑、观测配置，运行时写 })
  * $trace (str * { 原始观测 trace 的目录；Measure 从这里读数，校验时核这里是否齐全 })
  * $metrics (list[sli.CkptSli] * { 这次运行的 SLI：每项一条，没有阈值 })
  * $slo (list[sli.CkptSlo] * { 阈值已给的指标的判定；没给阈值的项不出现 })
  * $report (str * { 人读报告的位置 })

Failure =
  Object
  * $kind (str * { 失败分类：environment、dependency、timeout、observation、assertion 等 })
  * $detail (str * { 具体说明 })
Model =
  Object
  * $id (str * { 模型标识，例如 HuggingFace 的 repo id })
  * $git_commit_id (str * { 代码 commit，钉死到具体一份代码 })

SampleConfigBase =
  Object
  * $model (Model * { 被评估的模型 })
  * $topology (Topology * { 节点、卡、网络、挂载 })
  * $observe (ObservationConfig * { 观测设置 })

Topology =
  Object
  * $nodes (int * { 节点数 })
  * $gpus_per_node (int * { 每节点卡数 })
  * $network (str * { 网络类型：rdma、tcp、none })
  * $mount (str * { 存储挂载方式：local-nvme、nfs、fuse })
  * $parallel (str * { 并行切分：dp、tp、pp、ep 各自的度数，写成 dp8-tp2-pp1-ep1 })

ObservationConfig =
  Object
  * $enabled (bool * { 是否开观测 })
  * $sample_rate (float * { 采样率，0 到 1 })
  * $layers (list[observation.ObservationLayer] * { 采集层；至少两层，其中必须含 sys })

```

## 基本操作

两个操作。

1. 执行一次：把同一份 `RunSpec` 交给样本进程跑到结束，拿到五份产物；旁路与观测由调用方接入。
2. 测量一次：一次运行跑完，从 `Artifacts.trace` 里算出三项指标，每项一条 `CkptSli`，填进 `Artifacts.metrics`。

## apis.viba

```bash apis
import aisp.bench.checkpoint.sample.types as sample
import aisp.bench.checkpoint.performance.public as sli

Execute =
     sample.Artifacts
  <- $spec (sample.RunSpec * { 同一份运行请求 })
  <- {
    执行接口：同一份请求同步跑到结束，返回时五份产物已经写完；旁路与观测由调用方接入
  }

Measure =
     list[sli.CkptSli]
  <- $run (sample.RunRecord * { 一次已经跑完、观测已开的运行 })
  <- {
    测量接口：从 Artifacts.trace 里算出三项指标，填进 Artifacts.metrics；返回每项一条，没有阈值
  }
```
