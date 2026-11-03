# checkpoint 样本接口

一份 RunSpec 进，一条 RunRecord 出。一次运行 = 一条样本 × 一个存储版本。

## public

只做转发：从 apis、configs、types 里 import，再把要发布的名字重新绑定一次。具体定义在下面三章各自的文件里。

```bash
import apis
import configs
import types

Start = apis.Start
Stop = apis.Stop
Query = apis.Query
Execute = apis.Execute
GetLevel = apis.GetLevel
RunSpec = types.RunSpec
RunRecord = types.RunRecord
Artifacts = types.Artifacts
CkptSli = types.CkptSli
CkptSlo = types.CkptSlo
SampleConfigBase = configs.SampleConfigBase
```

## apis

```bash
import configs
import types

Start =
     types.RunRecord
  <- $spec (types.RunSpec * Hint[{ 这次评估的运行请求 }])
  <- { 提交接口：请求交出去就返回，不等样本跑完。校验请求，按配置起一个样本进程，把运行标识与当前状态交回来；此时状态可能仍在排队或执行中，产物位置可能还缺 }

Stop =
     types.RunRecord
  <- $run_id (str * Hint[{ 要停的那次运行 }])
  <- { 取消接口：让服务停下这次运行，已经写完的产物保留。返回的记录状态为 cancelled；已经结束的运行原样交回，不报错 }

Query =
     types.RunRecord
  <- $run_id (str * Hint[{ 要查的那次运行 }])
  <- { 查一次运行：答当前状态、进度与产物位置。只读，不改变运行；完成与否只看状态，不看进度 }

Execute =
     types.Artifacts
  <- $spec (types.RunSpec * Hint[{ 同一份运行请求 }])
  <- { 执行接口：同一份请求同步跑到结束，返回时四份产物已经写完。它由 Start 在后台触发；Start 只拿到标识与状态，拿不到产物本身 }

GetLevel =
     types.Level
  <- $config (configs.SampleConfigBase * Hint[{ 样本配置 }])
  <- { 导出属性：按节点数与每节点卡数落到 S0 到 S5 的哪一级，阈值由配方的 scaling 阶梯给 }
```

## types

```bash
RunRecord =
  Object
  * $run_id (str * Hint[{ 服务分配的运行标识，查状态、取产物都用它 }])
  * $state (State * Hint[{ 这次运行现在在哪一步 }])
  * $progress (WorkProgress * Hint[{ 已完成的工作量占总量的多少，单位由配置定 }])
  * $artifacts (Artifacts * Hint[{ 产物的位置；没跑完时相应字段缺 }])

RunSpec =
  Object
  * $sample (str * Hint[{ 跑哪个样本程序，写 name@version }])
  * $config (str * Hint[{ 样本 repo 里那份配置的名字；那份配置必须含 SampleConfigBase 的字段 }])
  * $storage (StorageLayer * Hint[{ 这次要评的存储两层 }])
  * $seed (int * Hint[{ 随机种子，决定同一请求重跑的一致性 }])

StorageLayer =
  Object
  * $backend (Component * Hint[{ 纯存储系统，例如 GPFS、Ceph }])
  * $adapter (Component * Hint[{ 存储传输适配层，例如 torchstore }])

Component =
  Object
  * $name (str * Hint[{ 组件名 }])
  * $version (str * Hint[{ 组件版本 }])
  * $git_commit_id ((str | nil) * Hint[{ 组件源码的 commit；只发版本不发源码时给 nil }])

State =
  Oneof
  | $queued (QueueProgress * Hint[{ 排队中，还没开始跑 }])
  | $running (nil * Hint[{ 正在执行 }])
  | $completed (nil * Hint[{ 正常结束 }])
  | $failed (Failure * Hint[{ 执行失败，带分类与说明 }])
  | $rejected (Failure * Hint[{ 请求不合法，没进队列 }])
  | $cancelled (nil * Hint[{ 被取消 }])

QueueProgress =
  Object
  * $pos (int * Hint[{ 在队列里排第几位 }])
  * $len (int * Hint[{ 队列里一共几个 }])

WorkProgress =
  Object
  * $done (int * Hint[{ 已完成的工作量 }])
  * $total (int * Hint[{ 总工作量；还没算出来时是 0 }])

Artifacts =
  Object
  * $manifest (str * Hint[{ 运行清单：输入、版本、拓扑、观测配置，服务写 }])
  * $metrics (list[CkptSli] * Hint[{ 这次运行的 SLI：每项一条，没有阈值 }])
  * $slo (list[CkptSlo] * Hint[{ 每个 SLI 指标的判定，阈值由部署方给 }])
  * $report (str * Hint[{ 人读报告的位置 }])

CkptSlo =
  Oneof
  | $check_point_duration_slo (MetricLE[CheckPointDurationMetric] * Hint[{ 写入时长不超过部署方给的阈值 }])
  | $training_stall_slo (MetricLE[TrainingStallMetric] * Hint[{ 训练停顿不超过部署方给的阈值 }])
  | $restore_duration_slo (MetricLE[RestoreDurationMetric] * Hint[{ 恢复时长不超过部署方给的阈值 }])
  | $write_throughput_slo (MetricGE[WriteThroughputMetric] * Hint[{ 写入吞吐不低于部署方给的阈值 }])
  | $metadata_commit_slo (MetricLE[MetadataCommitMetric] * Hint[{ 元数据提交时长不超过部署方给的阈值 }])
  | $write_latency_p99_slo (MetricLE[WriteLatencyP99Metric] * Hint[{ 写请求 P99 不超过部署方给的阈值 }])

CkptSli =
  Oneof
  | $check_point_duration_sli (CheckPointDurationMetric * Hint[{ 一次 checkpoint 从开始写到元数据可见的时长，秒 }])
  | $training_stall_sli (TrainingStallMetric * Hint[{ 训练被写入阻塞的时长；异步写入扣掉与计算重叠的部分，秒 }])
  | $restore_duration_sli (RestoreDurationMetric * Hint[{ 从 checkpoint 恢复到可以继续训练的时长，秒 }])
  | $write_throughput_sli (WriteThroughputMetric * Hint[{ 写入期间按 rank 聚合的吞吐，字节每秒 }])
  | $metadata_commit_sli (MetadataCommitMetric * Hint[{ 分片元数据提交到可见的时长，毫秒 }])
  | $write_latency_p99_sli (WriteLatencyP99Metric * Hint[{ 单个写请求的 P99，毫秒 }])

MetricLE[Value] =
  Object
  * $actual Value
  * $threshold Value

MetricGE[Value] =
  Object
  * $actual Value
  * $threshold Value

CheckPointDurationMetric = float * Hint[{ 一次 checkpoint 从开始写到元数据可见的时长，秒 }]

TrainingStallMetric = float * Hint[{ 训练被写入阻塞的时长；异步写入扣掉与计算重叠的部分，秒 }]

RestoreDurationMetric = float * Hint[{ 从 checkpoint 恢复到可以继续训练的时长，秒 }]

WriteThroughputMetric = float * Hint[{ 写入期间按 rank 聚合的吞吐，字节每秒 }]

MetadataCommitMetric = float * Hint[{ 分片元数据提交到可见的时长，毫秒 }]

WriteLatencyP99Metric = float * Hint[{ 单个写请求的 P99，毫秒 }]

Level =
  Oneof
  | "S0" * Hint[{ 单机，最小参数规模；对齐基准 }]
  | "S1" * Hint[{ 单机多卡或双机；引入并行切分与多 rank 并发 }]
  | "S2" * Hint[{ 数十至百卡；引入网络与共享存储的争用 }]
  | "S3" * Hint[{ 千卡；引入调度与故障恢复 }]
  | "S4" * Hint[{ 万卡；实测上限 }]
  | "S5" * Hint[{ 十万卡；外推目标 }]

Failure =
  Object
  * $kind (str * Hint[{ 失败分类：environment、dependency、timeout、observation、assertion 等 }])
  * $detail (str * Hint[{ 具体说明 }])
```

## configs

```bash
SampleConfigBase =
  Object
  * $model (Model * Hint[{ 被评估的模型 }])
  * $topology (Topology * Hint[{ 节点、卡、网络、挂载 }])
  * $observe (ObservationConfig * Hint[{ 观测设置 }])

Model =
  Object
  * $id (str * Hint[{ 模型标识，例如 HuggingFace 的 repo id }])
  * $git_commit_id (str * Hint[{ 代码 commit，钉死到具体一份代码 }])

Topology =
  Object
  * $nodes (int * Hint[{ 节点数 }])
  * $gpus_per_node (int * Hint[{ 每节点卡数 }])
  * $network (str * Hint[{ 网络类型：rdma、tcp、none }])
  * $mount (str * Hint[{ 存储挂载方式：local-nvme、nfs、fuse }])

ObservationConfig =
  Object
  * $enabled (bool * Hint[{ 是否开观测 }])
  * $sample_rate (float * Hint[{ 采样率，0 到 1 }])
  * $layers (list[str] * Hint[{ 采集层：app、sys、storage }])
```

## json schema

由 `scripts/export_json_schema.py` 生成，不要手改。每个 public 导出类型一份，标题就是导出名。

`RunSpec`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RunSpec",
  "$ref": "#/$defs/types.RunSpec",
  "$defs": {
    "types.RunSpec": {
      "type": "object",
      "properties": {
        "sample": {
          "type": "string"
        },
        "config": {
          "type": "string"
        },
        "storage": {
          "$ref": "#/$defs/types.StorageLayer"
        },
        "seed": {
          "type": "integer"
        }
      },
      "required": [
        "sample",
        "config",
        "storage",
        "seed"
      ],
      "additionalProperties": false
    },
    "types.StorageLayer": {
      "type": "object",
      "properties": {
        "backend": {
          "$ref": "#/$defs/types.Component"
        },
        "adapter": {
          "$ref": "#/$defs/types.Component"
        }
      },
      "required": [
        "backend",
        "adapter"
      ],
      "additionalProperties": false
    },
    "types.Component": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "version": {
          "type": "string"
        },
        "git_commit_id": {
          "oneOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "name",
        "version",
        "git_commit_id"
      ],
      "additionalProperties": false
    }
  }
}
```

`RunRecord`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RunRecord",
  "$ref": "#/$defs/types.RunRecord",
  "$defs": {
    "types.RunRecord": {
      "type": "object",
      "properties": {
        "run_id": {
          "type": "string"
        },
        "state": {
          "$ref": "#/$defs/types.State"
        },
        "progress": {
          "$ref": "#/$defs/types.WorkProgress"
        },
        "artifacts": {
          "$ref": "#/$defs/types.Artifacts"
        }
      },
      "required": [
        "run_id",
        "state",
        "progress",
        "artifacts"
      ],
      "additionalProperties": false
    },
    "types.State": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "queued": {
              "$ref": "#/$defs/types.QueueProgress"
            }
          },
          "required": [
            "queued"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "running": {
              "type": "null"
            }
          },
          "required": [
            "running"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "completed": {
              "type": "null"
            }
          },
          "required": [
            "completed"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "failed": {
              "$ref": "#/$defs/types.Failure"
            }
          },
          "required": [
            "failed"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "rejected": {
              "$ref": "#/$defs/types.Failure"
            }
          },
          "required": [
            "rejected"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "cancelled": {
              "type": "null"
            }
          },
          "required": [
            "cancelled"
          ],
          "additionalProperties": false
        }
      ]
    },
    "types.QueueProgress": {
      "type": "object",
      "properties": {
        "pos": {
          "type": "integer"
        },
        "len": {
          "type": "integer"
        }
      },
      "required": [
        "pos",
        "len"
      ],
      "additionalProperties": false
    },
    "types.Failure": {
      "type": "object",
      "properties": {
        "kind": {
          "type": "string"
        },
        "detail": {
          "type": "string"
        }
      },
      "required": [
        "kind",
        "detail"
      ],
      "additionalProperties": false
    },
    "types.WorkProgress": {
      "type": "object",
      "properties": {
        "done": {
          "type": "integer"
        },
        "total": {
          "type": "integer"
        }
      },
      "required": [
        "done",
        "total"
      ],
      "additionalProperties": false
    },
    "types.Artifacts": {
      "type": "object",
      "properties": {
        "manifest": {
          "type": "string"
        },
        "metrics": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/types.CkptSli"
          }
        },
        "slo": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/types.CkptSlo"
          }
        },
        "report": {
          "type": "string"
        }
      },
      "required": [
        "manifest",
        "metrics",
        "slo",
        "report"
      ],
      "additionalProperties": false
    },
    "types.CkptSli": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "check_point_duration_sli": {
              "$ref": "#/$defs/types.CheckPointDurationMetric"
            }
          },
          "required": [
            "check_point_duration_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "training_stall_sli": {
              "$ref": "#/$defs/types.TrainingStallMetric"
            }
          },
          "required": [
            "training_stall_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "restore_duration_sli": {
              "$ref": "#/$defs/types.RestoreDurationMetric"
            }
          },
          "required": [
            "restore_duration_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_throughput_sli": {
              "$ref": "#/$defs/types.WriteThroughputMetric"
            }
          },
          "required": [
            "write_throughput_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "metadata_commit_sli": {
              "$ref": "#/$defs/types.MetadataCommitMetric"
            }
          },
          "required": [
            "metadata_commit_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_latency_p99_sli": {
              "$ref": "#/$defs/types.WriteLatencyP99Metric"
            }
          },
          "required": [
            "write_latency_p99_sli"
          ],
          "additionalProperties": false
        }
      ]
    },
    "types.CheckPointDurationMetric": {
      "type": "number"
    },
    "types.TrainingStallMetric": {
      "type": "number"
    },
    "types.RestoreDurationMetric": {
      "type": "number"
    },
    "types.WriteThroughputMetric": {
      "type": "number"
    },
    "types.MetadataCommitMetric": {
      "type": "number"
    },
    "types.WriteLatencyP99Metric": {
      "type": "number"
    },
    "types.CkptSlo": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "check_point_duration_slo": {
              "$ref": "#/$defs/types.MetricLE@1910e53e"
            }
          },
          "required": [
            "check_point_duration_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "training_stall_slo": {
              "$ref": "#/$defs/types.MetricLE@f4dd4d27"
            }
          },
          "required": [
            "training_stall_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "restore_duration_slo": {
              "$ref": "#/$defs/types.MetricLE@f421fc96"
            }
          },
          "required": [
            "restore_duration_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_throughput_slo": {
              "$ref": "#/$defs/types.MetricGE@c5b2fe43"
            }
          },
          "required": [
            "write_throughput_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "metadata_commit_slo": {
              "$ref": "#/$defs/types.MetricLE@292a31ac"
            }
          },
          "required": [
            "metadata_commit_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_latency_p99_slo": {
              "$ref": "#/$defs/types.MetricLE@9a4b591e"
            }
          },
          "required": [
            "write_latency_p99_slo"
          ],
          "additionalProperties": false
        }
      ]
    },
    "types.MetricLE@1910e53e": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.CheckPointDurationMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.CheckPointDurationMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricLE@f4dd4d27": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.TrainingStallMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.TrainingStallMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricLE@f421fc96": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.RestoreDurationMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.RestoreDurationMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricGE@c5b2fe43": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.WriteThroughputMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.WriteThroughputMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricLE@292a31ac": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.MetadataCommitMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.MetadataCommitMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricLE@9a4b591e": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.WriteLatencyP99Metric"
        },
        "threshold": {
          "$ref": "#/$defs/types.WriteLatencyP99Metric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    }
  }
}
```

`Artifacts`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Artifacts",
  "$ref": "#/$defs/types.Artifacts",
  "$defs": {
    "types.Artifacts": {
      "type": "object",
      "properties": {
        "manifest": {
          "type": "string"
        },
        "metrics": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/types.CkptSli"
          }
        },
        "slo": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/types.CkptSlo"
          }
        },
        "report": {
          "type": "string"
        }
      },
      "required": [
        "manifest",
        "metrics",
        "slo",
        "report"
      ],
      "additionalProperties": false
    },
    "types.CkptSli": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "check_point_duration_sli": {
              "$ref": "#/$defs/types.CheckPointDurationMetric"
            }
          },
          "required": [
            "check_point_duration_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "training_stall_sli": {
              "$ref": "#/$defs/types.TrainingStallMetric"
            }
          },
          "required": [
            "training_stall_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "restore_duration_sli": {
              "$ref": "#/$defs/types.RestoreDurationMetric"
            }
          },
          "required": [
            "restore_duration_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_throughput_sli": {
              "$ref": "#/$defs/types.WriteThroughputMetric"
            }
          },
          "required": [
            "write_throughput_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "metadata_commit_sli": {
              "$ref": "#/$defs/types.MetadataCommitMetric"
            }
          },
          "required": [
            "metadata_commit_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_latency_p99_sli": {
              "$ref": "#/$defs/types.WriteLatencyP99Metric"
            }
          },
          "required": [
            "write_latency_p99_sli"
          ],
          "additionalProperties": false
        }
      ]
    },
    "types.CheckPointDurationMetric": {
      "type": "number"
    },
    "types.TrainingStallMetric": {
      "type": "number"
    },
    "types.RestoreDurationMetric": {
      "type": "number"
    },
    "types.WriteThroughputMetric": {
      "type": "number"
    },
    "types.MetadataCommitMetric": {
      "type": "number"
    },
    "types.WriteLatencyP99Metric": {
      "type": "number"
    },
    "types.CkptSlo": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "check_point_duration_slo": {
              "$ref": "#/$defs/types.MetricLE@1910e53e"
            }
          },
          "required": [
            "check_point_duration_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "training_stall_slo": {
              "$ref": "#/$defs/types.MetricLE@f4dd4d27"
            }
          },
          "required": [
            "training_stall_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "restore_duration_slo": {
              "$ref": "#/$defs/types.MetricLE@f421fc96"
            }
          },
          "required": [
            "restore_duration_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_throughput_slo": {
              "$ref": "#/$defs/types.MetricGE@c5b2fe43"
            }
          },
          "required": [
            "write_throughput_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "metadata_commit_slo": {
              "$ref": "#/$defs/types.MetricLE@292a31ac"
            }
          },
          "required": [
            "metadata_commit_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_latency_p99_slo": {
              "$ref": "#/$defs/types.MetricLE@9a4b591e"
            }
          },
          "required": [
            "write_latency_p99_slo"
          ],
          "additionalProperties": false
        }
      ]
    },
    "types.MetricLE@1910e53e": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.CheckPointDurationMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.CheckPointDurationMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricLE@f4dd4d27": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.TrainingStallMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.TrainingStallMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricLE@f421fc96": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.RestoreDurationMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.RestoreDurationMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricGE@c5b2fe43": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.WriteThroughputMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.WriteThroughputMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricLE@292a31ac": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.MetadataCommitMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.MetadataCommitMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetricLE@9a4b591e": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.WriteLatencyP99Metric"
        },
        "threshold": {
          "$ref": "#/$defs/types.WriteLatencyP99Metric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    }
  }
}
```

`CkptSli`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CkptSli",
  "$ref": "#/$defs/types.CkptSli",
  "$defs": {
    "types.CkptSli": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "check_point_duration_sli": {
              "$ref": "#/$defs/types.CheckPointDurationMetric"
            }
          },
          "required": [
            "check_point_duration_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "training_stall_sli": {
              "$ref": "#/$defs/types.TrainingStallMetric"
            }
          },
          "required": [
            "training_stall_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "restore_duration_sli": {
              "$ref": "#/$defs/types.RestoreDurationMetric"
            }
          },
          "required": [
            "restore_duration_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_throughput_sli": {
              "$ref": "#/$defs/types.WriteThroughputMetric"
            }
          },
          "required": [
            "write_throughput_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "metadata_commit_sli": {
              "$ref": "#/$defs/types.MetadataCommitMetric"
            }
          },
          "required": [
            "metadata_commit_sli"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_latency_p99_sli": {
              "$ref": "#/$defs/types.WriteLatencyP99Metric"
            }
          },
          "required": [
            "write_latency_p99_sli"
          ],
          "additionalProperties": false
        }
      ]
    },
    "types.CheckPointDurationMetric": {
      "type": "number"
    },
    "types.TrainingStallMetric": {
      "type": "number"
    },
    "types.RestoreDurationMetric": {
      "type": "number"
    },
    "types.WriteThroughputMetric": {
      "type": "number"
    },
    "types.MetadataCommitMetric": {
      "type": "number"
    },
    "types.WriteLatencyP99Metric": {
      "type": "number"
    }
  }
}
```

`CkptSlo`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CkptSlo",
  "$ref": "#/$defs/types.CkptSlo",
  "$defs": {
    "types.CkptSlo": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "check_point_duration_slo": {
              "$ref": "#/$defs/types.MetricLE@1910e53e"
            }
          },
          "required": [
            "check_point_duration_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "training_stall_slo": {
              "$ref": "#/$defs/types.MetricLE@f4dd4d27"
            }
          },
          "required": [
            "training_stall_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "restore_duration_slo": {
              "$ref": "#/$defs/types.MetricLE@f421fc96"
            }
          },
          "required": [
            "restore_duration_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_throughput_slo": {
              "$ref": "#/$defs/types.MetricGE@c5b2fe43"
            }
          },
          "required": [
            "write_throughput_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "metadata_commit_slo": {
              "$ref": "#/$defs/types.MetricLE@292a31ac"
            }
          },
          "required": [
            "metadata_commit_slo"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "write_latency_p99_slo": {
              "$ref": "#/$defs/types.MetricLE@9a4b591e"
            }
          },
          "required": [
            "write_latency_p99_slo"
          ],
          "additionalProperties": false
        }
      ]
    },
    "types.MetricLE@1910e53e": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.CheckPointDurationMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.CheckPointDurationMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.CheckPointDurationMetric": {
      "type": "number"
    },
    "types.MetricLE@f4dd4d27": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.TrainingStallMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.TrainingStallMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.TrainingStallMetric": {
      "type": "number"
    },
    "types.MetricLE@f421fc96": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.RestoreDurationMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.RestoreDurationMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.RestoreDurationMetric": {
      "type": "number"
    },
    "types.MetricGE@c5b2fe43": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.WriteThroughputMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.WriteThroughputMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.WriteThroughputMetric": {
      "type": "number"
    },
    "types.MetricLE@292a31ac": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.MetadataCommitMetric"
        },
        "threshold": {
          "$ref": "#/$defs/types.MetadataCommitMetric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.MetadataCommitMetric": {
      "type": "number"
    },
    "types.MetricLE@9a4b591e": {
      "type": "object",
      "properties": {
        "actual": {
          "$ref": "#/$defs/types.WriteLatencyP99Metric"
        },
        "threshold": {
          "$ref": "#/$defs/types.WriteLatencyP99Metric"
        }
      },
      "required": [
        "actual",
        "threshold"
      ],
      "additionalProperties": false
    },
    "types.WriteLatencyP99Metric": {
      "type": "number"
    }
  }
}
```

`SampleConfigBase`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SampleConfigBase",
  "$ref": "#/$defs/configs.SampleConfigBase",
  "$defs": {
    "configs.SampleConfigBase": {
      "type": "object",
      "properties": {
        "model": {
          "$ref": "#/$defs/configs.Model"
        },
        "topology": {
          "$ref": "#/$defs/configs.Topology"
        },
        "observe": {
          "$ref": "#/$defs/configs.ObservationConfig"
        }
      },
      "required": [
        "model",
        "topology",
        "observe"
      ],
      "additionalProperties": false
    },
    "configs.Model": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "git_commit_id": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "git_commit_id"
      ],
      "additionalProperties": false
    },
    "configs.Topology": {
      "type": "object",
      "properties": {
        "nodes": {
          "type": "integer"
        },
        "gpus_per_node": {
          "type": "integer"
        },
        "network": {
          "type": "string"
        },
        "mount": {
          "type": "string"
        }
      },
      "required": [
        "nodes",
        "gpus_per_node",
        "network",
        "mount"
      ],
      "additionalProperties": false
    },
    "configs.ObservationConfig": {
      "type": "object",
      "properties": {
        "enabled": {
          "type": "boolean"
        },
        "sample_rate": {
          "type": "number"
        },
        "layers": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      },
      "required": [
        "enabled",
        "sample_rate",
        "layers"
      ],
      "additionalProperties": false
    }
  }
}
```
