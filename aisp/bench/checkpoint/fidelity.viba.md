# 保真边界表

## public.viba

```bash public
import aisp.bench.checkpoint.fidelity.types as fidelity

FidelityBoundary = fidelity.FidelityBoundary
```

## types.viba

```bash types
import aisp.bench.checkpoint.bypass.types as bypass

Bypassed =
  Oneof
  | "yes" * { 整条路径被旁路，走的是替代实现 }
  | "no" * { 路径没有被旁路，走真实实现 }
  | "partial" * { 路径部分被旁路；必须写清部分的范围边界，例如「写入路径真实，元数据提交被 mock」 }

FidelityBoundary =
  Object
  * $path (str * { 被登记的代码路径或模块，写到函数级，例如 torch.distributed.checkpoint.save })
  * $bypassed (Bypassed * { 是否被旁路；partial 时必须写清部分的范围边界，例如「写入路径真实，元数据提交被 mock」 })
  * $method ((bypass.BypassMethod | nil) * { 用哪种手段旁路的；bypassed 为 no 时给 nil })
  * $fidelity (bypass.FidelityLevel * { 请求序列的保真等级；IO 路径一律不允许 L0，写 L0 说明评估对象已被替换，该路径的结论无效 })
  * $kept (str * { 保留了哪些，必须具体，例如「每个 rank 的独立分片写入」 })
  * $known_bias (str * { 这个偏差把哪个指标往哪个方向推高或压低；答不出方向的说明还没理解它。没有偏差写 none，不留空 })
```

## 基本操作

只有一个操作：登记一行。给出路径、旁路程度、手段、保真等级、保留项与已知偏差，返回这一行。

## apis.viba

```bash apis
import aisp.bench.checkpoint.bypass.types as bypass
import aisp.bench.checkpoint.fidelity.types as fidelity

Record =
     fidelity.FidelityBoundary
  <- $path (str * { 被登记的代码路径，写到函数级，例如 torch.distributed.checkpoint.save })
  <- $bypassed (fidelity.Bypassed * { 这条路径被旁路到什么程度 })
  <- $method ((bypass.BypassMethod | nil) * { 用哪种手段旁路；没有旁路给 nil })
  <- $fidelity (bypass.FidelityLevel * { 请求序列的保真等级 })
  <- $kept (str * { 保留了哪些，必须具体 })
  <- $known_bias (str * { 偏差把哪个指标往哪个方向推；没有偏差写 none })
  <- {
    登记一行保真边界：五条必填行一条不能少；IO 路径一律不允许 L0，写 L0 说明评估对象已被替换，该路径的结论无效
  }
```
