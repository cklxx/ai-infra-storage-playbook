# Scaling 一致性

## 背景

从较小规模外推到较大规模时，必须逐级验证声明的 scaling 不变量是否仍保持在容差内，外推依据才算成立。本文定义逐级记录、偏差计算、阈值来源与五种判定结论，它是阶段门 G3 的门槛；当前版本 1.0.0。

## 问题

```viba scaling_consistency
import gates
import levels

ScalingConsistencySpec =
  Object
  * $ladder (ScalingConsistencyLadder * Hint[{ 逐级记录：每一级运行的度量值 }])
  * $invariants (list[ScalingConsistencyInvariant] * Hint[{ 声明的 scaling 不变量：名字、偏差口径、自己的容差 }])
  * $tolerance (ScalingConsistencyTolerance * Hint[{ 默认容差：per_level 与 first_last，写在配方的 metrics.yaml }])
  * $verdicts (list[ScalingConsistencyVerdict] * Hint[{ 判定结论的五种取值 }])
  * $limits (list[ScalingConsistencyLimit] * Hint[{ 已知限制：这个指标测不出什么 }])
  * $gate (gates.Gate * Hint[{ 这个指标是阶段门 G3 的门槛 }])
  * $checker (str * Hint[{ 计算脚本：checks/check_scaling_consistency.py；脚本只知道输入里有几级，不知道配方应该有几级 }])

ScalingConsistencyLadder =
  Object
  * $levels (list[ScalingConsistencyLevelRecord] * Hint[{ 每一级的记录，按规模从小到大排；与配方 scaling_plan.levels 是否一致由评审检查 }])

ScalingConsistencyLevelRecord =
  Object
  * $level (levels.Level * Hint[{ 这一级的规模档位，取值见 levels.Level；输入文件里的取值必须匹配 ^S[0-9]+$ }])
  * $values (dict[str, ScalingConsistencyMeasurement] * Hint[{ 这一级上每条不变量的实测值，键是不变量名；任一级缺数据判不可比 }])

ScalingConsistencyMeasurement =
  Oneof
  | $scalar (float * Hint[{ 标量值；相邻级偏差按这条不变量的口径算 }])
  | $distribution (list[float] * Hint[{ 分布值：按与 IO pattern 对齐度相同的分桶方式切出的各桶数值；相邻级偏差改用分布距离 }])

ScalingConsistencyInvariant =
  Object
  * $name (str * Hint[{ 不变量名，例如 per_parameter_bytes、write_concurrency_p50；与每一级记录里的键对应 }])
  * $mode (ScalingConsistencyDeviationMode * Hint[{ 这条不变量的值按哪种口径算偏差 }])
  * $tolerance ((float | nil) * Hint[{ 这条不变量自己的容差；需要更宽或更紧时在输入文件里写，不写就用配方的 per_level；两边都没有时报错，不给默认值 }])

ScalingConsistencyDeviationMode =
  Oneof
  | "relative" * Hint[{ 默认口径：|值(Si) - 值(Si-1)| / 值(Si-1) }]
  | "absolute" * Hint[{ 值接近 0 时改用绝对差，阈值单独声明 }]
  | "distribution" * Hint[{ 值是分布时改用分布距离，分桶方式与 IO pattern 对齐度相同 }]

ScalingConsistencyTolerance =
  Object
  * $per_level (float * Hint[{ 相邻级偏差的默认容差，默认 0.10（即 10%），写在配方 metrics.yaml 的 tolerance.per_level }])
  * $first_last (float * Hint[{ 首末级总偏差的容差，默认 0.15（即 15%），写在 tolerance.first_last }])

ScalingConsistencyComparison =
  Object
  * $invariant (str * Hint[{ 这条偏差属于哪条不变量 }])
  * $from (levels.Level * Hint[{ 这一对里较小的一级 }])
  * $to (levels.Level * Hint[{ 这一对里较大的一级 }])
  * $deviation (float * Hint[{ 这一对的偏差，按这条不变量的口径算：相对偏差、绝对差或分布距离 }])
  * $tolerance (float * Hint[{ 这一对使用的容差：相邻级用不变量自己的或 per_level，首末级用 first_last }])
  * $within (bool * Hint[{ 偏差是否在这个容差内 }])

ScalingConsistencyComparisonSet =
  Object
  * $adjacent (list[ScalingConsistencyComparison] * Hint[{ 每一对相邻级的偏差，按不变量与级顺序排 }])
  * $first_last (list[ScalingConsistencyComparison] * Hint[{ 每条不变量的首末级总偏差 }])
  * $max_adjacent ((list[ScalingConsistencyComparison] | nil) * Hint[{ 每条不变量的最大相邻偏差；不小于三级时报告，不足三级时给 nil }])
  * $comparable (bool * Hint[{ 每一级都有完整数据、每条不变量都拿得到容差时才可比；与配方 scaling_plan.levels 是否一致由评审检查 }])
  * $incomparable_reason ((str | nil) * Hint[{ 不可比的原因：任一级缺数据或阈值缺失；可比时给 nil }])

ScalingConsistencyDirection =
  Oneof
  | "up" * Hint[{ 这一级的值比上一级高 }]
  | "down" * Hint[{ 这一级的值比上一级低 }]
  | "flat" * Hint[{ 这一级的值与上一级相等，不算漂移方向 }]

ScalingConsistencyDrift =
  Object
  * $invariant (str * Hint[{ 检查的是哪条不变量 }])
  * $directions (list[ScalingConsistencyDirection] * Hint[{ 相邻级的变化方向，按级顺序，每一对一项 }])
  * $monotonic (bool * Hint[{ 偏差随规模的变化是否单调漂移：每一级的值都朝同一方向变化；即使每级都在容差内，也说明不变量选错了 }])

ScalingConsistencyAttribution =
  Object
  * $invariant (str * Hint[{ 哪条不变量的偏差超出容差 }])
  * $detail ((str | nil) * Hint[{ 有归因且不影响目标结论时写明归因；归因不明时给 nil }])

ScalingConsistencyVerdict =
  Oneof
  | "consistent" * Hint[{ 一致，允许外推：全部不变量在全部级别容差内，无单调漂移 }]
  | "conditionally_consistent" * Hint[{ 有条件一致，需评审：有不变量超出容差，偏差有归因且不影响目标结论 }]
  | "inconsistent" * Hint[{ 不一致，停止外推：有不变量超出容差，归因不明 }]
  | "wrong_invariant" * Hint[{ 不变量选错，停止外推：有不变量在容差内但单调漂移 }]
  | "incomparable" * Hint[{ 不可比，补齐后再算：任一级缺数据、阈值缺失 }]

ScalingConsistencyJudgement =
  Object
  * $verdict (ScalingConsistencyVerdict * Hint[{ 这次判定的结论 }])
  * $drift (list[ScalingConsistencyDrift] * Hint[{ 每条不变量的漂移检查结果 }])
  * $failed_invariants (list[str] * Hint[{ 没通过的不变量：超出容差或单调漂移的那些；结论为一致时为空 }])

ScalingConsistencyLimit =
  Oneof
  | "form_only" * Hint[{ 一致性成立只说明外推的形式依据成立，不说明外推后的绝对数值一定准 }]
  | "few_invariants" * Hint[{ 不变量选得少时容易通过，但外推可信度低；指标本身不能防止选错不变量 }]
  | "one_dimension" * Hint[{ 只沿一个维度放大时结论清晰；多维度同时放大时必须分别计算，不能合并成一个数 }]

ScalingConsistencyReport =
  Object
  * $ladder (ScalingConsistencyLadder * Hint[{ 报告覆盖的逐级记录 }])
  * $comparisons (ScalingConsistencyComparisonSet * Hint[{ 相邻级偏差、首末级总偏差、最大相邻偏差与可比性 }])
  * $tolerance (ScalingConsistencyTolerance * Hint[{ 这次判定使用的默认容差 }])
  * $judgement (ScalingConsistencyJudgement * Hint[{ 判定结论、漂移检查与没通过的不变量 }])
```

## 基本操作

登记一级：每一级运行结束后，把这一级上每条不变量的实测值登记进来，得到按规模从小到大排的逐级记录。登记齐之后比较相邻级：对每条不变量算出每一对相邻级的偏差，与它自己的容差或配方的 per_level 比较，同时算出首末级总偏差，不小于三级时再给出最大相邻偏差。然后判定：每条不变量的相邻级偏差在它自己的容差内，首末级总偏差在 first_last 内，且没有单调漂移，判为一致、允许外推；有不变量超出容差时看归因，有归因且不影响目标结论判为有条件一致、需评审，归因不明判为不一致、停止外推。有不变量在容差内但单调漂移，判为不变量选错、停止外推；任一级缺数据或阈值缺失，判为不可比、补齐后再算。最后报告：把逐级记录、偏差、漂移检查与判定结论汇总成一份报告。阈值默认值写在配方的 metrics.yaml，单条不变量可以在输入文件里写自己的 tolerance 覆盖 per_level，两边都没有时报错，不给默认值。

## 接口

```viba scaling_consistency_api
import scaling_consistency

RecordLevel =
     scaling_consistency.ScalingConsistencyLadder
  <- $ladder (scaling_consistency.ScalingConsistencyLadder * Hint[{ 已经登记的逐级记录 }])
  <- $record (scaling_consistency.ScalingConsistencyLevelRecord * Hint[{ 这一级的档位与每条不变量的实测值 }])
  <- Hint[{ 登记一级：把这一级的实测值追加到逐级记录里，按规模从小到大排；任一级缺数据判不可比。返回登记后的逐级记录 }]

CompareAdjacent =
     scaling_consistency.ScalingConsistencyComparisonSet
  <- $ladder (scaling_consistency.ScalingConsistencyLadder * Hint[{ 已登记的逐级记录 }])
  <- $invariants (list[scaling_consistency.ScalingConsistencyInvariant] * Hint[{ 参与比较的不变量：名字、偏差口径、自己的容差 }])
  <- $tolerance (scaling_consistency.ScalingConsistencyTolerance * Hint[{ 默认容差：不变量没写 tolerance 时用 per_level，首末级用 first_last }])
  <- Hint[{ 比较相邻级：对每条不变量算出每一对相邻级的偏差，落在它自己的容差或 per_level 内就记为在容差内；同时算出首末级总偏差，不小于三级时再给出最大相邻偏差。任一级缺数据或阈值缺失时记为不可比。返回这些偏差与可比性 }]

Judge =
     scaling_consistency.ScalingConsistencyJudgement
  <- $ladder (scaling_consistency.ScalingConsistencyLadder * Hint[{ 已登记的逐级记录；用来检查每一级是否朝同一方向漂移 }])
  <- $comparisons (scaling_consistency.ScalingConsistencyComparisonSet * Hint[{ 比较相邻级得到的偏差 }])
  <- $attribution (list[scaling_consistency.ScalingConsistencyAttribution] * Hint[{ 超出容差的不变量各自怎么归因；每条带不变量名与说明，归因不明时说明为 nil }])
  <- Hint[{ 判定：按三件事判——每条不变量的相邻级偏差在它自己的容差内，首末级总偏差在 first_last 内，逐级值没有单调漂移；有不变量超出容差时看归因；任一级缺数据或阈值缺失时判不可比。返回五种结论之一、每条不变量的漂移检查与没通过的不变量 }]

Report =
     scaling_consistency.ScalingConsistencyReport
  <- $ladder (scaling_consistency.ScalingConsistencyLadder * Hint[{ 参与判定的逐级记录 }])
  <- $comparisons (scaling_consistency.ScalingConsistencyComparisonSet * Hint[{ 相邻级偏差、首末级总偏差与最大相邻偏差 }])
  <- $tolerance (scaling_consistency.ScalingConsistencyTolerance * Hint[{ 这次判定使用的默认容差 }])
  <- $judgement (scaling_consistency.ScalingConsistencyJudgement * Hint[{ 判定结论、漂移检查与没通过的不变量 }])
  <- Hint[{ 报告：汇总逐级记录、偏差、漂移检查与判定结论。返回一份报告 }]
```

## 组织

```viba scaling_consistency_flow
import scaling_consistency
import scaling_consistency_api

ScalingConsistencyRecordDuty =
  Object
  * $step (scaling_consistency_api.RecordLevel * Hint[{ 登记一级：把这一级的实测值追加到逐级记录 }])
  * $ladder (scaling_consistency.ScalingConsistencyLadder * Hint[{ 这一步的产物：登记后的逐级记录 }])

ScalingConsistencyCompareDuty =
  Object
  * $step (scaling_consistency_api.CompareAdjacent * Hint[{ 比较相邻级：算出相邻级偏差、首末级总偏差与最大相邻偏差 }])
  * $comparisons (scaling_consistency.ScalingConsistencyComparisonSet * Hint[{ 这一步的产物：偏差 }])

ScalingConsistencyJudgeDuty =
  Object
  * $step (scaling_consistency_api.Judge * Hint[{ 判定：按三件事给出五种结论之一 }])
  * $judgement (scaling_consistency.ScalingConsistencyJudgement * Hint[{ 这一步的产物：结论、漂移检查与没通过的不变量 }])

ScalingConsistencyReportDuty =
  Object
  * $step (scaling_consistency_api.Report * Hint[{ 报告：汇总逐级记录、偏差、漂移检查与判定结论 }])
  * $report (scaling_consistency.ScalingConsistencyReport * Hint[{ 这一步的产物：一份报告 }])

ScalingConsistencyFlow =
  Object
  * $spec (scaling_consistency.ScalingConsistencySpec * Hint[{ 问题定义：逐级记录、不变量值、偏差判定 }])
  * $record (ScalingConsistencyRecordDuty * Hint[{ 第一步：登记一级 }])
  * $compare (ScalingConsistencyCompareDuty * Hint[{ 第二步：比较相邻级 }])
  * $judge (ScalingConsistencyJudgeDuty * Hint[{ 第三步：判定 }])
  * $report (ScalingConsistencyReportDuty * Hint[{ 第四步：报告 }])
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
