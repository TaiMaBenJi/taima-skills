from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "transcript_diff.py"


def package(seed: str) -> dict[str, object]:
    final_request = {
        "method": "POST",
        "url": "https://example.test/business",
        "headers": [
            ["Content-Type", "application/octet-stream"],
            ["X-Trace", "same"],
            ["X-Trace", "same-again"],
        ],
        "body": {"length": 4, "sha256": "deadbeef"},
    }
    return {
        "schema_version": 1,
        "generated_at": "ignored-build-metadata",
        "chains": [
            {
                "chain_id": "round-1",
                "steps": [
                    {
                        "name": "entry",
                        "request": {
                            "method": "GET",
                            "url": "https://example.test/entry",
                            "headers": [],
                            "body": {"length": 0, "sha256": None},
                        },
                        "response": {
                            "status": 200,
                            "headers": [["Set-Cookie", seed], ["X-Step", "entry"]],
                            "body": {"length": 2, "sha256": "entry-body"},
                        },
                        "state_writes": [
                            {"kind": "cookie", "name": "seed", "value": seed}
                        ],
                    },
                    {
                        "name": "business",
                        "request": final_request,
                        "response": {
                            "status": 200,
                            "headers": [],
                            "body": {"length": 2, "sha256": "same-response"},
                        },
                        "state_writes": [],
                    },
                ],
            }
        ],
    }


class TranscriptDiffTests(unittest.TestCase):
    def run_cli(self, left: dict[str, object], right: dict[str, object], *args: str):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left.json"
            right_path = root / "right.json"
            left_path.write_text(json.dumps(left), encoding="utf-8")
            right_path.write_text(json.dumps(right), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    str(left_path),
                    str(right_path),
                    *args,
                ],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_reports_first_state_divergence_before_identical_final_request(self) -> None:
        result = self.run_cli(package("<redacted:a>"), package("<redacted:b>"), "--json")

        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["equal"])
        self.assertEqual(payload["first_divergence"]["step_index"], 0)
        self.assertIn("response.headers[0][1]", payload["first_divergence"]["path"])
        self.assertEqual(payload["left_steps"], 2)
        self.assertEqual(payload["right_steps"], 2)

    def test_preserves_duplicate_header_order(self) -> None:
        right = package("<redacted:a>")
        headers = right["chains"][0]["steps"][1]["request"]["headers"]
        headers.reverse()

        result = self.run_cli(package("<redacted:a>"), right, "--json")

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["first_divergence"]["step_index"], 1)
        self.assertIn("request.headers[0]", payload["first_divergence"]["path"])

    def test_identical_chains_ignore_generated_at(self) -> None:
        left = package("<redacted:a>")
        right = package("<redacted:a>")
        right["generated_at"] = "different-build-metadata"

        result = self.run_cli(left, right, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["equal"])

    def test_selects_evidence_normalizer_session_chain_ids(self) -> None:
        left = package("<redacted:a>")
        right = package("<redacted:b>")
        left["chains"][0]["session_chain_id"] = left["chains"][0].pop("chain_id")
        right["chains"][0]["session_chain_id"] = right["chains"][0].pop("chain_id")

        result = self.run_cli(
            left,
            right,
            "--left-chain",
            "round-1",
            "--right-chain",
            "round-1",
            "--json",
        )

        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["left_chain"], "round-1")
        self.assertEqual(payload["right_chain"], "round-1")

    def test_numeric_divergence_does_not_echo_raw_values(self) -> None:
        left = package("<redacted:a>")
        right = package("<redacted:a>")
        left["chains"][0]["steps"][0]["state_writes"][0]["value"] = 987654321012345
        right["chains"][0]["steps"][0]["state_writes"][0]["value"] = 987654321012346

        result = self.run_cli(left, right, "--json")

        self.assertEqual(result.returncode, 1, result.stderr)
        divergence = json.loads(result.stdout)["first_divergence"]
        self.assertNotIn("value", divergence["left"])
        self.assertNotIn("value", divergence["right"])
        self.assertNotIn("987654321012345", result.stdout)
        self.assertNotIn("987654321012346", result.stdout)

    def test_self_test_mode(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--self-test"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("transcript_diff_self_test=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
