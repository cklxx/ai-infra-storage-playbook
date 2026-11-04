# checkpoint 样本接口

## 需求背景

一次运行要能被描述、被执行、被记录：进的是一份 `RunSpec`，出的是一条 `RunRecord`。样本用哪个模型、什么并行与观测设置，运行到哪一步、产物有哪些，这些字段是所有下游文档共用的词汇，所以本篇把它们发布成 public。

## public.viba

```bash public
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample
import aisp.bench.checkpoint.ckpt_sample.apis as ckpt_sample_api

RunRecord = ckpt_sample.RunRecord
RunSpec = ckpt_sample.RunSpec
StorageLayer = ckpt_sample.StorageLayer
Component = ckpt_sample.Component
State = ckpt_sample.State
QueueProgress = ckpt_sample.QueueProgress
WorkProgress = ckpt_sample.WorkProgress
Artifacts = ckpt_sample.Artifacts
Failure = ckpt_sample.Failure
Model = ckpt_sample.Model
SampleConfigBase = ckpt_sample.SampleConfigBase
Topology = ckpt_sample.Topology
ObservationConfig = ckpt_sample.ObservationConfig
Execute = ckpt_sample_api.Execute
```

## types.viba

```bash types
import aisp.bench.checkpoint.performance.public as sli
import aisp.bench.checkpoint.observation.public as observation

RunRecord =
  Object
  * $run_id (str * { 运行标识，查状态、取产物都用它 })
  * $state (State * { 这次运行现在在哪一步 })
  * $progress (WorkProgress * { 已完成的工作量占总量的多少，单位由配置定 })
  * $artifacts (Artifacts * { 产物的位置；没跑完时相应字段缺 })

RunSpec =
  Object
  * $sample (str * { 跑哪个样本程序，写 name@version })
  * $config (SampleConfigBase * { 样本 repo 里那份配置；下方列出的字段必须写全 })
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
  * $manifest (str * { 运行清单：输入、版本、拓扑、观测配置，运行时写 })
  * $metrics (list[sli.CkptSli] * { 这次运行的 SLI：每项一条，没有阈值 })
  * $slo (list[sli.CkptSlo] * { 每个 SLI 指标的判定，阈值由部署方给 })
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

ObservationConfig =
  Object
  * $enabled (bool * { 是否开观测 })
  * $sample_rate (float * { 采样率，0 到 1 })
  * $layers (list[observation.ObservationLayer] * { 采集层；至少两层，其中必须含 sys })

```

## 基本操作

只有一个操作：执行一次。把同一份 `RunSpec` 交给样本进程跑到结束，拿到四份产物；旁路与观测由调用方接入。

## apis.viba

```bash apis
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample

Execute =
     ckpt_sample.Artifacts
  <- $spec (ckpt_sample.RunSpec * { 同一份运行请求 })
  <- {
    执行接口：同一份请求同步跑到结束，返回时四份产物已经写完；旁路与观测由调用方接入
  }
```
