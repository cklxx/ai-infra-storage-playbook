# 本配方专属校验

## 背景

配方里有一批只对这个评估集成立的校验；通用校验不在这里重复实现，放 `aisp/bench/checks/`。这份文档规定这类校验放在哪里、脚本接收什么输入、往标准输出写什么、用哪些退出码，让同一配方里的 check 脚本对外表现一致。

## 问题

问题形式化为一个模块：`check_template` 定义校验的归属、能放进这份文档的示例、用例目录的结构，以及输出与退出码。

```viba check_template
CheckTemplatePlacement =
  Oneof
  | "recipe" * Hint[{ 只对这个评估集成立的校验，放本配方的 checks/；这份文档只写这一类 }]
  | "bench" * Hint[{ 通用校验，放 aisp/bench/checks/；不在这里重复实现 }]

CheckTemplateExampleCheck =
  Oneof
  | "shard_key_structure" * Hint[{ 分片键结构核对：state_dict() 的键与真实运行一致 }]
  | "per_token_kv_bytes" * Hint[{ 每 token KV 写入字节核对：与模型配置算出的值比对 }]
  | "prefix_hit_rate" * Hint[{ 前缀命中率核对：与负载配置的理论命中率比对 }]

CheckTemplateCaseFile =
  Oneof
  | "metrics.json" * Hint[{ 用例目录里的 metrics.json }]
  | "manifest.json" * Hint[{ 用例目录里的 manifest.json }]

CheckTemplateRunDir =
  Object
  * $path (str * Hint[{ check 脚本用 --run-dir 收到的目录路径 }])
  * $files (list[CheckTemplateCaseFile] * Hint[{ 目录里必须有的两份文件；缺任何一份算输入缺失，退出码 2 }])

CheckTemplateStatus =
  Oneof
  | "pass" * Hint[{ 通过 }]
  | "fail" * Hint[{ 不通过 }]
  | "skip" * Hint[{ 跳过：缺依赖或输入缺失时给出的状态，没有得出通过或不通过的结论 }]

CheckTemplateReport =
  Object
  * $check (str * Hint[{ check 的名字，写进输出字段 check }])
  * $status (CheckTemplateStatus * Hint[{ 写进输出字段 status；只取 pass、fail、skip }])
  * $detail (str * Hint[{ 具体说明，写进输出字段 detail }])

CheckTemplateExitCode =
  Oneof
  | 0 * Hint[{ 通过 }]
  | 1 * Hint[{ 不通过 }]
  | 2 * Hint[{ 缺依赖或输入缺失 }]

CheckTemplateContract =
  Object
  * $input (CheckTemplateRunDir * Hint[{ 输入：--run-dir <path> 指向的用例目录，目录里必须有 metrics.json 与 manifest.json }])
  * $output (CheckTemplateReport * Hint[{ 输出：一行 JSON 到标准输出 }])
  * $exit_code (CheckTemplateExitCode * Hint[{ 退出码：0 通过，1 不通过，2 缺依赖或输入缺失 }])

CheckTemplateSpec =
  Object
  * $placement (CheckTemplatePlacement * Hint[{ 这条校验的归属：只对这个评估集成立的取 recipe，通用校验取 bench }])
  * $examples (list[CheckTemplateExampleCheck] * Hint[{ 能放进这份文档的校验示例 }])
  * $contract (CheckTemplateContract * Hint[{ 每个 check 脚本都要遵守的输入、输出与退出码约定 }])
```

## 基本操作

解决这个问题需要四个操作。归属：判断一条校验是不是只对这个评估集成立，成立就放进本配方的 `checks/`，不成立就是通用校验，放 `aisp/bench/checks/`，不在配方里重复实现。读入：按 `--run-dir <path>` 收下用例目录，确认目录里有 `metrics.json` 与 `manifest.json`，缺任何一份按输入缺失处理。运行：在用例目录上执行这个 check，往标准输出写一行 JSON，字段是 `check`、`status`、`detail`，`status` 只取 `pass`、`fail`、`skip`。退出：按结果给出退出码，0 表示通过，1 表示不通过，2 表示缺依赖或输入缺失。

## 接口

```viba check_template_api
import check_template

Place =
     check_template.CheckTemplatePlacement
  <- $only_for_this_recipe (bool * Hint[{ 这条校验是否只对这个评估集成立 }])
  <- Hint[{ 归属接口：只对这个评估集成立的校验交回 recipe，放本配方的 checks/；不成立的交回 bench，放 aisp/bench/checks/，不在配方里重复实现 }]

Inspect =
     check_template.CheckTemplateRunDir
  <- $run_dir (str * Hint[{ --run-dir 的取值：用例目录的路径 }])
  <- Hint[{ 读入接口：确认用例目录里有 metrics.json 与 manifest.json，把目录路径与两份文件交回；缺任何一份按输入缺失处理，退出码 2 }]

Run =
     check_template.CheckTemplateReport
  <- $dir (check_template.CheckTemplateRunDir * Hint[{ 读入接口交回的用例目录 }])
  <- $name (str * Hint[{ 这个 check 的名字，写进输出的 check 字段 }])
  <- Hint[{ 运行接口：在用例目录上按这个 check 的判定核对，往标准输出写一行 JSON，交回 check、status 与 detail；status 只取 pass、fail、skip }]

Exit =
     check_template.CheckTemplateExitCode
  <- $status (check_template.CheckTemplateStatus * Hint[{ 运行接口交回的状态 }])
  <- Hint[{ 退出接口：按状态交回退出码，pass 交回 0，fail 交回 1；skip 表示缺依赖或输入缺失，交回 2 }]
```

## 组织

```viba check_template_flow
import check_template
import check_template_api

CheckTemplatePlaceDuty =
  Object
  * $place (check_template_api.Place * Hint[{ 第一步：判断校验只对这个评估集成立，还是通用校验 }])
  * $placement (check_template.CheckTemplatePlacement * Hint[{ 交回的归属：recipe 放本配方的 checks/，bench 放 aisp/bench/checks/ }])

CheckTemplateInspectDuty =
  Object
  * $inspect (check_template_api.Inspect * Hint[{ 第二步：按 --run-dir 读入用例目录 }])
  * $run_dir (check_template.CheckTemplateRunDir * Hint[{ 交回的用例目录：路径与两份文件 }])

CheckTemplateRunDuty =
  Object
  * $run (check_template_api.Run * Hint[{ 第三步：执行 check，往标准输出写一行 JSON }])
  * $report (check_template.CheckTemplateReport * Hint[{ 交回的输出内容：check、status、detail }])

CheckTemplateExitDuty =
  Object
  * $exit (check_template_api.Exit * Hint[{ 第四步：按 status 给出退出码 }])
  * $code (check_template.CheckTemplateExitCode * Hint[{ 退出码：0 通过，1 不通过，2 缺依赖或输入缺失 }])

CheckTemplateFlow =
  Object
  * $spec (check_template.CheckTemplateSpec * Hint[{ 问题定义：归属、示例与脚本约定 }])
  * $place (CheckTemplatePlaceDuty * Hint[{ 第一步：决定校验放在哪里 }])
  * $inspect (CheckTemplateInspectDuty * Hint[{ 第二步：读入用例目录 }])
  * $run (CheckTemplateRunDuty * Hint[{ 第三步：执行并输出一行 JSON }])
  * $exit (CheckTemplateExitDuty * Hint[{ 第四步：按状态给退出码 }])
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
