from __future__ import annotations

import os
import subprocess
import sys
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from urllib import error


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import scaffold_reverse_project as scaffold_module  # noqa: E402


def load_generated_client(project: Path) -> types.ModuleType:
    module = types.ModuleType("generated_collector_client")
    source = project.joinpath("collector", "client.py").read_text(encoding="utf-8")
    exec(compile(source, "collector/client.py", "exec"), module.__dict__)
    return module


class ScaffoldPathSafetyTests(unittest.TestCase):
    def make_symlink(self, link: Path, target: Path, *, directory: bool = False) -> None:
        try:
            os.symlink(target, link, target_is_directory=directory)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"filesystem symlinks unavailable: {exc}")

    def test_rejects_linked_file_with_and_without_force(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "projects"
            project = root / "sample"
            target = base / "outside-client.py"
            target.write_text("outside-original\n", encoding="utf-8")
            (project / "collector").mkdir(parents=True)
            self.make_symlink(project / "collector" / "client.py", target)

            for force in (False, True):
                with self.subTest(force=force):
                    with self.assertRaises(scaffold_module.UnsafeProjectPathError):
                        scaffold_module.scaffold(root, "sample", "generic", force)
                    self.assertEqual(
                        target.read_text(encoding="utf-8"),
                        "outside-original\n",
                    )

    def test_rejects_linked_parent_directory(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "projects"
            project = root / "sample"
            outside = base / "outside-collector"
            outside.mkdir()
            project.mkdir(parents=True)
            self.make_symlink(project / "collector", outside, directory=True)

            with self.assertRaises(scaffold_module.UnsafeProjectPathError):
                scaffold_module.scaffold(root, "sample", "generic", True)
            self.assertEqual(list(outside.iterdir()), [])

    def test_write_file_rejects_parent_traversal(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "sample"
            project.mkdir()
            outside = project.parent / "outside.txt"

            with self.assertRaises(scaffold_module.UnsafeProjectPathError):
                scaffold_module.write_file(
                    project,
                    project / ".." / "outside.txt",
                    "must-not-write",
                    True,
                    scaffold_module.WriteStats(),
                )
            self.assertFalse(outside.exists())

    def test_force_rejects_hard_link_without_changing_other_name(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / "sample"
            project.mkdir()
            outside = base / "outside.txt"
            outside.write_text("outside-original\n", encoding="utf-8")
            linked = project / "client.py"
            try:
                os.link(outside, linked)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"filesystem hard links unavailable: {exc}")

            with self.assertRaises(scaffold_module.UnsafeProjectPathError):
                scaffold_module.write_file(
                    project,
                    linked,
                    "replacement",
                    True,
                    scaffold_module.WriteStats(),
                )

            self.assertEqual(outside.read_text(encoding="utf-8"), "outside-original\n")
            self.assertEqual(linked.read_text(encoding="utf-8"), "outside-original\n")

    def test_failed_atomic_replace_preserves_existing_file_and_cleans_temp(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory) / "sample"
            project.mkdir()
            target = project / "client.py"
            target.write_text("original\n", encoding="utf-8")

            with mock.patch.object(
                scaffold_module.os,
                "replace",
                side_effect=OSError("simulated replace failure"),
            ):
                with self.assertRaises(OSError):
                    scaffold_module.write_file(
                        project,
                        target,
                        "replacement",
                        True,
                        scaffold_module.WriteStats(),
                    )

            self.assertEqual(target.read_text(encoding="utf-8"), "original\n")
            self.assertEqual(list(project.glob(".client.py.*.tmp")), [])


class GeneratedClientTests(unittest.TestCase):
    def make_client_module(self, directory: str) -> types.ModuleType:
        project, _ = scaffold_module.scaffold(
            Path(directory),
            "sample",
            "generic",
            False,
        )
        return load_generated_client(project)

    def test_seed_cookie_is_replaced_by_server_rotation(self) -> None:
        seen_cookies: list[str] = []

        class CookieHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                seen_cookies.append(self.headers.get("Cookie", ""))
                self.send_response(200)
                if len(seen_cookies) == 1:
                    self.send_header("Set-Cookie", "sid=new; Path=/")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, format: str, *args: object) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), CookieHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as directory:
                client_module = self.make_client_module(directory)
                base_url = f"http://127.0.0.1:{server.server_port}"
                client = client_module.ProtocolClient(
                    default_headers={"Cookie": "sid=static"}
                )
                client.seed_cookies({"sid": "old"}, url=base_url)

                self.assertFalse(
                    any(key.lower() == "cookie" for key in client.default_headers)
                )
                client.request_bytes(f"{base_url}/rotate")
                client.request_bytes(f"{base_url}/next")

                self.assertEqual(seen_cookies, ["sid=old", "sid=new"])
                self.assertEqual(client.cookies_as_dict(), {"sid": "new"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_seed_cookie_supports_single_label_hosts(self) -> None:
        with TemporaryDirectory() as directory:
            client_module = self.make_client_module(directory)
            client = client_module.ProtocolClient()
            client.seed_cookies({"sid": "old"}, url="http://localhost/")
            probe = client_module.request.Request("http://localhost/next")

            client.cookie_jar.add_cookie_header(probe)

            self.assertEqual(probe.get_header("Cookie"), "sid=old")

    def test_http_error_is_redacted_and_body_read_is_bounded(self) -> None:
        class TrackedBody:
            def __init__(self) -> None:
                self.read_sizes: list[int] = []
                self.closed = False

            def read(self, size: int = -1) -> bytes:
                self.read_sizes.append(size)
                return b"BODY_SECRET"

            def close(self) -> None:
                self.closed = True

        class FailingOpener:
            def __init__(self, failure: error.HTTPError) -> None:
                self.failure = failure

            def open(self, request: object, timeout: float) -> object:
                raise self.failure

        with TemporaryDirectory() as directory:
            client_module = self.make_client_module(directory)
            body = TrackedBody()
            url = (
                "https://user:USERINFO_SECRET@example.invalid/private"
                "?access_token=QUERY_SECRET#FRAGMENT_SECRET"
            )
            failure = error.HTTPError(url, 401, "Unauthorized", {}, body)
            client = client_module.ProtocolClient()
            client.opener = FailingOpener(failure)

            with self.assertRaises(RuntimeError) as raised:
                client.request_bytes(url)

            message = str(raised.exception)
            self.assertEqual(message, "HTTP 401 for https://example.invalid/private")
            self.assertNotIn("QUERY_SECRET", message)
            self.assertNotIn("FRAGMENT_SECRET", message)
            self.assertNotIn("USERINFO_SECRET", message)
            self.assertNotIn("BODY_SECRET", message)
            self.assertEqual(body.read_sizes, [client_module.ERROR_BODY_READ_LIMIT])
            self.assertLessEqual(body.read_sizes[0], 64 * 1024)
            self.assertTrue(body.closed)

    def test_url_error_does_not_echo_reason_or_query(self) -> None:
        class FailingOpener:
            def open(self, request: object, timeout: float) -> object:
                raise error.URLError("REASON_SECRET")

        with TemporaryDirectory() as directory:
            client_module = self.make_client_module(directory)
            client = client_module.ProtocolClient()
            client.opener = FailingOpener()

            with self.assertRaises(RuntimeError) as raised:
                client.request_bytes(
                    "https://example.invalid/path?token=QUERY_SECRET#FRAGMENT_SECRET"
                )

            self.assertEqual(
                str(raised.exception),
                "Network failure for https://example.invalid/path",
            )

    def test_invalid_url_is_redacted_before_request_construction(self) -> None:
        with TemporaryDirectory() as directory:
            client_module = self.make_client_module(directory)
            client = client_module.ProtocolClient()

            with self.assertRaises(RuntimeError) as raised:
                client.request_bytes(
                    "not-a-url?token=QUERY_SECRET#FRAGMENT_SECRET"
                )

            self.assertEqual(
                str(raised.exception),
                "Invalid request URL for not-a-url",
            )

    def test_gitignore_excludes_task_local_and_secret_bearing_paths(self) -> None:
        with TemporaryDirectory() as directory:
            project, _ = scaffold_module.scaffold(
                Path(directory),
                "sample",
                "generic",
                False,
            )
            patterns = set(
                project.joinpath(".gitignore").read_text(encoding="utf-8").splitlines()
            )

            for expected in (
                "/input/*",
                "!/input/.gitkeep",
                "/output/*",
                "!/output/.gitkeep",
                "/logs/*",
                "!/logs/.gitkeep",
                "/js_reverse_cache/",
                "/analysis/request_samples/*",
                "!/analysis/request_samples/README.md",
                "/analysis/runtime_vectors/*",
                "!/analysis/runtime_vectors/README.md",
                ".env",
                ".env.*",
                "/local_settings.py",
                "/settings.local.*",
                "/collector/local_settings.py",
                "/collector/settings.local.*",
            ):
                self.assertIn(expected, patterns)

    def test_missing_list_url_fails_without_overwriting_outputs(self) -> None:
        with TemporaryDirectory() as directory:
            project, _ = scaffold_module.scaffold(
                Path(directory),
                "sample",
                "generic",
                False,
            )
            json_output = project / "output" / "items.json"
            csv_output = project / "output" / "items.csv"
            json_output.write_text("json-sentinel\n", encoding="utf-8")
            csv_output.write_text("csv-sentinel\n", encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, str(project / "main.py")],
                cwd=project,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("list_url is empty", completed.stderr)
            self.assertEqual(json_output.read_text(encoding="utf-8"), "json-sentinel\n")
            self.assertEqual(csv_output.read_text(encoding="utf-8"), "csv-sentinel\n")


if __name__ == "__main__":
    unittest.main()
