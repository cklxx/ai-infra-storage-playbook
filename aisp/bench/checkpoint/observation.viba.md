# 采集层

## 需求背景

trace 有没有来源，取决于开跑前开了哪几层观测。采集层的取值决定数据的口径与观测开销，运行与判定都从这里取，所以本篇把它发布成 public。

## public.viba

```bash public
import aisp.bench.checkpoint.observation.types as observation
import aisp.bench.checkpoint.observation.apis as observation_api

ObservationLayer = observation.ObservationLayer
Collect = observation_api.Collect
```

## types.viba

```bash types
ObservationLayer =
  Oneof
  | "app" * { 在数据加载器、写入器、block manager 外面包一层。拿得到请求的逻辑含义、偏移、大小、调用栈；看不到合并后的真实请求 }
  | "sys" * { 块设备 trace、文件系统客户端统计、网络计数器。拿得到真实下发的请求、排队、重传；丢失逻辑归属，难以按 rank 拆分 }
  | "storage" * { 存储服务端的请求日志与指标。拿得到服务端视角的吞吐、尾延迟、元数据操作；采样率与聚合粒度受限 }
```

## 基本操作

只有一个操作：开观测。给出想开的层，返回实际开起来的层。

## apis.viba

```bash apis
import aisp.bench.checkpoint.observation.types as observation

Collect =
     list[observation.ObservationLayer]
  <- $wanted (list[observation.ObservationLayer] * { 想开的层 })
  <- {
    开观测：写清每层的采样率与统计口径；少于两层就不足以交叉核对，返回实际开起来的层
  }
```
