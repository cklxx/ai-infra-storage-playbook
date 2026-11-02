# sample：checkpoint 样本接口的 Python 落地

对齐 [`playbook/ckpt-sample-interface.md`](../playbook/ckpt-sample-interface.md)。
一次运行 = 一条样本 × 一个存储版本；一份 `RunSpec` 进，一条 `RunRecord` 出。

## 模块

| 文件 | 对应文档模块 | 是什么 |
|---|---|---|
| `types.py` | `types` | RunSpec / RunRecord / StorageLayer / State(oneof) / Artifacts / CkptSli(6 种) / CkptSlo(MetricLE/GE) / Level / Failure |
| `configs.py` | `configs` | SampleConfigBase（model + topology + observe）；默认 S0–S5 阶梯与 `resolve_level` |
| `apis.py` | `apis` | `SampleService` Protocol：Start / Stop / Query / Execute / GetLevel；`SampleRunner` 是样本作者要实现的 callable |
| `memory.py` | — | `InMemorySampleService` 参考实现：后台线程跑 Start、锁内推进状态机、可取消 |
| `__init__.py` | `public` | 只做转发与重绑定，外部 `from aisp.bench.sample import ...` |

## 最小用法

```python
from sample import (
    InMemorySampleService, RunSpec, StorageLayer, Component,
)

def my_sample(spec, config):
    return [  # 六种 CkptSli 任选
        # CheckPointDuration(value=...),
    ]

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
# record.state 在 queued / running / completed / failed / rejected / cancelled 之间迁移
```

## 自检

```text
python3 checks/check_sample_interface.py
```

覆盖：GetLevel 落档、Execute 同步返回产物、Start 异步跑完翻 completed、Stop 置 cancelled、非法样本 Rejected、MetricLE/GE 判定。

## 边界

- 这是**样本接口**的落地，不是评估服务的 HTTP 层。HTTP/CLI 适配在 `playbook/evaluation-service.md`，后续再做。
- `InMemorySampleService` 只用于开发期自检：不做进程隔离，产物路径是 `memory://` 占位，生产实现要替换 `artifact_writer` 落对象存储。
- S0–S5 阶梯的默认阈值在 `configs.py`；配方要覆盖时由 `get_level` 注入自己的阶梯，不在代码里写死。
