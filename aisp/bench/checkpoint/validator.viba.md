# 运行校验

## 需求背景

阈值判定之前，先要判这次运行算不算数。协议只说要求什么，校验负责把证据核出来：逐条核对，答合规、不合规或证据不足；只有合规的运行才进入判定与版本比较。判定、比较与读报告的人都按这一份走，所以 `ValidationEvidence`、`ValidationVerdict`、`ValidationFinding` 与校验操作从这里发布。

## public.viba

```bash public
import aisp.bench.checkpoint.validator.types as validator
import aisp.bench.checkpoint.validator.apis as validator_api

ValidationVerdict = validator.ValidationVerdict
ValidationEvidence = validator.ValidationEvidence
ValidationFinding = validator.ValidationFinding
Validate = validator_api.Validate
```

## types.viba

校验只做一件事：拿一份协议和一次运行，逐条核对证据。判定分三种：合规、不合规、证据不足；不合规与证据不足都不产生可比结论。

```bash types
import aisp.bench.checkpoint.protocol.public as protocol
import aisp.bench.checkpoint.sample.public as sample

ValidationEvidence =
  Object
  * $rule (protocol.ProtocolRule * { 对应哪条规则 })
  * $where (str * { 证据在哪：清单字段、trace 文件、计数器或日志的位置 })
  * $detail (str * { 观察到什么 })

ValidationFinding =
  Object
  * $rule ((protocol.ProtocolRule | nil) * { 哪条规则没有通过；nil 表示协议版本不一致这类前置条件 })
  * $where (str * { 证据在哪：清单字段、trace 文件、计数器或日志的位置 })
  * $detail (str * { 观察到什么；缺证据时写清缺哪份产物 })

ValidationVerdict =
  Oneof
  | $valid (list[ValidationEvidence] * { 每条规则都有证据且满足；证据随判定留档 })
  | $invalid (list[ValidationFinding] * { 至少一条规则或前置条件不满足；这次运行作废 })
  | $incomplete (list[ValidationFinding] * { 至少一条规则缺证据；补齐后重判，当前不产生结论 })
```

## 基本操作

只有一个操作：校验一次运行。先核运行记录的协议版本与当前协议是否一致，不一致直接答不合规；这一步是前置条件，不写成协议规则。再逐条核对证据：全部满足答合规，有规则不满足答不合规，有规则缺证据答证据不足。不合规与证据不足的运行不进入判定，也不参与版本比较。

## apis.viba

```bash apis
import aisp.bench.checkpoint.validator.types as validator
import aisp.bench.checkpoint.protocol.public as protocol
import aisp.bench.checkpoint.sample.public as sample

Validate =
     validator.ValidationVerdict
  <- $protocol (protocol.RunProtocol * { 这次评测共用的协议；逐条按它核对 })
  <- $run (sample.RunRecord * { 一次已经跑完的运行 })
  <- {
    先核 RunRecord.protocol_version 与 protocol.version 是否一致；再逐条核对：规则有证据且满足答合规，证据齐全但不满足答不合规，缺证据答证据不足。返回判定与证据
  }
```
