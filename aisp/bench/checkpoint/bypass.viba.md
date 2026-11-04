# 旁路手段与保真等级

## public.viba

```bash public
import aisp.bench.checkpoint.bypass.types as bypass

BypassMethod = bypass.BypassMethod
FidelityLevel = bypass.FidelityLevel
```

## types.viba

```bash types
BypassMethod =
  Oneof
  | "meta_device" * { 张量只保留 dtype 与逻辑尺寸，不分配显存/内存。请求序列 L2；成本极低；用于需要真实控制流的全部计算 }
  | "module_mock" * { 替换指定模块的 forward/step，返回预先约定的张量。请求序列 L2；成本低；用于只关心某几条 IO 路径、其余整段旁路 }
  | "cpu_offload" * { 计算在 CPU 上用极小规模真实执行。请求序列 L2；成本中；用于需要真实 kernel 调用顺序、但不需要 GPU }
  | "real_small_scale" * { 不做旁路，直接小规模真实运行。请求序列 L3；成本高；用于标定其它手段的偏差 }

FidelityLevel =
  Oneof
  | "L0" * { 只保证调用到同一对外接口，内部实现已被替换，例如用自己的写入器替代框架的 checkpoint 实现 }
  | "L1" * { 代码路径相同，但请求在本地被缓冲或合并，请求的大小与偏移已经改变 }
  | "L2" * { 代码路径与请求序列相同，每条请求与真实运行一一对应 }
  | "L3" * { 在 L2 之上，时序与并发也与真实运行一致，跨节点传输是真实的 }
```

## 基本操作

只有一个操作：选手段。给出这个配方要求的保真等级与可接受的成本，在四种手段里挑一个。

## apis.viba

```bash apis
import aisp.bench.checkpoint.bypass.types as bypass

Choose =
     bypass.BypassMethod
  <- $needed (bypass.FidelityLevel * { 这个配方要求请求序列达到的保真等级 })
  <- $budget (str * { 可接受的成本：低、中、高 })
  <- {
    在四种手段里挑一个：成本与保真度递增，达到要求的保真等级里挑成本最低的；L3 只用于对齐基准，不用于批量运行
  }
```
