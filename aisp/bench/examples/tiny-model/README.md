# 最小模型样例

## public

只做转发：从 `## 问题` 的 `tiny_model` 模块与 `## 接口` 的 `tiny_model_api` 模块 import，再把要发布的名字重新绑定一次。本文对外发布七个名字：类型 `TinyModelPurpose`、`TinyModelSample` 与 `TinyModelCheckStatus`，操作 `Inspect`、`CheckConfig`、`CheckManifest` 与 `RunForward`；先看 `TinyModelSample` 与 `Inspect`，再按 `CheckConfig`、`CheckManifest`、`RunForward` 的顺序读到 `TinyModelCheckStatus`，`TinyModelPurpose` 说明这份样例为什么存在。

```viba tiny_model_public
import tiny_model
import tiny_model_api

TinyModelPurpose = tiny_model.TinyModelPurpose
TinyModelSample = tiny_model.TinyModelSample
TinyModelCheckStatus = tiny_model.TinyModelCheckStatus
Inspect = tiny_model_api.Inspect
CheckConfig = tiny_model_api.CheckConfig
CheckManifest = tiny_model_api.CheckManifest
RunForward = tiny_model_api.RunForward
```

## 背景

这份最小模型样例演示语料里的一条记录长什么样：它演示清单条目的字段，给 [`checks/`](../../checks/) 的脚本一个可以跑通的最小输入，也让新同学在五分钟内看懂收集与验证流程。它不是评估目标。

## tiny_model

问题的形式化以 `TinyModelSample` 这个 Object 类型为入口：`$path` 与 `$evaluation_target` 是 `str` 与 `bool` 两个字段，`$purpose`、`$files`、`$checks` 分别取 `TinyModelPurpose`、`TinyModelFile`、`TinyModelCheck` 三个枚举的列表，`$manifest` 取对象类型 `TinyModelManifestEntry`。这三个枚举都用 Oneof 表示，取值只能落在列出的分支上；`TinyModelManifestEntry` 则是只含两个 `str` 字段的小 Object 类型。核对结果不放进 `TinyModelSample` 的字段，单独写成 Oneof 枚举 `TinyModelCheckStatus`，由 `$passed`、`$failed`、`$skipped` 三个分支覆盖，并作为 `## 接口` 里 `CheckConfig`、`CheckManifest` 与 `RunForward` 的返回类型。

```viba tiny_model
TinyModelPurpose =
  Oneof
  | "manifest_fields_demo" * { 演示清单条目的字段 }
  | "check_input" * { 让 checks/ 的脚本有一个可以跑通的最小输入 }
  | "onboarding" * { 让新同学在五分钟内看懂收集与验证流程 }

TinyModelFile =
  Oneof
  | "config" * { config.json：一个极小模型的配置 }
  | "modeling" * { modeling_tiny.py：对应的建模代码，能在 meta device 上跑一次前向 }
  | "manifest_entry" * { manifest-entry.json：与 schemas/model-manifest.schema.json 一致的清单条目 }

TinyModelCheck =
  Oneof
  | "config_json" * { 核对方法：用 python3 -m json.tool 解析 config.json }
  | "manifest_entry_json" * { 核对方法：用 json.load 解析 manifest-entry.json }
  | "modeling_forward" * { 核对方法：运行 modeling_tiny.py，在 meta device 上做一次前向；需要 PyTorch }

TinyModelManifestEntry =
  Object
  * $path (str * { 清单条目的位置：manifest-entry.json })
  * $schema (str * { 清单条目遵循的 schema：schemas/model-manifest.schema.json })

TinyModelCheckStatus =
  Oneof
  | $passed (nil * { 核对通过 })
  | $failed (str * { 核对失败，附具体原因 })
  | $skipped (str * { 跳过，附具体原因；没有安装 PyTorch 时建模代码的前向走到这里 })

TinyModelSample =
  Object
  * $path (str * { 样例目录：examples/tiny-model })
  * $purpose (list[TinyModelPurpose] * { 用途：演示清单条目的字段、给 checks/ 一个最小输入、让新同学看懂收集与验证流程 })
  * $files (list[TinyModelFile] * { 结构：配置、建模代码、清单条目三个文件 })
  * $checks (list[TinyModelCheck] * { 核对方法：两个 JSON 文件各解析一次，建模代码跑一次前向 })
  * $manifest (TinyModelManifestEntry * { 清单条目：这个样例对应的一条记录 })
  * $evaluation_target (bool * { 是否评估目标；这份样例不是评估目标，固定为 false })
```

## 基本操作

先 `Inspect` 读取样例：用途、三个文件各是什么、清单条目遵循哪份 schema、有哪几条核对方法。`CheckConfig` 解析 [`config.json`](config.json)，`CheckManifest` 解析 [`manifest-entry.json`](manifest-entry.json)；清单条目与 [`schemas/model-manifest.schema.json`](../../schemas/model-manifest.schema.json) 一致。`RunForward` 在装了 PyTorch 的环境里运行 [`modeling_tiny.py`](modeling_tiny.py)，在 meta device 上做一次前向。没有安装 PyTorch 时 `RunForward` 返回跳过，不报错；跳过的运行不写进任何结论。

## tiny_model_api

```viba tiny_model_api
import tiny_model

Inspect =
     tiny_model.TinyModelSample
  <- $dir (str * { 样例目录：examples/tiny-model })
  <- { 读样例：返回用途、三个文件各是什么、清单条目遵循哪份 schema、有哪几条核对方法 }

CheckConfig =
     tiny_model.TinyModelCheckStatus
  <- $file (str * { 要解析的配置文件：examples/tiny-model/config.json })
  <- { 核对配置：用 python3 -m json.tool 解析 config.json；能解析返回 passed，不能解析返回 failed 并带具体原因 }

CheckManifest =
     tiny_model.TinyModelCheckStatus
  <- $file (str * { 要解析的清单条目：examples/tiny-model/manifest-entry.json })
  <- { 核对清单条目：用 json.load 解析 manifest-entry.json；能解析返回 passed，不能解析返回 failed 并带具体原因 }

RunForward =
     tiny_model.TinyModelCheckStatus
  <- $file (str * { 要运行的建模代码：examples/tiny-model/modeling_tiny.py })
  <- { 跑一次前向：在 meta device 上执行 modeling_tiny.py；需要 PyTorch，没有安装时返回 skipped，不报错，这次跳过不写进任何结论 }
```

## tiny_model_flow

```viba tiny_model_flow
import tiny_model
import tiny_model_api

TinyModelFlow =
  Object
  * $purpose (list[tiny_model.TinyModelPurpose] * { 这份样例解决什么：演示清单条目的字段、给 checks/ 一个最小输入、让新同学看懂收集与验证流程 })
  * $files (list[tiny_model.TinyModelFile] * { 结构：config.json、modeling_tiny.py、manifest-entry.json })
  * $manifest (tiny_model.TinyModelManifestEntry * { 清单条目：遵循 schemas/model-manifest.schema.json })
  * $inspect (tiny_model_api.Inspect * { 操作：读取用途与结构 })
  * $check_config (tiny_model_api.CheckConfig * { 操作：解析 config.json })
  * $check_manifest (tiny_model_api.CheckManifest * { 操作：解析 manifest-entry.json })
  * $run_forward (tiny_model_api.RunForward * { 操作：在 meta device 上跑一次前向；没有 PyTorch 时跳过 })
  * $result (list[tiny_model.TinyModelCheckStatus] * { 三个核对的结果：两个 JSON 文件各一条，前向一条；没有 PyTorch 时前向为 skipped })
  * $note (str * { modeling_tiny.py 需要 PyTorch；没有安装时跳过运行，不要把它写进任何结论 })
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
