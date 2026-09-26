from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import protocol_diff  # noqa: E402
import transport_profile_diff  # noqa: E402
from _bounded_input import BoundedInputError, read_utf8_text, validate_json_shape  # noqa: E402


class ProtocolDiffTests(unittest.TestCase):
    def test_flatten_paths_do_not_collide_and_preserve_empty_containers(self) -> None:
        flattened = protocol_diff.flatten_json(
            {
                "a": {"b": 1},
                "a.b": 2,
                "empty_object": {},
                "empty_list": [],
            }
        )

        self.assertEqual(flattened["$.a.b"], "1")
        self.assertEqual(flattened['$["a.b"]'], "2")
        self.assertEqual(flattened["$.empty_object"], "{}")
        self.assertEqual(flattened["$.empty_list"], "[]")

    def test_invalid_utf8_is_a_stable_cli_error(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / "invalid.txt"
            valid = root / "valid.txt"
            invalid.write_bytes(b"\xff\xfe")
            valid.write_text("ok", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPTS / "protocol_diff.py"),
                    str(invalid),
                    str(valid),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("not valid UTF-8", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_shared_input_limits_reject_size_depth_and_node_excess(self) -> None:
        with TemporaryDirectory() as directory:
            oversized = Path(directory) / "oversized.txt"
            oversized.write_bytes(b"1234")
            with self.assertRaisesRegex(BoundedInputError, "exceeds 3 bytes"):
                read_utf8_text(oversized, max_bytes=3)

        with self.assertRaisesRegex(BoundedInputError, "nesting exceeds 2 levels"):
            validate_json_shape([[[0]]], label="sample", max_depth=2)
        with self.assertRaisesRegex(BoundedInputError, "more than 2 values"):
            validate_json_shape([1, 2], label="sample", max_nodes=2)


class TransportProfileDiffTests(unittest.TestCase):
    def test_grease_requires_equal_bytes(self) -> None:
        self.assertTrue(transport_profile_diff.is_grease(0x0A0A))
        self.assertTrue(transport_profile_diff.is_grease("0xfafa"))
        self.assertFalse(transport_profile_diff.is_grease(0x1A2A))
        self.assertFalse(transport_profile_diff.is_grease(0x0A1A))


class DiffCliSafetyTests(unittest.TestCase):
    def run_tool(self, script: str, left: Path, right: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPTS / script),
                str(left),
                str(right),
                "--json-output",
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_transport_output_cannot_replace_an_input(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.json"
            right = root / "right.json"
            payload = {"tls": {"cipher_suites": [4865]}}
            original = json.dumps(payload)
            left.write_text(original, encoding="utf-8")
            right.write_text(original, encoding="utf-8")

            completed = self.run_tool("transport_profile_diff.py", left, right, left)

            self.assertEqual(completed.returncode, 2)
            self.assertIn("output path must differ", completed.stderr)
            self.assertEqual(left.read_text(encoding="utf-8"), original)

    def test_transform_output_cannot_replace_an_input(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.json"
            right = root / "right.json"
            payload = {
                "trace_version": 1,
                "stages": [
                    {"name": "one", "input": {"encoding": "utf8", "data": "x"}}
                ],
            }
            original = json.dumps(payload)
            left.write_text(original, encoding="utf-8")
            right.write_text(original, encoding="utf-8")

            completed = self.run_tool("transform_trace_diff.py", left, right, left)

            self.assertEqual(completed.returncode, 2)
            self.assertIn("output path must differ", completed.stderr)
            self.assertEqual(left.read_text(encoding="utf-8"), original)

    def test_output_hardlink_is_rejected_before_read_or_write(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.json"
            right = root / "right.json"
            output = root / "report.json"
            sentinel = root / "sentinel.json"
            payload = json.dumps({"tls": {"cipher_suites": [4865]}})
            left.write_text(payload, encoding="utf-8")
            right.write_text(payload, encoding="utf-8")
            sentinel.write_text("sentinel\n", encoding="utf-8")
            try:
                os.link(sentinel, output)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"filesystem hard links unavailable: {exc}")

            completed = self.run_tool("transport_profile_diff.py", left, right, output)

            self.assertEqual(completed.returncode, 2)
            self.assertIn("hard-linked", completed.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "sentinel\n")

    def test_json_loaders_reject_invalid_utf8_without_tracebacks(self) -> None:
        cases = {
            "transport_profile_diff.py": {"tls": {}},
            "transform_trace_diff.py": {
                "trace_version": 1,
                "stages": [{"name": "one", "input": {"encoding": "utf8", "data": "x"}}],
            },
            "transcript_diff.py": {"steps": []},
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / "invalid.json"
            invalid.write_bytes(b"\xff")
            for script, valid_payload in cases.items():
                with self.subTest(script=script):
                    valid = root / f"{script}.json"
                    valid.write_text(json.dumps(valid_payload), encoding="utf-8")
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-B",
                            str(SCRIPTS / script),
                            str(invalid),
                            str(valid),
                        ],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 2)
                    self.assertIn("not valid UTF-8", completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)

    def test_self_tests_still_execute_under_optimized_python(self) -> None:
        for script in (
            "evidence_normalizer.py",
            "transport_profile_diff.py",
            "transform_trace_diff.py",
            "practice_lab.py",
        ):
            with self.subTest(script=script):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-O",
                        "-B",
                        str(SCRIPTS / script),
                        "--self-test",
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("PASS", completed.stdout)


if __name__ == "__main__":
    unittest.main()
