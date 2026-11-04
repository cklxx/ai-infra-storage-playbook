# 本配方专属校验

## public.viba

只做转发：从 `## 问题` 的 `check_template` 模块与 `## 接口` 的 `check_template_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布八个名字：类型 `CheckTemplateSpec`、`CheckTemplateContract`、`CheckTemplateReport` 与 `CheckTemplateExitCode`，操作 `Place`、`Inspect`、`Run` 与 `Exit`；先看 `CheckTemplateSpec` 与 `CheckTemplateContract`，再按 `Place`、`Inspect`、`Run`、`Exit` 的顺序读，`CheckTemplateReport` 是 `Run` 的返回类型，`CheckTemplateExitCode` 是 `Exit` 的返回类型。

```bash public
import aisp.bench.recipes._template.checks.readme.types as check_template
import aisp.bench.recipes._template.checks.readme.apis as check_template_api

CheckTemplateSpec = check_template.CheckTemplateSpec
CheckTemplateContract = check_template.CheckTemplateContract
CheckTemplateReport = check_template.CheckTemplateReport
CheckTemplateExitCode = check_template.CheckTemplateExitCode
Place = check_template_api.Place
Inspect = check_template_api.Inspect
Run = check_template_api.Run
Exit = check_template_api.Exit
```

## 背景

配方里有一批只对这个评估集成立的校验；通用校验不在这里重复实现，放 `aisp/bench/checks/`。这份文档规定这类校验放在哪里、脚本接收什么输入、往标准输出写什么、用哪些退出码，让同一配方里的 check 脚本对外表现一致。

## types.viba

问题形式化为 `check_template` 模块：需要组合的结构写成对象类型，取值范围固定的概念写成枚举类型。对象类型有 `CheckTemplateRunDir`、`CheckTemplateReport`、`CheckTemplateContract` 与 `CheckTemplateSpec`：`CheckTemplateRunDir` 描述用例目录，`CheckTemplateReport` 描述一次 check 写出的报告，`CheckTemplateContract` 把输入、输出与退出码归结到一起，`CheckTemplateSpec` 再由归属、示例和这份契约组成。枚举类型有 `CheckTemplatePlacement`、`CheckTemplateExampleCheck`、`CheckTemplateCaseFile`、`CheckTemplateStatus` 与 `CheckTemplateExitCode`：`CheckTemplateSpec` 的 `placement` 取 `CheckTemplatePlacement`、`examples` 的元素取 `CheckTemplateExampleCheck`，`CheckTemplateRunDir` 的 `files` 元素取 `CheckTemplateCaseFile`，`CheckTemplateReport` 的 `status` 取 `CheckTemplateStatus`，契约的 `exit_code` 取 `CheckTemplateExitCode`。

```bash types
CheckTemplatePlacement =
  Oneof
  | "recipe" * { 只对这个评估集成立的校验，放本配方的 checks/；这份文档只写这一类 }
  | "bench" * { 通用校验，放 aisp/bench/checks/；不在这里重复实现 }

CheckTemplateExampleCheck =
  Oneof
  | "shard_key_structure" * { 分片键结构核对：state_dict() 的键与真实运行一致 }
  | "per_token_kv_bytes" * { 每 token KV 写入字节核对：与模型配置算出的值比对 }
  | "prefix_hit_rate" * { 前缀命中率核对：与负载配置的理论命中率比对 }

CheckTemplateCaseFile =
  Oneof
  | "metrics.json" * { 用例目录里的 metrics.json }
  | "manifest.json" * { 用例目录里的 manifest.json }

CheckTemplateRunDir =
  Object
  * $path (str * { check 脚本用 --run-dir 收到的目录路径 })
  * $files (list[CheckTemplateCaseFile] * { 目录里必须有的两份文件；缺任何一份算输入缺失，退出码 2 })

CheckTemplateStatus =
  Oneof
  | "pass" * { 通过 }
  | "fail" * { 不通过 }
  | "skip" * { 跳过：缺依赖或输入缺失时给出的状态，没有得出通过或不通过的结论 }

CheckTemplateReport =
  Object
  * $check (str * { check 的名字，写进输出字段 check })
  * $status (CheckTemplateStatus * { 写进输出字段 status；只取 pass、fail、skip })
  * $detail (str * { 具体说明，写进输出字段 detail })

CheckTemplateExitCode =
  Oneof
  | 0 * { 通过 }
  | 1 * { 不通过 }
  | 2 * { 缺依赖或输入缺失 }

CheckTemplateContract =
  Object
  * $input (CheckTemplateRunDir * { 输入：--run-dir <path> 指向的用例目录，目录里必须有 metrics.json 与 manifest.json })
  * $output (CheckTemplateReport * { 输出：一行 JSON 到标准输出 })
  * $exit_code (CheckTemplateExitCode * { 退出码：0 通过，1 不通过，2 缺依赖或输入缺失 })

CheckTemplateSpec =
  Object
  * $placement (CheckTemplatePlacement * { 这条校验的归属：只对这个评估集成立的取 recipe，通用校验取 bench })
  * $examples (list[CheckTemplateExampleCheck] * { 能放进这份文档的校验示例 })
  * $contract (CheckTemplateContract * { 每个 check 脚本都要遵守的输入、输出与退出码约定 })
```

## 基本操作

解决这个问题需要四个操作。

1. 归属：判断一条校验是不是只对这个评估集成立，成立就放进本配方的 `checks/`，不成立就是通用校验，放 `aisp/bench/checks/`，不在配方里重复实现。
2. 读入：按 `--run-dir <path>` 收下用例目录，确认目录里有 `metrics.json` 与 `manifest.json`，缺任何一份按输入缺失处理。
3. 运行：在用例目录上执行这个 check，往标准输出写一行 JSON，字段是 `check`、`status`、`detail`，`status` 只取 `pass`、`fail`、`skip`。
4. 退出：按结果给出退出码，0 表示通过，1 表示不通过，2 表示缺依赖或输入缺失。

## apis.viba

```bash apis
import aisp.bench.recipes._template.checks.readme.types as check_template

Place =
     check_template.CheckTemplatePlacement
  <- $only_for_this_recipe (bool * { 这条校验是否只对这个评估集成立 })
  <- {
    归属接口：只对这个评估集成立的校验交回 recipe，放本配方的 checks/；不成立的交回 bench，放 aisp/bench/checks/，不在配方里重复实现
  }

Inspect =
     check_template.CheckTemplateRunDir
  <- $run_dir (str * { --run-dir 的取值：用例目录的路径 })
  <- {
    读入接口：确认用例目录里有 metrics.json 与 manifest.json，把目录路径与两份文件交回；缺任何一份按输入缺失处理，退出码 2
  }

Run =
     check_template.CheckTemplateReport
  <- $dir (check_template.CheckTemplateRunDir * { 读入接口交回的用例目录 })
  <- $name (str * { 这个 check 的名字，写进输出的 check 字段 })
  <- {
    运行接口：在用例目录上按这个 check 的判定核对，往标准输出写一行 JSON，交回 check、status 与 detail；status 只取 pass、fail、skip
  }

Exit =
     check_template.CheckTemplateExitCode
  <- $status (check_template.CheckTemplateStatus * { 运行接口交回的状态 })
  <- {
    退出接口：按状态交回退出码，pass 交回 0，fail 交回 1；skip 表示缺依赖或输入缺失，交回 2
  }
```

## flow.viba

```bash flow
import aisp.bench.recipes._template.checks.readme.types as check_template
import aisp.bench.recipes._template.checks.readme.apis as check_template_api

CheckTemplatePlaceDuty =
  Object
  * $place (check_template_api.Place * { 第一步：判断校验只对这个评估集成立，还是通用校验 })
  * $placement (check_template.CheckTemplatePlacement * { 交回的归属：recipe 放本配方的 checks/，bench 放 aisp/bench/checks/ })

CheckTemplateInspectDuty =
  Object
  * $inspect (check_template_api.Inspect * { 第二步：按 --run-dir 读入用例目录 })
  * $run_dir (check_template.CheckTemplateRunDir * { 交回的用例目录：路径与两份文件 })

CheckTemplateRunDuty =
  Object
  * $run (check_template_api.Run * { 第三步：执行 check，往标准输出写一行 JSON })
  * $report (check_template.CheckTemplateReport * { 交回的输出内容：check、status、detail })

CheckTemplateExitDuty =
  Object
  * $exit (check_template_api.Exit * { 第四步：按 status 给出退出码 })
  * $code (check_template.CheckTemplateExitCode * { 退出码：0 通过，1 不通过，2 缺依赖或输入缺失 })

CheckTemplateFlow =
  Object
  * $spec (check_template.CheckTemplateSpec * { 问题定义：归属、示例与脚本约定 })
  * $place (CheckTemplatePlaceDuty * { 第一步：决定校验放在哪里 })
  * $inspect (CheckTemplateInspectDuty * { 第二步：读入用例目录 })
  * $run (CheckTemplateRunDuty * { 第三步：执行并输出一行 JSON })
  * $exit (CheckTemplateExitDuty * { 第四步：按状态给退出码 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
