# 附录 A：基础术语

## public

本文对外发布 5 个名字，全部是转发：类型 `GlossaryTerm`、`GlossaryCategory`、`GlossaryDefinition` 来自 glossary，操作 `Lookup`、`Define` 来自 glossary_api。先看 `GlossaryTerm` 与 `GlossaryCategory` 弄清一个词归哪一类，再看 `Lookup` 与 `Define` 怎么查到它的定义。

```bash glossary_public
import aisp.bench.checkpoint.appendix_glossary.glossary as glossary
import aisp.bench.checkpoint.appendix_glossary.glossary_api as glossary_api

GlossaryCategory = glossary.GlossaryCategory
GlossaryTerm = glossary.GlossaryTerm
GlossaryDefinition = glossary.GlossaryDefinition
Lookup = glossary_api.Lookup
Define = glossary_api.Define
```

## 背景

本附录解释各篇文档里反复出现、但属于存储与推理领域而非本项目的词，按并行策略、模型结构、存储与 IO、旁路相关四类组织。项目自造词（评估集、配方、旁路、保真、回链）在 [`README.md`](../README.md) 的「术语」里，本附录不重复。读到不认识的词先查本附录，本附录没有的再去 README 查；两处都没有，就是文档的缺口，补进来。

## glossary

术语表分成「分类」与「术语」两层，都写成枚举：`GlossaryCategory` 是分类枚举，四个取值分别对应并行策略、模型结构、存储与 IO、旁路相关；每一类术语各有一个术语枚举，即 `ParallelStrategyTerm`、`ModelStructureTerm`、`StorageIoTerm`、`BypassTerm`，枚举中的每个取值就是一个术语。`GlossaryTerm` 把四个术语枚举收进同一个枚举，四个变体各携带其中一个取值，因此一个 `GlossaryTerm` 取值同时确定术语本身与它所属的 `GlossaryCategory`。术语的定义单独写成 `GlossaryDefinition`，类型是 `str`，与 `GlossaryTerm` 的取值一一对应。

```bash glossary
GlossaryCategory =
  Oneof
  | "parallel_strategy" * { 并行策略：把模型与 batch 切到多个 rank 上的四种方式。四种可以组合（例如 DP × TP × PP），组合方式直接改变 checkpoint 的分片与每 rank 的写入量，因此 scaling 一章把并行策略列为独立维度 }
  | "model_structure" * { 模型结构：注意力与专家怎么组织、推理时按什么粒度处理序列。KV 头数、层数与 head_dim 共同决定每 token 的 KV 字节数 }
  | "storage_io" * { 存储与 IO：读写数据时涉及的分片、带宽、元数据与延迟，外加判定一次运行的结论算不算数时用的两个词（基线、无结论） }
  | "bypass" * { 旁路相关：把计算换成不产生计算的实现时用到的 PyTorch 概念；旁路之后时间热点消失，写入时序会变 }

ParallelStrategyTerm =
  Oneof
  | "DP" * { 数据并行（data parallel）：把 batch 切开，每个 rank 持有完整模型 }
  | "TP" * { 张量并行（tensor parallel）：把单层权重按维度切开 }
  | "PP" * { 流水线并行（pipeline parallel）：把层分成若干段，按阶段流水 }
  | "EP" * { 专家并行（expert parallel）：把 MoE 的专家分到不同 rank }

ModelStructureTerm =
  Oneof
  | "MoE" * { 混合专家（mixture of experts）：每层有多个前馈专家，按路由只激活其中一部分 }
  | "GQA" * { 分组查询注意力（grouped-query attention）：多个查询头共享一组 KV 头，KV 头数少于查询头数 }
  | "MQA" * { multi-query attention：所有查询头共享一组 KV 头，是最省 KV 的一种 }
  | "MLA" * { multi-head latent attention：把 KV 压缩到低维潜空间再展开，KV 体积小但访问模式特殊 }
  | "prefill" * { 预填充：一次处理整个输入序列，KV 按 token 成批写入 }
  | "decode" * { 解码：逐 token 生成，每步只写一个 token 的 KV，读历史 KV }

StorageIoTerm =
  Oneof
  | "shard" * { 分片（shard）：把一份大文件或一份状态切成若干片，分别写到不同位置。分片数决定并发度与元数据量 }
  | "aggregate_bandwidth" * { 聚合带宽：多个 rank 同时读写时，存储侧承受的总带宽。它不等于单 rank 带宽乘以 rank 数：存储侧饱和后会走平 }
  | "metadata_op" * { 元数据操作：创建、删除、重命名、stat、列目录这类不搬运数据本体、只改目录信息的操作。小文件多、分片多时，元数据可能先于数据饱和 }
  | "read_amplification" * { 读放大：实际读取的字节数除以逻辑上需要的字节数。缓存命中率低、块重复读、预取过多都会放大读取 }
  | "tail_latency" * { 尾延迟：延迟分布的高分位，常用 P95、P99、P999。大规模下它比平均值更能反映排队与重传 }
  | "baseline" * { 基线：上一次通过验收的那次运行的度量值。不是「最近一次运行」，失败的运行不更新基线 }
  | "inconclusive" * { 无结论：运行没有产生可用度量（超时、观测失败、断言失败）。它既不算通过也不算失败，不计入通过率 }

BypassTerm =
  Oneof
  | "meta_device" * { meta device：PyTorch 的一种设备。张量只保留 dtype 与逻辑尺寸，不分配真实存储，因此前向可以执行但不产生计算 }
  | "module_mock" * { module mock：把指定模块替换成返回约定张量的实现，其余代码路径不变 }
  | "process_group" * { process group：PyTorch 分布式通信的进程组。mock 它可以在单卡上跑通按 rank 分支的代码，但 rank 之间的真实同步会消失 }
  | "activation_checkpoint" * { 激活检查点（activation checkpointing）：训练时用重算换显存。旁路后其时间热点消失，写入时序会变 }

GlossaryTerm =
  Oneof
  | $parallel_strategy (ParallelStrategyTerm * { 并行策略这一类里的一个词 })
  | $model_structure (ModelStructureTerm * { 模型结构这一类里的一个词 })
  | $storage_io (StorageIoTerm * { 存储与 IO 这一类里的一个词 })
  | $bypass (BypassTerm * { 旁路相关这一类里的一个词 })

GlossaryDefinition = str * { 一个术语的定义，内容就是该术语取值上挂的那段说明 }
```

## 基本操作

查一个词要两个操作：Lookup 查它属于哪一类，Define 查它的定义。Lookup 收一个 GlossaryTerm 取值，答一个 GlossaryCategory 取值，也就是并行策略、模型结构、存储与 IO、旁路相关四类里的哪一类。Define 收同一个 GlossaryTerm 取值，答一个 GlossaryDefinition，也就是这个词在「问题」里挂的那段说明。两个操作都只读：不修改术语表，也不新增词。附录里没列的词说明它属于项目自造词，按「背景」说的去 [`README.md`](../README.md) 的「术语」里查。

## glossary_api

```bash glossary_api
import aisp.bench.checkpoint.appendix_glossary.glossary as glossary

Lookup =
     glossary.GlossaryCategory
  <- $term (glossary.GlossaryTerm * { 要查的术语，GlossaryTerm 的一个取值 })
  <- { 查类别接口：答这个术语属于四类里的哪一类，给 GlossaryCategory 的一个取值。只读，不改变术语表 }

Define =
     glossary.GlossaryDefinition
  <- $term (glossary.GlossaryTerm * { 要查的同一个术语 })
  <- { 查定义接口：答这个术语的定义，就是它的取值上挂的那段说明。只读；与 Lookup 用同一个输入，两步可以先后走 }
```

## glossary_flow

```bash glossary_flow
import aisp.bench.checkpoint.appendix_glossary.glossary as glossary
import aisp.bench.checkpoint.appendix_glossary.glossary_api as glossary_api

GlossaryOp =
  Object
  * $lookup (glossary_api.Lookup * { 第一段，查类别：输入 GlossaryTerm，答出 GlossaryCategory })
  * $define (glossary_api.Define * { 第二段，查定义：输入同一个 GlossaryTerm，答出 GlossaryDefinition })

GlossaryFlow =
  Object
  * $term (glossary.GlossaryTerm * { 输入：要查的那个术语，它的具体取值决定后面两段答什么 })
  * $step (GlossaryOp * { 两段串联，顺序固定为先 Lookup 后 Define；两段都只读，输入是同一个术语 })
  * $category (glossary.GlossaryCategory * { Lookup 的返回：这个术语属于四类里的哪一类 })
  * $definition (glossary.GlossaryDefinition * { Define 的返回：这个术语的定义 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 `scripts/export_json_schema.py` 生成。
