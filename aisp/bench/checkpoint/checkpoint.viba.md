# Checkpoint 存储评估

## types.viba

checkpoint 存储评估的形式化：`CheckpointBypassPlan` 是旁路的入口，把五步做法与四条约束分别收成 `$steps` 与 `$constraints`，`CheckpointBypassStep` 是五步之一的取值，`CheckpointBypassConstraint` 是四条约束之一的取值；`CheckpointParallel` 记 DP/TP/PP/EP 四个度数，旁路按它保持真实的并行切分。

```bash types

CheckpointParallel =
  Object
  * $dp (int * { 数据并行的度数，按真实配置设置 })
  * $tp (int * { 张量并行的度数，按真实配置设置 })
  * $pp (int * { 流水并行的度数，按真实配置设置 })
  * $ep (int * { 专家并行的度数，按真实配置设置 })

CheckpointBypassStep =
  Oneof
  | "meta_model" * { 用 torch.device("meta") 构建模型：参数与缓冲区只保留 dtype 与逻辑尺寸，不分配真实内存 }
  | "meta_forward" * { 前向：输入也放在 meta device 上，前向照常执行；计算不发生，但控制流、模块调用顺序、张量的逻辑尺寸全部真实 }
  | "placeholder_backward" * { 反向：直接对 meta 张量调 backward() 会因为没有真实存储而失败；按训练框架的用法构造梯度的占位实现，保证 param.grad 存在且尺寸正确 }
  | "mock_optimizer" * { optimizer：替换为只更新占位张量的 mock，保留 state_dict() 的键结构与分片逻辑；检查点写入依赖 state_dict() 的键与分片，不能简化成空实现 }
  | "unchanged_checkpoint_write" * { 检查点写入：完全不改，走框架原有实现 }

CheckpointBypassConstraint =
  Oneof
  | "model_code_source" * { 模型代码必须是训练侧可用的实现，不能拿推理代码来跑预训练；推理代码不能直接拿来跑预训练 }
  | "parallel_strategy" * { 并行策略（DP/TP/PP/EP）必须按真实配置设置；旁路只去掉计算，不去掉并行切分 }
  | "parameter_init" * { 参数初始化：meta device 不需要真实初始化，但若框架在初始化阶段就写盘（例如初始化检查点），该路径必须保留 }
  | "mixed_precision" * { 混合精度：dtype 必须与真实训练一致，否则写入字节数直接错 }

CheckpointBypassPlan =
  Object
  * $steps (list[CheckpointBypassStep] * { 旁路的五步做法，按原顺序执行 })
  * $constraints (list[CheckpointBypassConstraint] * { 旁路必须满足的四条约束 })
```

## 基本操作

只有一个操作：准备旁路。先跑通一次不旁路的训练若干步（G0），再按真实配置确定并行与 dtype，选一种旁路手段，写出五步做法与四条约束；IO 路径保留真实实现。

## apis.viba

```bash apis
import aisp.bench.checkpoint.checkpoint.types as checkpoint
import aisp.bench.checkpoint.ckpt_sample.types as ckpt_sample
import aisp.bench.checkpoint.bypass.apis as bypass_api
import aisp.bench.checkpoint.gates.apis as gates_api

PrepareBypass =
     checkpoint.CheckpointBypassPlan
  <- $model (ckpt_sample.Component * { 模型代码；必须是训练侧可用的实现 })
  <- $implementation (ckpt_sample.Component * { 训练框架的分布式检查点实现，记录名字与版本 })
  <- $parallel (checkpoint.CheckpointParallel * { 并行策略 DP/TP/PP/EP 的度数，按真实配置设置；旁路只去掉计算，不去掉并行切分 })
  <- $dtype (str * { 混合精度：dtype 必须与真实训练一致，否则写入字节数直接错 })
  <- {
    准备旁路：先跑通一次不旁路的训练若干步（门 G0），再用 meta device 构建模型，前向照常执行，反向与 optimizer 换成占位实现，checkpoint 写入完全不改；返回五步做法与四条约束
  }
  <- $choose (bypass_api.Choose * { 把要求的保真等级与可接受的成本交给它，它指定用哪种旁路手段；下面五步做法按它选的手段写 })
  <- $pass_g0 (gates_api.Pass * { 不旁路那次跑通之后拿产出判 G0；G0 不通过，旁路一步都不做 })
```
