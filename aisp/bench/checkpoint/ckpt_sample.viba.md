# checkpoint 样本接口

一份 RunSpec 进，一条 RunRecord 出。一次运行 = 一条样本 × 一个存储版本。

## types.viba

```bash types
import aisp.bench.checkpoint.performance.types as sli
import aisp.bench.checkpoint.performance.slo as slo
import aisp.bench.checkpoint.observation.types as observation

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
  * $slo (list[slo.CkptSlo] * { 每个 SLI 指标的判定，阈值由部署方给 })
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

## apis.viba

```bash apis
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample
import aisp.bench.checkpoint.scaling.types as levels

GetLevel =
     levels.Level
  <- $config (ckpt_sample.SampleConfigBase * { 样本配置 })
  <- {
    导出属性：按节点数与每节点卡数落到 S0 到 S5 的哪一级，阈值由配方的 scaling 阶梯给
  }
```

## json schema

接口里的每个类型各有一份 JSON Schema，放在 [`json_schema/`](json_schema/) 下，文件名是类型名加 `.schema.json`。函数没有对应的 JSON 值，不生成文件。

这些文件由 `scripts/export_json_schema.py` 从文档里的 viba 代码块生成，不要手改。
