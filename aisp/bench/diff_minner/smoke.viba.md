# Diff Minner 真实写准入

## 需求背景

在正式对比前，用一次受控的 EFS/GPFS 真实写测试验证路径、权限、FIO 运行和原始产物留存。此操作只做准入检查，不计算性能差距，不产生 `candidate=true`。

## public.viba

```bash public
import aisp.bench.diff_minner.smoke.types as smoke
import aisp.bench.diff_minner.smoke.apis as smoke_api

SmokeRequest = smoke.SmokeRequest
SmokeResult = smoke.SmokeResult
RunSmokePair = smoke_api.RunSmokePair
```

## types.viba

```bash types
import aisp.bench.diff_minner.types as diff

SmokeRequest =
  Object
  * $efs_root (str * { EFS 中已有的被测目录；拒绝符号链接 })
  * $gpfs_root (str * { GPFS 中已有的被测目录；拒绝符号链接 })
  * $artifacts_root (str * { 原始 stdout、stderr 和 manifest 的输出目录；必须位于两侧被测文件系统之外 })
  * $size_bytes (int * { 每侧本次 FIO 文件大小，必须大于 0；参考实现默认 1073741824 })
  * $first (diff.StorageSide * { 首先执行的一侧；另一侧只执行一次，不重试 })

SmokeResult =
  Oneof
  | $completed (str * { 两侧 FIO 均完成且 JSON 产物通过结构检查；值为 manifest 绝对路径 })
  | $failed (str * { 任一已启动侧执行或产物检查失败；值为 manifest 绝对路径，另一侧可为 skipped })
  | $rejected (str * { 参数或写前预检失败；值为错误说明，此时尚未启动 FIO })
  | $interrupted (str * { 调用方中断；值为中断说明，已生成 manifest 时必须给出其路径 })
```

## 基本操作

- 执行前必须向调用方展示两侧真实写入路径、每侧文件大小、固定 120 秒时长和产物目录，并取得明确确认。
- 预检拒绝符号链接、相同或嵌套的两侧目录、相同 `st_dev`、空间不足，以及位于被测文件系统内的产物目录。
- 每侧只运行一次 `randwrite`：`bs=4k`、`ioengine=libaio`、`direct=1`、`iodepth=16`、`numjobs=1`、`time_based=1`。
- 原始 stdout、stderr 和 manifest 均保留。任何失败都不自动重试，也不删除被测文件。
- `completed` 只表示真实写准入完成。正式结论仍需完整比较格和 `CompareGroup` 判定。

## apis.viba

```bash apis
import aisp.bench.diff_minner.smoke.types as smoke

RunSmokePair =
     smoke.SmokeResult
  <- $request (smoke.SmokeRequest * { 同一份真实写准入请求 })
  <- {
    展示路径、容量、时长并取得明确确认后才启动 FIO；先完成全部预检，再按请求顺序分别执行 EFS 和 GPFS。保存原始产物，返回四种状态之一；不得由本次结果直接给出正式对比结论
  }
```

参考实现：`aisp/bench/diff_minner/smoke/scripts/smoke.py`。CLI 参数与 `SmokeRequest` 字段同名，退出码 `0/1/2/130` 分别映射到 `completed/failed/rejected/interrupted`。

测试：`python3 -m unittest discover -s aisp/bench/diff_minner/smoke/tests -v`。测试使用 fake FIO，不写真实 EFS 或 GPFS。
