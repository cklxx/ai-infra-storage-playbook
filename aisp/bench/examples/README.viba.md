# 样例

## public.viba

只做转发：从 `## 问题` 的 `examples` 模块与 `## 接口` 的 `examples_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布七个名字：类型 `ExampleSampleSet`、`ExampleRunPlan` 与 `ExampleRunResult`，操作 `ListSamples`、`RunAll`、`RunOne` 与 `Verify`；先看 `ExampleSampleSet` 与 `ExampleRunPlan` 这两个输入类型，再按 `ListSamples`、`RunAll`、`RunOne`、`Verify` 的顺序读到 `ExampleRunResult`。

```bash public
import aisp.bench.examples.readme.types as examples
import aisp.bench.examples.readme.apis as examples_api

ExampleSampleSet = examples.ExampleSampleSet
ExampleRunPlan = examples.ExampleRunPlan
ExampleRunResult = examples.ExampleRunResult
ListSamples = examples_api.ListSamples
RunAll = examples_api.RunAll
RunOne = examples_api.RunOne
Verify = examples_api.Verify
```

## 背景

`examples/` 下的文件让校验脚本有可跑通的输入，也让新同学看到各类清单长什么样。所有内容都是样例，不代表任何真实运行。这份文档给出每个样例的用途、正向与负向样例的划分，以及整套和单项的跑法。

## types.viba

问题形式化为 `examples` 模块，概念分成类型与枚举两类。样例路径与极性写成枚举：正向样例的每条路径是 `ExamplePositiveSample` 的一个取值，负向样例的每条路径是 `ExampleNegativeSample` 的一个取值，`ExamplePolarity` 只有 positive 与 negative 两个取值，三者都是 Oneof 枚举。承载字段的结构写成对象类型：`ExampleSampleSet` 的 `$positive` 与 `$negative` 分别是 `ExamplePositiveSample` 与 `ExampleNegativeSample` 的列表，`ExampleAllRun` 与 `ExampleSingleRun` 各收下一种跑法要用的取值，`ExampleRunPlan` 再用 `$all` 与 `$single` 两个分支把这两个对象类型合成一个 Oneof 枚举。判结果的部分同样有类型：`ExampleOutcome` 是只有 accepted 与 rejected 两个取值的 Oneof 枚举，`ExampleRunResult` 由样例路径列表、期望的 `ExamplePolarity` 与实际给出的 `ExampleOutcome` 组成，`ExampleRunReport` 再收下 `ExampleRunResult` 的列表与不一致的样例路径。

```bash types
ExamplePolarity =
  Oneof
  | "positive" * { 正向样例：校验脚本应当接受，让检查有可跑通的输入 }
  | "negative" * { 负向样例：放在 invalid/ 下，校验脚本必须拒绝 }

ExamplePositiveSample =
  Oneof
  | "tiny_model/" * { 最小模型代码与清单条目，演示 recipes/model_code_collection 的产物 }
  | "io-pattern-real.json" * { 真实运行的 IO pattern 记录 }
  | "io-pattern-bypassed.json" * { 旁路运行的记录，偏差在 checkpoint 阈值内 }
  | "coverage.json" * { 覆盖度清单，覆盖度刚好等于阈值 0.6 }
  | "scaling-levels.json" * { 逐级不变量值 }
  | "run-spec.json" * { 提交给评估服务的运行请求，含 storage 两层 }
  | "sli.json" * { 一次运行的 SLI 记录，含存储两层身份 }

ExampleNegativeSample =
  Oneof
  | "invalid/io-pattern-bad-sources.json" * { 只有一层采集来源，记录非法 }
  | "invalid/metrics-unknown-tolerance.yaml" * { 阈值里出现 check 不支持的键 }
  | "invalid/coverage-missing-axis.json" * { 格子缺 arch_family 轴 }
  | "invalid/scaling-bad-lengths.json" * { 不变量值个数与级别数不一致 }
  | "invalid/run-spec-bad-level.json" * { 规模档位不在 S0–S5 里 }
  | "invalid/sli-missing-storage.json" * { SLI 记录缺存储两层身份 }
  | "invalid/recipe-missing-field.yaml" * { 配方缺 metrics_ref }

ExampleSampleSet =
  Object
  * $positive (list[ExamplePositiveSample] * { 正向样例：校验脚本应当接受，让检查有可跑通的输入 })
  * $negative (list[ExampleNegativeSample] * { 负向样例：全部放在 invalid/ 下，必须被拒绝；由 checks/selftest.py 使用，证明检查不只会通过 })

ExampleAllRun =
  Object
  * $command (str * { 整套跑的命令：python3 scripts/run_checks.py })

ExampleSingleRun =
  Object
  * $check (str * { 单独跑一项用的校验脚本：checks/check_io_pattern.py })
  * $real (str * { --real 的取值：examples/io-pattern-real.json，真实运行的 IO pattern 记录 })
  * $bypassed (str * { --bypassed 的取值：examples/io-pattern-bypassed.json，旁路运行的记录，偏差在 checkpoint 阈值内 })
  * $metrics (str * { --metrics 的取值：recipes/checkpoint/metrics.yaml；单独跑一项时阈值从配方读取 })

ExampleRunPlan =
  Oneof
  | $all (ExampleAllRun * { 整套跑：一次跑完全部样例 })
  | $single (ExampleSingleRun * { 单项跑：只跑一个 check，阈值从配方读取 })

ExampleOutcome =
  Oneof
  | "accepted" * { 校验脚本接受这次输入 }
  | "rejected" * { 校验脚本拒绝这次输入 }

ExampleRunResult =
  Object
  * $samples (list[str] * { 这次跑用到的样例路径；整套跑时每个结果只放一个样例，单项跑时放 --real 与 --bypassed 指向的两条 })
  * $expected (ExamplePolarity * { 这次跑期望的极性：正向样例应当 accepted，负向样例应当 rejected })
  * $outcome (ExampleOutcome * { 校验脚本实际给出的结果 })

ExampleRunReport =
  Object
  * $results (list[ExampleRunResult] * { 每次跑一条结果；整套跑时一个样例一条，单项跑时一次跑法一条 })
  * $mismatches (list[str] * { 结果与期望不一致、期望与样例集的正负不一致，或者没有结果的样例路径；空列表表示全部符合 })
```

## 基本操作

解决这个问题需要四个操作。

1. 列样例：交回正向样例与负向样例，并说明每个样例的用途；负向样例放在 `invalid/` 下，必须被拒绝。
2. 整套跑：执行 `python3 scripts/run_checks.py`，一次跑完全部样例。
3. 单项跑：执行 `python3 checks/check_io_pattern.py`，用 `--real`、`--bypassed` 与 `--metrics` 指定输入；单独跑一项时阈值从配方读取，示例里取 `recipes/checkpoint/metrics.yaml`。
4. 判结果：正向样例应当被接受，负向样例应当被拒绝；负向样例由 `checks/selftest.py` 使用，证明检查不只会通过。

## apis.viba

```bash apis
import aisp.bench.examples.readme.types as examples

ListSamples =
     examples.ExampleSampleSet
  <- $root (str * { 样例根目录：examples/，所有样例路径都相对它 })
  <- {
    列样例：交回正向样例与负向样例；正向样例是校验脚本的合法输入，负向样例放在 invalid/ 下，必须被拒绝
  }

RunAll =
     list[examples.ExampleRunResult]
  <- $plan (examples.ExampleAllRun * { 整套跑法：command 取 python3 scripts/run_checks.py })
  <- {
    整套跑：执行 command，一次跑完全部样例；返回每个样例的结果，正向样例期望 accepted，负向样例期望 rejected
  }

RunOne =
     examples.ExampleRunResult
  <- $plan (examples.ExampleSingleRun * { 单项跑法：check、--real、--bypassed 与 --metrics 的取值 })
  <- {
    单项跑：只跑一个 check；单独跑一项时阈值从配方读取，示例取 recipes/checkpoint/metrics.yaml；返回这次跑法的结果
  }

Verify =
     examples.ExampleRunReport
  <- $set (examples.ExampleSampleSet * { 样例集：正向样例与负向样例，用来确认每个样例都有结果 })
  <- $results (list[examples.ExampleRunResult] * { 跑法交回的结果；整套跑时一条一个样例，单项跑时一次跑法一条 })
  <- {
    判结果：逐个样例比对 outcome 与 expected，并确认每个样例的 expected 与它在样例集里的正负一致、且都有结果；正向样例应当 accepted，负向样例应当 rejected。返回结果清单与不一致的样例路径
  }
```

## flow.viba

```bash flow
import aisp.bench.examples.readme.types as examples
import aisp.bench.examples.readme.apis as examples_api

ExampleStep =
  Oneof
  | $list (examples_api.ListSamples * { 第一步：列样例，拿到正向与负向样例及每个样例的用途 })
  | $run_all (examples_api.RunAll * { 整套跑：python3 scripts/run_checks.py })
  | $run_one (examples_api.RunOne * { 单项跑：只跑一个 check，阈值从配方读取 })
  | $verify (examples_api.Verify * { 判结果：正向样例 accepted，负向样例 rejected })

ExampleFlow =
  Object
  * $set (examples.ExampleSampleSet * { 样例集：正向样例与负向样例；每个样例的用途写在取值上 })
  * $plans (list[examples.ExampleRunPlan] * { 跑法：整套跑与单项跑，按需要选 })
  * $results (list[examples.ExampleRunResult] * { 跑法交回的结果；整套跑时一条一个样例，单项跑时一次跑法一条 })
  * $report (examples.ExampleRunReport * { 判结果的产物：结果清单与不一致的样例路径 })
  * $steps (list[ExampleStep] * { 四个操作：列样例、整套跑、单项跑、判结果 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
