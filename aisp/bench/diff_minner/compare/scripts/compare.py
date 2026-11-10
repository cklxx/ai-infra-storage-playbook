#!/usr/bin/env python3
"""Validate and compare one normalized Diff Minner ComparisonGroup."""

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

import numpy as np


APP_METRICS = {
    "dataset": {
        "dataset_samples_per_gpu": ("mean",),
        "dataset_first_batch_wait": ("mean",),
        "dataset_gpu_io_wait": ("mean",),
        "dataset_epoch_duration": ("mean",),
        "dataset_job_startup": ("mean",),
    },
    "ckpt": {
        "ckpt_save_stall": ("mean",),
        "ckpt_load": ("mean",),
        "ckpt_save_duration": ("mean",),
        "ckpt_write_bandwidth": ("mean",),
        "ckpt_failure_recovery": ("mean",),
    },
    "kvcache": {
        "kv_ttft": ("mean", "p99"),
        "kv_fetch_segment": ("mean",),
        "kv_tpot": ("mean",),
        "kv_effective_hit_rate": ("mean",),
        "kv_qps": ("mean",),
    },
}
METADATA_OPS = ("create", "stat", "unlink", "open", "readdir")
NATIVE_STATS = {
    "storage_sequential_read_bandwidth": ("mean",),
    "storage_random_read_bandwidth": ("mean",),
    "storage_write_bandwidth": ("mean",),
    "storage_random_read_iops": ("mean",),
    "storage_random_write_iops": ("mean",),
    "storage_io_latency": ("mean", "p50", "p99", "p999"),
    **{f"metadata_{op}_qps": ("mean",) for op in METADATA_OPS},
    **{f"metadata_{op}_latency": ("mean", "p50", "p99", "p999") for op in METADATA_OPS},
    "interference_read_bandwidth": ("mean",),
    "interference_read_latency": ("p99",),
}
APP_ALL = {name for metrics in APP_METRICS.values() for name in metrics}
METRICS = APP_ALL | set(NATIVE_STATS)
LOWER_BETTER = {
    "dataset_samples_per_gpu", "ckpt_write_bandwidth", "kv_effective_hit_rate", "kv_qps",
    "storage_sequential_read_bandwidth", "storage_random_read_bandwidth", "storage_write_bandwidth",
    "storage_random_read_iops", "storage_random_write_iops", "interference_read_bandwidth",
    *{f"metadata_{op}_qps" for op in METADATA_OPS},
}
BLOCKS = ("4KiB", "128KiB", "1MiB", "64MiB")
READ_OPS = ("sequential_read", "random_read")
OPERATIONS = READ_OPS + ("sequential_write", "random_write")
BACKGROUND_RATES = (0.0, 256.0, 512.0)
ENV_KEYS = (
    "machine_model", "cpu_model", "nic_model", "nic_count", "disk_model", "disk_count",
    "filesystem_version", "adapter", "mount_options", "client_count", "iodepth", "direct",
)
SHAPE_KEYS = ("duration_s", "warmup_discard_s")
SCENARIO_KEYS = (
    "operation", "block_size", "streams", "metadata_file_kind", "background_write_mb_s_per_disk",
)
ROUND_KEYS = (
    "index", "efs_value", "gpfs_value", "first", "environments", "window", "interference",
    "admission", "evidence_uri",
)
SIDE_ADMISSION_KEYS = (
    "content_match", "checksum_algorithm", "content_evidence_uri", "checkpoint_recovery",
    "mlperf_storage_version", "training_state_evidence_uri", "error_rate", "timeout_rate",
    "throttle_count", "retry_count", "stability_window_s", "stability_started_at",
    "stability_ended_at", "performance_decay", "periodic_jitter", "stability_series_uri",
)
INTERFERENCE_KEYS = (
    "configured_mb_s_per_disk", "actual_mb_s_per_disk", "disk_count", "started_at", "ended_at",
    "evidence_uri",
)
NOISE_MEASUREMENT_KEYS = (
    "measured_on", "value", "started_at", "ended_at", "interference", "evidence_uri",
)
POLICY_KEYS = (
    "version", "mean_threshold", "tail_threshold", "metadata_qps_threshold", "bootstrap_resamples",
    "bootstrap_seed", "stability", "interference_tolerance_mb_s_per_disk", "calibration_evidence_uri",
)
STABILITY_KEYS = (
    "min_window_s", "max_error_rate", "max_timeout_rate", "max_throttle_count", "max_retry_count",
    "max_performance_decay", "max_periodic_jitter",
)


class InputError(ValueError):
    pass


def _object(value, keys, path):
    if not isinstance(value, dict):
        raise InputError(f"{path}: expected object")
    expected = set(keys)
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise InputError(f"{path}: missing={missing}, unknown={unknown}")
    return value


def _list(value, path):
    if not isinstance(value, list):
        raise InputError(f"{path}: expected list")
    return value


def _string(value, path):
    if not isinstance(value, str):
        raise InputError(f"{path}: expected string")
    return value


def _number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{path}: expected finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise InputError(f"{path}: expected finite number")
    return value


def _integer(value, path):
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputError(f"{path}: expected integer")
    return value


def _boolean(value, path):
    if not isinstance(value, bool):
        raise InputError(f"{path}: expected boolean")
    return value


def _nullable_string(value, path):
    if value is not None:
        _string(value, path)


def _choice(value, choices, path):
    if not isinstance(value, str) or value not in choices:
        raise InputError(f"{path}: illegal branch {value!r}")
    return value


def _schema_payload(payload, path="payload"):
    if not isinstance(payload, dict) or len(payload) != 1:
        raise InputError(f"{path}: expected one payload branch")
    kind = next(iter(payload))
    _choice(kind, tuple(APP_METRICS), path)
    body = payload[kind]
    if kind == "dataset":
        keys = ("file_count", "file_size", "files_per_rank", "random_read")
        _object(body, keys, path)
        _integer(body["file_count"], f"{path}.file_count")
        _integer(body["files_per_rank"], f"{path}.files_per_rank")
        _boolean(body["random_read"], f"{path}.random_read")
        size = body["file_size"]
        if not isinstance(size, dict) or len(size) != 1:
            raise InputError(f"{path}.file_size: expected one branch")
        branch = next(iter(size))
        _choice(branch, ("fixed_bytes", "distribution"), f"{path}.file_size")
        if branch == "fixed_bytes":
            _integer(size[branch], f"{path}.file_size.fixed_bytes")
        else:
            _string(size[branch], f"{path}.file_size.distribution")
    elif kind == "ckpt":
        keys = ("model_parameters", "sharding", "save_frequency_steps", "async_write")
        _object(body, keys, path)
        for key in ("model_parameters", "save_frequency_steps"):
            _integer(body[key], f"{path}.{key}")
        _string(body["sharding"], f"{path}.sharding")
        _boolean(body["async_write"], f"{path}.async_write")
    else:
        keys = ("bytes_per_token", "context_length", "hit_rate", "block_size_bytes", "concurrent_sessions")
        _object(body, keys, path)
        for key in ("bytes_per_token", "context_length", "block_size_bytes", "concurrent_sessions"):
            _integer(body[key], f"{path}.{key}")
        _number(body["hit_rate"], f"{path}.hit_rate")
    return kind


def _schema_environment(environment, path):
    _object(environment, ENV_KEYS, path)
    for key in ("machine_model", "cpu_model", "nic_model", "disk_model", "filesystem_version", "adapter", "mount_options"):
        _string(environment[key], f"{path}.{key}")
    for key in ("nic_count", "disk_count", "client_count", "iodepth"):
        _integer(environment[key], f"{path}.{key}")
    _boolean(environment["direct"], f"{path}.direct")


def _schema_shape(shape, path):
    _object(shape, SHAPE_KEYS, path)
    for key in SHAPE_KEYS:
        _number(shape[key], f"{path}.{key}")


def _schema_scenario(scenario, path):
    if scenario is None:
        return
    _object(scenario, SCENARIO_KEYS, path)
    if scenario["operation"] is not None:
        _choice(scenario["operation"], OPERATIONS, f"{path}.operation")
    _nullable_string(scenario["block_size"], f"{path}.block_size")
    if scenario["streams"] is not None:
        _integer(scenario["streams"], f"{path}.streams")
    if scenario["metadata_file_kind"] is not None:
        _choice(scenario["metadata_file_kind"], ("empty", "real_small"), f"{path}.metadata_file_kind")
    if scenario["background_write_mb_s_per_disk"] is not None:
        _number(scenario["background_write_mb_s_per_disk"], f"{path}.background_write_mb_s_per_disk")


def _schema_interference(record, path):
    if record is None:
        return
    _object(record, INTERFERENCE_KEYS, path)
    for key in ("configured_mb_s_per_disk", "actual_mb_s_per_disk"):
        _number(record[key], f"{path}.{key}")
    _integer(record["disk_count"], f"{path}.disk_count")
    for key in ("started_at", "ended_at", "evidence_uri"):
        _string(record[key], f"{path}.{key}")


def _schema_side_admission(side, path):
    _object(side, SIDE_ADMISSION_KEYS, path)
    _boolean(side["content_match"], f"{path}.content_match")
    _nullable_string(side["checksum_algorithm"], f"{path}.checksum_algorithm")
    _string(side["content_evidence_uri"], f"{path}.content_evidence_uri")
    for key in ("mlperf_storage_version", "training_state_evidence_uri"):
        _nullable_string(side[key], f"{path}.{key}")
    if side["checkpoint_recovery"] is not None:
        _boolean(side["checkpoint_recovery"], f"{path}.checkpoint_recovery")
    for key in ("error_rate", "timeout_rate", "performance_decay", "periodic_jitter", "stability_window_s"):
        _number(side[key], f"{path}.{key}")
    for key in ("throttle_count", "retry_count"):
        _integer(side[key], f"{path}.{key}")
    for key in ("stability_started_at", "stability_ended_at", "stability_series_uri"):
        _string(side[key], f"{path}.{key}")


def _schema_series(series, path):
    _object(series, ("metric", "statistic", "storage_scenario", "order_seed", "rounds", "noise"), path)
    _choice(series["metric"], METRICS, f"{path}.metric")
    _choice(series["statistic"], ("mean", "p50", "p99", "p999"), f"{path}.statistic")
    _schema_scenario(series["storage_scenario"], f"{path}.storage_scenario")
    _integer(series["order_seed"], f"{path}.order_seed")
    for i, round_ in enumerate(_list(series["rounds"], f"{path}.rounds")):
        rpath = f"{path}.rounds[{i}]"
        _object(round_, ROUND_KEYS, rpath)
        _integer(round_["index"], f"{rpath}.index")
        _number(round_["efs_value"], f"{rpath}.efs_value")
        _number(round_["gpfs_value"], f"{rpath}.gpfs_value")
        _choice(round_["first"], ("efs", "gpfs"), f"{rpath}.first")
        _object(round_["environments"], ("efs", "gpfs"), f"{rpath}.environments")
        for side in ("efs", "gpfs"):
            _schema_environment(round_["environments"][side], f"{rpath}.environments.{side}")
        window = _object(round_["window"], ("shape", "efs_started_at", "efs_ended_at", "gpfs_started_at", "gpfs_ended_at"), f"{rpath}.window")
        _schema_shape(window["shape"], f"{rpath}.window.shape")
        for key in ("efs_started_at", "efs_ended_at", "gpfs_started_at", "gpfs_ended_at"):
            _string(window[key], f"{rpath}.window.{key}")
        if round_["interference"] is not None:
            pair = _object(round_["interference"], ("efs", "gpfs"), f"{rpath}.interference")
            for side in ("efs", "gpfs"):
                if pair[side] is None:
                    raise InputError(f"{rpath}.interference.{side}: expected object")
                _schema_interference(pair[side], f"{rpath}.interference.{side}")
        admission = _object(round_["admission"], ("efs", "gpfs"), f"{rpath}.admission")
        for side in ("efs", "gpfs"):
            _schema_side_admission(admission[side], f"{rpath}.admission.{side}")
        _string(round_["evidence_uri"], f"{rpath}.evidence_uri")
    for i, noise in enumerate(_list(series["noise"], f"{path}.noise")):
        npath = f"{path}.noise[{i}]"
        keys = (
            "side", "payload", "metric", "statistic", "cache_state", "storage_scenario", "environment",
            "window", "measurements", "between_round_differences", "between_day_differences", "band", "evidence_uri",
        )
        _object(noise, keys, npath)
        _choice(noise["side"], ("efs", "gpfs"), f"{npath}.side")
        _schema_payload(noise["payload"], f"{npath}.payload")
        _choice(noise["metric"], METRICS, f"{npath}.metric")
        _choice(noise["statistic"], ("mean", "p50", "p99", "p999"), f"{npath}.statistic")
        _choice(noise["cache_state"], ("cold", "hot"), f"{npath}.cache_state")
        _schema_scenario(noise["storage_scenario"], f"{npath}.storage_scenario")
        _schema_environment(noise["environment"], f"{npath}.environment")
        _schema_shape(noise["window"], f"{npath}.window")
        for j, measurement in enumerate(_list(noise["measurements"], f"{npath}.measurements")):
            mpath = f"{npath}.measurements[{j}]"
            _object(measurement, NOISE_MEASUREMENT_KEYS, mpath)
            _string(measurement["measured_on"], f"{mpath}.measured_on")
            _number(measurement["value"], f"{mpath}.value")
            _string(measurement["started_at"], f"{mpath}.started_at")
            _string(measurement["ended_at"], f"{mpath}.ended_at")
            _schema_interference(measurement["interference"], f"{mpath}.interference")
            _string(measurement["evidence_uri"], f"{mpath}.evidence_uri")
        for key in ("between_round_differences", "between_day_differences"):
            for j, value in enumerate(_list(noise[key], f"{npath}.{key}")):
                _number(value, f"{npath}.{key}[{j}]")
        _number(noise["band"], f"{npath}.band")
        _string(noise["evidence_uri"], f"{npath}.evidence_uri")


def validate_transport(data):
    _object(data, ("group", "policy"), "input")
    group = data["group"]
    _object(group, ("group_id", "run_id", "payload", "cache_state", "series"), "group")
    _string(group["group_id"], "group.group_id")
    _string(group["run_id"], "group.run_id")
    _schema_payload(group["payload"], "group.payload")
    _choice(group["cache_state"], ("cold", "hot"), "group.cache_state")
    for i, series in enumerate(_list(group["series"], "group.series")):
        _schema_series(series, f"group.series[{i}]")
    policy = _object(data["policy"], POLICY_KEYS, "policy")
    _string(policy["version"], "policy.version")
    for key in ("mean_threshold", "tail_threshold", "metadata_qps_threshold", "interference_tolerance_mb_s_per_disk"):
        _number(policy[key], f"policy.{key}")
    _integer(policy["bootstrap_resamples"], "policy.bootstrap_resamples")
    _integer(policy["bootstrap_seed"], "policy.bootstrap_seed")
    stability = _object(policy["stability"], STABILITY_KEYS, "policy.stability")
    for key in STABILITY_KEYS:
        if key in ("max_throttle_count", "max_retry_count"):
            _integer(stability[key], f"policy.stability.{key}")
        else:
            _number(stability[key], f"policy.stability.{key}")
    _nullable_string(policy["calibration_evidence_uri"], "policy.calibration_evidence_uri")


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed
    except (ValueError, OverflowError):
        return None


def _elapsed(start, end):
    return (end - start).total_seconds()


def _scenario_key(scenario):
    if scenario is None:
        return None
    return tuple(scenario[key] for key in SCENARIO_KEYS)


def _scenario(operation=None, block=None, streams=None, kind=None, background=None):
    return {
        "operation": operation, "block_size": block, "streams": streams,
        "metadata_file_kind": kind, "background_write_mb_s_per_disk": background,
    }


def native_requirements(kind):
    """Return (metric, statistic, scenario, streams_are_wildcard) requirements."""
    required = []

    def add(metric, stats, operations, blocks, backgrounds=(None,)):
        for operation in operations:
            for block in blocks:
                for background in backgrounds:
                    for statistic in stats:
                        required.append((metric, statistic, _scenario(operation, block, background=background), True))

    if kind == "dataset":
        add("storage_sequential_read_bandwidth", ("mean",), ("sequential_read",), BLOCKS)
        add("storage_random_read_bandwidth", ("mean",), ("random_read",), BLOCKS)
        for file_kind in ("empty", "real_small"):
            for operation in METADATA_OPS:
                required.append((f"metadata_{operation}_qps", "mean", _scenario(kind=file_kind), False))
                for statistic in NATIVE_STATS[f"metadata_{operation}_latency"]:
                    required.append((f"metadata_{operation}_latency", statistic, _scenario(kind=file_kind), False))
    elif kind == "ckpt":
        add("storage_write_bandwidth", ("mean",), ("sequential_write",), BLOCKS)
        add("storage_io_latency", NATIVE_STATS["storage_io_latency"], ("sequential_write", "random_write"), BLOCKS)
    else:
        add("storage_random_read_iops", ("mean",), ("random_read",), ("4KiB",))
        add("storage_io_latency", NATIVE_STATS["storage_io_latency"], ("random_read",), ("4KiB",))
    if kind in ("ckpt", "kvcache"):
        for metric, stats in (("interference_read_bandwidth", ("mean",)), ("interference_read_latency", ("p99",))):
            add(metric, stats, READ_OPS, BLOCKS, BACKGROUND_RATES)
    return required


class Validator:
    def __init__(self, group, policy, only_side=None):
        self.group = group
        self.policy = policy
        self.only_side = only_side
        self.kind = next(iter(group["payload"]))
        self.errors = []

    def checks(self, side):
        return self.only_side is None or self.only_side == side

    def fail(self, path, message):
        self.errors.append(f"{path}: {message}")

    def run(self):
        self.policy_rules()
        if not self.group["group_id"].strip():
            self.fail("group.group_id", "empty")
        if not self.group["run_id"].strip():
            self.fail("group.run_id", "empty")
        self.payload_rules(self.group["payload"], "group.payload")
        identities = set()
        for i, series in enumerate(self.group["series"]):
            path = f"group.series[{i}]"
            identity = (series["metric"], series["statistic"], _scenario_key(series["storage_scenario"]))
            if identity in identities:
                self.fail(path, "duplicate (metric, statistic, storage_scenario)")
            identities.add(identity)
            self.series_rules(series, path)
        self.matrix_rules()
        return self.errors

    def policy_rules(self):
        policy = self.policy
        if not policy["version"].strip():
            self.fail("policy.version", "empty")
        for key in ("mean_threshold", "tail_threshold", "metadata_qps_threshold", "interference_tolerance_mb_s_per_disk"):
            if policy[key] < 0:
                self.fail(f"policy.{key}", "must be non-negative")
        if policy["bootstrap_resamples"] <= 0:
            self.fail("policy.bootstrap_resamples", "must be positive")
        if policy["bootstrap_seed"] < 0:
            self.fail("policy.bootstrap_seed", "must be non-negative")
        stability = policy["stability"]
        for key in STABILITY_KEYS:
            if stability[key] < 0:
                self.fail(f"policy.stability.{key}", "must be non-negative")
        calibration = policy["calibration_evidence_uri"]
        if policy["version"] == "diff-minner-v1":
            fixed = {
                "mean_threshold": 0.10,
                "tail_threshold": 0.20,
                "metadata_qps_threshold": 0.15,
                "bootstrap_resamples": 10000,
            }
            for key, expected in fixed.items():
                if policy[key] != expected:
                    self.fail(f"policy.{key}", f"must be {expected} for diff-minner-v1")
            if calibration is not None:
                self.fail("policy.calibration_evidence_uri", "must be null for diff-minner-v1")
        elif not calibration or not calibration.strip():
            self.fail("policy.calibration_evidence_uri", "required after v1")

    def payload_rules(self, payload, path):
        body = payload[self.kind]
        integer_keys = {
            "dataset": ("file_count", "files_per_rank"),
            "ckpt": ("model_parameters", "save_frequency_steps"),
            "kvcache": ("bytes_per_token", "context_length", "block_size_bytes", "concurrent_sessions"),
        }[self.kind]
        for key in integer_keys:
            if body[key] <= 0:
                self.fail(f"{path}.{key}", "must be positive")
        if self.kind == "dataset":
            size = body["file_size"]
            if "fixed_bytes" in size and size["fixed_bytes"] <= 0:
                self.fail(f"{path}.file_size.fixed_bytes", "must be positive")
            if "distribution" in size and not size["distribution"].strip():
                self.fail(f"{path}.file_size.distribution", "empty")
        elif self.kind == "ckpt" and not body["sharding"].strip():
            self.fail(f"{path}.sharding", "empty")
        elif self.kind == "kvcache" and not 0 <= body["hit_rate"] <= 1:
            self.fail(f"{path}.hit_rate", "outside [0, 1]")

    def matrix_rules(self):
        expected = []
        for metric, stats in APP_METRICS[self.kind].items():
            expected.extend((metric, statistic, None, False) for statistic in stats)
        expected.extend(native_requirements(self.kind))
        actual = self.group["series"]
        for metric, statistic, scenario, concurrent in expected:
            matches = [
                series for series in actual
                if series["metric"] == metric and series["statistic"] == statistic
                and self.scenario_matches(series["storage_scenario"], scenario, concurrent)
            ]
            if concurrent:
                single = any(s["storage_scenario"]["streams"] == 1 for s in matches)
                high = any(
                    s["storage_scenario"]["streams"] is not None
                    and s["storage_scenario"]["streams"] >= 10
                    for s in matches
                )
                if not single or not high:
                    self.fail("group.series", f"missing {metric}/{statistic} {scenario} streams=1 or streams>=10")
            elif not matches:
                self.fail("group.series", f"missing {metric}/{statistic} {scenario}")

    @staticmethod
    def scenario_matches(actual, expected, concurrent):
        if actual is None:
            return expected is None
        if expected is None:
            return False
        return all(
            key == "streams" and concurrent or actual[key] == value
            for key, value in expected.items()
        )

    def series_rules(self, series, path):
        metric = series["metric"]
        statistic = series["statistic"]
        if metric in APP_ALL:
            if self.kind not in APP_METRICS or metric not in APP_METRICS[self.kind]:
                self.fail(path, "application metric belongs to another payload")
            if series["storage_scenario"] is not None:
                self.fail(f"{path}.storage_scenario", "application metrics require null")
            legal_stats = APP_METRICS[self.kind].get(metric, ())
        else:
            legal_stats = NATIVE_STATS[metric]
            self.native_scenario(series["storage_scenario"], metric, f"{path}.storage_scenario")
        if statistic not in legal_stats:
            self.fail(f"{path}.statistic", "illegal metric/statistic combination")
        if series["order_seed"] < 0:
            self.fail(f"{path}.order_seed", "must be non-negative")
        rounds = series["rounds"]
        if len(rounds) < 5:
            self.fail(f"{path}.rounds", "at least five rounds required")
        first_shape = rounds[0]["window"]["shape"] if rounds else None
        first_environments = rounds[0]["environments"] if rounds else None
        interference_disks = {"efs": None, "gpfs": None}
        for i, round_ in enumerate(rounds):
            rpath = f"{path}.rounds[{i}]"
            if round_["index"] != i + 1:
                self.fail(f"{rpath}.index", "round indices must start at 1 and be consecutive")
            if i and round_["first"] == rounds[i - 1]["first"]:
                self.fail(f"{rpath}.first", "first side must alternate every round")
            if round_["window"]["shape"] != first_shape:
                self.fail(f"{rpath}.window.shape", "window shape differs within series")
            if self.only_side is None:
                if round_["environments"] != first_environments:
                    self.fail(f"{rpath}.environments", "environment differs within series")
            elif round_["environments"][self.only_side] != first_environments[self.only_side]:
                self.fail(f"{rpath}.environments.{self.only_side}", "environment differs within series")
            self.environment_rules(round_["environments"], metric in NATIVE_STATS, f"{rpath}.environments")
            windows = self.window_rules(round_["window"], metric in NATIVE_STATS, f"{rpath}.window")
            if windows and self.only_side is None:
                first = round_["first"]
                second = "gpfs" if first == "efs" else "efs"
                if windows[first][1] > windows[second][0]:
                    self.fail(rpath, "actual order does not match first or effective windows overlap")
            disks = self.round_interference(round_, series["storage_scenario"], windows, f"{rpath}.interference")
            for side in ("efs", "gpfs"):
                if disks[side] is not None:
                    if interference_disks[side] is None:
                        interference_disks[side] = disks[side]
                    elif interference_disks[side] != disks[side]:
                        self.fail(f"{rpath}.interference.{side}.disk_count", "disk count differs within series")
            self.admission_rules(round_["admission"], windows, f"{rpath}.admission")
            if not round_["evidence_uri"].strip():
                self.fail(f"{rpath}.evidence_uri", "empty evidence URI")
        self.noise_rules(series, first_shape, first_environments, rounds, interference_disks, f"{path}.noise")

    def native_scenario(self, scenario, metric, path):
        if scenario is None:
            self.fail(path, "native metric requires a scenario")
            return
        if metric.startswith("metadata_"):
            if scenario["metadata_file_kind"] not in ("empty", "real_small"):
                self.fail(f"{path}.metadata_file_kind", "required")
            for key in ("operation", "block_size", "streams", "background_write_mb_s_per_disk"):
                if scenario[key] is not None:
                    self.fail(f"{path}.{key}", "must be null for metadata")
            return
        if scenario["metadata_file_kind"] is not None:
            self.fail(f"{path}.metadata_file_kind", "must be null")
        if scenario["operation"] not in OPERATIONS:
            self.fail(f"{path}.operation", "required")
        allowed_ops = {
            "storage_sequential_read_bandwidth": ("sequential_read",),
            "storage_random_read_bandwidth": ("random_read",),
            "storage_write_bandwidth": ("sequential_write", "random_write"),
            "storage_random_read_iops": ("random_read",),
            "storage_random_write_iops": ("random_write",),
            "interference_read_bandwidth": READ_OPS,
            "interference_read_latency": READ_OPS,
        }.get(metric, OPERATIONS)
        if scenario["operation"] not in allowed_ops:
            self.fail(f"{path}.operation", "does not match metric")
        if scenario["block_size"] not in BLOCKS:
            self.fail(f"{path}.block_size", "illegal or missing block size")
        if metric in ("storage_random_read_iops", "storage_random_write_iops") and scenario["block_size"] != "4KiB":
            self.fail(f"{path}.block_size", "IOPS requires 4KiB")
        if scenario["streams"] is None or not (scenario["streams"] == 1 or scenario["streams"] >= 10):
            self.fail(f"{path}.streams", "must be 1 or at least 10")
        background = scenario["background_write_mb_s_per_disk"]
        if metric.startswith("interference_"):
            if background not in BACKGROUND_RATES:
                self.fail(f"{path}.background_write_mb_s_per_disk", "must be 0, 256, or 512")
        elif background is not None:
            self.fail(f"{path}.background_write_mb_s_per_disk", "must be null")

    def environment_rules(self, pair, native, path):
        for side in ("efs", "gpfs"):
            if not self.checks(side):
                continue
            environment = pair[side]
            for key in ("machine_model", "cpu_model", "nic_model", "disk_model", "filesystem_version", "adapter", "mount_options"):
                if not environment[key].strip():
                    self.fail(f"{path}.{side}.{key}", "empty")
            for key in ("nic_count", "disk_count", "client_count"):
                if environment[key] <= 0:
                    self.fail(f"{path}.{side}.{key}", "must be positive")
            if native and (environment["direct"] is not True or environment["iodepth"] != 16):
                self.fail(f"{path}.{side}", "native microbenchmarks require direct=true and iodepth=16")
        if self.only_side is not None:
            return
        for key in ENV_KEYS:
            if key not in ("filesystem_version", "mount_options") and pair["efs"][key] != pair["gpfs"][key]:
                self.fail(path, f"environment control {key} differs")

    def window_rules(self, window, native, path):
        shape = window["shape"]
        if shape["duration_s"] <= 0 or shape["warmup_discard_s"] < 0:
            self.fail(f"{path}.shape", "duration must be positive and warmup non-negative")
        if native and shape["duration_s"] != 120:
            self.fail(f"{path}.shape.duration_s", "native microbenchmarks require 120 seconds")
        windows = {}
        for side in ("efs", "gpfs"):
            if not self.checks(side):
                continue
            start = _timestamp(window[f"{side}_started_at"])
            end = _timestamp(window[f"{side}_ended_at"])
            if start is None or end is None:
                self.fail(f"{path}.{side}", "invalid timezone-aware ISO 8601 window")
                return None
            if _elapsed(start, end) != shape["duration_s"]:
                self.fail(f"{path}.{side}", "actual duration differs from shape.duration_s")
            windows[side] = (start, end)
        return windows

    def admission_rules(self, admission, windows, path):
        stability = {}
        for side in ("efs", "gpfs"):
            if not self.checks(side):
                continue
            evidence = admission[side]
            spath = f"{path}.{side}"
            if evidence["checksum_algorithm"] is not None and not evidence["checksum_algorithm"].strip():
                self.fail(f"{spath}.checksum_algorithm", "empty")
            if not evidence["content_evidence_uri"].strip() or not evidence["stability_series_uri"].strip():
                self.fail(spath, "empty evidence URI")
            if self.kind == "ckpt":
                if not evidence["mlperf_storage_version"] or not evidence["mlperf_storage_version"].strip():
                    self.fail(f"{spath}.mlperf_storage_version", "required for ckpt")
                if not evidence["training_state_evidence_uri"] or not evidence["training_state_evidence_uri"].strip():
                    self.fail(f"{spath}.training_state_evidence_uri", "required for ckpt")
                if evidence["checkpoint_recovery"] is None:
                    self.fail(f"{spath}.checkpoint_recovery", "required for ckpt")
            elif any(evidence[key] is not None for key in ("checkpoint_recovery", "mlperf_storage_version", "training_state_evidence_uri")):
                self.fail(spath, "checkpoint-only evidence must be null")
            for key in ("error_rate", "timeout_rate", "performance_decay", "periodic_jitter"):
                if evidence[key] < 0:
                    self.fail(f"{spath}.{key}", "must be non-negative")
            for key in ("throttle_count", "retry_count"):
                if evidence[key] < 0:
                    self.fail(f"{spath}.{key}", "must be non-negative")
            start = _timestamp(evidence["stability_started_at"])
            end = _timestamp(evidence["stability_ended_at"])
            duration = evidence["stability_window_s"]
            stability[side] = duration
            if start is None or end is None:
                self.fail(spath, "invalid stability window")
                continue
            if _elapsed(start, end) != duration:
                self.fail(f"{spath}.stability_window_s", "differs from actual duration")
            if duration < self.policy["stability"]["min_window_s"]:
                self.fail(f"{spath}.stability_window_s", "below policy minimum")
            if windows and (start > windows[side][0] or end < windows[side][1]):
                self.fail(spath, "stability window does not cover effective measurement window")
        if self.only_side is None and stability["efs"] != stability["gpfs"]:
            self.fail(path, "EFS and GPFS stability windows differ")

    def round_interference(self, round_, scenario, windows, path):
        disks = {"efs": None, "gpfs": None}
        is_interference = scenario is not None and scenario["background_write_mb_s_per_disk"] is not None
        pair = round_["interference"]
        if not is_interference:
            if pair is not None:
                self.fail(path, "must be null for non-interference metric")
            return disks
        if pair is None:
            self.fail(path, "required for interference metric")
            return disks
        target = scenario["background_write_mb_s_per_disk"]
        for side in ("efs", "gpfs"):
            if not self.checks(side):
                continue
            record = pair[side]
            disks[side] = self.interference_rules(
                record, target, windows[side] if windows else None, None, f"{path}.{side}"
            )
        if self.only_side is None and disks["efs"] != disks["gpfs"]:
            self.fail(path, "EFS and GPFS disk counts differ")
        return disks

    def interference_rules(self, record, target, window, expected_disks, path):
        if record["configured_mb_s_per_disk"] != target:
            self.fail(f"{path}.configured_mb_s_per_disk", "does not equal scenario target")
        actual = record["actual_mb_s_per_disk"]
        if target == 0 and actual != 0:
            self.fail(f"{path}.actual_mb_s_per_disk", "must be zero for zero target")
        if target != 0 and abs(actual - target) > self.policy["interference_tolerance_mb_s_per_disk"]:
            self.fail(f"{path}.actual_mb_s_per_disk", "outside policy tolerance")
        if record["disk_count"] <= 0:
            self.fail(f"{path}.disk_count", "must be positive")
        if expected_disks is not None and record["disk_count"] != expected_disks:
            self.fail(f"{path}.disk_count", "differs from formal rounds")
        if not record["evidence_uri"].strip():
            self.fail(f"{path}.evidence_uri", "empty evidence URI")
        start = _timestamp(record["started_at"])
        end = _timestamp(record["ended_at"])
        if start is None or end is None:
            self.fail(path, "invalid interference window")
        elif window and (start > window[0] or end < window[1]):
            self.fail(path, "interference does not cover measurement window")
        return record["disk_count"]

    def noise_rules(self, series, first_shape, first_environments, rounds, formal_disks, path):
        baselines = series["noise"]
        sides = [baseline["side"] for baseline in baselines]
        expected_sides = Counter({self.only_side: 1}) if self.only_side else Counter({"efs": 1, "gpfs": 1})
        actual_sides = Counter(side for side in sides if self.checks(side))
        if actual_sides != expected_sides:
            self.fail(path, "required noise baselines are missing or duplicated")
        for i, baseline in enumerate(baselines):
            side = baseline["side"]
            if not self.checks(side):
                continue
            bpath = f"{path}[{i}]"
            if baseline["payload"] != self.group["payload"]:
                self.fail(f"{bpath}.payload", "differs from group payload")
            for key in ("metric", "statistic", "storage_scenario"):
                if baseline[key] != series[key]:
                    self.fail(f"{bpath}.{key}", "differs from metric series")
            if baseline["cache_state"] != self.group["cache_state"]:
                self.fail(f"{bpath}.cache_state", "differs from group")
            if first_environments is not None and baseline["environment"] != first_environments[side]:
                self.fail(f"{bpath}.environment", "differs from first formal round")
            if first_shape is not None and baseline["window"] != first_shape:
                self.fail(f"{bpath}.window", "differs from formal window shape")
            if not baseline["evidence_uri"].strip():
                self.fail(f"{bpath}.evidence_uri", "empty evidence URI")
            self.noise_measurements(
                baseline, rounds[0] if rounds else None, formal_disks[side], bpath
            )

    def noise_measurements(self, baseline, first_round, formal_disks, path):
        measurements = baseline["measurements"]
        parsed = []
        all_valid = True
        scenario = baseline["storage_scenario"]
        is_interference = scenario is not None and scenario["background_write_mb_s_per_disk"] is not None
        for i, measurement in enumerate(measurements):
            mpath = f"{path}.measurements[{i}]"
            if not measurement["evidence_uri"].strip():
                self.fail(f"{mpath}.evidence_uri", "empty evidence URI")
            start = _timestamp(measurement["started_at"])
            end = _timestamp(measurement["ended_at"])
            try:
                measured_on = date.fromisoformat(measurement["measured_on"])
            except ValueError:
                measured_on = None
                self.fail(f"{mpath}.measured_on", "invalid ISO 8601 date")
            if start is None or end is None:
                self.fail(mpath, "invalid timezone-aware ISO 8601 window")
                all_valid = False
                continue
            if measured_on is None or measured_on != start.date():
                self.fail(f"{mpath}.measured_on", "must equal started_at date")
                all_valid = False
            if _elapsed(start, end) != baseline["window"]["duration_s"]:
                self.fail(mpath, "actual duration differs from noise window")
                all_valid = False
            if is_interference:
                if measurement["interference"] is None:
                    self.fail(f"{mpath}.interference", "required")
                else:
                    self.interference_rules(
                        measurement["interference"], scenario["background_write_mb_s_per_disk"],
                        (start, end), formal_disks, f"{mpath}.interference",
                    )
            elif measurement["interference"] is not None:
                self.fail(f"{mpath}.interference", "must be null")
            parsed.append((measured_on, measurement["value"], start, end))
        counts = Counter(item[0] for item in parsed if item[0] is not None)
        if len(counts) < 2 or any(count < 2 for count in counts.values()):
            self.fail(f"{path}.measurements", "at least two dates with two measurements each required")
        ordered = sorted(parsed, key=lambda item: item[2])
        if any(current[2] < previous[3] for previous, current in zip(ordered, ordered[1:])):
            self.fail(f"{path}.measurements", "noise measurement windows overlap")
        if first_round is not None and parsed:
            side = baseline["side"]
            formal_start = _timestamp(first_round["window"][f"{side}_started_at"])
            if formal_start is not None and max(item[3] for item in parsed) >= formal_start:
                self.fail(f"{path}.measurements", "latest noise measurement must end before first formal measurement")
        if not all_valid or len(parsed) != len(measurements) or len(counts) < 2 or any(count < 2 for count in counts.values()):
            return
        by_day = defaultdict(list)
        for measured_on, value, start, _ in parsed:
            by_day[measured_on].append((start, value))
        between_round = []
        daily_medians = []
        zero = False
        for measured_on in sorted(by_day):
            values = [value for _, value in sorted(by_day[measured_on])]
            for before, after in zip(values, values[1:]):
                if before == 0:
                    zero = True
                else:
                    between_round.append(abs(after - before) / abs(before))
            daily_medians.append(statistics.median(values))
        between_day = []
        for before, after in zip(daily_medians, daily_medians[1:]):
            if before == 0:
                zero = True
            else:
                between_day.append(abs(after - before) / abs(before))
        if zero:
            self.fail(f"{path}.measurements", "zero predecessor in noise relative difference")
            return
        expected_band = max(between_round + between_day)
        if baseline["between_round_differences"] != between_round:
            self.fail(f"{path}.between_round_differences", "not reproducible from measurements")
        if baseline["between_day_differences"] != between_day:
            self.fail(f"{path}.between_day_differences", "not reproducible from measurements")
        if baseline["band"] != expected_band:
            self.fail(f"{path}.band", f"expected {expected_band}")


def measured_defects(group, policy, side):
    kind = next(iter(group["payload"]))
    reasons = []
    limits = {
        "error_rate": "max_error_rate", "timeout_rate": "max_timeout_rate",
        "throttle_count": "max_throttle_count", "retry_count": "max_retry_count",
        "performance_decay": "max_performance_decay", "periodic_jitter": "max_periodic_jitter",
    }
    for i, series in enumerate(group["series"]):
        for j, round_ in enumerate(series["rounds"]):
            evidence = round_["admission"][side]
            path = f"series[{i}].rounds[{j}].{side}"
            if evidence["content_match"] is False:
                reasons.append(f"{path}: content_match=false")
            if kind == "ckpt" and evidence["checkpoint_recovery"] is False:
                reasons.append(f"{path}: checkpoint_recovery=false")
            for field, limit in limits.items():
                if evidence[field] > policy["stability"][limit]:
                    reasons.append(f"{path}: {field} exceeds {limit}")
    return reasons


def bootstrap_ci(differences, resamples, seed):
    rng = np.random.Generator(np.random.PCG64(seed))
    boot = []
    n = len(differences)
    for _ in range(resamples):
        indices = rng.integers(0, n, size=n)
        boot.append(np.median(differences[indices]))
    return np.percentile(boot, [2.5, 97.5], method="linear")


def gates_for(ci_lower, relative_gap, threshold, noise_band):
    return {
        "statistical": bool(ci_lower > 0),
        "practical": bool(relative_gap >= threshold),
        "above_noise": bool(relative_gap > noise_band),
    }


def finite_derived(value, name):
    if not np.all(np.isfinite(value)):
        raise ArithmeticError(f"{name}: non-finite derived statistic")
    return value


def metric_comparison(series, policy):
    efs = np.array([round_["efs_value"] for round_ in series["rounds"]], dtype=float)
    gpfs = np.array([round_["gpfs_value"] for round_ in series["rounds"]], dtype=float)
    lower_better = series["metric"] in LOWER_BETTER
    with np.errstate(over="ignore", invalid="ignore"):
        efs_median = float(finite_derived(np.median(efs), "EFS median"))
        gpfs_median = float(finite_derived(np.median(gpfs), "GPFS median"))
        efs_mad = float(finite_derived(np.median(np.abs(efs - efs_median)), "EFS MAD"))
        gpfs_mad = float(finite_derived(np.median(np.abs(gpfs - gpfs_median)), "GPFS MAD"))
        differences = finite_derived(gpfs - efs if lower_better else efs - gpfs, "paired differences")
        ci = finite_derived(
            bootstrap_ci(differences, policy["bootstrap_resamples"], policy["bootstrap_seed"]),
            "paired difference CI",
        )
        if series["metric"].startswith("metadata_") and series["metric"].endswith("_qps"):
            threshold_kind = "metadata_qps"
            threshold = policy["metadata_qps_threshold"]
        elif series["statistic"] in ("p99", "p999"):
            threshold_kind = "tail_latency"
            threshold = policy["tail_threshold"]
        else:
            threshold_kind = "mean"
            threshold = policy["mean_threshold"]
        noise_band = max(baseline["band"] for baseline in series["noise"])
        relative_gap = None
        gates = None
        reason = None
        material = False
        if gpfs_median == 0:
            reason = "GPFS median is zero; relative gap is undefined"
        else:
            if lower_better:
                relative_gap = (gpfs_median - efs_median) / abs(gpfs_median)
            else:
                relative_gap = (efs_median - gpfs_median) / abs(gpfs_median)
            relative_gap = float(finite_derived(relative_gap, "relative gap"))
            gates = gates_for(ci[0], relative_gap, threshold, noise_band)
            material = all(gates.values())
    return {
        "series": series,
        "efs_median": efs_median,
        "gpfs_median": gpfs_median,
        "efs_mad": efs_mad,
        "gpfs_mad": gpfs_mad,
        "paired_difference_ci": {"lower": float(ci[0]), "upper": float(ci[1])},
        "relative_gap": relative_gap,
        "threshold_kind": threshold_kind,
        "applied_threshold": threshold,
        "noise_band": noise_band,
        "gates": gates,
        "uncomparable_reason": reason,
        "material_diff": material,
    }


def evaluate(data):
    validate_transport(data)
    group = data["group"]
    policy = data["policy"]
    policy_validator = Validator(group, policy)
    policy_validator.policy_rules()
    if policy_validator.errors:
        return {"incomplete": policy_validator.errors}
    efs_defects = measured_defects(group, policy, "efs")
    gpfs_defects = measured_defects(group, policy, "gpfs")
    if efs_defects:
        validation = Validator(group, policy, only_side="gpfs").run()
        return {
            "defect": {
                "group": group, "policy": policy, "reasons": efs_defects,
                "baseline_valid": not gpfs_defects and not validation,
            }
        }
    if gpfs_defects:
        return {"incomplete": gpfs_defects}
    reasons = Validator(group, policy).run()
    if reasons:
        return {"incomplete": reasons}
    metrics = []
    for i, series in enumerate(group["series"]):
        try:
            metrics.append(metric_comparison(series, policy))
        except ArithmeticError as error:
            reasons.append(f"group.series[{i}]: {error}")
    if reasons:
        return {"incomplete": reasons}
    candidate = any(
        comparison["material_diff"] and comparison["series"]["metric"] in APP_ALL
        for comparison in metrics
    )
    return {
        "compared": {
            "group": group, "policy": policy, "metrics": metrics, "candidate": candidate,
            "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    }


def main():
    if len(sys.argv) != 1:
        print("usage: compare.py < input.json", file=sys.stderr)
        return 2
    try:
        text = sys.stdin.read()
        data = json.loads(
            text,
            parse_constant=lambda value: (_ for _ in ()).throw(InputError(f"non-finite number {value}")),
            object_pairs_hook=_unique_object,
        )
        result = evaluate(data)
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (InputError, json.JSONDecodeError, UnicodeError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(encoded + "\n")
    return 0


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


if __name__ == "__main__":
    raise SystemExit(main())
