#!/usr/bin/env python3
"""命令行入口：读 RunSpec JSON + SampleConfigBase JSON，跑一次并落盘 Artifacts。

用法：
    python3 -m sample.runner_cli --spec spec.json --config config.json --out artifacts.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import (
    Component,
    InMemorySampleService,
    Model,
    ObservationConfig,
    RunSpec,
    SampleConfigBase,
    StorageLayer,
    Topology,
)
from .samples import tiny_ckpt


def load_spec(path: Path) -> RunSpec:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return RunSpec(
        sample=raw["sample"],
        config=raw["config"],
        storage=StorageLayer(
            backend=Component(
                name=raw["storage"]["backend"]["name"],
                version=raw["storage"]["backend"]["version"],
                git_commit_id=raw["storage"]["backend"].get("git_commit_id"),
            ),
            adapter=Component(
                name=raw["storage"]["adapter"]["name"],
                version=raw["storage"]["adapter"]["version"],
                git_commit_id=raw["storage"]["adapter"].get("git_commit_id"),
            ),
        ),
        seed=raw["seed"],
    )


def load_config(path: Path) -> SampleConfigBase:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SampleConfigBase(
        model=Model(id=raw["model"]["id"], git_commit_id=raw["model"]["git_commit_id"]),
        topology=Topology(
            nodes=raw["topology"]["nodes"],
            gpus_per_node=raw["topology"]["gpus_per_node"],
            network=raw["topology"]["network"],
            mount=raw["topology"]["mount"],
        ),
        observe=ObservationConfig(
            enabled=raw["observe"]["enabled"],
            sample_rate=raw["observe"]["sample_rate"],
            layers=tuple(raw["observe"]["layers"]),
        ),
    )


def artifacts_to_json(artifacts, level: str) -> dict:
    return {
        "level": level,
        "manifest": artifacts.manifest,
        "report": artifacts.report,
        "metrics": [
            {"name": m.tag, "value": m.value} for m in artifacts.metrics
        ],
        "slo": [
            {"name": s.tag, "actual": s.verdict.actual, "threshold": s.verdict.threshold}
            for s in artifacts.slo
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    spec = load_spec(args.spec)
    config = load_config(args.config)

    svc = InMemorySampleService(
        runners={"tiny-ckpt@0.1.0": tiny_ckpt.runner},
        config_loader=lambda name: config,
    )
    level = svc.get_level(config)
    artifacts = svc.execute(spec)

    payload = artifacts_to_json(artifacts, level)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "level": level, "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
