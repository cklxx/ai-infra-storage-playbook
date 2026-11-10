import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "smoke.py"
SPEC = importlib.util.spec_from_file_location("diff_minner_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)

FAKE_FIO = r'''#!/usr/bin/env python3
import json
import os
import sys
import time

with open(os.environ["FAKE_FIO_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
mode = os.environ.get("FAKE_FIO_MODE", "success")
if mode == "timeout":
    print('{"partial"', end="", flush=True)
    time.sleep(30)
if mode == "invalid":
    print("not-json", end="")
else:
    print(json.dumps({"jobs": [{
        "error": 0,
        "write": {
            "iops": 100,
            "clat_ns": {"percentile": {
                "50.000000": 10,
                "99.000000": 20,
                "99.900000": 30
            }}}
    }]}))
sys.exit(7 if mode == "fail" else 0)
'''


class SmokeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.efs = root / "efs"
        self.gpfs = root / "gpfs"
        self.artifacts = root / "artifacts"
        for path in (self.efs, self.gpfs, self.artifacts):
            path.mkdir()
        self.fake = root / "fake-fio"
        self.fake.write_text(FAKE_FIO, encoding="utf-8")
        self.fake.chmod(0o755)
        self.log = root / "calls.jsonl"
        self.environment = os.environ.copy()
        self.environment["FAKE_FIO_LOG"] = str(self.log)

    def tearDown(self):
        self.temporary.cleanup()

    def run_smoke(self, mode="success", timeout=2):
        self.environment["FAKE_FIO_MODE"] = mode
        arguments = [
            "--efs-root",
            str(self.efs),
            "--gpfs-root",
            str(self.gpfs),
            "--artifacts-root",
            str(self.artifacts),
            "--size-bytes",
            "4096",
            "--first",
            "gpfs",
            "--fio",
            str(self.fake),
            "--timeout-s",
            str(timeout),
        ]
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(smoke, "check_filesystem_roots", return_value=None),
            mock.patch.object(smoke, "check_artifacts_root", return_value=None),
            mock.patch.dict(os.environ, self.environment, clear=True),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            returncode = smoke.main(arguments)
        return SimpleNamespace(returncode=returncode, stdout=stdout.getvalue(), stderr=stderr.getvalue())

    def manifest(self):
        runs = list(self.artifacts.glob("diff-minner-smoke-*"))
        self.assertEqual(len(runs), 1)
        return runs[0], json.loads((runs[0] / "manifest.json").read_text())

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_same_filesystem_is_rejected(self):
        error = smoke.check_filesystem_roots({"efs": self.efs, "gpfs": self.gpfs}, 4096)
        self.assertIn("same filesystem", error)

    def test_insufficient_space_is_rejected(self):
        roots = {"efs": mock.Mock(), "gpfs": mock.Mock()}
        roots["efs"].stat.return_value = SimpleNamespace(st_dev=1)
        roots["gpfs"].stat.return_value = SimpleNamespace(st_dev=2)
        with mock.patch.object(smoke.shutil, "disk_usage", return_value=SimpleNamespace(free=0)):
            error = smoke.check_filesystem_roots(roots, 4096)
        self.assertIn("insufficient free space", error)

    def test_artifacts_on_tested_filesystem_are_rejected(self):
        artifacts = mock.Mock()
        artifacts.stat.return_value = SimpleNamespace(st_dev=1)
        roots = {"efs": mock.Mock(), "gpfs": mock.Mock()}
        roots["efs"].stat.return_value = SimpleNamespace(st_dev=1)
        roots["gpfs"].stat.return_value = SimpleNamespace(st_dev=2)
        self.assertIn("tested filesystem", smoke.check_artifacts_root(artifacts, roots))

    def test_non_finite_timeout_is_rejected_before_fio(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_smoke(timeout="nan")
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(self.calls(), [])

    def test_huge_json_number_is_a_validation_failure(self):
        raw = json.dumps({"jobs": [{"error": 0, "write": {"iops": 10**400}}]})
        with self.assertRaises(ValueError):
            smoke.validate_fio_json(raw)

    def test_success_preserves_pair_and_fixed_arguments(self):
        result = self.run_smoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        run_dir, manifest = self.manifest()
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["order"], ["gpfs", "efs"])
        self.assertFalse(manifest["formal_comparison"])
        self.assertGreaterEqual(
            manifest["sides"]["efs"]["started_at"],
            manifest["sides"]["gpfs"]["ended_at"],
        )
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertIn(str(self.gpfs), calls[0][-1])
        self.assertIn(str(self.efs), calls[1][-1])
        required = {
            "--rw=randwrite",
            "--bs=4k",
            "--ioengine=libaio",
            "--direct=1",
            "--iodepth=16",
            "--numjobs=1",
            "--runtime=120",
            "--time_based=1",
            "--size=4096",
        }
        for arguments in calls:
            self.assertTrue(required.issubset(arguments))
        for side in ("efs", "gpfs"):
            self.assertEqual(manifest["sides"][side]["status"], "completed")
            self.assertTrue((run_dir / f"{side}.stdout.json").is_file())
        self.assertNotIn("candidate", manifest)
        self.assertNotIn("winner", manifest)

    def test_failure_skips_second_side(self):
        result = self.run_smoke(mode="fail")
        self.assertEqual(result.returncode, 1)
        _, manifest = self.manifest()
        self.assertEqual(manifest["sides"]["gpfs"]["status"], "failed")
        self.assertEqual(manifest["sides"]["efs"]["status"], "skipped")
        self.assertEqual(len(self.calls()), 1)

    def test_invalid_json_is_preserved_and_rejected(self):
        with self.assertRaises(ValueError):
            smoke.validate_fio_json(b"[]")
        result = self.run_smoke(mode="invalid")
        self.assertEqual(result.returncode, 1)
        run_dir, manifest = self.manifest()
        self.assertFalse(manifest["sides"]["gpfs"]["json_valid"])
        self.assertEqual((run_dir / "gpfs.stdout.json").read_text(), "not-json")
        self.assertEqual(manifest["sides"]["efs"]["status"], "skipped")

    def test_pending_sigint_after_spawn_kills_process_group(self):
        process = mock.Mock()
        manifest = {"sides": {"gpfs": {"timed_out": False}}}
        args = SimpleNamespace(fio=str(self.fake), size_bytes=4096, timeout_s=2)
        with (
            mock.patch.object(smoke.subprocess, "Popen", return_value=process),
            mock.patch.object(smoke.signal, "pthread_sigmask", side_effect=[None, KeyboardInterrupt]),
            mock.patch.object(smoke, "kill_process_group") as kill,
            self.assertRaises(KeyboardInterrupt),
        ):
            smoke.run_side(
                "gpfs", self.gpfs, self.artifacts, args, manifest, self.artifacts / "manifest.json"
            )
        kill.assert_called_once_with(process)
        process.wait.assert_not_called()
        self.assertEqual(manifest["sides"]["gpfs"]["status"], "interrupted")

    def test_timeout_kills_job_and_preserves_partial_output(self):
        result = self.run_smoke(mode="timeout")
        self.assertEqual(result.returncode, 1)
        run_dir, manifest = self.manifest()
        self.assertTrue(manifest["sides"]["gpfs"]["timed_out"])
        self.assertEqual((run_dir / "gpfs.stdout.json").read_text(), '{"partial"')
        self.assertEqual(manifest["sides"]["efs"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
