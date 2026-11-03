# sample：checkpoint 样本接口的 Python 落地

对齐 [`playbook/ckpt-sample-interface.md`](../playbook/ckpt-sample-interface.md)。
一次运行 = 一条样本 × 一个存储版本；一份 `RunSpec` 进，一条 `RunRecord` 出。

每个导出类型的 `to_json()` 输出，直接通过 [`playbook/json_schema/`](../playbook/json_schema/) 的同名 schema。

## 模块

| 文件 | 对应文档模块 | 是什么 |
|---|---|---|
| `types.py` | `types` | RunSpec / RunRecord / StorageLayer / Component / State(oneof) / QueueProgress / WorkProgress / Artifacts / CkptSli(6 种) / CkptSlo(MetricLE/GE) / 6 个 Metric / Failure |
| `configs.py` | `configs` | SampleConfigBase（model + topology + observe）；Model / Topology / ObservationConfig |
| `levels.py` | `levels`（scaling.md） | `Level` = S0..S5；默认阶梯与 `resolve_level` |
| `observation.py` | `observation`（methodology.md） | `ObservationLayer` = app / sys / storage |
| `apis.py` | `apis` | `SampleService` Protocol：Start / Stop / Query / Execute / GetLevel；`SampleRunner` 是样本作者要实现的 callable |
| `memory.py` | — | `InMemorySampleService` 参考实现：后台线程跑 Start、锁内推进状态机、可取消 |
| `__init__.py` | `public` | 只做转发；导出集合严格等于文档 public 的十个名字 |

## JSON 形态

oneof 是单键对象，键名就是 schema 里的属性名：

```json
{"state": {"queued": {"pos": 1, "len": 3}}}
{"state": {"completed": null}}
{"metrics": [{"check_point_duration_sli": 0.064}, {"write_throughput_sli": 5.2e8}]}
{"slo": [{"check_point_duration_slo": {"actual": 0.064, "threshold": 0.1}}]}
```

`RunRecord` 的四个字段与 `Artifacts` 的四个字段在 schema 里都是必填；未产出的路径用空字符串占位。

## 最小用法

```python
from sample import RunSpec, SampleConfigBase
from sample.memory import InMemorySampleService
from sample.types import Component, StorageLayer, CheckPointDuration

def my_sample(spec, config):
    return [CheckPointDuration(value=12.5)]  # 六种 CkptSli 任选

svc = InMemorySampleService(
    runners={"tiny-ckpt@0.1.0": my_sample},
    config_loader=lambda name: load_my_config(name),
)

record = svc.start(RunSpec(
    sample="tiny-ckpt@0.1.0",
    config="tiny-64-s0",
    storage=StorageLayer(
        backend=Component(name="gpfs", version="5.1"),
        adapter=Component(name="torchstore", version="0.2"),
    ),
    seed=20261103,
))
record.to_json()  # 直接可过 RunRecord.schema.json
```

## 自检

```text
python3 checks/check_sample_interface.py
```

81 例：GetLevel 落档、Execute 同步产物、Start 异步翻 completed、Stop 置 cancelled（含排队期立即取消与迟到终态不覆盖）、非法样本 Rejected（含非 int seed、空白组件名、config 加载失败）、记录上限淘汰、10 个解码器逐类拒绝未知键、0 规模拓扑被拒、MetricLE/GE 判定、严格解码，以及本接口 23 个类型各自 schema 的逐份校验与 5 个非法实例被拒。

## 测量口径

- **恢复是冷读**：读每个分片前先 `POSIX_FADV_DONTNEED` 丢页缓存，否则测到的是页缓存而不是存储。热读与冷读在同一台 64 核机上差 17–26 倍。
- **工作目录跟随 mount**：`nfs` / `fuse` 必须用 `TINY_CKPT_ROOT` 指向真实挂载点，不给就报错，不允许默默写本地盘。`local-nvme` 走临时目录。
- **写入是同步模式**：`training_stall_sli` 因此等于 `check_point_duration_sli`。异步写入与计算重叠的场景不在本样本范围内。
- **元数据提交**测的是「全部分片 fsync + 清单 fsync」，不是单个文件的 fsync。

## 边界

- 这是**样本接口**的落地，不是评估服务的 HTTP 层。HTTP/CLI 适配在 `playbook/evaluation-service.md`，后续再做。
- `InMemorySampleService` 只用于开发期自检：不做进程隔离，产物路径是 `memory://` 占位，生产实现要替换 `artifact_writer` 落对象存储。
- S0–S5 阶梯的默认阈值在 `levels.py`；配方要覆盖时由 `get_level` 注入自己的阶梯，不在代码里写死。
- `Topology` 的 `network` / `mount` 用 `Literal` 收窄，比 schema 的 `string` 更严；schema 只约束类型，取值约束来自文档 Hint。
- `Topology` 要求 `nodes` 与 `gpus_per_node` 至少为 1。schema 只写了 `integer`，没有下限；0 规模算不出有意义的档位，样本侧也会退化成空跑，因此解码与构造都拒绝。
- `start()` 只登记请求就返回；`stop()` 是取消请求，返回时状态已是 `cancelled`，但样本本身可能还跑到下一个检查点。`cancelled` 是吸收态，后台线程迟到的 `completed` / `failed` 不会覆盖它。
- 记录默认最多留 1000 条（`max_records`），超出时按插入顺序淘汰最早的终态记录；被淘汰的 `run_id` 再 `query` 会抛 `KeyError`。运行中的记录不淘汰。
- `progress` 恒为 0/0，表示「该实现不报告细粒度工作量」；完成与否只看 `state`。不拿 SLI 条数当 `total`。
- `public` 层只导出文档列的十个名字（Start / Stop / Query / Execute / GetLevel / RunSpec / RunRecord / Artifacts / CkptSli / CkptSlo / SampleConfigBase）。实现类要从 `sample.memory`、`sample.types`、`sample.levels` 导入。
- `Start` / `Stop` 等是 `SampleService` 的未绑定方法，使用时要带实例：`Start(svc, spec)`。
