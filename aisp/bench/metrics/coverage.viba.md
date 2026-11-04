# 覆盖度

## 需求背景

挑样本按覆盖缺口走：清单里哪些格子已经覆盖、哪些还空着。覆盖度清单、覆盖率与缺口清单由本篇定义，挑样本与补缺口都从这里取。

## public.viba

```bash public
import aisp.bench.metrics.coverage.types as coverage
import aisp.bench.metrics.coverage.apis as coverage_api

CoverageAxis = coverage.CoverageAxis
CoverageAxisValue = coverage.CoverageAxisValue
CoverageCellKey = coverage.CoverageCellKey
CoverageCellState = coverage.CoverageCellState
CoverageExemption = coverage.CoverageExemption
CoverageCell = coverage.CoverageCell
CoverageGap = coverage.CoverageGap
CoverageManifest = coverage.CoverageManifest
CoverageStats = coverage.CoverageStats
CoverageReport = coverage.CoverageReport
ComputeCoverage = coverage_api.ComputeCoverage
```

## types.viba

问题形式化为 `coverage` 模块：枚举 `CoverageAxis` 的九个取值是覆盖矩阵的九条轴，枚举 `CoverageCellState` 的五个取值是格子所处的五种状态，其中 `exempt` 状态要配一条 `CoverageExemption`。对象 `CoverageAxisValue` 把一条轴与这条轴上的一个取值配成一对，`$axis` 取 `CoverageAxis` 的一个取值，`$value` 是这条轴上的取值字符串；别名 `CoverageCellKey` 是 `CoverageAxisValue` 的列表，也就是一个格子的坐标。对象 `CoverageCell` 由坐标、状态与可选的 `CoverageExemption` 组成，别名 `CoverageGap` 就是 `CoverageCellKey`，指应有但没有的格子；对象 `CoverageManifest` 收配方声明的轴与全部格子。对象 `CoverageStats` 是计算产物，收分母、已覆盖数、覆盖度、缺口率与 `CoverageGap` 清单；Oneof `CoverageReport` 的两个分支分别携带 `CoverageStats` 与清单非法的原因。

```bash types
CoverageAxis =
  Oneof
  | "arch_family" * { 覆盖矩阵的一维：架构族；每份配方的轴集合至少三项，且必须包含它 }
  | "model_scale" * { 覆盖矩阵的一维：模型规模 }
  | "attention" * { 覆盖矩阵的一维：attention 变体 }
  | "framework" * { 覆盖矩阵的一维：框架 }
  | "parallel" * { 覆盖矩阵的一维：并行策略 }
  | "cluster" * { 覆盖矩阵的一维：集群 }
  | "io_feature" * { 覆盖矩阵的一维：IO 特征 }
  | "storage_backend" * { 覆盖矩阵的一维：存储后端 }
  | "storage_adapter" * { 覆盖矩阵的一维：存储适配层 }

CoverageAxisValue =
  Object
  * $axis (CoverageAxis * { 这个取值属于哪一条轴 })
  * $value (str * { 这条轴上的取值；具体取值由配方决定，不在 schema 里固定 })

CoverageCellKey =
  list[CoverageAxisValue]
  * { 格子的坐标：清单声明的每条轴上一个取值；轴至少三项，且必须包含 arch_family }

CoverageCellState =
  Oneof
  | "covered" * { 至少一个用例，最近一次运行通过；计入分母，计入已覆盖 }
  | "failed" * { 有用例，最近一次运行不通过；计入分母，不计入已覆盖 }
  | "stale" * { 有用例，超过一个版本周期未运行；计入分母，不计入已覆盖 }
  | "gap" * { 应该有但没有；计入分母，不计入已覆盖 }
  | "exempt" * { 明确判定不需要覆盖，有理由与复核日期；不计入分母，也不计入已覆盖；超过复核日期自动转为 gap }

CoverageExemption =
  Object
  * $reason (str * { 明确判定不需要覆盖的理由 })
  * $review_due (str * { 复核日期；超过它豁免自动转为 gap })

CoverageCell =
  Object
  * $key (CoverageCellKey * { 格子的坐标：每条轴上的取值组合 })
  * $state (CoverageCellState * { 这个格子的状态，决定是否计入分母、是否计入已覆盖 })
  * $exemption ((CoverageExemption | nil) * { 这个格子的豁免；state 为 exempt 时必须有理由与复核日期，其余状态给 nil })

CoverageGap = CoverageCellKey * { 缺口：应该有但没有的格子；豁免过期后转成的格子也是缺口；缺口清单按优先级排序 }

CoverageManifest =
  Object
  * $axes (list[CoverageAxis] * { 配方声明的轴，写在 metrics.yaml 的 params.axes；至少三项，且必须包含 arch_family })
  * $cells (list[CoverageCell] * { 清单里的全部格子；清单由评估服务在每次运行后更新 })

CoverageStats =
  Object
  * $denominator (int * { 计入分母的格子数：covered + failed + stale + gap；exempt 不进分母 })
  * $covered (int * { covered 格子数：至少一个用例，最近一次运行通过；覆盖度的分子 })
  * $ratio (float * { 覆盖度 = covered 格子数 / 分母；只表示通过用例存在，不表示该格子的 IO 特征被充分覆盖，同一格子内的样本可能高度相似；对用例数量敏感，批量加入相似用例会虚高，要配合结构距离分布一起看 })
  * $gap_ratio (float * { 缺口率 = gap 格子数 / 分母 })
  * $gaps (list[CoverageGap] * { 缺口清单；按优先级排序，排在前面的先补 })

CoverageReport =
  Oneof
  | $computed (CoverageStats * { 清单合法：给出分母、已覆盖数、覆盖度、缺口率与缺口清单 })
  | $invalid (str * { 清单非法：缺轴（至少三项且必须包含 arch_family）或者状态未知；不可比，要重跑，这里给出原因 })
```

## 基本操作

只有一个操作：算覆盖率。按清单算覆盖度与缺口率，exempt 不进分母，豁免过期自动转为 gap，缺口按优先级排序；清单缺轴或状态未知时返回不可比及原因。

## apis.viba

```bash apis
import aisp.bench.metrics.coverage.types as coverage

ComputeCoverage =
     coverage.CoverageReport
  <- $manifest (coverage.CoverageManifest * { 要计算的覆盖度清单；记录配方声明的轴与已有格子 })
  <- {
    算覆盖率：按清单算覆盖度 = covered 格子数 / (covered + failed + stale + gap) 格子数，缺口率 = gap 格子数 / 分母；exempt 不进分母，豁免过期自动转为 gap；缺口按优先级排序。返回分母、已覆盖数、覆盖度、缺口率与缺口清单；清单缺轴或状态未知时返回不可比及原因
  }
```
