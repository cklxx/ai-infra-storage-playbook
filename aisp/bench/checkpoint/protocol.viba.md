# 评测协议

## 需求背景

同一个 checkpoint，换一种跑法就得到另一组数。两次运行要能比，前提是都按同一份协议执行：前置条件一致、步骤固定、计时点固定、证据留全。运行、校验与判定都按这一份走，所以 `RunProtocol`、`ProtocolRule`、`ProtocolEvidence` 与定协议的操作从这里发布。

## public.viba

```bash public
import aisp.bench.checkpoint.protocol.types as protocol
import aisp.bench.checkpoint.protocol.apis as protocol_api

RunProtocol = protocol.RunProtocol
ProtocolRule = protocol.ProtocolRule
ProtocolEvidence = protocol.ProtocolEvidence
Adopt = protocol_api.Adopt
```

## types.viba

协议由一组规则、重复次数、预热步数、字节容差与超时组成；规则逐条对应单次运行能核对的证据，没有证据的运行不算合规。重复次数不在单次运行里核对，比较前按协议凑齐。

```bash types
ProtocolRule =
  Oneof
  | "real_io_path" * { 写入与读取走真实存储实现：旁路只作用在计算，checkpoint 的写入与读取没换实现、没缓冲合并，请求序列保真不低于 L2。证据：旁路计划里的手段与保真等级 }
  | "pinned_config" * { 模型 commit、训练框架版本、存储 backend 与 adapter 版本、拓扑（含 DP/TP/PP/EP）、预热步数与超时全部写进运行清单，跑完不再改。证据：manifest }
  | "observation_layers" * { 观测至少开两层且含 sys；要测写请求时延还必须含 app。证据：Collect 交回的实际层 }
  | "warmup" * { 测量前跑够预热步数，存储与缓存进入稳态。证据：trace 时间线里预热段与测量段分开 }
  | "cold_read" * { 恢复前丢掉页缓存与客户端缓存；不丢就把读测成内存带宽。证据：读前清缓存的记录 }
  | "same_bytes" * { 实际写入字节数与按模型配置推算的字节数一致，相对误差不超过协议给的容差。证据：trace 字节计数与配置推算 }
  | "all_ranks_committed" * { 每个 rank 都写完自己的分片并收到提交确认；缺一个 rank 这次运行就不完整。证据：rank 级完成记录 }
  | "isolated_window" * { 测量窗口内这套存储没有别的负载共用。证据：集群作业记录或存储侧基线 }
  | "within_timeout" * { 单次运行没有超过协议给的超时；超时的运行不产生结论。证据：trace 的首条与末条时间戳 }
  | "protocol_version_match" * { 运行记录的协议版本与当前协议一致；版本不同，历史结果不参与比较。证据：RunRecord.protocol_version }
  | "artifacts_complete" * { manifest、trace、三项 SLI 与人读报告齐全；slo 由判定填，不在校验时要求。证据：Artifacts 的 manifest、trace、metrics、report }

ProtocolEvidence =
  Object
  * $rule (ProtocolRule * { 对应哪条规则 })
  * $ok (bool * { 这条规则是否满足 })
  * $where (str * { 证据在哪：清单字段、trace 文件、计数器或日志的位置 })
  * $detail (str * { 观察到什么；不满足时写清差在哪 })

RunProtocol =
  Object
  * $version (str * { 协议版本；规则、重复次数、预热步数、容差或超时任一变化都要换版本，历史结果只在同版本内可比 })
  * $rules (list[ProtocolRule] * { 这次评测要满足的规则；列出的每一条都要有证据 })
  * $repeat (int * { 同一配置重复几次；至少 3，取中位数；单次运行校验不了重复次数，比较前按它凑齐 })
  * $warmup_steps (int * { 测量前跑多少步预热；按模型与并行配置定 })
  * $byte_tolerance (float * { 写入字节数允许的相对误差；默认 0.01 })
  * $timeout_s (float * { 单次运行超时；超时记为不合规 })
```

## 基本操作

只有一个操作：定协议。按评测目标列出规则、重复次数、预热步数、字节容差与超时，形成一个带版本号的 `RunProtocol`；规则缺一条，协议就不完整，这次评测的结果不进结论。

首版协议固定为：`version` 取 `ckpt-bench-v1`，`rules` 取上面十一条，`repeat` 取 3，`byte_tolerance` 取 0.01；`warmup_steps` 按模型规模与并行配置定，`timeout_s` 按同类运行实测时长的两倍定。改规则或改其中任一数值都要换 `version`，旧版本的结果不参与新版本的比较。

## apis.viba

```bash apis
import aisp.bench.checkpoint.protocol.types as protocol

Adopt =
     protocol.RunProtocol
  <- $version (str * { 协议版本；规则、重复次数、预热步数、容差或超时任一变化都要换版本 })
  <- $rules (list[protocol.ProtocolRule] * { 这次评测要满足的规则；一条不能少 })
  <- $repeat (int * { 同一配置重复几次；至少 3；凑不齐就不进比较 })
  <- $warmup_steps (int * { 测量前跑多少步预热 })
  <- $byte_tolerance (float * { 写入字节数允许的相对误差 })
  <- $timeout_s (float * { 单次运行超时，秒 })
  <- {
    定协议：规则按评测目标列全，repeat 至少 3，warmup_steps 按模型与并行配置定；返回带版本号的协议，运行、校验与判定都按它走。重复次数由比较前凑齐，不由单次运行的校验判定
  }
```
