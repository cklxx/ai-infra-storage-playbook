# 指标定义

## public.viba

只做转发：从 `## 问题` 的 `metrics_registry` 模块与 `## 接口` 的 `metrics_registry_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布七个名字：类型 `MetricsRegistryEntry`、`MetricsRegistryRef`、`MetricsRegistryVersionInfo` 与 `MetricsRegistryProblem`，操作 `RegisterMetric`、`LookupMetric` 与 `ValidateRefs`；先看 `MetricsRegistryEntry` 与 `MetricsRegistryRef` 的字段，再看 `ValidateRefs` 怎么用登记表把引用逐项比对，`MetricsRegistryProblem` 是比对没有通过时的返回项，`LookupMetric` 按指标名给出 `MetricsRegistryVersionInfo`。

```bash public
import aisp.bench.metrics.readme.types as metrics_registry
import aisp.bench.metrics.readme.apis as metrics_registry_api

MetricsRegistryEntry = metrics_registry.MetricsRegistryEntry
MetricsRegistryRef = metrics_registry.MetricsRegistryRef
MetricsRegistryVersionInfo = metrics_registry.MetricsRegistryVersionInfo
MetricsRegistryProblem = metrics_registry.MetricsRegistryProblem
RegisterMetric = metrics_registry_api.RegisterMetric
LookupMetric = metrics_registry_api.LookupMetric
ValidateRefs = metrics_registry_api.ValidateRefs
```

## 背景

指标登记表是校验脚本的输入。任何进入 `recipes/*/metrics.yaml` 的指标，必须先在 `metrics/` 有口径定义，并在 `metrics/registry.yaml` 登记；同一个指标名口径不同，算出来的数就不同，历史结果就不可比，回归全部失效。本目录剩下的两个指标衡量评估集自身是否可信：[覆盖度](coverage.viba.md) 判断评估集是否覆盖目标维度，[scaling 一致性](scaling_consistency.viba.md) 判断外推依据是否成立；被测对象在一个样本上的 SLI 与 SLO 不在本目录，见 [`checkpoint/performance.viba.md`](../checkpoint/performance.viba.md)。

## types.viba

指标登记表的形式化分成类型与枚举两类。登记记录、配方引用、查询结果与校验未通过项写成了类型：`MetricsRegistryEntry` 是一条登记记录，七个字段收下指标名、文档位置、当前版本、支持的版本、可服务的阶段门、单位与方向；`MetricsRegistryRef` 是配方对指标的一次引用，`$gate` 取 `gates.Gate` 的一个取值，`$acceptance_gates` 与 `$compatible_versions` 收下配方在 `acceptance.gates` 与 `compatible_metrics` 里为该指标列出的门与版本；`MetricsRegistryVersionInfo` 是查询结果，收下当前版本与支持的版本；`MetricsRegistryProblem` 是校验未通过的一项，收下出问题的指标名、未通过的那条检查与具体说明。指标名、版本、单位与方向各自写成 `str` 上的类型别名 `MetricsRegistryName`、`MetricsRegistryVersion`、`MetricsRegistryUnit` 与 `MetricsRegistryDirection`，`MetricsRegistryEntry` 与 `MetricsRegistryRef` 的对应字段都取这些别名；校验一个 `MetricsRegistryRef` 就是把它与登记表中的 `MetricsRegistryEntry` 逐项比对。未通过的检查种类写成了枚举：`MetricsRegistryProblemKind` 是 Oneof 枚举，六个取值各对应一条检查，`MetricsRegistryProblem` 的 `$kind` 字段取其中一个取值。

```bash types
import aisp.bench.checkpoint.gates.types as gates

MetricsRegistryName = str * { 指标名；配方的 compatible_metrics 与 metrics.yaml 按这个名字引用指标 }

MetricsRegistryVersion = str * { 指标口径的版本，例如 1.0.0；口径变了就升版本，旧口径保留在文档末尾 }

MetricsRegistryUnit = str * { 单位：口径的一部分，写在指标文档的口径一节；同名指标口径不同，算出来的数就不可比 }

MetricsRegistryDirection = str * { 方向：口径的一部分，写在指标文档的口径一节，说明这个指标的值往哪个方向算变好 }

MetricsRegistryEntry =
  Object
  * $name (MetricsRegistryName * { 指标名；配方的 compatible_metrics 与 metrics.yaml 按这个名字引用指标 })
  * $doc (str * { 指标文档的位置，在 metrics/ 下；一个指标一篇文档，实现放在 checks/，实测值放对象存储、仓库里只写回链，业务结论放配方的 README.viba.md })
  * $version (MetricsRegistryVersion * { 当前版本 })
  * $supported (list[MetricsRegistryVersion] * { 支持的版本；配方使用的版本必须在这个列表里 })
  * $gates (list[gates.Gate] * { 这个指标可服务的阶段门；IO pattern 对齐度服务 G2，scaling 一致性服务 G3；配方声明的 gate 必须是这里列出的之一 })
  * $unit (MetricsRegistryUnit * { 单位：口径的一部分，写在指标文档的口径一节 })
  * $direction (MetricsRegistryDirection * { 方向：口径的一部分，写在指标文档的口径一节 })
  * { 登记表存当前版本、支持的版本、可服务的阶段门与文档位置；单位与方向写在指标文档的口径一节，登记时一并核对 }

MetricsRegistryRef =
  Object
  * $name (MetricsRegistryName * { 配方引用的指标名 })
  * $version (MetricsRegistryVersion * { 配方使用的版本 })
  * $gate (gates.Gate * { 配方为这个指标声明的 gate })
  * $acceptance_gates (list[gates.Gate] * { 配方 acceptance.gates 里列出的门 })
  * $compatible_versions (list[MetricsRegistryVersion] * { 配方 compatible_metrics 里为该指标列出的版本 })

MetricsRegistryProblemKind =
  Oneof
  | "not_registered" * { 指标没有登记 }
  | "version_not_supported" * { 配方使用的版本不在登记表的 supported 里 }
  | "gate_not_declared" * { 配方声明的 gate 不在登记表为该指标列出的 gate 里 }
  | "gate_not_in_acceptance" * { 该 gate 不在配方的 acceptance.gates 里 }
  | "not_compatible" * { 该指标与版本不在配方的 compatible_metrics 里 }
  | "version_not_published" * { compatible_metrics 里为该指标列出的某个版本没有在登记表发布过 }

MetricsRegistryProblem =
  Object
  * $metric (MetricsRegistryName * { 出问题的指标名 })
  * $kind (MetricsRegistryProblemKind * { 哪一条检查没有通过 })
  * $detail (str * { 具体说明，指出缺的是什么 })

MetricsRegistryVersionInfo =
  Object
  * $current (MetricsRegistryVersion * { 当前版本 })
  * $supported (list[MetricsRegistryVersion] * { 支持的版本 })
```

## 基本操作

先在 `metrics/` 下写这个指标的文档：定义、口径、阈值、采集、判定、已知限制、变更记录七项都要有，口径一节写清计算公式、统计范围、时间窗口、单位与方向。

1. 把指标登记进 `metrics/registry.yaml`：写当前版本、支持的版本、可服务的阶段门与文档位置，单位与方向随口径一起核对。
2. 配方写好后用登记表校验引用：指标要已登记，版本要受支持，配方声明的 gate 要是登记表为该指标列出的 gate，该 gate 还要出现在配方的 `acceptance.gates` 里，指标与版本必须出现在 `compatible_metrics` 里。

## apis.viba

```bash apis
import aisp.bench.metrics.readme.types as metrics_registry

RegisterMetric =
     metrics_registry.MetricsRegistryEntry
  <- $entry (metrics_registry.MetricsRegistryEntry * { 要登记的指标条目：指标名、文档位置、当前版本、支持的版本、可服务的阶段门、单位与方向 })
  <- {
    登记一个指标：把条目写进 metrics/registry.yaml；新增指标时文档、登记表、引用它的配方配置三者都要改；返回登记后的条目
  }

LookupMetric =
     (metrics_registry.MetricsRegistryVersionInfo | nil)
  <- $name (metrics_registry.MetricsRegistryName * { 要查的指标名 })
  <- {
    查一个指标的版本：返回当前版本与支持的版本；配方使用的版本与 compatible_metrics 里列出的版本都必须在这个列表里；登记表里没有这个指标时给 nil
  }

ValidateRefs =
     list[metrics_registry.MetricsRegistryProblem]
  <- $refs (list[metrics_registry.MetricsRegistryRef] * { 配方里对指标的引用，一项一个指标；每项带指标名、配方使用的版本、声明的 gate、acceptance.gates 与 compatible_metrics 里的版本 })
  <- $registry (list[metrics_registry.MetricsRegistryEntry] * { 登记表：一项一个指标，提供该指标的版本、支持的版本与可服务的阶段门 })
  <- {
    校验引用：逐条检查指标是否已登记、版本是否受支持、gate 是否在登记表为该指标列出的 gate 里、该 gate 是否在配方的 acceptance.gates 里、该指标与版本是否在 compatible_metrics 里、compatible_metrics 里的版本是否都已发布；返回没有通过的项，空列表表示通过
  }
```

## flow.viba

```bash flow
import aisp.bench.metrics.readme.types as metrics_registry
import aisp.bench.metrics.readme.apis as metrics_registry_api

MetricsRegistryFlow =
  Object
  * $entry (metrics_registry.MetricsRegistryEntry * { 登记表的一条条目：指标名、文档位置、当前版本、支持的版本、可服务的阶段门、单位与方向 })
  * $refs (list[metrics_registry.MetricsRegistryRef] * { 配方里对指标的引用，一项一个指标；校验操作逐条检查它们 })
  * $steps (list[MetricsRegistryStep] * { 登记、查版本、校验引用三个操作，按登记 → 查询 → 校验的顺序 })

MetricsRegistryStep =
  Oneof
  | $register (metrics_registry_api.RegisterMetric * { 登记一个指标：把条目写进 metrics/registry.yaml；新增指标时指标文档与引用它的配方配置也要一起改 })
  | $lookup (metrics_registry_api.LookupMetric * { 查一个指标的版本：返回当前版本与支持的版本，配方引用的版本必须在其中 })
  | $validate (metrics_registry_api.ValidateRefs * { 校验引用：用登记表检查配方对指标的引用，返回没有通过的项；空列表表示通过 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
