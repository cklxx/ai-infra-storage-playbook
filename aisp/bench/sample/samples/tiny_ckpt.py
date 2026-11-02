"""tiny-ckpt@0.1.0：一个不依赖 GPU / torch 的 checkpoint 样本。

按旁路原则：不跑真实模型前向，只按真实分片策略把字节写到临时目录，
再读回来。用线程池模拟多 rank，单进程内并发。产出 6 种 CkptSli。

规模由 SampleConfigBase.topology 决定：rank 数 = nodes * gpus_per_node。
每 rank 分片大小固定（默认 4 MiB），便于跨规模比较。
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..configs import SampleConfigBase
from ..types import (
    CheckPointDuration,
    MetadataCommit,
    RestoreDuration,
    RunSpec,
    TrainingStall,
    WriteLatencyP99,
    WriteThroughput,
)

BYTES_PER_RANK = 4 * 1024 * 1024  # 4 MiB / rank
WRITE_CHUNK = 64 * 1024           # 64 KiB 一次 write()，用于测 P99


def _write_one_rank(
    rank_id: int,
    directory: Path,
    total_bytes: int,
    write_latencies_ms: list[float],
    latencies_lock: threading.Lock,
) -> int:
    """一个 rank 写自己的分片；返回实际写入字节数。"""

    target = directory / f"rank-{rank_id:05d}.bin"
    remaining = total_bytes
    written = 0
    with open(target, "wb", buffering=0) as handle:
        while remaining > 0:
            chunk = min(WRITE_CHUNK, remaining)
            buf = os.urandom(chunk)
            t0 = time.perf_counter()
            handle.write(buf)
            t1 = time.perf_counter()
            with latencies_lock:
                write_latencies_ms.append((t1 - t0) * 1000.0)
            written += chunk
            remaining -= chunk
    os.sync()
    return written


def _read_all_ranks(directory: Path, rank_count: int) -> int:
    total = 0
    for rank_id in range(rank_count):
        target = directory / f"rank-{rank_id:05d}.bin"
        with open(target, "rb", buffering=0) as handle:
            while handle.read(WRITE_CHUNK):
                pass
        total += target.stat().st_size
    return total


def _p99(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(len(ordered) * 0.99)))
    return ordered[idx]


def runner(spec: RunSpec, config: SampleConfigBase) -> list:
    rank_count = max(1, config.topology.nodes * config.topology.gpus_per_node)
    workdir = Path(tempfile.mkdtemp(prefix="tiny-ckpt-"))
    latencies: list[float] = []
    lock = threading.Lock()

    # ---- 同步写入：所有 rank 并发写，主线程等全部完成 ----
    t_write_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=min(rank_count, 32)) as pool:
        list(
            pool.map(
                lambda r: _write_one_rank(r, workdir, BYTES_PER_RANK, latencies, lock),
                range(rank_count),
            )
        )
    t_write_end = time.perf_counter()

    # ---- 元数据提交：写 manifest + fsync ----
    t_meta_start = time.perf_counter()
    manifest = workdir / "manifest.json"
    with open(manifest, "wb", buffering=0) as handle:
        handle.write(f'{{"ranks": {rank_count}}}\n'.encode())
        handle.flush()
        os.fsync(handle.fileno())
    t_meta_end = time.perf_counter()

    # ---- 恢复：重新读全部分片 ----
    t_restore_start = time.perf_counter()
    restored_bytes = _read_all_ranks(workdir, rank_count)
    t_restore_end = time.perf_counter()

    # ---- 清理 ----
    for path in workdir.iterdir():
        path.unlink()
    workdir.rmdir()

    write_duration = t_write_end - t_write_start
    total_written = rank_count * BYTES_PER_RANK
    return [
        CheckPointDuration(value=write_duration),
        # 同步写入时训练停顿 = 写入本身（异步重叠场景后续样本再测）
        TrainingStall(value=write_duration),
        RestoreDuration(value=t_restore_end - t_restore_start),
        WriteThroughput(value=total_written / write_duration if write_duration > 0 else 0.0),
        MetadataCommit(value=(t_meta_end - t_meta_start) * 1000.0),
        WriteLatencyP99(value=_p99(latencies)),
    ]
