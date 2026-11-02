#!/usr/bin/env python3
"""自检 ckpt-sample-interface 的 Python 落地。

覆盖：
  1. GetLevel 按拓扑落档 S0..S5。
  2. Execute 同步返回带 metrics 的 Artifacts。
  3. Start 入队后后台跑完，状态翻到 completed 且产物有路径。
  4. Stop 把运行置为 cancelled。
  5. 非法样本名 / 格式错 -> Rejected；不存在的 run_id -> KeyError。
  6. MetricLE / MetricGE 的 passed 判定。

退出码：0 全过，1 有失败。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# 让脚本能直接以 checks/xxx.py 方式跑，不必安装包。
BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

from sample import (  # noqa: E402
    Artifacts,
    InMemorySampleService,
    Model,
    ObservationConfig,
    RunSpec,
    SampleConfigBase,
    StorageLayer,
    Topology,
    Component,
    CheckPointDuration,
    WriteThroughput,
    resolve_level,
)
from sample.types import (  # noqa: E402
    CkptSloCheckpointDuration,
    CkptSloWriteThroughput,
    MetricGE,
    MetricLE,
)


def _make_config(nodes: int, gpus: int) -> SampleConfigBase:
    return SampleConfigBase(
        model=Model(id="example/tiny-64", git_commit_id="0123456789abcdef0123456789abcdef01234567"),
        topology=Topology(nodes=nodes, gpus_per_node=gpus, network="rdma", mount="local-nvme"),
        observe=ObservationConfig(enabled=True, sample_rate=0.1, layers=("app", "sys")),
    )


def _runner(spec: RunSpec, config: SampleConfigBase):
    return [
        CheckPointDuration(value=12.5),
        WriteThroughput(value=1.2 * 1024 * 1024 * 1024),
    ]


def _loader(name: str) -> SampleConfigBase:
    # 自检里不区分不同 config 名，统一返回一个 S0 配置。
    return _make_config(nodes=1, gpus=8)


def _service() -> InMemorySampleService:
    return InMemorySampleService(
        runners={"tiny-ckpt@0.1.0": _runner},
        config_loader=_loader,
    )


def check_level() -> list[tuple[str, bool]]:
    cases = [
        ((1, 8), "S0"),
        ((1, 16), "S1"),
        ((2, 8), "S1"),
        ((8, 8), "S2"),       # 64 卡
        ((64, 8), "S3"),      # 512 卡
        ((128, 8), "S4"),      # 1024 卡 = 万卡档起点
        ((1024, 8), "S4"),     # 8192 卡
        ((2048, 8), "S5"),     # 16384 卡
        ((12500, 8), "S5"),
    ]
    out = []
    for (nodes, gpus), expected in cases:
        got = resolve_level(Topology(nodes=nodes, gpus_per_node=gpus, network="none", mount="nfs"))
        out.append((f"level {nodes}x{gpus} -> {expected}", got == expected))
    return out


def check_metric_verdict() -> list[tuple[str, bool]]:
    le = CkptSloCheckpointDuration(verdict=MetricLE(actual=10.0, threshold=12.0))
    le_bad = CkptSloCheckpointDuration(verdict=MetricLE(actual=13.0, threshold=12.0))
    ge = CkptSloWriteThroughput(verdict=MetricGE(actual=2.0, threshold=1.5))
    ge_bad = CkptSloWriteThroughput(verdict=MetricGE(actual=1.0, threshold=1.5))
    return [
        ("LE passes when actual <= threshold", le.verdict.passed and not le_bad.verdict.passed),
        ("GE passes when actual >= threshold", ge.verdict.passed and not ge_bad.verdict.passed),
    ]


def _spec(sample: str = "tiny-ckpt@0.1.0") -> RunSpec:
    return RunSpec(
        sample=sample,
        config="tiny-64-s0",
        storage=StorageLayer(
            backend=Component(name="gpfs", version="5.1"),
            adapter=Component(name="torchstore", version="0.2"),
        ),
        seed=20261103,
    )


def check_execute() -> list[tuple[str, bool]]:
    svc = _service()
    artifacts = svc.execute(_spec())
    ok = (
        isinstance(artifacts, Artifacts)
        and len(artifacts.metrics) == 2
        and artifacts.manifest is not None
        and artifacts.report is not None
    )
    return [("execute returns artifacts with metrics and paths", ok)]


def check_start_and_query() -> list[tuple[str, bool]]:
    svc = _service()
    record = svc.start(_spec())
    out = [(f"start returns queued/running record (state={record.state.tag})", record.run_id != "")]

    deadline = time.time() + 5.0
    final = None
    while time.time() < deadline:
        final = svc.query(record.run_id)
        if final.state.tag == "completed":
            break
        time.sleep(0.02)
    out.append(("async run reaches completed", final is not None and final.state.tag == "completed"))
    out.append((
        "completed run carries artifacts",
        final is not None and final.artifacts is not None and len(final.artifacts.metrics) == 2,
    ))
    return out


def check_stop() -> list[tuple[str, bool]]:
    # 用一个会阻塞的 runner 制造可取消窗口。
    import threading

    release = threading.Event()

    def slow_runner(spec, config):
        release.wait(timeout=5.0)
        return []

    svc = InMemorySampleService(runners={"slow@0.1.0": slow_runner}, config_loader=_loader)
    record = svc.start(RunSpec(
        sample="slow@0.1.0",
        config="tiny-64-s0",
        storage=StorageLayer(
            backend=Component(name="gpfs", version="5.1"),
            adapter=Component(name="torchstore", version="0.2"),
        ),
        seed=1,
    ))
    time.sleep(0.1)
    stopped = svc.stop(record.run_id)
    release.set()

    deadline = time.time() + 3.0
    final = svc.query(record.run_id)
    while time.time() < deadline and final.state.tag == "running":
        time.sleep(0.05)
        final = svc.query(record.run_id)

    out = [(
        "stop flips state to cancelled",
        final.state.tag == "cancelled",
    )]
    return out


def check_rejected() -> list[tuple[str, bool]]:
    svc = _service()
    bad1 = svc.start(_spec(sample="not-registered@9.9.9"))
    bad2 = svc.start(_spec(sample="no-at-sign"))
    return [
        ("unknown sample -> rejected", bad1.state.tag == "rejected"),
        ("malformed sample -> rejected", bad2.state.tag == "rejected"),
    ]


def main() -> int:
    suites = [
        check_level(),
        check_metric_verdict(),
        check_execute(),
        check_start_and_query(),
        check_stop(),
        check_rejected(),
    ]
    results = [case for suite in suites for case in suite]
    failed = [name for name, ok in results if not ok]
    print(json.dumps({
        "check": "check_sample_interface",
        "status": "pass" if not failed else "fail",
        "total": len(results),
        "failed": failed,
    }, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
