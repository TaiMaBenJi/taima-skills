#!/usr/bin/env python3
"""Create reusable protocol-first reverse-collection projects."""

from __future__ import annotations

import argparse
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent


PROJECT_DIRS = [
    "analysis",
    "analysis/request_samples",
    "analysis/runtime_vectors",
    "collector",
    "input",
    "logs",
    "output",
    "tests",
]


@dataclass(slots=True)
class WriteStats:
    created: int = 0
    updated: int = 0


@dataclass(frozen=True, slots=True)
class ProfileSpec:
    name: str
    summary: str
    first_moves: tuple[str, ...]
    anti_patterns: tuple[str, ...]
    list_method: str
    list_body_kind: str
    response_body_kind: str
    transport_field: str
    sign_field: str
    timestamp_field: str
    page_param: str
    category_param: str
    use_compact_json: bool
    sign_before_timestamp: bool


PROFILE_SPECS: dict[str, ProfileSpec] = {
    "generic": ProfileSpec(
        name="generic",
        summary="Balanced scaffold for unknown protocol targets. Start broad, prove one stable replay, then specialize.",
        first_moves=(
            "Confirm the real wire endpoint before reading giant bundles.",
            "Freeze one known-good request and one response sample.",
            "Recover sign, cookie, decode, or transport state only after the wire path is proven.",
        ),
        anti_patterns=(
            "Do not assume every hard target is only a sign problem.",
            "Do not mix bootstrap, transport, decode, and storage logic in one file.",
        ),
        list_method="GET",
        list_body_kind="query",
        response_body_kind="json",
        transport_field="",
        sign_field="sign",
        timestamp_field="timestamp",
        page_param="page",
        category_param="category",
        use_compact_json=True,
        sign_before_timestamp=True,
    ),
    "public-envelope": ProfileSpec(
        name="public-envelope",
        summary="For public pages that still require entry-route cookies, bootstrap artifacts, and wrapped or encrypted business payloads.",
        first_moves=(
            "Hit the real public entry route once and freeze the seeded cookies.",
            "Freeze the bootstrap artifact such as a public key, config blob, nonce seed, or envelope metadata.",
            "Recover the exact payload build order: payload, compact JSON, sign, timestamp, encode or encrypt, wrapper field.",
        ),
        anti_patterns=(
            "Do not assume public list access means detail access is also public.",
            "Do not trust empty filters when the UI may be injecting category or mode state.",
        ),
        list_method="POST",
        list_body_kind="json",
        response_body_kind="json",
        transport_field="param",
        sign_field="sign",
        timestamp_field="timeStamp",
        page_param="pageIndex",
        category_param="category",
        use_compact_json=True,
        sign_before_timestamp=True,
    ),
    "structured-transport": ProfileSpec(
        name="structured-transport",
        summary="For GraphQL, WebSocket, protobuf, msgpack, or nested envelope contracts where transport shape is the real protocol.",
        first_moves=(
            "Freeze one known-good envelope with all metadata intact.",
            "Separate transport fields from business fields before rewriting anything.",
            "Document auth, sequencing, operation names, and heartbeat or cursor rules explicitly.",
        ),
        anti_patterns=(
            "Do not flatten envelope metadata away just because the business payload looks simple.",
            "Do not treat channel names, frame types, or persisted-query hashes as optional noise.",
        ),
        list_method="POST",
        list_body_kind="json",
        response_body_kind="json",
        transport_field="",
        sign_field="sign",
        timestamp_field="timestamp",
        page_param="page",
        category_param="channel",
        use_compact_json=False,
        sign_before_timestamp=False,
    ),
    "response-decode": ProfileSpec(
        name="response-decode",
        summary="For targets where HTTP replay is easy but the payload stays unreadable until a local decode chain is rebuilt.",
        first_moves=(
            "Freeze the raw payload before tracing any decoder.",
            "Find the first consumer of the raw payload rather than guessing from helper names.",
            "Rebuild the decode order exactly and prove it against a captured sample.",
        ),
        anti_patterns=(
            "Do not optimize parsing before the raw payload is frozen.",
            "Do not mark success when replay works but the local decode chain is still missing.",
        ),
        list_method="GET",
        list_body_kind="query",
        response_body_kind="bytes",
        transport_field="",
        sign_field="sign",
        timestamp_field="timestamp",
        page_param="page",
        category_param="",
        use_compact_json=True,
        sign_before_timestamp=True,
    ),
}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "reverse-job"


def normalize_content(content: str) -> str:
    text = dedent(content).lstrip("\n").rstrip()
    return f"{text}\n"


def replace_tokens(template: str, mapping: dict[str, str]) -> str:
    rendered = template
    for key, value in mapping.items():
        rendered = rendered.replace(f"__{key}__", value)
    return rendered


class UnsafeProjectPathError(RuntimeError):
    """Raised before a scaffold write could traverse a filesystem link."""


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & reparse_flag
    )


def _reject_link_or_reparse(path: Path) -> None:
    if _is_link_or_reparse(path):
        raise UnsafeProjectPathError(
            f"Refusing scaffold path through a symlink or reparse point: {path}"
        )


def _reject_hard_link(path: Path) -> None:
    if not _lexists(path):
        return
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise UnsafeProjectPathError(f"Cannot inspect scaffold path: {path}") from exc
    if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink > 1:
        raise UnsafeProjectPathError(
            f"Refusing scaffold path backed by a hard-linked file: {path}"
        )


def _require_within(project_root: Path, target: Path) -> None:
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise UnsafeProjectPathError(
            f"Refusing scaffold path outside project root: {target}"
        ) from exc


def _validate_existing_components(start: Path, target: Path) -> None:
    start = _absolute_path(start)
    target = _absolute_path(target)
    _require_within(start, target)

    current = start
    if _lexists(current):
        _reject_link_or_reparse(current)
    for part in target.relative_to(start).parts:
        current /= part
        if _lexists(current):
            _reject_link_or_reparse(current)


def _validate_resolved_target(project_root: Path, target: Path) -> None:
    project_root = _absolute_path(project_root)
    target = _absolute_path(target)
    _require_within(project_root, target)
    _validate_existing_components(project_root, target)

    resolved_root = project_root.resolve(strict=True)
    existing = target
    while not _lexists(existing):
        existing = existing.parent
    resolved_existing = existing.resolve(strict=True)
    _require_within(resolved_root, resolved_existing)


def _mkdir_without_links(path: Path) -> None:
    path = _absolute_path(path)
    anchor = Path(path.anchor)
    current = anchor
    for part in path.relative_to(anchor).parts:
        current /= part
        if _lexists(current):
            _reject_link_or_reparse(current)
            if not current.is_dir():
                raise NotADirectoryError(current)
            continue
        current.mkdir()
        _reject_link_or_reparse(current)


def _mkdir_in_project(project_root: Path, path: Path) -> None:
    project_root = _absolute_path(project_root)
    path = _absolute_path(path)
    _require_within(project_root, path)
    _validate_existing_components(project_root, path)

    current = project_root
    for part in path.relative_to(project_root).parts:
        current /= part
        if _lexists(current):
            _reject_link_or_reparse(current)
            if not current.is_dir():
                raise NotADirectoryError(current)
        else:
            current.mkdir()
            _reject_link_or_reparse(current)
        _validate_resolved_target(project_root, current)


def write_file(
    project_root: Path,
    path: Path,
    content: str,
    force: bool,
    stats: WriteStats,
) -> None:
    project_root = _absolute_path(project_root)
    path = _absolute_path(path)
    _validate_resolved_target(project_root, path)
    _mkdir_in_project(project_root, path.parent)
    _validate_resolved_target(project_root, path)

    exists = _lexists(path)
    if exists and not force:
        return
    if exists:
        _reject_hard_link(path)

    file_descriptor: int | None = None
    temporary_path: Path | None = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        _validate_resolved_target(project_root, temporary_path)
        _reject_link_or_reparse(temporary_path)
        _reject_hard_link(temporary_path)
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            file_descriptor = None
            handle.write(normalize_content(content))
            handle.flush()
            os.fsync(handle.fileno())

        _validate_resolved_target(project_root, path.parent)
        _validate_resolved_target(project_root, path)
        if _lexists(path):
            _reject_link_or_reparse(path)
            _reject_hard_link(path)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    _validate_resolved_target(project_root, path)
    if exists:
        stats.updated += 1
    else:
        stats.created += 1


def profile_moves(spec: ProfileSpec) -> str:
    return "\n".join(f"- {line}" for line in spec.first_moves)


def profile_anti_patterns(spec: ProfileSpec) -> str:
    return "\n".join(f"- {line}" for line in spec.anti_patterns)


def build_mapping(slug: str, spec: ProfileSpec) -> dict[str, str]:
    return {
        "SLUG": slug,
        "PROFILE": spec.name,
        "PROFILE_SUMMARY": spec.summary,
        "PROFILE_FIRST_MOVES": profile_moves(spec),
        "PROFILE_ANTI_PATTERNS": profile_anti_patterns(spec),
        "LIST_METHOD": spec.list_method,
        "LIST_BODY_KIND": spec.list_body_kind,
        "RESPONSE_BODY_KIND": spec.response_body_kind,
        "TRANSPORT_FIELD": spec.transport_field,
        "SIGN_FIELD": spec.sign_field,
        "TIMESTAMP_FIELD": spec.timestamp_field,
        "PAGE_PARAM": spec.page_param,
        "CATEGORY_PARAM": spec.category_param,
        "USE_COMPACT_JSON": "True" if spec.use_compact_json else "False",
        "SIGN_BEFORE_TIMESTAMP": "True" if spec.sign_before_timestamp else "False",
    }


def analysis_templates() -> dict[str, str]:
    return {
        ".gitignore": """
            __pycache__/
            .pytest_cache/
            .venv/
            .env
            .env.*
            *.pyc
            *.pyo
            *.pyd
            *.log
            /input/*
            !/input/.gitkeep
            /output/*
            !/output/.gitkeep
            /logs/*
            !/logs/.gitkeep
            /js_reverse_cache/
            /analysis/request_samples/*
            !/analysis/request_samples/README.md
            /analysis/runtime_vectors/*
            !/analysis/runtime_vectors/README.md
            /local_settings.py
            /settings.local.*
            /collector/local_settings.py
            /collector/settings.local.*
        """,
        "pyproject.toml": """
            [tool.pytest.ini_options]
            pythonpath = ["."]
            testpaths = ["tests"]
        """,
        "analysis/key_logic.js": """
            // Put extracted signer, bootstrap, or decrypt logic here.
            // Keep original names when they help with diffing.
        """,
        "analysis/deobfuscated.js": """
            // Put beautified or deobfuscated JavaScript snapshots here.
            // Save one stable copy before each major edit.
        """,
        "analysis/notes.md": """
            # __SLUG__ analysis notes

            ## Target
            - Site:
            - Final page URL:
            - Data goal:
            - Active profile: __PROFILE__

            ## Real interfaces
            - Entry:
            - Bootstrap:
            - List:
            - Detail:
            - Submit:

            ## Protocol contract
            - Transport kind:
            - Request method:
            - Body kind:
            - Outer transport field:
            - Required headers:
            - Required cookies:
            - Required query or body fields:
            - Session rules:

            ## Dynamic state
            - sign:
            - token:
            - nonce:
            - timestamp:
            - rotating cookie:
            - bootstrap artifact:
            - decode key or glyph map:
            - page-specific exception:
            - permission boundary:

            ## Validation
            - Fixed-input browser outputs:
            - Fixed-input local outputs:
            - Fixed-sample decode outputs:
            - Replay status:
            - Remaining gaps:
        """,
        "analysis/profile_brief.md": """
            # Profile brief: __PROFILE__

            __PROFILE_SUMMARY__

            ## First moves
            __PROFILE_FIRST_MOVES__

            ## Anti-patterns
            __PROFILE_ANTI_PATTERNS__
        """,
        "analysis/bootstrap_contract.md": """
            # Bootstrap contract

            - Entry route:
            - Entry method:
            - Entry cookies seeded:
            - Bootstrap route:
            - Bootstrap method:
            - Bootstrap artifact type:
            - Artifact parse function:
            - Artifact reuse scope:
            - Bootstrap proof sample saved:
        """,
        "analysis/envelope_map.md": """
            # Envelope map

            ## Build order
            1. raw business payload
            2. exact serialization
            3. sign input
            4. sign field injection
            5. timestamp or nonce injection
            6. encode or encrypt step
            7. outer wrapper field

            ## Verified values
            - compact JSON sample:
            - sign input sample:
            - sign output sample:
            - timestamp precision:
            - wrapper field:
            - chunking rule:
        """,
        "analysis/permission_matrix.md": """
            # Permission matrix

            - Public entry:
            - Public list:
            - Public detail:
            - Logged-in list:
            - Logged-in detail:
            - Submit:
            - Same-session requirement:
            - Account-bound behavior:
        """,
        "analysis/fixed_inputs.md": """
            # Fixed inputs

            ## Helper vectors
            - Input:
            - Expected browser output:
            - Expected local output:

            ## Decode vectors
            - Raw payload sample:
            - Expected decoded sample:
            - Parser or decoder involved:

            ## Envelope vectors
            - Raw payload JSON:
            - Signed payload JSON:
            - Wrapped request body:
        """,
        "analysis/replay_checklist.md": """
            # Replay checklist

            - Confirm the real endpoint on the wire
            - Freeze one known-good request sample
            - Freeze the entry-route response and seeded cookies
            - Freeze the bootstrap artifact when public replay still needs it
            - Freeze helper vectors such as "abc" or a captured timestamp
            - Freeze one raw response sample when decode is involved
            - Rebuild dynamic state offline
            - Prove envelope build order exactly
            - Replay page 1 successfully at least twice
            - Verify pagination or cursor advance
            - Document list-versus-detail permission boundaries
            - Document account-bound or page-specific rules
        """,
        "analysis/request_samples/README.md": """
            Save redacted request and response samples here.

            Recommended files:
            - entry-response.html
            - bootstrap-response.txt
            - page1-request.txt
            - page1-response.json
            - detail-request.txt
            - detail-response.json
        """,
        "analysis/runtime_vectors/README.md": """
            Save narrow runtime proof artifacts here.

            Recommended files:
            - sign-vectors.md
            - decode-vectors.md
            - bootstrap-artifact.txt
            - envelope-build-order.md
        """,
        "input/.gitkeep": "",
        "logs/.gitkeep": "",
        "output/.gitkeep": "",
        "requirements.txt": """
            # The scaffold runs on the Python standard library by default.
            # Uncomment only what the target truly needs.
            # requests>=2.31.0
            # httpx>=0.27.0
            # brotli>=1.1.0
            # protobuf>=5.0.0
            # pycryptodome>=3.20.0
            # pytest>=8.0.0
        """,
        "main.py": """
            from collector.main import main


            if __name__ == "__main__":
                # PyCharm right-click entrypoint. Keep defaults here; do not require CLI flags.
                raise SystemExit(main())
            """,
        "js_reverse_cache/tasks/README.md": """
            # Task cache

            Put investigation artifacts under `js_reverse_cache/tasks/<task-id>/`:

            - `task.json`
            - `network.jsonl`
            - `runtime-evidence.jsonl`
            - `handoff.json`
            - `fixtures/`
            - `report.md`

            Do not store durable collector code here. Delivery proof stays in `analysis/proof_manifest.json`.
            Never commit raw cookies, tokens, or account secrets.
            """,
        "README.md": """
            # __SLUG__

            ## Goal
            - Site:
            - Final page URL:
            - Data scope:
            - Scaffold profile: __PROFILE__

            ## Profile summary
            __PROFILE_SUMMARY__

            ## Protocol checklist
            1. Confirm the real wire endpoint
            2. Freeze entry, bootstrap, request, and response proof artifacts
            3. Validate helper outputs on fixed inputs
            4. Prove envelope build order exactly
            5. Replay page 1 at least twice
            6. Scale pagination only after repeatability is proven
            7. Document list-versus-detail permissions when they differ

            ## Suggested file usage
            - `analysis/notes.md`: real endpoint, moving parts, and replay proof
            - `analysis/bootstrap_contract.md`: entry route, bootstrap endpoint, and artifact reuse rules
            - `analysis/envelope_map.md`: payload serialization, sign input, wrapper field, and encode order
            - `analysis/permission_matrix.md`: public, logged-in, detail, and submit boundaries
            - `collector/client.py`: HTTP transport and cookie handling
            - `collector/bootstrap.py`: entry and bootstrap replay plus artifact parsing
            - `collector/envelope.py`: compact JSON, sign order, timestamp injection, and wrapper building
            - `collector/sign.py`: signer and fixed-input self-checks
            - `collector/decode.py`: local decode or parser chain
            - `main.py`: PyCharm right-click entrypoint (no required CLI args)
- `collector/main.py`: protocol replay entry point
- `js_reverse_cache/tasks/`: investigation cache only

            ## Run
            ```bash
            python -m venv .venv
            .venv\\Scripts\\activate
            pip install -r requirements.txt
            python -m unittest discover
            python main.py
            python -m collector.main --pages 3
            ```

            ## Rule of thumb
            Keep the final collector pure protocol.
            If something looks browser-only, first identify the exact bootstrap, envelope, decode, or permission dependency.
        """,
    }


def collector_templates() -> dict[str, str]:
    return {
        "collector/__init__.py": "",
        "collector/settings.py": """
            from __future__ import annotations

            from dataclasses import dataclass, field


            @dataclass(slots=True)
            class Settings:
                profile_name: str = "__PROFILE__"
                base_url: str = ""
                entry_url: str = ""
                bootstrap_url: str = ""
                list_url: str = ""
                detail_url: str = ""
                entry_method: str = "GET"
                bootstrap_method: str = "GET"
                list_method: str = "__LIST_METHOD__"
                detail_method: str = "GET"
                list_body_kind: str = "__LIST_BODY_KIND__"
                response_body_kind: str = "__RESPONSE_BODY_KIND__"
                transport_field: str = "__TRANSPORT_FIELD__"
                sign_field: str = "__SIGN_FIELD__"
                timestamp_field: str = "__TIMESTAMP_FIELD__"
                page_param: str = "__PAGE_PARAM__"
                category_param: str = "__CATEGORY_PARAM__"
                category_value: str = ""
                use_compact_json: bool = __USE_COMPACT_JSON__
                sign_before_timestamp: bool = __SIGN_BEFORE_TIMESTAMP__
                sign_on_raw_payload: bool = True
                page_start: int = 1
                page_size: int = 20
                timeout: float = 20.0
                sleep_seconds: float = 0.2
                max_retries: int = 2
                output_json: str = "output/items.json"
                output_csv: str = "output/items.csv"
                base_headers: dict[str, str] = field(
                    default_factory=lambda: {
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/json, text/plain, */*",
                    }
                )
                entry_headers: dict[str, str] = field(default_factory=dict)
                bootstrap_headers: dict[str, str] = field(default_factory=dict)
                list_headers: dict[str, str] = field(default_factory=dict)
                detail_headers: dict[str, str] = field(default_factory=dict)
                cookies: dict[str, str] = field(default_factory=dict)
                base_payload: dict[str, object] = field(default_factory=dict)
        """,
        "collector/client.py": """
            from __future__ import annotations

            import json
            from http.cookiejar import Cookie, CookieJar
            from typing import Any
            from urllib import error, parse, request


            ERROR_BODY_READ_LIMIT = 64 * 1024


            def _safe_url_for_error(url: str) -> str:
                try:
                    parts = parse.urlsplit(url)
                except ValueError:
                    return "<invalid-url>"
                hostname = parts.hostname or ""
                if ":" in hostname and not hostname.startswith("["):
                    hostname = f"[{hostname}]"
                try:
                    port = parts.port
                except ValueError:
                    port = None
                netloc = hostname if port is None else f"{hostname}:{port}"
                return parse.urlunsplit((parts.scheme, netloc, parts.path, "", ""))


            def _cookie_domain_for_url(url: str) -> str:
                hostname = parse.urlsplit(url).hostname or ""
                if hostname and "." not in hostname and ":" not in hostname:
                    return f"{hostname}.local"
                return hostname


            class ProtocolClient:
                def __init__(self, default_headers: dict[str, str] | None = None) -> None:
                    self.cookie_jar = CookieJar()
                    self.opener = request.build_opener(request.HTTPCookieProcessor(self.cookie_jar))
                    self.default_headers = dict(default_headers or {})

                def seed_cookies(self, cookies: dict[str, str], *, url: str = "") -> None:
                    self.default_headers = {
                        key: value
                        for key, value in self.default_headers.items()
                        if key.lower() != "cookie"
                    }
                    hostname = _cookie_domain_for_url(url)
                    names = set(cookies)
                    for cookie in list(self.cookie_jar):
                        if cookie.name in names:
                            self.cookie_jar.clear(cookie.domain, cookie.path, cookie.name)
                    for name, value in cookies.items():
                        self.cookie_jar.set_cookie(
                            Cookie(
                                version=0,
                                name=name,
                                value=str(value),
                                port=None,
                                port_specified=False,
                                domain=hostname,
                                domain_specified=False,
                                domain_initial_dot=False,
                                path="/",
                                path_specified=True,
                                secure=False,
                                expires=None,
                                discard=True,
                                comment=None,
                                comment_url=None,
                                rest={},
                                rfc2109=False,
                            )
                        )

                def cookies_as_dict(self) -> dict[str, str]:
                    return {cookie.name: cookie.value for cookie in self.cookie_jar}

                def serialize_json_body(self, json_body: Any, *, compact_json: bool = True) -> bytes:
                    if compact_json:
                        return json.dumps(json_body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    return json.dumps(json_body, ensure_ascii=False).encode("utf-8")

                def request_bytes(
                    self,
                    url: str,
                    *,
                    method: str = "GET",
                    params: dict[str, object] | None = None,
                    headers: dict[str, str] | None = None,
                    json_body: Any | None = None,
                    form_body: dict[str, object] | None = None,
                    raw_body: str | bytes | None = None,
                    compact_json: bool = True,
                    timeout: float = 20.0,
                ) -> bytes:
                    final_url = url
                    if params:
                        query = parse.urlencode(params, doseq=True)
                        separator = "&" if "?" in url else "?"
                        final_url = f"{url}{separator}{query}"

                    merged_headers = dict(self.default_headers)
                    if headers:
                        merged_headers.update(headers)

                    data: bytes | None = None
                    if json_body is not None:
                        data = self.serialize_json_body(json_body, compact_json=compact_json)
                        merged_headers.setdefault("Content-Type", "application/json")
                    elif form_body is not None:
                        data = parse.urlencode(form_body, doseq=True).encode("utf-8")
                        merged_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
                    elif raw_body is not None:
                        data = raw_body if isinstance(raw_body, bytes) else raw_body.encode("utf-8")

                    try:
                        http_request = request.Request(
                            final_url,
                            data=data,
                            headers=merged_headers,
                            method=method.upper(),
                        )
                        with self.opener.open(http_request, timeout=timeout) as response:
                            return response.read()
                    except error.HTTPError as exc:
                        try:
                            exc.read(ERROR_BODY_READ_LIMIT)
                        except Exception:
                            pass
                        try:
                            exc.close()
                        except Exception:
                            pass
                        safe_url = _safe_url_for_error(final_url)
                        raise RuntimeError(f"HTTP {exc.code} for {safe_url}") from None
                    except error.URLError:
                        safe_url = _safe_url_for_error(final_url)
                        raise RuntimeError(f"Network failure for {safe_url}") from None
                    except ValueError:
                        safe_url = _safe_url_for_error(final_url)
                        raise RuntimeError(f"Invalid request URL for {safe_url}") from None

                def request_text(self, url: str, **kwargs: Any) -> str:
                    return self.request_bytes(url, **kwargs).decode("utf-8")

                def request_json(self, url: str, **kwargs: Any) -> Any:
                    return json.loads(self.request_text(url, **kwargs))
        """,
        "collector/crypto_utils.py": """
            from __future__ import annotations

            import base64
            import hashlib


            def chunk_bytes(data: bytes, size: int) -> list[bytes]:
                return [data[index : index + size] for index in range(0, len(data), size)]


            def md5_hex(text: str) -> str:
                return hashlib.md5(text.encode("utf-8")).hexdigest()


            def sha256_hex(text: str) -> str:
                return hashlib.sha256(text.encode("utf-8")).hexdigest()


            def b64encode_text(text: str) -> str:
                return base64.b64encode(text.encode("utf-8")).decode("ascii")
        """,
        "collector/bootstrap.py": """
            from __future__ import annotations

            from typing import Any

            from collector.client import ProtocolClient
            from collector.settings import Settings


            def parse_bootstrap_artifact(raw_text: str, settings: Settings) -> dict[str, Any]:
                \"\"\"Parse public keys, config blobs, or nonce seeds here.\"\"\"
                _ = settings
                return {"bootstrap_raw": raw_text}


            def bootstrap_session(client: ProtocolClient, settings: Settings) -> dict[str, Any]:
                state: dict[str, Any] = {}

                if settings.entry_url:
                    client.request_text(
                        settings.entry_url,
                        method=settings.entry_method,
                        headers=settings.entry_headers,
                        timeout=settings.timeout,
                    )

                if settings.bootstrap_url:
                    bootstrap_text = client.request_text(
                        settings.bootstrap_url,
                        method=settings.bootstrap_method,
                        headers=settings.bootstrap_headers,
                        timeout=settings.timeout,
                    )
                    state.update(parse_bootstrap_artifact(bootstrap_text, settings))

                state["cookies"] = client.cookies_as_dict()
                return state
        """,
        "collector/sign.py": """
            from __future__ import annotations

            from typing import Any


            def run_self_check() -> None:
                \"\"\"Add fixed-input assertions here after the signer is recovered.\"\"\"


            def build_sign(
                sign_input: str,
                payload: dict[str, Any],
                *,
                bootstrap_state: dict[str, Any] | None = None,
            ) -> str:
                \"\"\"Rebuild the target sign here after fixed-input validation.\"\"\"
                _ = (sign_input, payload, bootstrap_state)
                return ""
        """,
        "collector/envelope.py": """
            from __future__ import annotations

            import json
            import time
            from typing import Any

            from collector.settings import Settings
            from collector.sign import build_sign


            def compact_json(payload: dict[str, Any]) -> str:
                return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


            def run_envelope_self_check() -> None:
                \"\"\"Add envelope-order assertions here when the request shape is recovered.\"\"\"


            def build_sign_input(payload: dict[str, Any], *, use_compact_json: bool) -> str:
                if use_compact_json:
                    return compact_json(payload)
                return json.dumps(payload, ensure_ascii=False)


            def encode_payload(
                serialized_payload: str,
                *,
                bootstrap_state: dict[str, Any] | None = None,
            ) -> str:
                \"\"\"Apply Base64, RSA, custom alphabets, or outer encryption here.\"\"\"
                _ = bootstrap_state
                return serialized_payload


            def inject_runtime_fields(
                payload: dict[str, Any],
                settings: Settings,
                *,
                bootstrap_state: dict[str, Any] | None = None,
            ) -> dict[str, Any]:
                runtime_payload = dict(payload)
                sign_source = dict(payload) if settings.sign_on_raw_payload else runtime_payload

                if settings.sign_field and settings.sign_before_timestamp:
                    runtime_payload[settings.sign_field] = build_sign(
                        build_sign_input(sign_source, use_compact_json=settings.use_compact_json),
                        payload,
                        bootstrap_state=bootstrap_state,
                    )

                if settings.timestamp_field:
                    runtime_payload[settings.timestamp_field] = int(time.time() * 1000)

                if settings.sign_field and not settings.sign_before_timestamp:
                    sign_source = dict(payload) if settings.sign_on_raw_payload else runtime_payload
                    runtime_payload[settings.sign_field] = build_sign(
                        build_sign_input(sign_source, use_compact_json=settings.use_compact_json),
                        payload,
                        bootstrap_state=bootstrap_state,
                    )

                return runtime_payload


            def build_transport_body(
                payload: dict[str, Any],
                settings: Settings,
                *,
                bootstrap_state: dict[str, Any] | None = None,
            ) -> dict[str, Any]:
                runtime_payload = inject_runtime_fields(
                    payload,
                    settings,
                    bootstrap_state=bootstrap_state,
                )
                if not settings.transport_field:
                    return runtime_payload

                serialized = build_sign_input(
                    runtime_payload,
                    use_compact_json=settings.use_compact_json,
                )
                encoded = encode_payload(serialized, bootstrap_state=bootstrap_state)
                return {settings.transport_field: encoded}
        """,
        "collector/decode.py": """
            from __future__ import annotations

            from typing import Any


            def run_decode_self_check() -> None:
                \"\"\"Add fixed-sample decode assertions here when decode is part of the contract.\"\"\"


            def decode_payload(payload: Any) -> Any:
                \"\"\"Decode encrypted, compressed, protobuf, or glyph-mapped payloads here.\"\"\"
                return payload
        """,
        "collector/extract.py": """
            from __future__ import annotations

            from typing import Any


            def _dict_items(value: Any) -> list[dict[str, Any]]:
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
                return []


            def extract_items(payload: Any) -> list[dict[str, Any]]:
                if isinstance(payload, list):
                    return _dict_items(payload)
                if isinstance(payload, dict):
                    for key in ("list", "items", "rows", "records", "result", "data"):
                        items = _dict_items(payload.get(key))
                        if items:
                            return items
                        nested = payload.get(key)
                        if isinstance(nested, dict):
                            child = extract_items(nested)
                            if child:
                                return child
                return []
        """,
        "collector/pipeline.py": """
            from __future__ import annotations

            import json


            def stable_key(item: dict) -> str:
                for candidate in ("id", "bm", "uuid", "code"):
                    if candidate in item:
                        return f"{candidate}:{item[candidate]}"
                return json.dumps(item, ensure_ascii=False, sort_keys=True)


            def normalize_items(items: list[dict]) -> list[dict]:
                seen: set[str] = set()
                result: list[dict] = []
                for item in items:
                    key = stable_key(item)
                    if key in seen:
                        continue
                    seen.add(key)
                    result.append(item)
                return result
        """,
        "collector/storage.py": """
            from __future__ import annotations

            import csv
            import json
            from pathlib import Path


            def save_outputs(items: list[dict], json_path: str, csv_path: str) -> None:
                json_file = Path(json_path)
                csv_file = Path(csv_path)
                json_file.parent.mkdir(parents=True, exist_ok=True)
                csv_file.parent.mkdir(parents=True, exist_ok=True)
                json_file.write_text(
                    json.dumps(items, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                fieldnames = sorted({key for item in items for key in item}) if items else []
                with csv_file.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    if fieldnames:
                        writer.writeheader()
                        for item in items:
                            writer.writerow(item)
        """,
        "collector/main.py": """
            from __future__ import annotations

            import argparse
            import sys
            import time
            from typing import Any

            from collector.bootstrap import bootstrap_session
            from collector.client import ProtocolClient
            from collector.decode import decode_payload, run_decode_self_check
            from collector.envelope import build_transport_body, run_envelope_self_check
            from collector.extract import extract_items
            from collector.pipeline import normalize_items
            from collector.settings import Settings
            from collector.sign import run_self_check
            from collector.storage import save_outputs


            def build_business_payload(settings: Settings, page_index: int) -> dict[str, Any]:
                payload = dict(settings.base_payload)
                if settings.category_param and settings.category_value:
                    payload.setdefault(settings.category_param, settings.category_value)
                if settings.page_param:
                    payload[settings.page_param] = page_index
                return payload


            def perform_list_request(
                client: ProtocolClient,
                settings: Settings,
                body: dict[str, Any],
            ) -> Any:
                kwargs: dict[str, Any] = {
                    "method": settings.list_method,
                    "headers": settings.list_headers,
                    "timeout": settings.timeout,
                }
                if settings.list_body_kind == "json":
                    kwargs["json_body"] = body
                    kwargs["compact_json"] = settings.use_compact_json
                elif settings.list_body_kind == "form":
                    kwargs["form_body"] = body
                elif settings.list_body_kind == "query":
                    kwargs["params"] = body
                else:
                    raise RuntimeError(f"Unsupported list_body_kind: {settings.list_body_kind}")
                if settings.response_body_kind == "json":
                    return client.request_json(settings.list_url, **kwargs)
                if settings.response_body_kind == "text":
                    return client.request_text(settings.list_url, **kwargs)
                if settings.response_body_kind == "bytes":
                    return client.request_bytes(settings.list_url, **kwargs)
                raise RuntimeError(f"Unsupported response_body_kind: {settings.response_body_kind}")


            def fetch_page(
                client: ProtocolClient,
                settings: Settings,
                page_index: int,
                *,
                bootstrap_state: dict[str, Any],
            ) -> list[dict[str, Any]]:
                business_payload = build_business_payload(settings, page_index)
                transport_body = build_transport_body(
                    business_payload,
                    settings,
                    bootstrap_state=bootstrap_state,
                )
                response_payload = perform_list_request(client, settings, transport_body)
                decoded_payload = decode_payload(response_payload)
                return extract_items(decoded_payload)


            def collect_items(settings: Settings, pages: int) -> list[dict[str, Any]]:
                if not settings.list_url:
                    raise RuntimeError("list_url is empty; update Settings before live replay")
                client = ProtocolClient(default_headers=settings.base_headers)
                seed_url = (
                    settings.base_url
                    or settings.entry_url
                    or settings.bootstrap_url
                    or settings.list_url
                )
                client.seed_cookies(settings.cookies, url=seed_url)

                run_self_check()
                run_envelope_self_check()
                run_decode_self_check()

                bootstrap_state = bootstrap_session(client, settings)
                items: list[dict[str, Any]] = []
                start = settings.page_start

                for page_index in range(start, start + pages):
                    items.extend(
                        fetch_page(
                            client,
                            settings,
                            page_index,
                            bootstrap_state=bootstrap_state,
                        )
                    )
                    if settings.sleep_seconds:
                        time.sleep(settings.sleep_seconds)

                return normalize_items(items)


            def build_parser() -> argparse.ArgumentParser:
                parser = argparse.ArgumentParser(description="Run the scaffolded protocol collector.")
                parser.add_argument("--pages", type=int, default=1, help="Number of pages to collect.")
                parser.add_argument("--json", default="", help="Optional JSON output override.")
                parser.add_argument("--csv", default="", help="Optional CSV output override.")
                return parser


            def main() -> int:
                args = build_parser().parse_args()
                settings = Settings()
                if args.json:
                    settings.output_json = args.json
                if args.csv:
                    settings.output_csv = args.csv
                if not settings.list_url:
                    print(
                        "error: list_url is empty; update Settings before live replay",
                        file=sys.stderr,
                    )
                    return 2
                items = collect_items(settings, pages=args.pages)
                save_outputs(items, settings.output_json, settings.output_csv)
                print(f"saved {len(items)} items")
                return 0


            if __name__ == "__main__":
                raise SystemExit(main())
        """,
    }


def test_templates() -> dict[str, str]:
    return {
        "tests/__init__.py": "",
        "tests/test_client.py": """
            import unittest

            from collector.client import ProtocolClient


            class ClientTests(unittest.TestCase):
                def test_serialize_json_body_compact(self) -> None:
                    client = ProtocolClient()
                    body = client.serialize_json_body({"a": 1, "b": 2}, compact_json=True)
                    self.assertEqual(body.decode("utf-8"), '{"a":1,"b":2}')

                def test_serialize_json_body_non_compact(self) -> None:
                    client = ProtocolClient()
                    body = client.serialize_json_body({"a": 1, "b": 2}, compact_json=False)
                    self.assertEqual(body.decode("utf-8"), '{"a": 1, "b": 2}')
        """,
        "tests/test_pipeline.py": """
            import unittest

            from collector.pipeline import normalize_items, stable_key


            class PipelineTests(unittest.TestCase):
                def test_stable_key_prefers_known_identifiers(self) -> None:
                    self.assertEqual(stable_key({"bm": "123", "name": "x"}), "bm:123")

                def test_normalize_items_dedupes(self) -> None:
                    items = [{"id": 1}, {"id": 1}, {"id": 2}]
                    self.assertEqual(len(normalize_items(items)), 2)
        """,
        "tests/test_envelope.py": """
            import json
            import unittest

            from collector.envelope import build_transport_body, compact_json
            from collector.settings import Settings


            class EnvelopeTests(unittest.TestCase):
                def test_compact_json_has_no_spaces(self) -> None:
                    self.assertEqual(compact_json({"a": 1, "b": 2}), '{"a":1,"b":2}')

                def test_transport_field_wraps_payload(self) -> None:
                    settings = Settings(transport_field="param", sign_field="", timestamp_field="")
                    body = build_transport_body({"pageIndex": 1}, settings)
                    expected = (
                        compact_json({"pageIndex": 1})
                        if settings.use_compact_json
                        else json.dumps({"pageIndex": 1}, ensure_ascii=False)
                    )
                    self.assertEqual(body, {"param": expected})
        """,
        "tests/test_extract.py": """
            import unittest

            from collector.extract import extract_items


            class ExtractTests(unittest.TestCase):
                def test_extract_items_handles_nested_dict_payloads(self) -> None:
                    payload = {"data": {"list": [{"id": 1}, {"id": 2}]}}
                    self.assertEqual(len(extract_items(payload)), 2)
        """,
        "tests/test_sign.py": """
            import unittest

            from collector.sign import build_sign, run_self_check


            class SignTests(unittest.TestCase):
                def test_run_self_check_is_callable(self) -> None:
                    run_self_check()

                def test_build_sign_defaults_to_empty_string(self) -> None:
                    self.assertEqual(build_sign("x", {"page": 1}), "")
        """,
        "tests/test_decode.py": """
            import unittest

            from collector.decode import decode_payload, run_decode_self_check


            class DecodeTests(unittest.TestCase):
                def test_run_decode_self_check_is_callable(self) -> None:
                    run_decode_self_check()

                def test_decode_payload_passthrough(self) -> None:
                    payload = {"ok": True}
                    self.assertEqual(decode_payload(payload), payload)
        """,
    }


def build_templates(slug: str, spec: ProfileSpec) -> dict[str, str]:
    mapping = build_mapping(slug, spec)
    templates = {}
    templates.update(analysis_templates())
    templates.update(collector_templates())
    templates.update(test_templates())
    return {path: replace_tokens(content, mapping) for path, content in templates.items()}


def scaffold(root: Path, name: str, profile: str, force: bool) -> tuple[Path, WriteStats]:
    slug = slugify(name)
    root = _absolute_path(root)
    _mkdir_without_links(root)
    project = root / slug
    if _lexists(project):
        _reject_link_or_reparse(project)
        if not project.is_dir():
            raise NotADirectoryError(project)
    else:
        project.mkdir()
    _reject_link_or_reparse(project)
    _validate_resolved_target(project, project)

    stats = WriteStats()
    spec = PROFILE_SPECS[profile]
    templates = build_templates(slug, spec)

    planned_paths = [project / rel for rel in PROJECT_DIRS]
    planned_paths.extend(project / relative_path for relative_path in templates)
    for planned_path in planned_paths:
        _validate_resolved_target(project, planned_path)

    for rel in PROJECT_DIRS:
        _mkdir_in_project(project, project / rel)

    for relative_path, content in templates.items():
        write_file(project, project / relative_path, content, force, stats)

    return project, stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold a protocol-first reverse-collection project.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("name", help="Project name or target slug")
    parser.add_argument("--root", default=".", help="Directory where the project will be created")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_SPECS),
        default="generic",
        help="Template profile tuned for the target symptom family",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    project, stats = scaffold(Path(args.root), args.name, args.profile, args.force)
    print(project)
    print(f"profile={args.profile}")
    print(f"created={stats.created} updated={stats.updated}")
    print(
        "next: fill analysis/notes.md and contracts, implement collector modules, "
        "keep main.py as the right-click entrypoint, and use js_reverse_cache/ for task evidence"
    )


if __name__ == "__main__":
    main()
