# 核心方法论：旁路计算，保真 IO

## public.viba

只做转发：从 `## 问题` 的 `methodology` 模块与 `## 接口` 的 `methodology_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `MethodologySpec`、`MethodologyBypassPlan`、`MethodologyBoundaryTable`、`MethodologyTolerance`，操作 `PlanBypass`、`RecordBoundary`、`Observe`、`Align`；先看 `MethodologySpec` 与 `PlanBypass`，再看 `RecordBoundary` 交回的 `MethodologyBoundaryTable` 与 `Observe`、`Align` 判定用的 `MethodologyTolerance`。

```bash public
import aisp.bench.checkpoint.measures.types as methodology
import aisp.bench.checkpoint.methodology.apis as methodology_api

MethodologySpec = methodology.MethodologySpec
MethodologyBypassPlan = methodology.MethodologyBypassPlan
MethodologyBoundaryTable = methodology.MethodologyBoundaryTable
MethodologyTolerance = methodology.MethodologyTolerance
PlanBypass = methodology_api.PlanBypass
RecordBoundary = methodology_api.RecordBoundary
Observe = methodology_api.Observe
Align = methodology_api.Align
```

## 背景

本文是整套方法的唯一出处：旁路、保真等级、保真边界表、IO pattern 度量项、对齐判定、阶段门只在这里定义一次；三类评估集的配方引用本文的章节，只写各自的差异。本文解决"评估集怎么建、怎么判它可信"。存储在一个样本上的表现（SLI）怎么测、重保子集怎么判（SLO）、两个存储版本怎么比，见 [`performance.viba.md`](performance.viba.md)，两篇的分工不要混。

## methodology

问题形式化为五个模块：`methodology` 汇总整套方法；`gates`、`bypass`、`fidelity`、`observation` 分别定义阶段门、旁路手段与保真等级、保真边界表、观测层。对象类型 `MethodologySpec`、`MethodologyBypassPlan`、`MethodologyBypassPremise`、`MethodologyBoundaryTable`、`MethodologyObservation`、`MethodologyAlignment`、`MethodologyScaling`、`MethodologyReproduction`、`MethodologyTolerance` 与 `MethodologyToleranceCalibration` 分别表示整套方法的汇总、旁路方案、旁路前提、保真边界表、一次采集、一次对齐判定、一级放大、可复现条件、一项容差与这项容差的标定记录。取值只能落在有限集合里的概念写成 `Oneof` 枚举：`MethodologyMetric`、`MethodologyToleranceStatistic`、`MethodologyAttributionCause`、`MethodologyScaleRule`、`MethodologyReproducibilityItem` 与 `MethodologyFailureMode` 分别表示 IO pattern 度量项、对齐统计量、偏差归因、scaling 规则、可复现项与失效模式。`MethodologySpec` 的九个字段分别引用这些类型：`$gates`、`$bypass_methods`、`$fidelity_boundaries`、`$observation_layers` 分别是 `gates.Gate`、`bypass.BypassMethod`、`fidelity.FidelityBoundary`、`observation.ObservationLayer` 的列表，`$metrics`、`$tolerances`、`$scale_rules`、`$failure_modes` 分别是 `MethodologyMetric`、`MethodologyTolerance`、`MethodologyScaleRule`、`MethodologyFailureMode` 的列表，`$reproduction` 是 `MethodologyReproduction`；`MethodologyBypassPlan` 的 `$method` 与 `$fidelity` 分别取 `bypass.BypassMethod` 与 `bypass.FidelityLevel` 的一个取值，`MethodologyTolerance` 的 `$metric` 与 `$statistic` 分别取 `MethodologyMetric` 与 `MethodologyToleranceStatistic` 的一个取值。

对齐的判定是：在选定的度量项上，旁路运行与同等规模的真实运行，其统计量落在声明的容差内。实际判定用配方 `metrics.yaml` 里的 `tolerance`，类型里的初始容差只是标定起点；容差需要按评估集标定，checkpoint 写入的请求大小由分片策略决定，容差应更紧。

G1 到 G4 的判定记录写进 `recipe.yaml`，不写进文档正文。

`BypassMethod` 写的是请求序列的保真等级，不含时序。旁路计算后时序一定被压缩：原本散布在整个训练步里的写入会挤到末尾。时序按 [`scaling.viba.md`](scaling.viba.md) 的「时序与重叠」折算，必要时在旁路实现里注入与真实计算等长的延迟；请求序列与时序必须分开评估。L2 是大多数场景的默认目标：它保证发了哪些请求，不保证什么时候发；L3 只用于对齐基准，不用于批量运行。

每个配方必须填写，没有这张表视为未完成。行结构见 [`json_schema/FidelityBoundary.schema.json`](json_schema/FidelityBoundary.schema.json)。

三层观测至少要两层交叉核对：应用层统计的总字节数与系统层统计的总字节数，偏差超过 1% 必须先解释；解释不清时先怀疑观测本身，再使用任何 pattern 结论。观测开销单独测量：开启与关闭观测各跑一次，关键指标变化超过 3% 时降低采样率或改用系统层。

## 基本操作

先准备旁路（`PlanBypass`）：从四种手段里选一种，确认发起 IO 的代码路径没有被替换，登记时序偏差，必要时在旁路实现里注入与真实计算等长的延迟。

1. 再记录保真边界表（`RecordBoundary`）：每个被旁路的路径一行，IO 路径的保真等级不得是 L0。
2. 采集（`Observe`）至少开两层观测并交叉核对：应用层与系统层的总字节偏差超过 1% 要先解释，观测开销超过 3% 要降低采样率或改用系统层。
3. 最后固定可复现条件（`Reproduce`）：模型代码、配置、依赖、拓扑、预热、观测、随机性七项，缺任何一项，结论都只能算某次运行的观测。

## apis.viba

```bash apis
import aisp.bench.checkpoint.bypass.types as bypass
import aisp.bench.checkpoint.fidelity.types as fidelity
import aisp.bench.checkpoint.bypass.apis as bypass_api
import aisp.bench.checkpoint.fidelity.apis as fidelity_api
import aisp.bench.checkpoint.measures.apis as measures_api
import aisp.bench.checkpoint.observation.apis as observation_api
import aisp.bench.checkpoint.scaling.apis as scaling_api
import aisp.bench.checkpoint.scaling.types as levels
import aisp.bench.checkpoint.measures.types as methodology
import aisp.bench.checkpoint.observation.types as observation

PlanBypass =
     methodology.MethodologyBypassPlan
  <- $method (bypass.BypassMethod * { 从四种旁路手段里选一种；它决定请求序列的保真等级 })
  <- $fidelity (bypass.FidelityLevel * { 请求序列的保真等级；L2 是大多数场景的默认目标，L3 只用于对齐基准，不用于批量运行 })
  <- $premise (methodology.MethodologyBypassPremise * { 旁路依赖的前提：发起 IO 的代码路径没有被替换，时序偏差已登记 })
  <- {
    准备旁路：选定手段与保真等级，确认 IO 路径不变，登记时序偏差；时序按 scaling.viba.md 的「时序与重叠」折算，必要时在旁路实现里注入与真实计算等长的延迟。返回旁路方案
  }
  <- $choose (bypass_api.Choose * { 把要求的保真等级与可接受的成本交给它，它指定用哪种手段；方案里的 method 与 fidelity 取它交回的那一个 })

RecordBoundary =
     methodology.MethodologyBoundaryTable
  <- $rows (list[fidelity.FidelityBoundary] * { 每个被旁路的代码路径一行，写到函数级；bypassed 为 partial 时写清部分的范围边界 })
  <- {
    记录保真边界表：每个配方必须填写，没有这张表视为未完成；IO 路径的保真等级不得是 L0，写 L0 说明评估对象已被替换，该路径的结论无效。返回填好的表
  }
  <- $record (fidelity_api.Record * { 每一行交给它登记；它交回的行组成这张表，bypassed 为 partial 时范围边界也写在它的 kept 与 known_bias 里 })

Observe =
     methodology.MethodologyObservation
  <- $layers (list[observation.ObservationLayer] * { 这次开了哪几层；三层里至少两层交叉核对 })
  <- $app_bytes (float * { 应用层统计的总字节数 })
  <- $sys_bytes (float * { 系统层统计的总字节数 })
  <- $explanation (str * { 偏差超过 1% 时的解释；没有偏差写 none，不留空 })
  <- $overhead (float * { 开启与关闭观测各跑一次，关键指标的变化比例 })
  <- {
    采集：三层观测至少开两层并交叉核对；应用层与系统层的总字节数偏差超过 1% 必须先解释，再使用任何 pattern 结论；观测开销超过 3% 时降低采样率或改用系统层。返回这次采集的观测结果
  }
  <- $collect (observation_api.Collect * { 想开的层交给它，它开起来并交回实际开的层；少于两层就不足以交叉核对，这次采集不算数 })

Align =
     methodology.MethodologyAlignment
  <- $real (methodology.MethodologyObservation * { 不做旁路的同规模真实运行，按 Observe 采集 })
  <- $bypass (methodology.MethodologyObservation * { 与真实运行同规模的旁路运行，也按 Observe 采集 })
  <- $tolerances (list[methodology.MethodologyTolerance] * { 配方 metrics.yaml 标定的容差；不是本文的初始容差 })
  <- {
    小规模对齐：在选定的度量项上比较两次运行的统计量，判定是否落在容差内；差异超过容差时按 MethodologyAttributionCause 的顺序逐项排除，归因结论写进配方的 README.viba.md。返回对齐判定
  }
  <- $compare (measures_api.CompareTolerance * { 每个度量项各调它一次，真实值与旁路值一起给它；有一项落在容差外就按归因顺序排查 })

Scale =
     methodology.MethodologyScaling
  <- $level (levels.Level * { 这次放大到的档位；级别的定义见 scaling.viba.md })
  <- $invariants (list[methodology.MethodologyMetric] * { 这一级要重新验证的不变量；对齐通过之前不允许进入 scaling })
  <- {
    逐级放大：总则见 scaling.viba.md；对齐通过之前不允许进入 scaling，每一级都要重新验证不变量，跳级得到的结论没有依据；偏差要有归因。返回这一级的结果
  }
  <- $scale (scaling_api.ScaleUp * { 这一级交给它跑：它验证不变量、记录偏差归因；它交回的层级结果就是 MethodologyScaling 的来源 })

Reproduce =
     methodology.MethodologyReproduction
  <- $fixed (list[methodology.MethodologyReproducibilityItem] * { 已经固定的项；七项都要固定 })
  <- {
    固定可复现条件：模型代码、配置、依赖、拓扑、预热、观测、随机性；返回固定的项与还缺的项。缺任何一项，结论都只能算某次运行的观测，不能算评估结论
  }
```

## flow.viba

```bash flow
import aisp.bench.checkpoint.measures.types as methodology
import aisp.bench.checkpoint.methodology.apis as methodology_api

MethodologyPrepareDuty =
  Object
  * $step (methodology_api.PlanBypass * { 准备旁路：对应门 G1，门 G0 是它的前提；先跑通不旁路的流程，再选旁路手段，保持 IO 路径不变 })
  * $plan (methodology.MethodologyBypassPlan * { 这一步的产物：旁路手段、请求序列保真等级、前提与时序偏差 })

MethodologyBoundaryDuty =
  Object
  * $step (methodology_api.RecordBoundary * { 记录保真边界：对应门 G1；每个配方必须填写 })
  * $table (methodology.MethodologyBoundaryTable * { 这一步的产物：保真边界表的行 })

MethodologyObserveDuty =
  Object
  * $step (methodology_api.Observe * { 采集：至少两层观测交叉核对；为门 G2 的对齐提供观测结果 })
  * $observation (methodology.MethodologyObservation * { 这一步的产物：观测层、字节偏差、解释与观测开销 })

MethodologyAlignDuty =
  Object
  * $step (methodology_api.Align * { 小规模对齐：与同规模真实运行对比选定度量项；对应门 G2 })
  * $alignment (methodology.MethodologyAlignment * { 这一步的产物：容差判定与偏差归因 })

MethodologyScaleDuty =
  Object
  * $step (methodology_api.Scale * { 逐级放大：每一级重新验证不变量；对应门 G3 })
  * $scaling (methodology.MethodologyScaling * { 这一步的产物：这一级的不变量保持情况与偏差归因 })

MethodologyReproduceDuty =
  Object
  * $step (methodology_api.Reproduce * { 固定可复现条件：结论登记前必须完成；缺任何一项，结论只能算某次运行的观测 })
  * $reproduction (methodology.MethodologyReproduction * { 这一步的产物：已固定的项与还缺的项 })

MethodologyFlow =
  Object
  * $spec (methodology.MethodologySpec * { 问题定义：阶段门、旁路、保真、观测、度量项、容差、scaling 规则、可复现与失效模式 })
  * $prepare (MethodologyPrepareDuty * { 第一步：准备旁路 })
  * $boundary (MethodologyBoundaryDuty * { 第二步：记录保真边界 })
  * $observe (MethodologyObserveDuty * { 第三步：采集并交叉核对观测 })
  * $align (MethodologyAlignDuty * { 第四步：小规模对齐 })
  * $scale (MethodologyScaleDuty * { 第五步：逐级放大 })
  * $reproduce (MethodologyReproduceDuty * { 第六步：固定可复现条件 })
```

Scaling 的总则见 [`scaling.viba.md`](scaling.viba.md)。

配方只写差异：`recipes/model_code_collection` 只写语料不变量与可跑性验证，`recipes/checkpoint` 只写 meta device 旁路与并行配置；共性的步骤、判定规则引用本文的章节标题加路径，不复制。新规则先写进本文，再改配方；配方里与本文冲突的表述以本文为准，并修正配方。改本文等于改三类评估集的共同定义，评审要求与改指标口径相同：说明影响哪些配方、哪些历史结论失效，并在 `CHANGELOG.md` 记录。

更多已知问题与开放问题见 [`pitfalls.viba.md`](pitfalls.viba.md)。

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
