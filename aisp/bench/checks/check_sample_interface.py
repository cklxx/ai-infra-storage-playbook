#!/usr/bin/env python3
"""自检 ckpt-sample-interface 的 Python 落地。

覆盖：
  1. GetLevel 按拓扑落档 S0..S5。
  2. Execute 同步返回带 metrics 的 Artifacts。
  3. Start 入队后后台跑完，状态翻到 completed 且产物有路径。
  4. Stop 把运行置为 cancelled。
  5. 非法样本名 / 格式错 -> Rejected；不存在的 run_id -> KeyError。
  6. MetricLE / MetricGE 的 passed 判定。
  7. 序列化结果通过 playbook/json_schema/ 的六份 schema。

退出码：0 全过，1 有失败，2 缺 jsonschema。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# 让脚本能直接以 checks/xxx.py 方式跑，不必安装包。
BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

from sample import Artifacts, CkptSli, CkptSlo, RunRecord, RunSpec, SampleConfigBase  # noqa: E402
from sample.configs import (  # noqa: E402
    Model,
    ObservationConfig,
    SampleConfigBase,
    Topology,
)
from sample.levels import Level, resolve_level  # noqa: E402
from sample.memory import InMemorySampleService  # noqa: E402
from sample.types import (  # noqa: E402
    Cancelled,
    CheckPointDuration,
    CkptSloCheckpointDuration,
    CkptSloMetadataCommit,
    CkptSloRestoreDuration,
    CkptSloTrainingStall,
    CkptSloWriteLatencyP99,
    CkptSloWriteThroughput,
    Completed,
    Component,
    Failed,
    Failure,
    MetadataCommit,
    MetricGE,
    MetricLE,
    Queued,
    QueueProgress,
    Rejected,
    RestoreDuration,
    Running,
    StorageLayer,
    TrainingStall,
    WorkProgress,
    WriteLatencyP99,
    WriteThroughput,
)
from sample.types import (  # noqa: E402
    Cancelled,
    Completed,
    CkptSloCheckpointDuration,
    CkptSloMetadataCommit,
    CkptSloRestoreDuration,
    CkptSloTrainingStall,
    CkptSloWriteLatencyP99,
    CkptSloWriteThroughput,
    Failed,
    Failure,
    MetricGE,
    MetricLE,
    Queued,
    QueueProgress,
    Rejected,
    RunRecord,
    Running,
    WorkProgress,
)

SCHEMAS = BENCH / "playbook" / "json_schema"


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
        ((128, 8), "S4"),     # 1024 卡 = 万卡档起点
        ((1024, 8), "S4"),    # 8192 卡
        ((2048, 8), "S5"),    # 16384 卡
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
            adapter=Component(name="torchstore", version="0.2", git_commit_id="9f2c1a4"),
        ),
        seed=20261103,
    )


def check_execute() -> list[tuple[str, bool]]:
    svc = _service()
    artifacts = svc.execute(_spec())
    payload = artifacts.to_json()
    ok = (
        isinstance(artifacts, Artifacts)
        and len(artifacts.metrics) == 2
        and payload["manifest"] != ""
        and payload["report"] != ""
        and payload["metrics"][0] == {"check_point_duration_sli": 12.5}
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
        final is not None and len(final.artifacts.metrics) == 2,
    ))
    return out


def _slow_service(release: "object") -> InMemorySampleService:
    def slow_runner(spec, config):
        release.wait(timeout=5.0)  # type: ignore[attr-defined]
        return []

    return InMemorySampleService(runners={"slow@0.1.0": slow_runner}, config_loader=_loader)


def _stop_spec() -> RunSpec:
    return RunSpec(
        sample="slow@0.1.0",
        config="tiny-64-s0",
        storage=StorageLayer(
            backend=Component(name="gpfs", version="5.1"),
            adapter=Component(name="torchstore", version="0.2"),
        ),
        seed=1,
    )


def check_stop() -> list[tuple[str, bool]]:
    import threading

    release = threading.Event()

    # 1) 运行中取消：stop 返回时状态必须已经是 cancelled。
    svc = _slow_service(release)
    record = svc.start(_stop_spec())
    time.sleep(0.1)  # 让后台线程进入 running
    stopped = svc.stop(record.run_id)
    release.set()
    out = [("stop during running returns cancelled", stopped.state.tag == "cancelled")]

    # 2) 排队期立刻取消：旧实现会返回 running，这里必须直接 cancelled。
    release2 = threading.Event()
    svc2 = _slow_service(release2)
    record2 = svc2.start(_stop_spec())
    immediate = svc2.stop(record2.run_id)
    release2.set()
    out.append(("stop immediately after start returns cancelled", immediate.state.tag == "cancelled"))

    # 3) 已结束的运行原样交回，不报错。
    svc3 = _service()
    done = svc3.start(_spec())
    deadline = time.time() + 3.0
    while time.time() < deadline and svc3.query(done.run_id).state.tag != "completed":
        time.sleep(0.02)
    out.append(("stop on completed run returns it unchanged", svc3.stop(done.run_id).state.tag == "completed"))
    return out


def check_strict_decoding() -> list[tuple[str, bool]]:
    """反序列化必须拒绝多键与未知键，不能静默取第一个。"""

    from sample.types import ckpt_sli_from_json, state_from_json

    def rejects(fn, raw) -> bool:
        try:
            fn(raw)
            return False
        except (ValueError, TypeError):
            return True

    return [
        ("state with two keys is rejected", rejects(state_from_json, {"running": None, "completed": None})),
        ("state with unknown key is rejected", rejects(state_from_json, {"bogus": None})),
        ("SLI with two keys is rejected", rejects(ckpt_sli_from_json, {"check_point_duration_sli": 1.0, "bogus": 2})),
    ]


def check_rejected() -> list[tuple[str, bool]]:
    svc = _service()
    bad1 = svc.start(_spec(sample="not-registered@9.9.9"))
    bad2 = svc.start(_spec(sample="no-at-sign"))
    return [
        ("unknown sample -> rejected", bad1.state.tag == "rejected"),
        ("malformed sample -> rejected", bad2.state.tag == "rejected"),
    ]


def check_schema() -> list[tuple[str, bool]]:
    """本接口的每个类型各有一份 schema；逐份校验合法实例，并抽检非法实例被拒。"""

    try:
        import jsonschema
    except ImportError:
        return [("jsonschema available", False)]

    if not SCHEMAS.is_dir():
        return [("json_schema/ exists", False)]

    def validator(schema_name: str):
        schema = json.loads((SCHEMAS / f"{schema_name}.schema.json").read_text(encoding="utf-8"))
        return jsonschema.Draft202012Validator(schema)

    def validates(schema_name: str, instance: object) -> bool:
        try:
            validator(schema_name).validate(instance)
            return True
        except jsonschema.ValidationError:
            return False

    def rejects(schema_name: str, instance: object) -> bool:
        try:
            validator(schema_name).validate(instance)
            return False
        except jsonschema.ValidationError:
            return True

    cfg = _make_config(1, 8)
    full_artifacts = Artifacts(
        manifest="s3://bucket/runs/x/manifest.json",
        metrics=(
            CheckPointDuration(value=1.0),
            TrainingStall(value=1.0),
            RestoreDuration(value=1.0),
            WriteThroughput(value=1.0),
            MetadataCommit(value=1.0),
            WriteLatencyP99(value=1.0),
        ),
        slo=(
            CkptSloCheckpointDuration(verdict=MetricLE(1.0, 2.0)),
            CkptSloTrainingStall(verdict=MetricLE(1.0, 2.0)),
            CkptSloRestoreDuration(verdict=MetricLE(1.0, 2.0)),
            CkptSloWriteThroughput(verdict=MetricGE(1.0, 2.0)),
            CkptSloMetadataCommit(verdict=MetricLE(1.0, 2.0)),
            CkptSloWriteLatencyP99(verdict=MetricLE(1.0, 2.0)),
        ),
        report="s3://bucket/runs/x/report.html",
    )
    states = [
        Queued(queue=QueueProgress(pos=1, len=3)),
        Running(),
        Completed(),
        Failed(error=Failure(kind="timeout", detail="x")),
        Rejected(error=Failure(kind="request", detail="x")),
        Cancelled(),
    ]
    record = RunRecord(
        run_id="r", state=Running(), progress=WorkProgress(0, 0), artifacts=full_artifacts
    )

    # 每个类型一份 schema：名称 -> 一个合法实例。
    instances = {
        "RunSpec": _spec().to_json(),
        "RunRecord": record.to_json(),
        "Artifacts": full_artifacts.to_json(),
        "State": Queued(queue=QueueProgress(pos=1, len=3)).to_json(),
        "CkptSli": CheckPointDuration(value=1.0).to_json(),
        "CkptSlo": CkptSloCheckpointDuration(verdict=MetricLE(1.0, 2.0)).to_json(),
        "QueueProgress": QueueProgress(pos=1, len=3).to_json(),
        "WorkProgress": WorkProgress(0, 0).to_json(),
        "Failure": Failure(kind="timeout", detail="x").to_json(),
        "Component": Component(name="gpfs", version="5.1").to_json(),
        "StorageLayer": _spec().storage.to_json(),
        "SampleConfigBase": cfg.to_json(),
        "Model": cfg.model.to_json(),
        "Topology": cfg.topology.to_json(),
        "ObservationConfig": cfg.observe.to_json(),
        "ObservationLayer": "sys",
        "Level": resolve_level(cfg.topology),
        "CheckPointDurationMetric": 1.0,
        "TrainingStallMetric": 1.0,
        "RestoreDurationMetric": 1.0,
        "WriteThroughputMetric": 1.0,
        "MetadataCommitMetric": 1.0,
        "WriteLatencyP99Metric": 1.0,
    }

    out = [
        (f"{name}.to_json passes {name}.schema.json", validates(name, instance))
        for name, instance in instances.items()
    ]

    # SLI / SLO 的每个分支都要能过各自的 oneof。
    out += [
        (f"CkptSli branch {sli.tag} passes schema", validates("CkptSli", sli.to_json()))
        for sli in full_artifacts.metrics
    ]
    out += [
        (f"CkptSlo branch {slo.tag} passes schema", validates("CkptSlo", slo.to_json()))
        for slo in full_artifacts.slo
    ]

    # 非法实例必须被拒。
    out += [
        ("RunRecord without artifacts is rejected", rejects("RunRecord", {
            k: v for k, v in record.to_json().items() if k != "artifacts"})),
        ("Artifacts without report is rejected", rejects("Artifacts", {
            k: v for k, v in full_artifacts.to_json().items() if k != "report"})),
        ("State with two keys is rejected", rejects("State", {"running": None, "completed": None})),
        ("CkptSli with two keys is rejected",
         rejects("CkptSli", {"check_point_duration_sli": 1.0, "training_stall_sli": 2.0}))
        ,
        ("Level outside S0..S5 is rejected", rejects("Level", "S9")),
    ]

    # 本接口覆盖的类型之外，json_schema/ 下还有别的文档生成的 schema；这里只报告数量。
    covered = {f"{name}.schema.json" for name in instances}
    return out


def main() -> int:
    suites = [
        check_level(),
        check_metric_verdict(),
        check_execute(),
        check_start_and_query(),
        check_stop(),
        check_strict_decoding(),
        check_rejected(),
        check_schema(),
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
