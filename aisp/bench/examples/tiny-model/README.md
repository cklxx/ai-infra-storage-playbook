# 最小模型样例

## 背景

这份最小模型样例演示语料里的一条记录长什么样：它演示清单条目的字段，给 [`checks/`](../../checks/) 的脚本一个可以跑通的最小输入，也让新同学在五分钟内看懂收集与验证流程。它不是评估目标。

## 问题

```viba tiny_model
TinyModelPurpose =
  Oneof
  | "manifest_fields_demo" * Hint[{ 演示清单条目的字段 }]
  | "check_input" * Hint[{ 让 checks/ 的脚本有一个可以跑通的最小输入 }]
  | "onboarding" * Hint[{ 让新同学在五分钟内看懂收集与验证流程 }]

TinyModelFile =
  Oneof
  | "config" * Hint[{ config.json：一个极小模型的配置 }]
  | "modeling" * Hint[{ modeling_tiny.py：对应的建模代码，能在 meta device 上跑一次前向 }]
  | "manifest_entry" * Hint[{ manifest-entry.json：与 schemas/model-manifest.schema.json 一致的清单条目 }]

TinyModelCheck =
  Oneof
  | "config_json" * Hint[{ 核对方法：用 python3 -m json.tool 解析 config.json }]
  | "manifest_entry_json" * Hint[{ 核对方法：用 json.load 解析 manifest-entry.json }]
  | "modeling_forward" * Hint[{ 核对方法：运行 modeling_tiny.py，在 meta device 上做一次前向；需要 PyTorch }]

TinyModelManifestEntry =
  Object
  * $path (str * Hint[{ 清单条目的位置：manifest-entry.json }])
  * $schema (str * Hint[{ 清单条目遵循的 schema：schemas/model-manifest.schema.json }])

TinyModelCheckStatus =
  Oneof
  | $passed (nil * Hint[{ 核对通过 }])
  | $failed (str * Hint[{ 核对失败，附具体原因 }])
  | $skipped (str * Hint[{ 跳过，附具体原因；没有安装 PyTorch 时建模代码的前向走到这里 }])

TinyModelSample =
  Object
  * $path (str * Hint[{ 样例目录：examples/tiny-model }])
  * $purpose (list[TinyModelPurpose] * Hint[{ 用途：演示清单条目的字段、给 checks/ 一个最小输入、让新同学看懂收集与验证流程 }])
  * $files (list[TinyModelFile] * Hint[{ 结构：配置、建模代码、清单条目三个文件 }])
  * $checks (list[TinyModelCheck] * Hint[{ 核对方法：两个 JSON 文件各解析一次，建模代码跑一次前向 }])
  * $manifest (TinyModelManifestEntry * Hint[{ 清单条目：这个样例对应的一条记录 }])
  * $evaluation_target (bool * Hint[{ 是否评估目标；这份样例不是评估目标，固定为 false }])
```

## 基本操作

先 `Inspect` 读取样例：用途、三个文件各是什么、清单条目遵循哪份 schema、有哪几条核对方法。`CheckConfig` 解析 [`config.json`](config.json)，`CheckManifest` 解析 [`manifest-entry.json`](manifest-entry.json)；清单条目与 [`schemas/model-manifest.schema.json`](../../schemas/model-manifest.schema.json) 一致。`RunForward` 在装了 PyTorch 的环境里运行 [`modeling_tiny.py`](modeling_tiny.py)，在 meta device 上做一次前向。没有安装 PyTorch 时 `RunForward` 返回跳过，不报错；跳过的运行不写进任何结论。

## 接口

```viba tiny_model_api
import tiny_model

Inspect =
     tiny_model.TinyModelSample
  <- $dir (str * Hint[{ 样例目录：examples/tiny-model }])
  <- Hint[{ 读样例：返回用途、三个文件各是什么、清单条目遵循哪份 schema、有哪几条核对方法 }]

CheckConfig =
     tiny_model.TinyModelCheckStatus
  <- $file (str * Hint[{ 要解析的配置文件：examples/tiny-model/config.json }])
  <- Hint[{ 核对配置：用 python3 -m json.tool 解析 config.json；能解析返回 passed，不能解析返回 failed 并带具体原因 }]

CheckManifest =
     tiny_model.TinyModelCheckStatus
  <- $file (str * Hint[{ 要解析的清单条目：examples/tiny-model/manifest-entry.json }])
  <- Hint[{ 核对清单条目：用 json.load 解析 manifest-entry.json；能解析返回 passed，不能解析返回 failed 并带具体原因 }]

RunForward =
     tiny_model.TinyModelCheckStatus
  <- $file (str * Hint[{ 要运行的建模代码：examples/tiny-model/modeling_tiny.py }])
  <- Hint[{ 跑一次前向：在 meta device 上执行 modeling_tiny.py；需要 PyTorch，没有安装时返回 skipped，不报错，这次跳过不写进任何结论 }]
```

## 组织

```viba tiny_model_flow
import tiny_model
import tiny_model_api

TinyModelFlow =
  Object
  * $purpose (list[tiny_model.TinyModelPurpose] * Hint[{ 这份样例解决什么：演示清单条目的字段、给 checks/ 一个最小输入、让新同学看懂收集与验证流程 }])
  * $files (list[tiny_model.TinyModelFile] * Hint[{ 结构：config.json、modeling_tiny.py、manifest-entry.json }])
  * $manifest (tiny_model.TinyModelManifestEntry * Hint[{ 清单条目：遵循 schemas/model-manifest.schema.json }])
  * $inspect (tiny_model_api.Inspect * Hint[{ 操作：读取用途与结构 }])
  * $check_config (tiny_model_api.CheckConfig * Hint[{ 操作：解析 config.json }])
  * $check_manifest (tiny_model_api.CheckManifest * Hint[{ 操作：解析 manifest-entry.json }])
  * $run_forward (tiny_model_api.RunForward * Hint[{ 操作：在 meta device 上跑一次前向；没有 PyTorch 时跳过 }])
  * $result (list[tiny_model.TinyModelCheckStatus] * Hint[{ 三个核对的结果：两个 JSON 文件各一条，前向一条；没有 PyTorch 时前向为 skipped }])
  * $note (str * Hint[{ modeling_tiny.py 需要 PyTorch；没有安装时跳过运行，不要把它写进任何结论 }])
```

这些类型的 JSON Schema 在 [`json_schema/`](json_schema/) 下，由 scripts/export_json_schema.py 生成。
