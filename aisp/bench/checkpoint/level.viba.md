# 规模档位

## 需求背景

样本落在哪个规模档位，决定并行配置与负载。档位枚举与落档位的操作从这里发布，挑样本时按它配并行。

## public.viba

```bash public
import aisp.bench.checkpoint.level.types as level
import aisp.bench.checkpoint.level.apis as level_api

Level = level.Level
GetLevel = level_api.GetLevel
```

## types.viba

`Level` 是规模档位，从单机最小规模到十万卡共六级；`GetLevel` 按节点数与每节点卡数把一份样本配置落到其中一级。

```bash types
Level =
  Oneof
  | "S0" * { 单机，最小参数规模。对齐基准；度量项在容差内 }
  | "S1" * { 单机多卡或双机。引入并行切分与多 rank 并发；不变量保持 }
  | "S2" * { 数十至百卡。引入网络与共享存储的争用；不变量保持，偏差有归因 }
  | "S3" * { 千卡。引入调度与故障恢复；不变量保持，偏差有归因 }
  | "S4" * { 万卡。实测上限；不变量保持，偏差有归因 }
  | "S5" * { 十万卡。外推目标；不变量保持，外推结论登记 }
```

## 基本操作

只有一个操作：落档位。按节点数与每节点卡数把一份样本配置落到 S0 到 S5 的一级。

## apis.viba

```bash apis
import aisp.bench.checkpoint.sample.public as sample
import aisp.bench.checkpoint.level.types as level

GetLevel =
     level.Level
  <- $config (sample.SampleConfigBase * { 样本配置 })
  <- {
    导出属性：按节点数与每节点卡数落到 S0 到 S5 的哪一级，阈值由配方的 scaling 阶梯给
  }
```
