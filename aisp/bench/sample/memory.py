"""SampleService 的内存参考实现。

只用于开发期自检与单机回放；不做进程隔离、不落盘到对象存储。
Start 在后台线程里跑 Execute，Query/Stop 通过锁与事件同步状态。
"""

from __future__ import annotations

import itertools
import threading
import time
import uuid
from dataclasses import replace
from typing import Callable, Dict, Optional

from .apis import SampleRunner
from .configs import SampleConfigBase, resolve_level
from .types import (
    Artifacts,
    Cancelled,
    Completed,
    Failed,
    Failure,
    Queued,
    QueueProgress,
    Rejected,
    Running,
    RunRecord,
    RunSpec,
    State,
    WorkProgress,
)


ConfigLoader = Callable[[str], SampleConfigBase]
ArtifactWriter = Callable[[str, RunSpec, SampleConfigBase, Artifacts], Artifacts]


def _default_artifact_writer(
    run_id: str, spec: RunSpec, config: SampleConfigBase, artifacts: Artifacts
) -> Artifacts:
    """默认 writer：只把路径写成内存占位，不落盘。生产实现替换成对象存储。"""

    return replace(
        artifacts,
        manifest=f"memory://runs/{run_id}/manifest.json",
        report=f"memory://runs/{run_id}/report.html",
    )


class InMemorySampleService:
    """单机同步/异步参考实现。

    - ``runners``：按 ``sample`` 字段（``name@version``）注册的样本执行器。
    - ``config_loader``：按 spec.config 名字加载 SampleConfigBase。
    - ``artifact_writer``：Execute 结束后落盘四份产物，返回带路径的 Artifacts。
    """

    def __init__(
        self,
        runners: Dict[str, SampleRunner],
        config_loader: ConfigLoader,
        artifact_writer: Optional[ArtifactWriter] = None,
    ) -> None:
        self._runners = dict(runners)
        self._load_config = config_loader
        self._write_artifacts = artifact_writer or _default_artifact_writer

        self._lock = threading.Lock()
        self._records: Dict[str, RunRecord] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._queue_order = itertools.count(1)

    # ------------------------------------------------------------------
    # SampleService
    # ------------------------------------------------------------------

    def get_level(self, config: SampleConfigBase) -> str:
        return resolve_level(config.topology)

    def start(self, spec: RunSpec) -> RunRecord:
        run_id = uuid.uuid4().hex
        try:
            self._validate(spec)
        except ValueError as exc:
            record = RunRecord(
                run_id=run_id,
                state=Rejected(error=Failure(kind="request", detail=str(exc))),
            )
            self._records[run_id] = record
            return record

        with self._lock:
            pos = next(self._queue_order)
            record = RunRecord(
                run_id=run_id,
                state=Queued(queue=QueueProgress(pos=pos, len=pos)),
                progress=WorkProgress(0, 0),
            )
            self._records[run_id] = record
            cancel_event = threading.Event()
            self._cancel_events[run_id] = cancel_event

        thread = threading.Thread(
            target=self._run_background, args=(run_id, spec, cancel_event), daemon=True
        )
        self._threads[run_id] = thread
        thread.start()
        return record

    def stop(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._records.get(run_id)
            if record is None:
                raise KeyError(run_id)
            if record.state.tag in ("completed", "failed", "cancelled", "rejected"):
                return record
            event = self._cancel_events.get(run_id)

        if event is not None:
            event.set()
        # 后台线程会在下一个检查点把状态翻成 cancelled；调用方随后 Query 即可。
        return self.query(run_id)

    def query(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._records.get(run_id)
            if record is None:
                raise KeyError(run_id)
            return record

    def execute(self, spec: RunSpec) -> Artifacts:
        self._validate(spec)
        config = self._load_config(spec.config)
        runner = self._runners[spec.sample]
        metrics = list(runner(spec, config))
        artifacts = Artifacts(metrics=tuple(metrics), slo=())
        # 落盘由 writer 完成；这里没有 run_id 概念，用 spec 的 sample 当占位。
        return self._write_artifacts(f"sync-{spec.sample}", spec, config, artifacts)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _validate(self, spec: RunSpec) -> None:
        if "@" not in spec.sample:
            raise ValueError(f"sample 必须写成 name@version，得到 {spec.sample!r}")
        if spec.sample not in self._runners:
            raise ValueError(f"未注册的样本: {spec.sample}")
        if spec.seed < 0:
            raise ValueError("seed 必须为非负整数")

    def _run_background(
        self, run_id: str, spec: RunSpec, cancel_event: threading.Event
    ) -> None:
        self._set_state(run_id, Running(), progress=WorkProgress(0, 0))
        try:
            if cancel_event.is_set():
                self._set_state(run_id, Cancelled())
                return

            config = self._load_config(spec.config)
            runner = self._runners[spec.sample]

            # 样本执行期间，runner 自己决定是否响应取消；这里只在结束点检查一次。
            metrics = list(runner(spec, config))
            if cancel_event.is_set():
                self._set_state(run_id, Cancelled())
                return

            artifacts = Artifacts(metrics=tuple(metrics), slo=())
            artifacts = self._write_artifacts(run_id, spec, config, artifacts)
            self._set_state(
                run_id,
                Completed(),
                progress=WorkProgress(len(metrics), max(1, len(metrics))),
                artifacts=artifacts,
            )
        except Exception as exc:  # noqa: BLE001 - 样本失败全部归类为 assertion
            self._set_state(
                run_id,
                Failed(error=Failure(kind="assertion", detail=f"{type(exc).__name__}: {exc}")),
            )

    def _set_state(
        self,
        run_id: str,
        state: State,
        progress: Optional[WorkProgress] = None,
        artifacts: Optional[Artifacts] = None,
    ) -> None:
        with self._lock:
            old = self._records[run_id]
            self._records[run_id] = RunRecord(
                run_id=run_id,
                state=state,
                progress=progress if progress is not None else old.progress,
                artifacts=artifacts if artifacts is not None else old.artifacts,
            )
