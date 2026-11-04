# 校验脚本

## public.viba

只做转发：从 `## 问题` 的 `checks` 模块与 `## 接口` 的 `checks_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布七个名字：类型 `CheckScript`、`CheckArgs`、`CheckOutput`、`CheckStatus` 与 `CheckExitCode`，操作 `RunCheck` 与 `RunAllChecks`；先看 `CheckScript`、`CheckArgs` 与 `CheckOutput`，弄清一个脚本收什么输入、往标准输出写什么，再看 `CheckStatus` 与 `CheckExitCode` 怎么判定，最后按 `RunCheck`、`RunAllChecks` 的顺序读。

```bash public
import aisp.bench.checks.readme.types as checks
import aisp.bench.checks.readme.apis as checks_api

CheckScript = checks.CheckScript
CheckArgs = checks.CheckArgs
CheckOutput = checks.CheckOutput
CheckStatus = checks.CheckStatus
CheckExitCode = checks.CheckExitCode
RunCheck = checks_api.RunCheck
RunAllChecks = checks_api.RunAllChecks
```

## 背景

这份文档说明本目录的通用校验脚本怎么用：本目录放通用校验，只对这个评估集成立的校验放 `recipes/<name>/checks/`。文档逐个说明五个脚本的作用、入参、退出码，以及阈值来源、输出约定、目录约定与依赖安装。

## types.viba

问题形式化为一个模块：`checks` 定义五个脚本、每个脚本的输入、输出、退出码与依赖，以及阈值来源、目录约定与指标文档的对应关系。

```bash types
import aisp.bench.checkpoint.scaling.types as levels

CheckScript =
  Oneof
  | "validate_repo" * { 校验配方与 schema、指标登记表、阈值引用的一致性 }
  | "selftest" * { 用 examples/ 与 examples/invalid/ 证明检查会通过、也会拒绝 }
  | "check_io_pattern" * { 比较真实运行与旁路运行的 IO pattern }
  | "check_coverage" * { 从覆盖度清单计算覆盖度与缺口 }
  | "check_scaling_consistency" * { 计算逐级偏差与单调漂移 }

CheckArgs =
  Oneof
  | $validate_repo (nil * { 这个脚本不收参数 })
  | $selftest (nil * { 这个脚本不收参数；用例来自 examples/ 与 examples/invalid/ })
  | $check_io_pattern (CheckIoPatternArgs * { check_io_pattern.py 的输入：--real、--bypassed、--metrics 与 --tolerance })
  | $check_coverage (CheckCoverageArgs * { check_coverage.py 的输入：--manifest、--metrics 与 --min-coverage })
  | $check_scaling_consistency (CheckScalingArgs * { check_scaling_consistency.py 的输入：--input 与 --metrics })

CheckIoPatternArgs =
  Object
  * $real (str * { --real 的取值：要比对的真实运行 })
  * $bypassed (str * { --bypassed 的取值：要比对的旁路运行 })
  * $metrics (str * { --metrics 的取值：recipes/<name>/metrics.yaml；阈值唯一来源，脚本读同一份文件，不在代码里保留默认值 })
  * $tolerance ((str | nil) * { --tolerance 的取值：逐项覆盖阈值的文件，一个 JSON 对象，键是指标项名，值是数字或百分号字符串，例如键 concurrency_p95、值 20%；只用于临时排查，不能作为结论依据 })

CheckCoverageArgs =
  Object
  * $manifest (str * { --manifest 的取值：覆盖度清单；JSON 结构见 schemas/coverage.schema.json })
  * $metrics (str * { --metrics 的取值：阈值来源 recipes/<name>/metrics.yaml，coverage_ratio_min 从这里读 })
  * $min_coverage ((float | nil) * { --min-coverage 的取值：临时覆盖 coverage_ratio_min；只用于临时排查，不能作为结论依据 })

CheckScalingArgs =
  Object
  * $input (str * { --input 的取值：一个文件，内容是 CheckScalingInput })
  * $metrics (str * { --metrics 的取值：默认容差来源 recipes/<name>/metrics.yaml，per_level 与 first_last 从这里读 })

CheckScalingInput =
  Object
  * $levels (list[levels.Level] * { 逐级比较的级别，按 S0 起的顺序；级别定义见 scaling.viba.md })
  * $invariants (dict[str, CheckScalingInvariant] * { 不变量名到这一条不变量的逐级数据 })

CheckScalingInvariant =
  Object
  * $values (list[float] * { 这条不变量逐级的实测值 })
  * $tolerance ((float | nil) * { 这条不变量的容差，可省略；省略时用 metrics.yaml 的 per_level })

CheckStatus =
  Oneof
  | "pass" * { 通过 }
  | "fail" * { 不通过 }
  | "skip" * { 跳过：缺依赖、输入缺失或阈值缺失都算跳过；跳过不等于通过 }

CheckExitCode =
  Oneof
  | 0 * { 通过、符合预期、达标或一致 }
  | 1 * { 不通过、不符合、未达标或不一致 }
  | 2 * { 缺依赖、输入非法或缺阈值 }

CheckOutcome =
  Object
  * $status (CheckStatus * { 这个脚本给出的状态 })
  * $exit_code (CheckExitCode * { 状态对应的退出码：pass 对 0，fail 对 1，skip 对 2 })

CheckJsonLine =
  Object
  * $check (str * { 写进输出字段 check 的脚本名 })
  * $status (CheckStatus * { 写进输出字段 status 的状态；通过、失败、跳过三态必须区分；输出至少包含 check 与 status 两个字段，可有其它字段 })

CheckReadableOutput =
  Object
  * $items (list[str] * { 逐项结果 })
  * $errors (list[str] * { 错误清单 })

CheckOutput =
  Oneof
  | $json_line (CheckJsonLine * { check_*.py 与 selftest.py：在标准输出打印一行 JSON，至少包含 check 与 status })
  | $readable (CheckReadableOutput * { validate_repo.py：打印人读的逐项结果与错误清单，不使用单行 JSON })

CheckDependency =
  Object
  * $install (str * { 安装依赖的命令：pip install -r ../requirements.txt })
  * $missing_status (CheckStatus * { 缺依赖时的状态：skip，不假装通过 })
  * $missing_exit_code (CheckExitCode * { 缺依赖时的退出码：2 })

CheckScriptSpec =
  Object
  * $script (CheckScript * { 这个脚本是哪一个 })
  * $args (CheckArgs * { 这个脚本收什么输入；变体与 script 一一对应 })
  * $output (CheckOutput * { 这个脚本往标准输出写什么 })
  * $outcomes (list[CheckOutcome] * { 这个脚本可能给出的状态与退出码：0 通过、符合预期、达标或一致；1 不通过、不符合、未达标或不一致；2 缺依赖、输入非法或缺阈值 })
  * $dependency (CheckDependency * { 这个脚本的依赖与缺依赖时的行为；依赖用 pip install -r ../requirements.txt 安装 })

CheckToleranceValue =
  Oneof
  | $number (float * { 小数值，例如 0.08 表示 8% })
  | $percent (str * { 百分号字符串，例如 "8%" })

CheckMetricItem =
  Oneof
  | "request_size_distribution" * { check_io_pattern.py 支持的度量项：请求大小分布 }
  | "read_write_ratio_bytes" * { check_io_pattern.py 支持的度量项：按字节数的读写比 }
  | "read_write_ratio_ops" * { check_io_pattern.py 支持的度量项：按请求数的读写比 }
  | "concurrency_p50" * { check_io_pattern.py 支持的度量项：并发度 P50 }
  | "concurrency_p95" * { check_io_pattern.py 支持的度量项：并发度 P95 }
  | "concurrency_max" * { check_io_pattern.py 支持的度量项：并发度峰值 }
  | "sequentiality" * { check_io_pattern.py 支持的度量项：顺序性 }
  | "hotness" * { check_io_pattern.py 支持的度量项：热度 }
  | "per_token_kv_bytes" * { check_io_pattern.py 支持的度量项：每 token 的 KV 字节数 }
  | "timing_peak" * { check_io_pattern.py 支持的度量项：时序峰值 }

CheckThresholdSource =
  Oneof
  | "metrics_yaml" * { 唯一来源：recipes/<name>/metrics.yaml 的 tolerance，由评审把关；脚本通过 --metrics 读同一份文件，不在代码里保留默认值 }
  | "command_line" * { --tolerance 与 --min-coverage 临时覆盖；只用于临时排查，不能作为结论依据 }

CheckThreshold =
  Object
  * $source (CheckThresholdSource * { 阈值从哪里来；结论只能依据 metrics_yaml 的阈值 })
  * $tolerance (dict[str, CheckToleranceValue] * { 阈值表；键必须是该 check 支持的度量项名，未知键直接报错退出 2；值可以是小数或百分号字符串；check_io_pattern.py 支持的十项见 CheckMetricItem })
  * $items ((list[str] | nil) * { 本配方判定哪些项；必须与 tolerance 的键完全一致；没有 items 时以 tolerance 的键为准 })

CheckDirectoryRule =
  Oneof
  | "template" * { recipes/ 下以 _ 开头的目录是模板，validate_repo.py 跳过它们 }
  | "negative_case" * { 负例放在 examples/invalid/，由 selftest.py 使用；不作为正向样例 }
  | "case_pair" * { 新增检查时同时补一条正向与一条负向用例，否则 selftest 覆盖不到 }

CheckDocLink =
  Object
  * $script (CheckScript * { 哪个脚本 })
  * $doc (str * { metrics/ 下对应的那篇文档；每个脚本对应一篇，公式必须一致；改公式时两边一起改，并在指标文档的变更记录里写一行 })

CheckRun =
  Object
  * $script (CheckScript * { 这次跑的是哪个脚本 })
  * $output (CheckOutput * { 这个脚本往标准输出写了什么 })
  * $outcome (CheckOutcome * { 这次运行的状态与退出码 })

CheckBatch =
  Object
  * $runs (list[CheckRun] * { 五个脚本各自的一次运行：输出、状态与退出码 })

CheckSpec =
  Object
  * $scripts (list[CheckScriptSpec] * { 五个脚本逐个说明输入、输出、退出码与依赖 })
  * $threshold (CheckThreshold * { 阈值只有一个来源：配方的 metrics.yaml；--tolerance 与 --min-coverage 只用于临时排查 })
  * $directories (list[CheckDirectoryRule] * { 目录约定：模板目录、负例目录与新增检查的用例要求 })
  * $doc_links (list[CheckDocLink] * { 每个脚本对应 metrics/ 的一篇文档，公式必须一致 })
```

## 基本操作

解决这个问题需要两个操作。

1. 跑一个检查：需要阈值时只从配方的 `metrics.yaml` 读，脚本通过 `--metrics` 读同一份文件，不在代码里保留默认值；`validate_repo.py` 与 `selftest.py` 不收参数；`check_io_pattern.py` 收 `--real` 与 `--bypassed`，可用 `--tolerance` 逐项覆盖；`check_coverage.py` 收 `--manifest`，可用 `--min-coverage` 覆盖；`check_scaling_consistency.py` 收 `--input`，默认容差来自 `per_level` 与 `first_last`。
2. 输出按脚本分两种：`check_*.py` 与 `selftest.py` 往标准输出打印一行 JSON，至少含 `check` 与 `status`；`validate_repo.py` 打印人读的逐项结果与错误清单，不使用单行 JSON。
3. 跑全部：依次跑这五个脚本，逐个交回输出、状态与退出码，每个脚本按自己的约定判定。

## apis.viba

```bash apis
import aisp.bench.checks.readme.types as checks

RunCheck =
     checks.CheckRun
  <- $script (checks.CheckScript * { 要跑哪一个脚本；五个脚本里选一个 })
  <- $args (checks.CheckArgs * { 这个脚本的输入；变体与 script 一一对应 })
  <- {
    跑一个检查：按脚本执行，标准输出按脚本的约定写，check_*.py 与 selftest.py 写一行 JSON，validate_repo.py 写人读结果；交回输出、状态与退出码。缺依赖、输入非法或缺阈值时状态为 skip、退出码 2，不假装通过
  }

RunAllChecks =
     checks.CheckBatch
  <- $spec (checks.CheckSpec * { 问题定义：五个脚本、阈值来源、目录约定与指标文档对应关系 })
  <- {
    跑全部：依次跑这五个脚本，逐个交回输出、状态与退出码；每个脚本按自己的约定判定
  }
  <- $run (RunCheck * { 每个脚本交给它跑一次；它交回的输出、状态与退出码原样进这批结果 })
```

## flow.viba

```bash flow
import aisp.bench.checks.readme.types as checks
import aisp.bench.checks.readme.apis as checks_api

CheckRunDuty =
  Object
  * $run (checks_api.RunCheck * { 操作：跑一个检查 })
  * $result (checks.CheckRun * { 交回：这个脚本的输出、状态与退出码 })

CheckAllDuty =
  Object
  * $run_all (checks_api.RunAllChecks * { 操作：跑全部五个脚本 })
  * $batch (checks.CheckBatch * { 交回：五个脚本各自的一次运行 })

CheckFlow =
  Object
  * $spec (checks.CheckSpec * { 问题定义：五个脚本的输入、输出、退出码与依赖，阈值来源，目录约定，指标文档对应关系 })
  * $single (CheckRunDuty * { 只跑一个检查 })
  * $all (CheckAllDuty * { 跑全部检查 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
