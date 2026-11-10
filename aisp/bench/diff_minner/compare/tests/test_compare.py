import copy
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare.py"
SPEC = importlib.util.spec_from_file_location("diff_minner_compare", SCRIPT)
compare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compare)

UTC = timezone.utc
APP_REQUIRED = {
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
APP_ALL = {metric for values in APP_REQUIRED.values() for metric in values}
METADATA_OPS = ("create", "stat", "unlink", "open", "readdir")
BLOCKS = ("4KiB", "128KiB", "1MiB", "64MiB")
LOWER_BETTER = {
    "dataset_samples_per_gpu", "ckpt_write_bandwidth", "kv_effective_hit_rate", "kv_qps",
    "storage_sequential_read_bandwidth", "storage_random_read_bandwidth", "storage_write_bandwidth",
    "storage_random_read_iops", "storage_random_write_iops", "interference_read_bandwidth",
    *{f"metadata_{op}_qps" for op in METADATA_OPS},
}


def scenario(operation=None, block=None, streams=None, kind=None, background=None):
    return {
        "operation": operation,
        "block_size": block,
        "streams": streams,
        "metadata_file_kind": kind,
        "background_write_mb_s_per_disk": background,
    }


def required_templates(kind):
    result = []
    for metric, statistics_ in APP_REQUIRED[kind].items():
        result.extend((metric, statistic, None, False) for statistic in statistics_)

    def add(metric, statistics_, operations, blocks, backgrounds=(None,)):
        for operation in operations:
            for block in blocks:
                for background in backgrounds:
                    for statistic in statistics_:
                        result.append((metric, statistic, scenario(operation, block, background=background), True))

    if kind == "dataset":
        add("storage_sequential_read_bandwidth", ("mean",), ("sequential_read",), BLOCKS)
        add("storage_random_read_bandwidth", ("mean",), ("random_read",), BLOCKS)
        for file_kind in ("empty", "real_small"):
            for operation in METADATA_OPS:
                result.append((f"metadata_{operation}_qps", "mean", scenario(kind=file_kind), False))
                for statistic in ("mean", "p50", "p99", "p999"):
                    result.append((f"metadata_{operation}_latency", statistic, scenario(kind=file_kind), False))
    elif kind == "ckpt":
        add("storage_write_bandwidth", ("mean",), ("sequential_write",), BLOCKS)
        add("storage_io_latency", ("mean", "p50", "p99", "p999"), ("sequential_write", "random_write"), BLOCKS)
    else:
        add("storage_random_read_iops", ("mean",), ("random_read",), ("4KiB",))
        add("storage_io_latency", ("mean", "p50", "p99", "p999"), ("random_read",), ("4KiB",))
    if kind in ("ckpt", "kvcache"):
        add("interference_read_bandwidth", ("mean",), ("sequential_read", "random_read"), BLOCKS, (0.0, 256.0, 512.0))
        add("interference_read_latency", ("p99",), ("sequential_read", "random_read"), BLOCKS, (0.0, 256.0, 512.0))
    return result


def payload(kind):
    if kind == "dataset":
        return {"dataset": {
            "file_count": 100, "file_size": {"fixed_bytes": 4096},
            "files_per_rank": 10, "random_read": True,
        }}
    if kind == "ckpt":
        return {"ckpt": {
            "model_parameters": 1000, "sharding": "rank=1", "save_frequency_steps": 10,
            "async_write": False,
        }}
    return {"kvcache": {
        "bytes_per_token": 128, "context_length": 4096, "hit_rate": 0.5,
        "block_size_bytes": 4096, "concurrent_sessions": 8,
    }}


def policy():
    return {
        "version": "diff-minner-test",
        "mean_threshold": 0.10,
        "tail_threshold": 0.20,
        "metadata_qps_threshold": 0.15,
        "bootstrap_resamples": 17,
        "bootstrap_seed": 7,
        "stability": {
            "min_window_s": 300.0,
            "max_error_rate": 0.0,
            "max_timeout_rate": 0.0,
            "max_throttle_count": 0,
            "max_retry_count": 0,
            "max_performance_decay": 0.0,
            "max_periodic_jitter": 0.0,
        },
        "interference_tolerance_mb_s_per_disk": 0.0,
        "calibration_evidence_uri": "evidence://policy-calibration",
    }


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def environment(side):
    return {
        "machine_model": "machine", "cpu_model": "cpu", "nic_model": "nic", "nic_count": 1,
        "disk_model": "disk", "disk_count": 1, "filesystem_version": side + "-1",
        "adapter": "adapter@1", "mount_options": "rw," + side, "client_count": 1,
        "iodepth": 16, "direct": True,
    }


def admission(kind, start):
    return {
        "content_match": True,
        "checksum_algorithm": "sha256 full file",
        "content_evidence_uri": "evidence://content",
        "checkpoint_recovery": True if kind == "ckpt" else None,
        "mlperf_storage_version": "mlperf-1" if kind == "ckpt" else None,
        "training_state_evidence_uri": "evidence://training" if kind == "ckpt" else None,
        "error_rate": 0.0, "timeout_rate": 0.0, "throttle_count": 0, "retry_count": 0,
        "stability_window_s": 300.0,
        "stability_started_at": iso(start - timedelta(seconds=30)),
        "stability_ended_at": iso(start + timedelta(seconds=270)),
        "performance_decay": 0.0, "periodic_jitter": 0.0,
        "stability_series_uri": "evidence://stability",
    }


def interference(start, target):
    return {
        "configured_mb_s_per_disk": target, "actual_mb_s_per_disk": target, "disk_count": 1,
        "started_at": iso(start - timedelta(seconds=60)),
        "ended_at": iso(start + timedelta(seconds=300)),
        "evidence_uri": "evidence://interference",
    }


def make_round(kind, storage_scenario, index, efs_value, gpfs_value):
    start = datetime(2026, 2, 1, tzinfo=UTC) + timedelta(seconds=(index - 1) * 600)
    first = "efs" if index % 2 else "gpfs"
    second = "gpfs" if first == "efs" else "efs"
    starts = {first: start, second: start + timedelta(seconds=120)}
    window = {"shape": {"duration_s": 120.0, "warmup_discard_s": 30.0}}
    for side in ("efs", "gpfs"):
        window[side + "_started_at"] = iso(starts[side])
        window[side + "_ended_at"] = iso(starts[side] + timedelta(seconds=120))
    background = storage_scenario is not None and storage_scenario["background_write_mb_s_per_disk"] is not None
    return {
        "index": index, "efs_value": efs_value, "gpfs_value": gpfs_value, "first": first,
        "environments": {"efs": environment("efs"), "gpfs": environment("gpfs")},
        "window": window,
        "interference": (
            {"efs": interference(start, storage_scenario["background_write_mb_s_per_disk"]),
             "gpfs": interference(start, storage_scenario["background_write_mb_s_per_disk"])}
            if background else None
        ),
        "admission": {"efs": admission(kind, start), "gpfs": admission(kind, start)},
        "evidence_uri": "evidence://round",
    }


def make_noise(kind, cache, metric, statistic, storage_scenario, first_round, side):
    measurements = []
    for day in (1, 2):
        for hour in (0, 1):
            start = datetime(2026, 1, day, hour, tzinfo=UTC)
            background = storage_scenario is not None and storage_scenario["background_write_mb_s_per_disk"] is not None
            measurements.append({
                "measured_on": start.date().isoformat(), "value": 10.0,
                "started_at": iso(start), "ended_at": iso(start + timedelta(seconds=120)),
                "interference": interference(start, storage_scenario["background_write_mb_s_per_disk"]) if background else None,
                "evidence_uri": "evidence://noise-measurement",
            })
    return {
        "side": side, "payload": payload(kind), "metric": metric, "statistic": statistic,
        "cache_state": cache, "storage_scenario": copy.deepcopy(storage_scenario),
        "environment": copy.deepcopy(first_round["environments"][side]),
        "window": copy.deepcopy(first_round["window"]["shape"]),
        "measurements": measurements,
        "between_round_differences": [0.0, 0.0],
        "between_day_differences": [0.0],
        "band": 0.0,
        "evidence_uri": "evidence://noise-calculation",
    }


def make_series(kind, cache, metric, statistic, storage_scenario):
    if metric in APP_ALL:
        efs_value = gpfs_value = 10.0
    elif metric in LOWER_BETTER:
        efs_value, gpfs_value = 5.0, 10.0
    else:
        efs_value, gpfs_value = 20.0, 10.0
    rounds = [make_round(kind, storage_scenario, index, efs_value, gpfs_value) for index in range(1, 6)]
    return {
        "metric": metric, "statistic": statistic, "storage_scenario": copy.deepcopy(storage_scenario),
        "order_seed": 123, "rounds": rounds,
        "noise": [make_noise(kind, cache, metric, statistic, storage_scenario, rounds[0], side) for side in ("efs", "gpfs")],
    }


def make_group(kind="dataset"):
    series = []
    for metric, statistic, template, concurrent in required_templates(kind):
        for streams in ((1, 16) if concurrent else (None,)):
            storage_scenario = copy.deepcopy(template)
            if concurrent:
                storage_scenario["streams"] = streams
            series.append(make_series(kind, "cold", metric, statistic, storage_scenario))
    return {
        "group_id": kind + "-cold", "run_id": "run-1", "payload": payload(kind),
        "cache_state": "cold", "series": series,
    }


def evaluate(group):
    return compare.evaluate({"group": group, "policy": policy()})


def get_series(group, metric, statistic="mean", **scenario_fields):
    for series in group["series"]:
        if series["metric"] != metric or series["statistic"] != statistic:
            continue
        if all(series["storage_scenario"] is not None and series["storage_scenario"][key] == value for key, value in scenario_fields.items()):
            return series
        if series["storage_scenario"] is None and not scenario_fields:
            return series
    raise AssertionError((metric, statistic, scenario_fields))


def run_cli(data=None, raw=None, args=()):
    environment_ = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args],
        input=raw if raw is not None else json.dumps(data),
        text=True, capture_output=True, env=environment_, timeout=60, check=False,
    )


class BootstrapTests(unittest.TestCase):
    def test_fixed_pcg64_vector_and_first_indices(self):
        real_generator = compare.np.random.Generator
        calls = []

        class RecordingGenerator(real_generator):
            def integers(self, *args, **kwargs):
                values = super().integers(*args, **kwargs)
                calls.append(values.copy())
                return values

        differences = np.array([0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
        with mock.patch.object(compare.np.random, "Generator", RecordingGenerator):
            ci = compare.bootstrap_ci(differences, 17, 7)
        self.assertEqual(calls[0].tolist(), [5, 3, 4, 5, 3, 4])
        self.assertEqual(len(calls), 17)
        self.assertAlmostEqual(float(ci[0]), 1.1)
        self.assertAlmostEqual(float(ci[1]), 2.4)

    def test_10000_resamples_are_deterministic(self):
        differences = np.arange(1, 21, dtype=float)
        first = compare.bootstrap_ci(differences, 10000, 20261103)
        second = compare.bootstrap_ci(differences, 10000, 20261103)
        np.testing.assert_array_equal(first, second)
        np.testing.assert_array_equal(first, np.array([6.5, 14.5]))

    def test_gate_boundaries(self):
        gates = compare.gates_for(0.0, 0.1, 0.1, 0.1)
        self.assertEqual(gates, {"statistical": False, "practical": True, "above_noise": False})

    def test_directions_and_threshold_kinds(self):
        group = make_group()
        higher = compare.metric_comparison(get_series(group, "dataset_first_batch_wait"), policy())
        for round_ in higher["series"]["rounds"]:
            round_["efs_value"], round_["gpfs_value"] = 20.0, 10.0
        higher = compare.metric_comparison(higher["series"], policy())
        self.assertEqual(higher["relative_gap"], 1.0)
        self.assertEqual(higher["paired_difference_ci"], {"lower": 10.0, "upper": 10.0})
        self.assertEqual(higher["threshold_kind"], "mean")

        lower_series = get_series(group, "dataset_samples_per_gpu")
        for round_ in lower_series["rounds"]:
            round_["efs_value"], round_["gpfs_value"] = 5.0, 10.0
        lower = compare.metric_comparison(lower_series, policy())
        self.assertEqual(lower["relative_gap"], 0.5)
        self.assertEqual(lower["paired_difference_ci"], {"lower": 5.0, "upper": 5.0})

        metadata = compare.metric_comparison(get_series(group, "metadata_create_qps"), policy())
        self.assertEqual(metadata["threshold_kind"], "metadata_qps")
        self.assertEqual(metadata["applied_threshold"], 0.15)
        ckpt = make_group("ckpt")
        tail = compare.metric_comparison(get_series(ckpt, "storage_io_latency", "p999"), policy())
        self.assertEqual(tail["threshold_kind"], "tail_latency")
        self.assertEqual(tail["applied_threshold"], 0.20)


class PolicyTests(unittest.TestCase):
    def test_v1_thresholds_and_resamples_are_fixed(self):
        valid = policy()
        valid.update({
            "version": "diff-minner-v1",
            "mean_threshold": 0.10,
            "tail_threshold": 0.20,
            "metadata_qps_threshold": 0.15,
            "bootstrap_resamples": 10000,
            "calibration_evidence_uri": None,
        })
        validator = compare.Validator(make_group(), valid)
        validator.policy_rules()
        self.assertEqual(validator.errors, [])
        for key, wrong in (
            ("mean_threshold", 0.01),
            ("tail_threshold", 0.10),
            ("metadata_qps_threshold", 0.10),
            ("bootstrap_resamples", 17),
        ):
            with self.subTest(key=key):
                configured = copy.deepcopy(valid)
                configured[key] = wrong
                with mock.patch.object(compare, "metric_comparison", side_effect=AssertionError("bootstrap called")):
                    result = compare.evaluate({"group": make_group(), "policy": configured})
                self.assertIn("incomplete", result)
                self.assertTrue(any(key in reason for reason in result["incomplete"]))


class FullGroupTests(unittest.TestCase):
    def test_independent_full_matrices_compare_and_native_hits_do_not_candidate(self):
        expected_counts = {"dataset": 71, "ckpt": 173, "kvcache": 112}
        for kind, count in expected_counts.items():
            with self.subTest(kind=kind):
                group = make_group(kind)
                self.assertEqual(len(group["series"]), count)
                result = evaluate(group)
                self.assertIn("compared", result, result.get("incomplete"))
                comparison = result["compared"]
                self.assertFalse(comparison["candidate"])
                self.assertTrue(any(
                    item["material_diff"] and item["series"]["metric"] not in APP_ALL
                    for item in comparison["metrics"]
                ))
                self.assertNotIn("review", comparison)

    def test_application_auxiliary_hit_triggers_candidate(self):
        group = make_group()
        series = get_series(group, "dataset_gpu_io_wait")
        for round_ in series["rounds"]:
            round_["efs_value"], round_["gpfs_value"] = 20.0, 10.0
        result = evaluate(group)
        self.assertTrue(result["compared"]["candidate"])

    def test_zero_gpfs_median_preserves_statistics_and_other_candidate(self):
        group = make_group()
        zero = get_series(group, "dataset_first_batch_wait")
        for index, round_ in enumerate(zero["rounds"]):
            round_["efs_value"] = (1.0, 2.0, 3.0, 4.0, 100.0)[index]
            round_["gpfs_value"] = 0.0
        auxiliary = get_series(group, "dataset_gpu_io_wait")
        for round_ in auxiliary["rounds"]:
            round_["efs_value"], round_["gpfs_value"] = 20.0, 10.0
        result = evaluate(group)
        self.assertIn("compared", result, result.get("incomplete"))
        self.assertTrue(result["compared"]["candidate"])
        item = next(item for item in result["compared"]["metrics"] if item["series"] is zero)
        self.assertEqual(item["efs_median"], 3.0)
        self.assertEqual(item["efs_mad"], 1.0)
        self.assertEqual(item["gpfs_mad"], 0.0)
        self.assertIsNone(item["relative_gap"])
        self.assertIsNone(item["gates"])
        self.assertFalse(item["material_diff"])
        self.assertTrue(item["uncomparable_reason"])
        self.assertIn("lower", item["paired_difference_ci"])

    def test_missing_required_matrix_members_are_incomplete(self):
        cases = (
            ("dataset", "dataset_gpu_io_wait", "mean", {}),
            ("dataset", "metadata_readdir_latency", "p999", {"metadata_file_kind": "real_small"}),
            ("dataset", "storage_random_read_bandwidth", "mean", {"block_size": "64MiB", "streams": 16}),
            ("ckpt", "storage_io_latency", "p50", {"operation": "random_write", "block_size": "4KiB", "streams": 1}),
            ("ckpt", "interference_read_latency", "p99", {"operation": "random_read", "block_size": "1MiB", "streams": 1, "background_write_mb_s_per_disk": 512.0}),
            ("kvcache", "kv_ttft", "p99", {}),
            ("kvcache", "storage_random_read_iops", "mean", {"streams": 16}),
        )
        for kind, metric, statistic, fields in cases:
            with self.subTest(kind=kind, metric=metric, statistic=statistic, fields=fields):
                group = make_group(kind)
                selected = get_series(group, metric, statistic, **fields)
                group["series"].remove(selected)
                result = evaluate(group)
                self.assertIn("incomplete", result)
                self.assertNotIn("compared", result)

    def test_duplicate_series_and_illegal_statistic_are_incomplete(self):
        group = make_group()
        group["series"].append(copy.deepcopy(group["series"][0]))
        self.assertIn("incomplete", evaluate(group))
        group = make_group()
        series = get_series(group, "dataset_gpu_io_wait")
        series["statistic"] = "p99"
        for baseline in series["noise"]:
            baseline["statistic"] = "p99"
        self.assertIn("incomplete", evaluate(group))
    def test_null_native_streams_are_incomplete_not_an_exception(self):
        group = make_group()
        series = get_series(group, "storage_sequential_read_bandwidth", streams=1)
        series["storage_scenario"]["streams"] = None
        for baseline in series["noise"]:
            baseline["storage_scenario"]["streams"] = None
        result = evaluate(group)
        self.assertIn("incomplete", result)
        self.assertTrue(any("streams" in reason for reason in result["incomplete"]))
    def test_numeric_equivalent_scenarios_are_duplicates(self):
        group = make_group("ckpt")
        series = get_series(
            group, "interference_read_bandwidth", operation="sequential_read",
            block_size="4KiB", streams=1, background_write_mb_s_per_disk=0.0,
        )
        duplicate = copy.deepcopy(series)
        duplicate["storage_scenario"]["background_write_mb_s_per_disk"] = 0
        group["series"].append(duplicate)
        result = evaluate(group)
        self.assertIn("incomplete", result)
        self.assertTrue(any("duplicate" in reason for reason in result["incomplete"]))


class AdmissionAndEvidenceTests(unittest.TestCase):
    def test_invalid_stability_policy_cannot_create_efs_defect(self):
        group = make_group()
        configured = policy()
        configured["stability"]["max_error_rate"] = -1.0
        result = compare.evaluate({"group": group, "policy": configured})
        self.assertIn("incomplete", result)
        self.assertTrue(any("max_error_rate" in reason for reason in result["incomplete"]))

    def test_efs_defect_precedes_incomplete_matrix_and_gpfs_failure(self):
        group = make_group()
        group["series"] = group["series"][:1]
        group["series"][0]["rounds"][0]["admission"]["efs"]["content_match"] = False
        group["series"][0]["rounds"][0]["admission"]["gpfs"]["content_match"] = False
        group["series"][0]["rounds"][1]["first"] = group["series"][0]["rounds"][0]["first"]
        result = evaluate(group)
        self.assertIn("defect", result)
        self.assertFalse(result["defect"]["baseline_valid"])

    def test_efs_defect_with_complete_passing_gpfs_has_valid_baseline(self):
        group = make_group()
        group["series"][0]["rounds"][0]["admission"]["efs"]["content_match"] = False
        result = evaluate(group)
        self.assertIn("defect", result)
        self.assertTrue(result["defect"]["baseline_valid"])

    def test_efs_only_evidence_error_does_not_invalidate_gpfs_baseline(self):
        group = make_group()
        admission = group["series"][0]["rounds"][0]["admission"]
        admission["efs"]["content_match"] = False
        admission["efs"]["content_evidence_uri"] = ""
        result = evaluate(group)
        self.assertIn("defect", result)
        self.assertTrue(result["defect"]["baseline_valid"])

        admission["gpfs"]["content_evidence_uri"] = ""
        result = evaluate(group)
        self.assertIn("defect", result)
        self.assertFalse(result["defect"]["baseline_valid"])

    def test_gpfs_only_failure_is_incomplete_without_statistics(self):
        group = make_group()
        group["series"][0]["rounds"][0]["admission"]["gpfs"]["error_rate"] = 1.0
        with mock.patch.object(compare, "metric_comparison", side_effect=AssertionError("bootstrap called")):
            result = evaluate(group)
        self.assertIn("incomplete", result)
        self.assertNotIn("candidate", result)

    def test_missing_admission_field_is_input_error(self):
        group = make_group()
        del group["series"][0]["rounds"][0]["admission"]["efs"]["content_match"]
        with self.assertRaises(compare.InputError):
            evaluate(group)

    def test_empty_admission_evidence_is_incomplete(self):
        group = make_group()
        group["series"][0]["rounds"][0]["admission"]["efs"]["content_evidence_uri"] = ""
        self.assertIn("incomplete", evaluate(group))

    def test_abba_actual_windows_and_stability_coverage(self):
        mutations = []
        def same_first(group):
            rounds = group["series"][0]["rounds"]
            rounds[1]["first"] = rounds[0]["first"]
        mutations.append(("first side must alternate", same_first))

        def bad_duration(group):
            window = group["series"][0]["rounds"][0]["window"]
            ended = datetime.fromisoformat(window["efs_ended_at"].replace("Z", "+00:00"))
            window["efs_ended_at"] = iso(ended + timedelta(seconds=1))
        mutations.append(("actual duration differs", bad_duration))

        def bad_coverage(group):
            round_ = group["series"][0]["rounds"][0]
            evidence = round_["admission"]["efs"]
            start = datetime.fromisoformat(round_["window"]["efs_started_at"].replace("Z", "+00:00")) + timedelta(seconds=1)
            evidence["stability_started_at"] = iso(start)
            evidence["stability_ended_at"] = iso(start + timedelta(seconds=300))
        mutations.append(("does not cover", bad_coverage))

        for message, mutate in mutations:
            with self.subTest(message=message):
                group = make_group()
                mutate(group)
                result = evaluate(group)
                self.assertIn("incomplete", result)
                self.assertTrue(any(message in reason for reason in result["incomplete"]), result["incomplete"])

    def test_native_environment_and_interference_tolerance(self):
        group = make_group()
        group["series"][5]["rounds"][0]["environments"]["efs"]["direct"] = False
        self.assertIn("incomplete", evaluate(group))
        group = make_group("ckpt")
        series = get_series(group, "interference_read_bandwidth", background_write_mb_s_per_disk=256.0)
        series["rounds"][0]["interference"]["efs"]["actual_mb_s_per_disk"] = 255.0
        self.assertIn("incomplete", evaluate(group))


class NoiseAndNativeOnlyTests(unittest.TestCase):
    def test_noise_band_and_differences_are_recomputed(self):
        for field in ("band", "between_round_differences", "between_day_differences"):
            with self.subTest(field=field):
                group = make_group()
                noise = group["series"][0]["noise"][0]
                if field == "band":
                    noise[field] = 0.1
                else:
                    noise[field] = [0.1] * len(noise[field])
                result = evaluate(group)
                self.assertIn("incomplete", result)
                self.assertTrue(any(field in reason for reason in result["incomplete"]))

    def test_noise_requires_two_sides_dates_and_nonzero_predecessors(self):
        group = make_group()
        group["series"][0]["noise"] = group["series"][0]["noise"][:1]
        self.assertIn("incomplete", evaluate(group))
        group = make_group()
        group["series"][0]["noise"][0]["measurements"] = group["series"][0]["noise"][0]["measurements"][:2]
        self.assertIn("incomplete", evaluate(group))
        group = make_group()
        group["series"][0]["noise"][0]["measurements"][0]["value"] = 0.0
        result = evaluate(group)
        self.assertIn("incomplete", result)
        self.assertTrue(any("zero predecessor" in reason for reason in result["incomplete"]))

    def test_native_only_and_one_round_never_bootstrap_or_candidate(self):
        for one_round in (False, True):
            with self.subTest(one_round=one_round):
                group = make_group()
                native = [series for series in group["series"] if series["metric"] not in APP_ALL]
                group["series"] = native[:1] if one_round else native
                if one_round:
                    group["series"][0]["rounds"] = group["series"][0]["rounds"][:1]
                with mock.patch.object(compare, "metric_comparison", side_effect=AssertionError("bootstrap called")):
                    result = evaluate(group)
                self.assertIn("incomplete", result)
                self.assertNotIn("compared", result)
                self.assertNotIn("candidate", result)


class CliTests(unittest.TestCase):
    def test_compared_defect_and_incomplete_exit_zero_with_one_json_value(self):
        group = make_group()
        compared = run_cli({"group": group, "policy": policy()})
        self.assertEqual(compared.returncode, 0, compared.stderr)
        self.assertIn("compared", json.loads(compared.stdout))

        defect_group = make_group()
        defect_group["series"] = defect_group["series"][:1]
        defect_group["series"][0]["rounds"][0]["admission"]["efs"]["content_match"] = False
        defect = run_cli({"group": defect_group, "policy": policy()})
        self.assertEqual(defect.returncode, 0, defect.stderr)
        self.assertIn("defect", json.loads(defect.stdout))

        incomplete_group = make_group()
        incomplete_group["series"] = [series for series in incomplete_group["series"] if series["metric"] not in APP_ALL]
        incomplete = run_cli({"group": incomplete_group, "policy": policy()})
        self.assertEqual(incomplete.returncode, 0, incomplete.stderr)
        self.assertIn("incomplete", json.loads(incomplete.stdout))

    def test_nonfinite_derived_statistics_are_incomplete(self):
        group = make_group()
        series = get_series(group, "dataset_first_batch_wait")
        for round_ in series["rounds"]:
            round_["efs_value"] = 1e308
            round_["gpfs_value"] = 1e-308
        result = run_cli({"group": group, "policy": policy()})
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("incomplete", payload)
        self.assertTrue(any("relative gap" in reason for reason in payload["incomplete"]))

    def test_raw_smoke_malformed_nonfinite_and_series_mode_are_input_errors(self):
        cases = (
            {"raw": json.dumps({"jobs": []})},
            {"raw": "{"},
            {"raw": json.dumps({"group": make_group(), "policy": policy()}).replace('"mean_threshold": 0.1', '"mean_threshold": NaN')},
            {"raw": json.dumps({"group": make_group(), "policy": policy()}).replace('"mean_threshold": 0.1', '"mean_threshold": 1' + '0' * 400)},
            {"raw": json.dumps({"group": make_group(), "policy": policy()}), "args": ("series",)},
        )
        for case in cases:
            with self.subTest(case=case.get("raw", "")[:40], args=case.get("args")):
                result = run_cli(raw=case["raw"], args=case.get("args", ()))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
