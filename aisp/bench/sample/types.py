"""Checkpoint 样本接口的类型定义。

对齐 ``playbook/ckpt-sample-interface.md`` 的 ``types`` 模块。
所有结构用标准库 dataclass；oneof 用带 ``tag`` 字段的 discriminated union。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Union


# ---------------------------------------------------------------------------
# 存储两层
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Component:
    """一个存储组件：纯存储系统或传输适配层。"""

    name: str
    version: str
    git_commit_id: Optional[str] = None  # 只发版本不发源码时为 None


@dataclass(frozen=True)
class StorageLayer:
    """一次运行要评的存储两层：backend 纯存储，adapter 传输适配。"""

    backend: Component
    adapter: Component


# ---------------------------------------------------------------------------
# 状态机
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueueProgress:
    pos: int
    len: int


@dataclass(frozen=True)
class WorkProgress:
    done: int
    total: int  # 还没算出来时为 0


@dataclass(frozen=True)
class Failure:
    kind: str  # environment / dependency / timeout / observation / assertion ...
    detail: str


# State 的六种取值。tag 字段用于 discriminated union。
QueuedState = tuple[Literal["queued"], QueueProgress]
RunningState = tuple[Literal["running"], None]
CompletedState = tuple[Literal["completed"], None]
FailedState = tuple[Literal["failed"], Failure]
RejectedState = tuple[Literal["rejected"], Failure]
CancelledState = tuple[Literal["cancelled"], None]

# 为了让 dataclass 风格统一，下面用带 tag 的 dataclass 替代上面的 tuple 别名。


@dataclass(frozen=True)
class Queued:
    tag: Literal["queued"] = "queued"
    queue: Optional[QueueProgress] = None


@dataclass(frozen=True)
class Running:
    tag: Literal["running"] = "running"


@dataclass(frozen=True)
class Completed:
    tag: Literal["completed"] = "completed"


@dataclass(frozen=True)
class Failed:
    tag: Literal["failed"] = "failed"
    error: Failure = field(default_factory=lambda: Failure(kind="assertion", detail=""))


@dataclass(frozen=True)
class Rejected:
    tag: Literal["rejected"] = "rejected"
    error: Failure = field(default_factory=lambda: Failure(kind="assertion", detail=""))


@dataclass(frozen=True)
class Cancelled:
    tag: Literal["cancelled"] = "cancelled"


State = Union[Queued, Running, Completed, Failed, Rejected, Cancelled]


# ---------------------------------------------------------------------------
# SLI 与 SLO
# ---------------------------------------------------------------------------


# 六种 SLI。底层都是 float，类型名承担语义与单位。
CheckPointDurationMetric = float  # 一次 checkpoint 从开始写到元数据可见，秒
TrainingStallMetric = float       # 训练被写入阻塞的时长，秒
RestoreDurationMetric = float     # 从 checkpoint 恢复到可继续训练，秒
WriteThroughputMetric = float     # 写入期间按 rank 聚合的吞吐，字节/秒
MetadataCommitMetric = float      # 分片元数据提交到可见，毫秒
WriteLatencyP99Metric = float     # 单个写请求 P99，毫秒


@dataclass(frozen=True)
class CheckPointDuration:
    tag: Literal["checkpoint_duration_s"] = "checkpoint_duration_s"
    value: CheckPointDurationMetric = 0.0


@dataclass(frozen=True)
class TrainingStall:
    tag: Literal["training_stall_s"] = "training_stall_s"
    value: TrainingStallMetric = 0.0


@dataclass(frozen=True)
class RestoreDuration:
    tag: Literal["restore_duration_s"] = "restore_duration_s"
    value: RestoreDurationMetric = 0.0


@dataclass(frozen=True)
class WriteThroughput:
    tag: Literal["write_throughput_bps"] = "write_throughput_bps"
    value: WriteThroughputMetric = 0.0


@dataclass(frozen=True)
class MetadataCommit:
    tag: Literal["metadata_commit_ms"] = "metadata_commit_ms"
    value: MetadataCommitMetric = 0.0


@dataclass(frozen=True)
class WriteLatencyP99:
    tag: Literal["write_latency_p99_ms"] = "write_latency_p99_ms"
    value: WriteLatencyP99Metric = 0.0


CkptSli = Union[
    CheckPointDuration,
    TrainingStall,
    RestoreDuration,
    WriteThroughput,
    MetadataCommit,
    WriteLatencyP99,
]


@dataclass(frozen=True)
class MetricLE:
    """actual 不超过 threshold 即通过。"""

    actual: float
    threshold: float

    @property
    def passed(self) -> bool:
        return self.actual <= self.threshold


@dataclass(frozen=True)
class MetricGE:
    """actual 不低于 threshold 即通过。"""

    actual: float
    threshold: float

    @property
    def passed(self) -> bool:
        return self.actual >= self.threshold


# 每个 SLO 绑定一个 SLI 类型。
@dataclass(frozen=True)
class CkptSloCheckpointDuration:
    tag: Literal["checkpoint_duration_s"] = "checkpoint_duration_s"
    verdict: MetricLE = field(default_factory=lambda: MetricLE(0.0, 0.0))


@dataclass(frozen=True)
class CkptSloTrainingStall:
    tag: Literal["training_stall_s"] = "training_stall_s"
    verdict: MetricLE = field(default_factory=lambda: MetricLE(0.0, 0.0))


@dataclass(frozen=True)
class CkptSloRestoreDuration:
    tag: Literal["restore_duration_s"] = "restore_duration_s"
    verdict: MetricLE = field(default_factory=lambda: MetricLE(0.0, 0.0))


@dataclass(frozen=True)
class CkptSloWriteThroughput:
    tag: Literal["write_throughput_bps"] = "write_throughput_bps"
    verdict: MetricGE = field(default_factory=lambda: MetricGE(0.0, 0.0))


@dataclass(frozen=True)
class CkptSloMetadataCommit:
    tag: Literal["metadata_commit_ms"] = "metadata_commit_ms"
    verdict: MetricLE = field(default_factory=lambda: MetricLE(0.0, 0.0))


@dataclass(frozen=True)
class CkptSloWriteLatencyP99:
    tag: Literal["write_latency_p99_ms"] = "write_latency_p99_ms"
    verdict: MetricLE = field(default_factory=lambda: MetricLE(0.0, 0.0))


CkptSlo = Union[
    CkptSloCheckpointDuration,
    CkptSloTrainingStall,
    CkptSloRestoreDuration,
    CkptSloWriteThroughput,
    CkptSloMetadataCommit,
    CkptSloWriteLatencyP99,
]


# ---------------------------------------------------------------------------
# 产物与运行请求
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Artifacts:
    """一次运行写完的四份产物。路径由服务落盘后填；没跑完时为 None。"""

    manifest: Optional[str] = None
    metrics: tuple[CkptSli, ...] = ()
    slo: tuple[CkptSlo, ...] = ()
    report: Optional[str] = None


Level = Literal["S0", "S1", "S2", "S3", "S4", "S5"]


@dataclass(frozen=True)
class RunRecord:
    """服务返回给调用方的运行标识、状态、进度与产物位置。"""

    run_id: str
    state: State
    progress: WorkProgress = field(default_factory=lambda: WorkProgress(0, 0))
    artifacts: Optional[Artifacts] = None


@dataclass(frozen=True)
class RunSpec:
    """提交给样本服务的一次运行请求。"""

    sample: str       # name@version
    config: str       # 样本 repo 里那份 SampleConfigBase 的名字
    storage: StorageLayer
    seed: int
