from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import evidence_normalizer as normalizer  # noqa: E402


HMAC_KEY = b"unit-test-redaction-key"


def sample_har() -> dict:
    request_body = json.dumps(
        {
            "query": "ordinary-value",
            "access_token": "body-secret",
            "nested": {"password": "password-secret"},
        },
        separators=(",", ":"),
    )
    return {
        "log": {
            "version": "1.2",
            "entries": [
                {
                    "startedDateTime": "2026-07-17T00:00:00.000Z",
                    "time": 12.5,
                    "_sessionChainId": "practice-chain",
                    "request": {
                        "method": "POST",
                        "url": (
                            "https://example.test/start?item=1"
                            "&token=query-secret&item=2"
                        ),
                        "httpVersion": "HTTP/2",
                        "headers": [
                            {"name": "X-Order", "value": "first"},
                            {
                                "name": "Cookie",
                                "value": "sid=cookie-secret; theme=dark",
                            },
                            {"name": "X-Order", "value": "second"},
                            {
                                "name": "Authorization",
                                "value": "Bearer auth-secret",
                            },
                            {
                                "name": "Content-Type",
                                "value": "application/json",
                            },
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": request_body,
                        },
                    },
                    "response": {
                        "status": 302,
                        "statusText": "Found",
                        "httpVersion": "HTTP/2",
                        "redirectURL": (
                            "https://example.test/next?access_token=redirect-secret"
                        ),
                        "headers": [
                            {"name": "X-Reply", "value": "one"},
                            {
                                "name": "Set-Cookie",
                                "value": (
                                    "sid=response-cookie-secret; Path=/; HttpOnly"
                                ),
                            },
                            {"name": "X-Reply", "value": "two"},
                            {
                                "name": "Location",
                                "value": (
                                    "https://example.test/next"
                                    "?access_token=redirect-secret"
                                ),
                            },
                        ],
                        "content": {
                            "mimeType": "text/plain",
                            "text": "response-body-secret",
                        },
                    },
                    "timings": {"send": 1.0, "wait": 10.0, "receive": 1.5},
                }
            ],
        }
    }


class EvidenceNormalizerTests(unittest.TestCase):
    def normalize_har(self, *, include_raw_hashes: bool = False) -> dict:
        document = sample_har()
        source = json.dumps(document, separators=(",", ":")).encode("utf-8")
        return normalizer.normalize_bytes(
            source,
            hmac_key=HMAC_KEY,
            include_raw_hashes=include_raw_hashes,
        )

    def test_har_preserves_ordered_duplicate_headers(self) -> None:
        package = self.normalize_har()
        step = package["chains"][0]["steps"][0]

        self.assertEqual(
            [item["name"] for item in step["request"]["headers"]],
            ["X-Order", "Cookie", "X-Order", "Authorization", "Content-Type"],
        )
        self.assertEqual(
            [item["name"] for item in step["response"]["headers"]],
            ["X-Reply", "Set-Cookie", "X-Reply", "Location"],
        )
        self.assertEqual(step["request"]["headers"][0]["value"], "first")
        self.assertEqual(step["request"]["headers"][2]["value"], "second")

    def test_redaction_is_stable_and_secret_free(self) -> None:
        first = self.normalize_har()
        second = self.normalize_har()
        self.assertEqual(first, second)

        step = first["chains"][0]["steps"][0]
        auth_value = step["request"]["headers"][3]["value"]
        self.assertRegex(auth_value, r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertIn("sid=hmac-sha256:", step["request"]["headers"][1]["value"])
        self.assertEqual(
            step["request"]["body"]["json"]["access_token"],
            normalizer.Redactor(HMAC_KEY).token("body-secret"),
        )

        serialized = normalizer.serialize_json(first).decode("utf-8")
        for secret in (
            "query-secret",
            "cookie-secret",
            "auth-secret",
            "body-secret",
            "password-secret",
            "response-cookie-secret",
            "redirect-secret",
            "response-body-secret",
            HMAC_KEY.decode("ascii"),
        ):
            self.assertNotIn(secret, serialized)

    def test_default_body_fingerprints_and_redirect_metadata(self) -> None:
        document = sample_har()
        request_text = document["log"]["entries"][0]["request"]["postData"]["text"]
        package = self.normalize_har()
        step = package["chains"][0]["steps"][0]

        self.assertNotIn("sha256", package["source"])
        self.assertNotIn("sha256", step["request"]["body"])
        self.assertNotIn("sha256", step["response"]["body"])
        self.assertEqual(
            step["request"]["body"]["hmac_sha256"],
            normalizer.Redactor(HMAC_KEY).digest(request_text.encode("utf-8")),
        )
        self.assertEqual(
            step["response"]["body"]["hmac_sha256"],
            normalizer.Redactor(HMAC_KEY).digest(b"response-body-secret"),
        )
        redirect = step["response"]["redirect"]
        self.assertEqual(redirect["status"], 302)
        self.assertTrue(redirect["location"].startswith("https://example.test/next?"))
        self.assertNotIn("redirect-secret", redirect["location"])

    def test_transcript_json_preserves_form_and_state_write_order(self) -> None:
        transcript = {
            "session_chain_id": "alpha",
            "steps": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://example.test/form",
                        "headers": [
                            ["X-Duplicate", "a"],
                            ["X-API-Key", "header-api-secret"],
                            ["Content-Type", "application/x-www-form-urlencoded"],
                            ["X-Duplicate", "b"],
                        ],
                        "body": "a=1&token=form-secret&a=2",
                    },
                    "response": {
                        "status": 200,
                        "headers": [["X-Duplicate", "one"], ["X-Duplicate", "two"]],
                        "body": {"ok": True, "access_token": "reply-secret"},
                    },
                    "state_writes": [
                        {
                            "surface": "cookie",
                            "name": "sid",
                            "value": "state-secret",
                            "old_value": "old-state-secret",
                        },
                        {"surface": "storage", "name": "counter", "value": 2},
                    ],
                }
            ],
        }
        package = normalizer.normalize_document(transcript, hmac_key=HMAC_KEY)
        step = package["chains"][0]["steps"][0]

        self.assertEqual(package["source"]["format"], "transcript")
        self.assertEqual(package["chains"][0]["session_chain_id"], "alpha")
        self.assertEqual(
            [header["name"] for header in step["request"]["headers"]],
            ["X-Duplicate", "X-API-Key", "Content-Type", "X-Duplicate"],
        )
        self.assertRegex(step["request"]["headers"][1]["value"], r"^hmac-sha256:")
        self.assertEqual(
            [field["name"] for field in step["request"]["body"]["form"]],
            ["a", "token", "a"],
        )
        self.assertEqual(step["request"]["body"]["form"][0]["value"], "1")
        self.assertRegex(
            step["request"]["body"]["form"][1]["value"],
            r"^hmac-sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(
            [item["name"] for item in step["state_writes"]],
            ["sid", "counter"],
        )
        self.assertRegex(step["state_writes"][0]["value"], r"^hmac-sha256:")
        self.assertRegex(step["state_writes"][0]["old_value"], r"^hmac-sha256:")
        self.assertRegex(step["state_writes"][1]["value"], r"^hmac-sha256:")

    def test_redacts_pii_opaque_headers_and_route_query_values(self) -> None:
        transcript = {
            "steps": [
                {
                    "route": "/reset/short-route-secret?token=route-secret",
                    "request": {
                        "method": "POST",
                        "url": "https://example.test/download/" + "B" * 48,
                        "headers": [
                            ["X-Device-Blob", "A" * 48],
                            ["X-Contact", "person@example.test"],
                            ["Content-Type", "application/json"],
                        ],
                        "body": {
                            "email": "person@example.test",
                            "full_name": "Private Person",
                            "otp": "123456",
                        },
                    },
                    "response": {"status": 200, "headers": [], "body": "ok"},
                }
            ]
        }

        package = normalizer.normalize_document(transcript, hmac_key=HMAC_KEY)
        step = package["chains"][0]["steps"][0]
        serialized = normalizer.serialize_json(package).decode("utf-8")

        self.assertRegex(step["request"]["headers"][0]["value"], r"^hmac-sha256:")
        self.assertRegex(step["request"]["headers"][1]["value"], r"^hmac-sha256:")
        self.assertRegex(step["request"]["body"]["json"]["email"], r"^hmac-sha256:")
        self.assertRegex(step["request"]["body"]["json"]["full_name"], r"^hmac-sha256:")
        self.assertRegex(step["request"]["body"]["json"]["otp"], r"^hmac-sha256:")
        self.assertNotIn("short-route-secret", step["route"])
        self.assertNotIn("route-secret", step["route"])
        for secret in (
            "person@example.test",
            "Private Person",
            "123456",
            "short-route-secret",
            "route-secret",
            "A" * 48,
            "B" * 48,
        ):
            self.assertNotIn(secret, serialized)

    def test_plain_json_body_keys_are_not_mistaken_for_encoded_descriptors(self) -> None:
        for key in ("data", "text", "base64"):
            with self.subTest(key=key):
                body = {key: "ordinary-json-value"}
                transcript = {
                    "steps": [
                        {
                            "request": {
                                "method": "POST",
                                "url": "https://example.test/items",
                                "headers": [["Content-Type", "application/json"]],
                                "body": body,
                            },
                            "response": {"status": 200, "headers": [], "body": "ok"},
                        }
                    ]
                }

                package = normalizer.normalize_document(transcript, hmac_key=HMAC_KEY)

                self.assertEqual(
                    package["chains"][0]["steps"][0]["request"]["body"]["json"],
                    body,
                )

    def test_explicit_encoded_body_descriptor_remains_supported(self) -> None:
        encoded = base64.b64encode(b'{"ok":true}').decode("ascii")
        transcript = {
            "steps": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://example.test/items",
                        "headers": [["Content-Type", "application/json"]],
                        "body": {
                            "data": encoded,
                            "encoding": "base64",
                            "mimeType": "application/json",
                        },
                    },
                    "response": {"status": 200, "headers": [], "body": "ok"},
                }
            ]
        }

        package = normalizer.normalize_document(transcript, hmac_key=HMAC_KEY)

        self.assertEqual(
            package["chains"][0]["steps"][0]["request"]["body"]["json"],
            {"ok": True},
        )

    def test_redacts_short_secrets_personal_fields_bare_query_and_folded_cookies(
        self,
    ) -> None:
        transcript = {
            "steps": [
                {
                    "request": {
                        "method": "POST",
                        "url": (
                            "https://example.test/path?session=abc"
                            "&secretKey=k9&opaque-bare&=anonymous"
                        ),
                        "headers": [["Content-Type", "application/json"]],
                        "body": {
                            "session": "abc",
                            "secretKey": "k9",
                            "name": "Private Person",
                            "billingAddress": "1 Private Street",
                        },
                    },
                    "response": {
                        "status": 200,
                        "headers": [
                            [
                                "Set-Cookie",
                                (
                                    "sid=short-session; Expires=Wed, 09 Jun 2027 "
                                    "10:18:14 GMT; Path=/, prefs=tiny; Path=/private"
                                ),
                            ]
                        ],
                        "body": "ok",
                    },
                }
            ]
        }

        package = normalizer.normalize_document(transcript, hmac_key=HMAC_KEY)
        step = package["chains"][0]["steps"][0]
        query = step["request"]["query"]
        request_json = step["request"]["body"]["json"]
        set_cookie = step["response"]["headers"][0]["value"]
        rendered = normalizer.serialize_json(package).decode("utf-8")

        self.assertEqual(query[0]["value"], request_json["session"])
        self.assertEqual(query[1]["value"], request_json["secretKey"])
        self.assertTrue(query[2]["bare"])
        self.assertRegex(query[2]["name"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(query[3]["value"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(request_json["name"], r"^hmac-sha256:[0-9a-f]{64}$")
        self.assertRegex(
            request_json["billingAddress"], r"^hmac-sha256:[0-9a-f]{64}$"
        )
        self.assertIn("sid=hmac-sha256:", set_cookie)
        self.assertIn("prefs=hmac-sha256:", set_cookie)
        self.assertIn("Expires=Wed, 09 Jun 2027 10:18:14 GMT", set_cookie)
        self.assertNotIn("session=abc", step["request"]["url"])
        self.assertNotIn("secretKey=k9", step["request"]["url"])
        self.assertNotIn("opaque-bare", step["request"]["url"])
        self.assertNotIn("=anonymous", step["request"]["url"])
        self.assertNotIn("short-session", set_cookie)
        self.assertNotIn("prefs=tiny", set_cookie)
        for secret in (
            "Private Person",
            "1 Private Street",
            "short-session",
        ):
            self.assertNotIn(secret, rendered)

    def test_raw_hashes_require_explicit_local_opt_in(self) -> None:
        default_package = self.normalize_har()
        local_package = self.normalize_har(include_raw_hashes=True)
        default_body = default_package["chains"][0]["steps"][0]["request"]["body"]
        local_body = local_package["chains"][0]["steps"][0]["request"]["body"]

        self.assertNotIn("sha256", default_package["source"])
        self.assertNotIn("sha256", default_body)
        self.assertIn("sha256", local_package["source"])
        self.assertIn("sha256", local_body)
        self.assertTrue(local_package["redaction"]["raw_hashes_included"])
        with self.assertRaisesRegex(
            normalizer.EvidenceError, "requires include_raw_hashes=True"
        ):
            normalizer.normalize_document(
                sample_har(),
                hmac_key=HMAC_KEY,
                source_sha256="0" * 64,
            )

    def test_cli_writes_public_proof_manifest_without_raw_source_hash(self) -> None:
        source_bytes = json.dumps(sample_har(), separators=(",", ":")).encode("utf-8")
        script = SCRIPTS_DIR / "evidence_normalizer.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "capture.har"
            output_path = root / "evidence.json"
            manifest_path = root / "proof_manifest.json"
            source_path.write_bytes(source_bytes)

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    str(source_path),
                    str(output_path),
                    "--hmac-key",
                    HMAC_KEY.decode("ascii"),
                    "--proof-manifest",
                    str(manifest_path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn(
                "evidence_package_path=%s" % output_path.resolve(), result.stdout
            )
            self.assertIn(
                "proof_manifest_path=%s" % manifest_path.resolve(), result.stdout
            )
            self.assertEqual(
                manifest["source"]["hmac_sha256"],
                normalizer.Redactor(HMAC_KEY).digest(source_bytes),
            )
            self.assertNotIn("sha256", manifest["source"])
            self.assertEqual(
                manifest["evidence_package"]["sha256"],
                hashlib.sha256(output_path.read_bytes()).hexdigest(),
            )
            self.assertIn(
                "proof_manifest_sha256=%s"
                % hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                result.stdout,
            )
            self.assertNotIn("secret_values_included", manifest)
            self.assertTrue(manifest["redaction"]["publication_review_required"])
            self.assertFalse(manifest["redaction"]["raw_hashes_included"])
            manifest_text = manifest_path.read_text(encoding="utf-8")
            self.assertNotIn(str(source_path), manifest_text)
            self.assertNotIn(HMAC_KEY.decode("ascii"), manifest_text)

    def test_cli_rejects_oversized_capture_before_writing(self) -> None:
        script = SCRIPTS_DIR / "evidence_normalizer.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "capture.json"
            output_path = root / "evidence.json"
            source_path.write_bytes(b'{"steps":[]}')

            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(script),
                    str(source_path),
                    str(output_path),
                    "--hmac-key",
                    "test-key",
                    "--max-input-bytes",
                    "3",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("capture input exceeds 3 bytes", result.stderr)
            self.assertFalse(output_path.exists())

    def test_normalize_bytes_rejects_excessive_json_depth(self) -> None:
        source = ("[" * (normalizer.MAX_JSON_DEPTH + 1) + "0" + "]" * (
            normalizer.MAX_JSON_DEPTH + 1
        )).encode("ascii")

        with self.assertRaisesRegex(normalizer.EvidenceError, "nesting exceeds"):
            normalizer.normalize_bytes(source, hmac_key=HMAC_KEY)

    def test_atomic_artifact_failure_preserves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "evidence.json"
            target.write_bytes(b"original\n")

            with mock.patch.object(normalizer.os, "replace", side_effect=OSError("fail")):
                with self.assertRaisesRegex(
                    normalizer.EvidenceError, "cannot write evidence artifact"
                ):
                    normalizer._write_artifact(target, b"replacement\n")

            self.assertEqual(target.read_bytes(), b"original\n")
            self.assertEqual(list(target.parent.glob(".evidence.json.*.tmp")), [])

    def test_cli_self_test(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "evidence_normalizer.py"),
                "--self-test",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("self_test=PASS", result.stdout)

    def test_cli_help_states_publication_boundary(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "evidence_normalizer.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Publication review remains required", result.stdout)
        self.assertIn("evidence proof-manifest v2", result.stdout)
        self.assertIn("do not use for a public package", result.stdout)


if __name__ == "__main__":
    unittest.main()
