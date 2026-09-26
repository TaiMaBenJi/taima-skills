from __future__ import annotations

import base64
import json
import subprocess
import sys
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import practice_lab  # noqa: E402


class PracticeLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lab = practice_lab.PracticeLab()
        cls.base_url = cls.lab.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.lab.stop()

    def test_exact_bytes_and_header_slot_have_a_negative_control(self) -> None:
        accepted = practice_lab.exact_bytes_request(self.base_url, correct=True)
        rejected = {
            failure: practice_lab.exact_bytes_request(
                self.base_url, correct=False, failure=failure
            )
            for failure in ("wrong-slot", "wrong-body", "wrong-order")
        }

        self.assertEqual(accepted.status, 200)
        self.assertEqual(json.loads(accepted.body)["anchor"], "exact-wire-accepted")
        for failure, response in rejected.items():
            with self.subTest(failure=failure):
                self.assertEqual(response.status, 422)
                self.assertEqual(
                    json.loads(response.body)["error"], "wire-contract-mismatch"
                )

    def test_session_bootstrap_rejects_cross_session_splicing(self) -> None:
        first = practice_lab.acquire_session(self.base_url)
        second = practice_lab.acquire_session(self.base_url)

        accepted = practice_lab.session_business_request(
            self.base_url, first.cookie, first.token
        )
        rejected = practice_lab.session_business_request(
            self.base_url, second.cookie, first.token
        )

        self.assertEqual(accepted.status, 200)
        self.assertEqual(json.loads(accepted.body)["anchor"], "same-chain-accepted")
        self.assertEqual(rejected.status, 403)
        self.assertEqual(json.loads(rejected.body)["error"], "session-chain-mismatch")

    def test_response_decode_requires_prefix_base64_zlib_order(self) -> None:
        response = practice_lab.simple_request(self.base_url, "GET", "/decode/data")

        decoded = practice_lab.decode_payload(response.body)

        self.assertEqual(response.status, 200)
        self.assertEqual(decoded["anchor"], "decode-chain-accepted")
        with self.assertRaises(ValueError):
            practice_lab.decode_payload(response.body.removeprefix(b"LAB1."))

    def test_response_decode_rejects_bombs_and_invalid_utf8(self) -> None:
        oversized = b"A" * (practice_lab.MAX_DECODED_JSON_BYTES + 1)
        bomb = b"LAB1." + base64.b64encode(zlib.compress(oversized))
        with self.assertRaisesRegex(ValueError, "exceeds limit"):
            practice_lab.decode_payload(bomb)

        invalid_utf8 = b"LAB1." + base64.b64encode(zlib.compress(b"\xff"))
        with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
            practice_lab.decode_payload(invalid_utf8)

        deeply_nested = (
            b"[" * practice_lab.MAX_JSON_DEPTH
            + b"0"
            + b"]" * practice_lab.MAX_JSON_DEPTH
        )
        nested_payload = b"LAB1." + base64.b64encode(zlib.compress(deeply_nested))
        with self.assertRaisesRegex(ValueError, "nesting limit"):
            practice_lab.decode_payload(nested_payload)

    def test_handler_rejects_oversized_content_length_before_reading(self) -> None:
        response = practice_lab.simple_request(
            self.base_url,
            "POST",
            "/exact/data",
            headers=(("Content-Length", str(practice_lab.MAX_REQUEST_BODY_BYTES + 1)),),
        )

        self.assertEqual(response.status, 413)
        self.assertEqual(json.loads(response.body)["error"], "request-body-too-large")

    def test_practice_state_has_session_and_export_caps(self) -> None:
        state = practice_lab.PracticeState(max_sessions=2, max_exports=1)
        state.issue_session()
        state.issue_context_session()
        with self.assertRaisesRegex(RuntimeError, "session limit"):
            state.issue_session()
        with self.assertRaisesRegex(RuntimeError, "export task limit"):
            state.issue_export_task(start="a", end="b", fields=["a"])

    def test_pagination_follows_live_route_instead_of_guessing(self) -> None:
        first = practice_lab.simple_request(self.base_url, "GET", "/page/list?page=1")
        first_payload = json.loads(first.body)
        guessed = practice_lab.simple_request(self.base_url, "GET", "/page/list?page=2")
        actual = practice_lab.simple_request(
            self.base_url, "GET", first_payload["next"]
        )

        self.assertEqual(first.status, 200)
        self.assertEqual(guessed.status, 404)
        self.assertEqual(actual.status, 200)
        self.assertEqual(json.loads(actual.body)["anchor"], "route-pivot-accepted")

    def test_modded_digest_rejects_standard_and_broken_ports(self) -> None:
        accepted = practice_lab.digest_request(self.base_url, mode="correct")
        rejected = {
            mode: practice_lab.digest_request(self.base_url, mode=mode)
            for mode in ("standard", "missing-mask", "broken-rotl")
        }

        self.assertEqual(accepted.status, 200)
        self.assertEqual(json.loads(accepted.body)["anchor"], "modded-digest-accepted")
        self.assertNotEqual(
            practice_lab.correct_modded_token(),
            practice_lab.standard_digest_token(),
        )
        for mode, response in rejected.items():
            with self.subTest(mode=mode):
                self.assertEqual(response.status, 403)
                self.assertEqual(
                    json.loads(response.body)["error"], "modded-digest-mismatch"
                )

    def test_multi_context_requires_full_activation_and_unique_labels(self) -> None:
        good = practice_lab.multi_context_request(self.base_url, mode="correct")
        missing = practice_lab.multi_context_request(self.base_url, mode="missing-range-type")
        labeled = practice_lab.multi_context_request(self.base_url, mode="label-as-value")

        self.assertEqual(good["activate"].status, 200)
        self.assertEqual(good["data"].status, 200)
        self.assertEqual(json.loads(good["data"].body)["anchor"], "multi-context-accepted")

        self.assertEqual(missing["activate"].status, 200)
        self.assertEqual(json.loads(missing["activate"].body)["success"], True)
        self.assertEqual(missing["data"].status, 409)

        self.assertEqual(labeled["data"].status, 409)
        self.assertEqual(
            practice_lab.resolve_protocol_id("Alpha Shop", practice_lab.CTX_AUTH_ROWS),
            "shop-100",
        )
        with self.assertRaises(ValueError):
            practice_lab.resolve_protocol_id("Alpha", practice_lab.CTX_AUTH_ROWS)

    def test_async_export_isolates_tasks_and_field_gates(self) -> None:
        good = practice_lab.async_export_flow(self.base_url, mode="correct")
        empty = practice_lab.async_export_flow(self.base_url, mode="empty-success")
        polluted = practice_lab.async_export_flow(self.base_url, mode="pollute-newest")

        self.assertEqual(good["gate"], "passed")
        self.assertEqual(good["columns"], ["a", "b", "c"])
        self.assertEqual(empty["create"].status, 200)
        self.assertEqual(empty.get("new_task_ids"), [])
        self.assertEqual(polluted["gate"], "failed")
        with self.assertRaises(ValueError):
            practice_lab.select_export_task(
                before_ids={"t0001"},
                after_tasks=[{"task_id": "t0001", "start": "2025-01-01", "end": "2025-01-02", "fields": ["a"]}],
                create_task_id=None,
                start="2026-01-01",
                end="2026-01-02",
                fields=["a", "b", "c"],
            )

        matching_old_task = {
            "task_id": "t0001",
            "start": "2026-01-01",
            "end": "2026-01-02",
            "fields": ["a", "b", "c"],
        }
        with self.assertRaisesRegex(ValueError, "one new matching task"):
            practice_lab.select_export_task(
                before_ids={"t0001"},
                after_tasks=[matching_old_task],
                create_task_id="t0001",
                start="2026-01-01",
                end="2026-01-02",
                fields=["a", "b", "c"],
            )

        with self.assertRaisesRegex(ValueError, "field-completeness"):
            practice_lab.export_field_gate(
                requested_fields=["a", "b"],
                downloaded_columns=["x", "y"],
            )
        practice_lab.export_field_gate(
            requested_fields=["a", "b"],
            downloaded_columns=["b", "a"],
        )
        with self.assertRaisesRegex(ValueError, "duplicates"):
            practice_lab.export_field_gate(
                requested_fields=["a", "b"],
                downloaded_columns=["a", "a"],
            )

    def test_cli_self_test_covers_seven_cases(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "practice_lab.py"), "--self-test"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("practice_lab_self_test=PASS", result.stdout)
        self.assertIn("cases=7", result.stdout)
        self.assertIn("negative_controls=15", result.stdout)


if __name__ == "__main__":
    unittest.main()
