# 覆盖度

## public

只做转发：从 `## 问题` 的 `coverage` 模块与 `## 接口` 的 `coverage_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布七个名字：类型 `CoverageManifest`、`CoverageCell`、`CoverageStats` 与 `CoverageVerdict`，操作 `RecordCell`、`ComputeCoverage` 与 `JudgeCoverage`；先看 `CoverageManifest` 与 `RecordCell`，再看 `CoverageStats` 与 `ComputeCoverage`，最后看 `CoverageVerdict` 与 `JudgeCoverage`。

```viba coverage_public
import coverage
import coverage_api

CoverageManifest = coverage.CoverageManifest
CoverageCell = coverage.CoverageCell
CoverageStats = coverage.CoverageStats
CoverageVerdict = coverage.CoverageVerdict
RecordCell = coverage_api.RecordCell
ComputeCoverage = coverage_api.ComputeCoverage
JudgeCoverage = coverage_api.JudgeCoverage
```

## 背景

这份文档定义覆盖度的口径、阈值与判定：覆盖度决定评估集是否够用，它是评估集在目标维度矩阵上的填充程度，用来判断还有哪些场景没测过，也是 playbook 生成下一版评估集的输入。覆盖度按矩阵计算，轴由配方声明，每个格子按最近一次运行的结果记为 covered、failed、stale、gap 或 exempt。覆盖度低于配方的 `coverage_ratio_min` 时不通过、缺口按优先级补；轴是人定的，轴选错了，覆盖度再高也测不到真正的风险。

## coverage

问题形式化为 `coverage` 模块：枚举 `CoverageAxis` 的九个取值是覆盖矩阵的九条轴，枚举 `CoverageCellState` 的五个取值是格子所处的五种状态，其中 `exempt` 状态要配一条 `CoverageExemption`。对象 `CoverageAxisValue` 把一条轴与这条轴上的一个取值配成一对，`$axis` 取 `CoverageAxis` 的一个取值，`$value` 是这条轴上的取值字符串；别名 `CoverageCellKey` 是 `CoverageAxisValue` 的列表，也就是一个格子的坐标。对象 `CoverageCell` 由坐标、状态与可选的 `CoverageExemption` 组成，别名 `CoverageGap` 就是 `CoverageCellKey`，指应有但没有的格子；对象 `CoverageManifest` 收配方声明的轴与全部格子。对象 `CoverageStats` 是计算产物，收分母、已覆盖数、覆盖度、缺口率与 `CoverageGap` 清单；Oneof `CoverageReport` 的两个分支分别携带 `CoverageStats` 与清单非法的原因；对象 `CoverageThreshold` 单独收通过判定用的 `$coverage_ratio_min`；Oneof `CoverageVerdict` 的取值是 `pass`、`fail`、`incomparable`，由 `CoverageReport` 与 `CoverageThreshold` 判定得到。

```viba coverage
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

CoverageCellKey = list[CoverageAxisValue] * { 格子的坐标：清单声明的每条轴上一个取值；轴至少三项，且必须包含 arch_family }

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

CoverageThreshold =
  Object
  * $coverage_ratio_min (float * { 唯一参与通过判定的阈值；写在配方的 metrics.yaml 的 tolerance 里；阶段目标在 params.targets，是规划目标，不参与通过判定 })

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

CoverageVerdict =
  Oneof
  | "pass" * { 通过：覆盖度 ≥ coverage_ratio_min }
  | "fail" * { 不通过：覆盖度低于阈值；缺口按优先级排序 }
  | "incomparable" * { 不可比：清单缺轴或者状态未知；重跑 }
```

## 基本操作

解决这个问题需要四个操作。登记格子：按最近一次运行的结果，把一条格子的状态写进覆盖度清单，清单由评估服务在每次运行后更新。算覆盖率：按清单算覆盖度与缺口率，exempt 不进分母，豁免过期自动转为 gap，缺口按优先级排序。判定是否够：用覆盖度对照配方 metrics.yaml 里的 coverage_ratio_min，大于或等于阈值判通过，低于阈值判不通过；清单缺轴或状态未知时判不可比，重跑。登记豁免：对明确不需要覆盖的格子记下理由与复核日期，写进清单，状态记为 exempt；超过复核日期自动转为 gap。

## coverage_api

```viba coverage_api
import coverage

RecordCell =
     coverage.CoverageManifest
  <- $manifest (coverage.CoverageManifest * { 当前的覆盖度清单；记录配方声明的轴与已有格子；覆盖度清单的 JSON 结构见 schemas/coverage.schema.json，放对象存储，仓库里只放 schema 与计算脚本 })
  <- $cell (coverage.CoverageCell * { 要登记的那条格子：轴上的取值组合与状态；state 为 exempt 时还要带理由与复核日期 })
  <- { 登记格子：按最近一次运行的结果把一条格子的状态写进覆盖度清单，清单由评估服务在每次运行后更新；返回更新后的清单 }

ComputeCoverage =
     coverage.CoverageReport
  <- $manifest (coverage.CoverageManifest * { 要计算的覆盖度清单；记录配方声明的轴与已有格子 })
  <- { 算覆盖率：按清单算覆盖度 = covered 格子数 / (covered + failed + stale + gap) 格子数，缺口率 = gap 格子数 / 分母；exempt 不进分母，豁免过期自动转为 gap；缺口按优先级排序。返回分母、已覆盖数、覆盖度、缺口率与缺口清单；清单缺轴或状态未知时返回不可比及原因 }

JudgeCoverage =
     coverage.CoverageVerdict
  <- $report (coverage.CoverageReport * { 算覆盖率交回的清单结果；合法的统计与不可比的原因都收 })
  <- $threshold (coverage.CoverageThreshold * { 配方 metrics.yaml 的 tolerance 里的 coverage_ratio_min；唯一参与通过判定的阈值 })
  <- { 判定是否够：覆盖度 ≥ coverage_ratio_min 判通过；低于阈值判不通过，缺口按优先级排序；豁免过期转为缺口后重新计算；清单非法（缺轴、状态未知）判不可比，重跑。阶段目标在 params.targets，不参与通过判定 }

GrantExemption =
     coverage.CoverageManifest
  <- $manifest (coverage.CoverageManifest * { 当前的覆盖度清单；记录配方声明的轴与已有格子 })
  <- $key (coverage.CoverageCellKey * { 要豁免的格子：轴上的取值组合 })
  <- $reason (str * { 明确判定不需要覆盖的理由 })
  <- $review_due (str * { 复核日期；超过它豁免自动转为 gap })
  <- { 登记豁免：明确判定这个格子不需要覆盖，记下理由与复核日期，把这条格子按 exempt 状态写进覆盖度清单；exempt 不进分母；超过复核日期后自动转为 gap。返回更新后的清单 }
```

## coverage_flow

```viba coverage_flow
import coverage
import coverage_api

CoverageStep =
  Oneof
  | $record (coverage_api.RecordCell * { 每次运行后：按最近一次运行的结果登记格子，写进清单 })
  | $exempt (coverage_api.GrantExemption * { 明确不需要覆盖时：登记豁免，把 exempt 格子写进清单 })
  | $compute (coverage_api.ComputeCoverage * { 汇总时：按清单算覆盖度与缺口率，豁免过期转为 gap })
  | $judge (coverage_api.JudgeCoverage * { 判定是否够：用覆盖度对照 coverage_ratio_min })

CoverageFlow =
  Object
  * $manifest (coverage.CoverageManifest * { 覆盖度清单：配方声明的轴与全部格子；登记与豁免的产物，放对象存储 })
  * $threshold (coverage.CoverageThreshold * { 配方 metrics.yaml 的 coverage_ratio_min；唯一参与通过判定的阈值 })
  * $steps (list[CoverageStep] * { 四个操作：先登记格子或豁免，再算覆盖率，最后判定 })
  * $report (coverage.CoverageReport * { 算覆盖率的产物：清单合法时给统计，非法时给不可比原因 })
  * $verdict (coverage.CoverageVerdict * { 判定的产物：通过、不通过或不可比 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
