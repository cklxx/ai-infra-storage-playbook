#!/usr/bin/env python3
"""Run one isolated FIO pair. This does not produce a Diff Minner verdict."""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

DURATION_S = 120
PERCENTILES = ("50.000000", "99.000000", "99.900000")


def now():
    return datetime.now(timezone.utc).isoformat()


def save_manifest(path, manifest):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_fio_json(raw):
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("FIO output must be a JSON object")
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 1:
        raise ValueError("expected exactly one FIO job")
    job = jobs[0]
    if not isinstance(job, dict) or job.get("error") != 0:
        raise ValueError(f"FIO job error: {job.get('error') if isinstance(job, dict) else 'invalid job'}")
    write = job.get("write")
    if not isinstance(write, dict) or not finite_number(write.get("iops")):
        raise ValueError("missing or invalid write IOPS")
    if write["iops"] <= 0:
        raise ValueError("write IOPS must be positive")
    clat = write.get("clat_ns")
    percentiles = clat.get("percentile") if isinstance(clat, dict) else None
    if not isinstance(percentiles, dict):
        raise ValueError("missing completion-latency percentiles")
    for key in PERCENTILES:
        value = percentiles.get(key)
        if not finite_number(value) or value < 0:
            raise ValueError(f"invalid completion-latency percentile: {key}")


def kill_process_group(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def run_side(side, test_dir, artifacts, args, manifest, manifest_path):
    record = manifest["sides"][side]
    raw_path = artifacts / f"{side}.stdout.json"
    error_path = artifacts / f"{side}.stderr.log"
    filename = test_dir / "smoke.bin"
    argv = [
        args.fio,
        "--name=diff-minner-smoke",
        "--rw=randwrite",
        "--bs=4k",
        "--ioengine=libaio",
        "--direct=1",
        "--iodepth=16",
        "--numjobs=1",
        f"--runtime={DURATION_S}",
        "--time_based=1",
        f"--size={args.size_bytes}",
        "--group_reporting=1",
        "--percentile_list=50:99:99.9",
        "--output-format=json",
        "--eta=never",
        f"--filename={filename}",
    ]
    record.update(
        status="running",
        started_at=now(),
        argv=argv,
        stdout=str(raw_path),
        stderr=str(error_path),
        test_file=str(filename),
    )
    save_manifest(manifest_path, manifest)

    process = None
    try:
        with raw_path.open("wb") as stdout, error_path.open("wb") as stderr:
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
            try:
                process = subprocess.Popen(
                    argv, stdout=stdout, stderr=stderr, start_new_session=True
                )
            finally:
                signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT})
            try:
                record["returncode"] = process.wait(timeout=args.timeout_s)
            except subprocess.TimeoutExpired:
                record["timed_out"] = True
                kill_process_group(process)
                record["returncode"] = process.returncode
    except KeyboardInterrupt:
        if process is not None:
            kill_process_group(process)
        record["status"] = "interrupted"
        record["ended_at"] = now()
        save_manifest(manifest_path, manifest)
        raise
    except OSError as error:
        record["error"] = str(error)
        record["returncode"] = None

    record["ended_at"] = now()
    if record.get("returncode") == 0 and not record.get("timed_out"):
        try:
            validate_fio_json(raw_path.read_bytes())
            record["json_valid"] = True
            record["status"] = "completed"
        except (ValueError, json.JSONDecodeError) as error:
            record["json_valid"] = False
            record["error"] = str(error)
            record["status"] = "failed"
    else:
        record["status"] = "failed"
    save_manifest(manifest_path, manifest)
    return record["status"] == "completed"


def is_within(path, parent):
    return path == parent or parent in path.parents


def check_filesystem_roots(roots, size_bytes):
    if roots["efs"].stat().st_dev == roots["gpfs"].stat().st_dev:
        return "EFS and GPFS roots resolve to the same filesystem"
    for side, root in roots.items():
        if shutil.disk_usage(root).free < size_bytes:
            return f"insufficient free space on {side} for {size_bytes} bytes"
    return None


def check_artifacts_root(artifacts_root, roots):
    device = artifacts_root.stat().st_dev
    if any(device == root.stat().st_dev for root in roots.values()):
        return "artifacts root resolves to a tested filesystem"
    return None


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--efs-root", type=Path, required=True)
    parser.add_argument("--gpfs-root", type=Path, required=True)
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--size-bytes", type=int, required=True)
    parser.add_argument("--first", choices=("efs", "gpfs"), required=True)
    parser.add_argument("--fio", default="fio")
    parser.add_argument("--timeout-s", type=float, default=180)
    args = parser.parse_args(argv)
    if args.size_bytes <= 0 or args.size_bytes % 4096:
        parser.error("--size-bytes must be a positive multiple of 4096")
    if not math.isfinite(args.timeout_s) or args.timeout_s <= 0:
        parser.error("--timeout-s must be positive")
    resolved = shutil.which(args.fio)
    if not resolved:
        parser.error(f"FIO executable not found: {args.fio}")
    args.fio = resolved
    return args


def main(argv=None):
    args = parse_args(argv)
    raw_roots = (args.efs_root, args.gpfs_root, args.artifacts_root)
    if any(path.is_symlink() for path in raw_roots):
        print("root directories must not be symlinks", file=sys.stderr)
        return 2
    roots = {side: getattr(args, f"{side}_root").resolve() for side in ("efs", "gpfs")}
    artifacts_root = args.artifacts_root.resolve()
    for path in (*roots.values(), artifacts_root):
        if not path.is_dir():
            print(f"not a directory: {path}", file=sys.stderr)
            return 2
    if is_within(roots["efs"], roots["gpfs"]) or is_within(roots["gpfs"], roots["efs"]):
        print("EFS and GPFS roots must be separate, non-nested directories", file=sys.stderr)
        return 2
    if any(root.parent == root for root in roots.values()):
        print("filesystem roots are not accepted; use the EFS/GPFS mount directories", file=sys.stderr)
        return 2
    if any(is_within(artifacts_root, root) for root in roots.values()):
        print("artifacts root must be outside both tested filesystems", file=sys.stderr)
        return 2
    try:
        error = check_filesystem_roots(roots, args.size_bytes) or check_artifacts_root(
            artifacts_root, roots
        )
        if error:
            print(error, file=sys.stderr)
            return 2
    except OSError as error:
        print(f"filesystem preflight failed: {error}", file=sys.stderr)
        return 2

    try:
        artifacts = Path(tempfile.mkdtemp(prefix="diff-minner-smoke-", dir=artifacts_root))
        test_dirs = {
            side: Path(tempfile.mkdtemp(prefix="diff-minner-smoke-", dir=root))
            for side, root in roots.items()
        }
    except OSError as error:
        print(f"could not create isolated directories: {error}", file=sys.stderr)
        return 2

    order = [args.first, "gpfs" if args.first == "efs" else "efs"]
    manifest = {
        "schema": "diff-minner-smoke-v1",
        "status": "running",
        "formal_comparison": False,
        "configured_duration_s": DURATION_S,
        "size_bytes_per_side": args.size_bytes,
        "order": order,
        "test_directories": {side: str(path) for side, path in test_dirs.items()},
        "sides": {side: {"status": "pending", "timed_out": False} for side in order},
    }
    manifest_path = artifacts / "manifest.json"
    save_manifest(manifest_path, manifest)
    print(f"artifacts: {artifacts}")

    try:
        for index, side in enumerate(order):
            if not run_side(side, test_dirs[side], artifacts, args, manifest, manifest_path):
                for skipped in order[index + 1 :]:
                    manifest["sides"][skipped]["status"] = "skipped"
                manifest["status"] = "failed"
                save_manifest(manifest_path, manifest)
                print(f"{side}: failed; raw artifacts preserved", file=sys.stderr)
                return 1
    except KeyboardInterrupt:
        manifest["status"] = "interrupted"
        save_manifest(manifest_path, manifest)
        return 130

    manifest["status"] = "completed"
    save_manifest(manifest_path, manifest)
    print("completed: both FIO outputs passed structural validation")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
