#!/usr/bin/env python3
"""Normalize HAR or transcript JSON into a reviewable public evidence package."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import parse_qsl, quote, unquote, unquote_plus, urlsplit, urlunsplit


EVIDENCE_PACKAGE_VERSION = 2
PROOF_MANIFEST_VERSION = 2
HMAC_SCHEME = "hmac-sha256"
REDACTION_SCOPE = "known-sensitive-fields-and-recognizable-values"
DEFAULT_MAX_INPUT_BYTES = 128 * 1024 * 1024
MAX_HMAC_KEY_BYTES = 64 * 1024
MAX_JSON_DEPTH = 256
MAX_JSON_NODES = 2_000_000

JsonValue = Union[
    None, bool, int, float, str, List["JsonValue"], Dict[str, "JsonValue"]
]


class EvidenceError(ValueError):
    """Raised when a capture cannot be normalized without guessing."""


@dataclass(frozen=True)
class BodyMaterial:
    data: bytes
    media_type: Optional[str]
    reconstructed: bool = False


class Redactor:
    """Produce deterministic pseudonyms without exposing source values or the key."""

    def __init__(self, key: bytes, *, include_raw_hashes: bool = False) -> None:
        if not isinstance(key, bytes) or not key:
            raise EvidenceError("the HMAC key must be non-empty bytes")
        if not isinstance(include_raw_hashes, bool):
            raise EvidenceError("include_raw_hashes must be a boolean")
        self._key = key
        self.include_raw_hashes = include_raw_hashes

    def digest(self, value: Any) -> str:
        payload = canonical_secret_bytes(value)
        return hmac.new(self._key, payload, hashlib.sha256).hexdigest()

    def token(self, value: Any) -> str:
        return "%s:%s" % (HMAC_SCHEME, self.digest(value))


def canonical_secret_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise EvidenceError("secret value is not JSON serializable: %s" % exc) from exc
    return rendered.encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def serialize_json(document: Any) -> bytes:
    """Serialize deterministically; the trailing newline is part of the artifact hash."""

    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _read_bounded_bytes(path: Path, *, max_bytes: int, label: str) -> bytes:
    if max_bytes < 1:
        raise EvidenceError("%s byte limit must be positive" % label)
    try:
        with path.open("rb") as handle:
            payload = handle.read(max_bytes + 1)
    except OSError as exc:
        raise EvidenceError("cannot read %s" % label) from exc
    if len(payload) > max_bytes:
        raise EvidenceError("%s exceeds %d bytes" % (label, max_bytes))
    return payload


def _validate_json_shape(document: Any) -> None:
    stack: List[Tuple[Any, int]] = [(document, 1)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise EvidenceError("input JSON contains too many values")
        if depth > MAX_JSON_DEPTH:
            raise EvidenceError("input JSON nesting exceeds %d levels" % MAX_JSON_DEPTH)
        if isinstance(value, Mapping):
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)


def _normalized_name(name: str) -> str:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name.strip())
    expanded = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", expanded)
    return re.sub(r"[^a-z0-9]+", "_", expanded.lower()).strip("_")


_SENSITIVE_EXACT_NAMES = {
    "authorization",
    "proxy_authorization",
    "cookie",
    "set_cookie",
    "password",
    "passwd",
    "passphrase",
    "access_token",
    "refresh_token",
    "id_token",
    "auth_token",
    "csrf_token",
    "xsrf_token",
    "api_key",
    "apikey",
    "client_secret",
    "private_key",
    "session",
    "session_id",
    "sessionid",
    "sid",
    "jwt",
    "credential",
    "credentials",
    "signature",
    "sign",
    "sig",
    "nonce",
    "challenge",
    "ticket",
    "proof",
    "cursor",
    "x_api_key",
    "x_auth_token",
    "x_csrf_token",
    "email",
    "email_address",
    "name",
    "full_name",
    "first_name",
    "middle_name",
    "last_name",
    "given_name",
    "family_name",
    "display_name",
    "legal_name",
    "phone",
    "phone_number",
    "address",
    "street_address",
    "billing_address",
    "shipping_address",
    "postal_address",
    "postal_code",
    "zip_code",
    "date_of_birth",
    "birth_date",
    "dob",
    "ssn",
    "national_id",
    "tax_id",
    "card_number",
    "cvv",
    "cvc",
    "bank_account",
    "iban",
    "ip_address",
    "latitude",
    "longitude",
    "username",
    "user_id",
    "account_id",
    "device_id",
    "otp",
    "otp_code",
    "pin",
    "verification_code",
    "one_time_password",
    "reset_token",
    "invite_token",
    "access_code",
    "security_code",
    "mfa_code",
    "two_factor_code",
}

_SENSITIVE_COLLAPSED_NAMES = {
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "authtoken",
    "csrftoken",
    "xsrftoken",
    "apikey",
    "clientsecret",
    "privatekey",
    "sessionid",
    "passwordhash",
    "xapikey",
    "xauthtoken",
    "xcsrftoken",
    "emailaddress",
    "name",
    "fullname",
    "firstname",
    "middlename",
    "lastname",
    "givenname",
    "familyname",
    "displayname",
    "legalname",
    "phonenumber",
    "streetaddress",
    "billingaddress",
    "shippingaddress",
    "postaladdress",
    "postalcode",
    "zipcode",
    "dateofbirth",
    "birthdate",
    "nationalid",
    "taxid",
    "cardnumber",
    "bankaccount",
    "ipaddress",
    "userid",
    "accountid",
    "deviceid",
    "otpcode",
    "verificationcode",
    "onetimepassword",
    "resettoken",
    "invitetoken",
    "accesscode",
    "securitycode",
    "mfacode",
    "twofactorcode",
}


def is_sensitive_name(name: Any) -> bool:
    if not isinstance(name, str):
        return False
    normalized = _normalized_name(name)
    if normalized in _SENSITIVE_EXACT_NAMES:
        return True
    if normalized.replace("_", "") in _SENSITIVE_COLLAPSED_NAMES:
        return True
    parts = set(normalized.split("_"))
    return bool(
        parts.intersection(
            {
                "token",
                "secret",
                "password",
                "passwd",
                "signature",
                "nonce",
                "challenge",
                "ticket",
                "proof",
                "credential",
                "auth",
                "otp",
                "pin",
            }
        )
    )


_JWT_RE = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")
_EMAIL_VALUE_RE = re.compile(
    r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9.-])"
)
_PHONE_VALUE_RE = re.compile(r"^\+?[0-9][0-9 .()\-]{6,}[0-9]$")
_SENSITIVE_PATH_PREDECESSORS = {
    "activate",
    "auth",
    "code",
    "download",
    "invite",
    "key",
    "otp",
    "password",
    "pin",
    "reset",
    "secret",
    "session",
    "share",
    "ticket",
    "token",
    "verify",
}


def looks_token_like(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered.startswith(("bearer ", "basic ", "digest ", "token ")):
        return True
    if _JWT_RE.fullmatch(stripped):
        return True
    return len(stripped) >= 32 and bool(re.fullmatch(r"[A-Za-z0-9._~+/=-]+", stripped))


def looks_sensitive_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return bool(
        looks_token_like(stripped)
        or _EMAIL_VALUE_RE.search(stripped)
        or _PHONE_VALUE_RE.fullmatch(stripped)
    )


def redact_structure(
    value: Any,
    redactor: Redactor,
    *,
    preserve_record_name: bool = False,
) -> Tuple[Any, int]:
    """Redact sensitive object fields while preserving list and object order."""

    if isinstance(value, dict):
        output: Dict[str, Any] = {}
        redaction_count = 0
        record_name = value.get("name")
        record_surface = value.get("surface", value.get("type"))
        redact_record_value = is_sensitive_name(record_name) or (
            isinstance(record_surface, str)
            and _normalized_name(record_surface)
            in {"cookie", "authorization", "token", "session", "secret"}
        )
        for key, child in value.items():
            string_key = str(key)
            sensitive_key = is_sensitive_name(string_key) and not (
                preserve_record_name and string_key == "name"
            )
            if sensitive_key or (
                string_key == "value" and redact_record_value
            ):
                output[string_key] = redactor.token(child)
                redaction_count += 1
            else:
                output[string_key], nested_count = redact_structure(child, redactor)
                redaction_count += nested_count
        return output, redaction_count
    if isinstance(value, list):
        output_list: List[Any] = []
        redaction_count = 0
        for child in value:
            normalized, nested_count = redact_structure(child, redactor)
            output_list.append(normalized)
            redaction_count += nested_count
        return output_list, redaction_count
    if looks_sensitive_value(value):
        return redactor.token(value), 1
    if value is None or isinstance(value, (bool, int, float, str)):
        return value, 0
    return str(value), 0


def _redact_cookie_header(value: str, redactor: Redactor) -> str:
    output: List[str] = []
    for component in value.split(";"):
        stripped = component.strip()
        if not stripped:
            continue
        if "=" not in stripped:
            output.append(redactor.token(stripped))
            continue
        name, raw_value = stripped.split("=", 1)
        output.append("%s=%s" % (name.strip(), redactor.token(raw_value)))
    return "; ".join(output)


def _redact_set_cookie_header(value: str, redactor: Redactor) -> str:
    return ", ".join(
        _redact_single_set_cookie(component, redactor)
        for component in _split_folded_set_cookie(value)
    )


_COOKIE_NAME_RE = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_SAFE_COOKIE_VALUE_ATTRIBUTES = {
    "domain",
    "expires",
    "max-age",
    "priority",
    "samesite",
}
_SAFE_COOKIE_FLAG_ATTRIBUTES = {"httponly", "partitioned", "secure"}


def _split_folded_set_cookie(value: str) -> List[str]:
    """Split folded Set-Cookie values without splitting an Expires date."""

    output: List[str] = []
    start = 0
    quoted = False
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quoted and character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if character != "," or quoted:
            continue
        remainder = value[index + 1 :].lstrip()
        match = _COOKIE_NAME_RE.match(remainder)
        if match is None or not remainder[match.end() :].lstrip().startswith("="):
            continue
        output.append(value[start:index].strip())
        start = index + 1
    output.append(value[start:].strip())
    return [component for component in output if component] or [value]


def _split_cookie_attributes(value: str) -> List[str]:
    output: List[str] = []
    start = 0
    quoted = False
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quoted and character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
        elif character == ";" and not quoted:
            output.append(value[start:index])
            start = index + 1
    output.append(value[start:])
    return output


def _redact_single_set_cookie(value: str, redactor: Redactor) -> str:
    components = _split_cookie_attributes(value)
    if not components or "=" not in components[0]:
        return redactor.token(value)

    cookie_name, cookie_value = components[0].strip().split("=", 1)
    output = ["%s=%s" % (cookie_name, redactor.token(cookie_value))]
    for component in components[1:]:
        stripped = component.strip()
        if not stripped:
            continue
        if "=" in stripped:
            name, attribute_value = stripped.split("=", 1)
            normalized_name = name.strip().lower()
            if normalized_name == "path":
                attribute_value = _redact_path(attribute_value, redactor)
            elif normalized_name not in _SAFE_COOKIE_VALUE_ATTRIBUTES:
                attribute_value = redactor.token(attribute_value)
            output.append("%s=%s" % (name, attribute_value))
        else:
            output.append(
                stripped
                if stripped.lower() in _SAFE_COOKIE_FLAG_ATTRIBUTES
                else redactor.token(stripped)
            )
    return "; ".join(output)


def _redact_path(path: str, redactor: Redactor) -> str:
    output: List[str] = []
    redact_next = False
    for raw_segment in path.split("/"):
        decoded = unquote(raw_segment)
        should_redact = bool(decoded) and (
            redact_next or looks_sensitive_value(decoded)
        )
        if should_redact:
            output.append(quote(redactor.token(decoded), safe=":-._~"))
        else:
            output.append(raw_segment)
        normalized = _normalized_name(decoded)
        redact_next = bool(
            normalized in _SENSITIVE_PATH_PREDECESSORS
            or is_sensitive_name(decoded)
        )
    return "/".join(output)


def redact_url(url: str, redactor: Redactor) -> Tuple[str, List[Dict[str, str]]]:
    if not isinstance(url, str):
        raise EvidenceError("URL must be a string")
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise EvidenceError("invalid URL %r: %s" % (url, exc)) from exc

    netloc = parsed.netloc
    if "@" in netloc:
        userinfo, host = netloc.rsplit("@", 1)
        netloc = "%s@%s" % (redactor.token(userinfo), host)

    query_rows: List[Dict[str, str]] = []
    redacted_components: List[str] = []
    if parsed.query:
        for component in parsed.query.split("&"):
            has_equals = "=" in component
            raw_name, raw_value = (
                component.split("=", 1) if has_equals else (component, "")
            )
            name = unquote_plus(raw_name)
            value = unquote_plus(raw_value)
            if not has_equals and component:
                normalized_name = redactor.token(name)
                query_rows.append(
                    {"name": normalized_name, "value": "", "bare": True}
                )
                redacted_components.append(
                    quote(normalized_name, safe=":-._~")
                )
                continue
            if (
                not name
                or is_sensitive_name(name)
                or looks_sensitive_value(value)
            ):
                normalized_value = redactor.token(value)
                rendered_value = quote(normalized_value, safe=":-._~")
            else:
                normalized_value = value
                rendered_value = raw_value
            query_rows.append({"name": name, "value": normalized_value})
            redacted_components.append(
                "%s=%s" % (raw_name, rendered_value)
                if has_equals or rendered_value
                else raw_name
            )

    fragment = redactor.token(parsed.fragment) if parsed.fragment else ""
    normalized_url = urlunsplit(
        (
            parsed.scheme,
            netloc,
            _redact_path(parsed.path, redactor),
            "&".join(redacted_components),
            fragment,
        )
    )
    return normalized_url, query_rows


def _header_items(headers: Any, label: str) -> Iterable[Tuple[str, str]]:
    if headers is None:
        return []
    if isinstance(headers, Mapping):
        return [(str(name), str(value)) for name, value in headers.items()]
    if not isinstance(headers, list):
        raise EvidenceError("%s must be a header list or object" % label)

    output: List[Tuple[str, str]] = []
    for index, item in enumerate(headers):
        item_label = "%s[%d]" % (label, index)
        if isinstance(item, Mapping):
            if "name" not in item or "value" not in item:
                raise EvidenceError("%s must contain name and value" % item_label)
            output.append((str(item["name"]), str(item["value"])))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            output.append((str(item[0]), str(item[1])))
        else:
            raise EvidenceError("%s must be a name/value pair" % item_label)
    return output


def normalize_headers(
    headers: Any, redactor: Redactor, label: str
) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    for name, value in _header_items(headers, label):
        lowered = name.strip().lower()
        if lowered == "cookie":
            normalized_value = _redact_cookie_header(value, redactor)
        elif lowered == "set-cookie":
            normalized_value = _redact_set_cookie_header(value, redactor)
        elif lowered in {"location", "content-location", "referer", "referrer"}:
            normalized_value, _ = redact_url(value, redactor)
        elif is_sensitive_name(name) or looks_sensitive_value(value):
            normalized_value = redactor.token(value)
        else:
            normalized_value = value
        output.append({"name": name, "value": normalized_value})
    return output


def _find_header(headers: Any, wanted: str, label: str) -> Optional[str]:
    result: Optional[str] = None
    for name, value in _header_items(headers, label):
        if name.strip().lower() == wanted.lower():
            result = value
    return result


def _decode_body_text(text: Any, encoding: Any, label: str) -> bytes:
    if not isinstance(text, str):
        raise EvidenceError("%s body text must be a string" % label)
    if encoding in (None, "", "utf8", "utf-8"):
        return text.encode("utf-8")
    if isinstance(encoding, str) and encoding.lower() == "base64":
        try:
            return base64.b64decode(text, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise EvidenceError("%s contains invalid base64 body data" % label) from exc
    if isinstance(encoding, str) and encoding.lower() == "hex":
        try:
            return bytes.fromhex(text)
        except ValueError as exc:
            raise EvidenceError("%s contains invalid hex body data" % label) from exc
    raise EvidenceError("%s uses unsupported body encoding %r" % (label, encoding))


def _is_body_descriptor(value: Mapping[str, Any]) -> bool:
    source_keys = {"text", "data", "base64"}.intersection(value)
    allowed_keys = {
        "text",
        "data",
        "base64",
        "encoding",
        "mimeType",
        "media_type",
    }
    metadata_keys = {"encoding", "mimeType", "media_type"}
    return (
        len(source_keys) == 1
        and set(value).issubset(allowed_keys)
        and bool(metadata_keys.intersection(value))
    )


def _material_from_value(
    value: Any,
    media_type: Optional[str],
    label: str,
) -> Optional[BodyMaterial]:
    if value is None:
        return BodyMaterial(b"", media_type)
    if isinstance(value, str):
        return BodyMaterial(value.encode("utf-8"), media_type)
    if isinstance(value, (dict, list)):
        if isinstance(value, dict) and _is_body_descriptor(value):
            embedded_media_type = value.get(
                "mimeType", value.get("media_type", media_type)
            )
            if embedded_media_type is not None and not isinstance(
                embedded_media_type, str
            ):
                embedded_media_type = str(embedded_media_type)
            if "base64" in value:
                declared_encoding = value.get("encoding")
                if declared_encoding not in (None, "") and not (
                    isinstance(declared_encoding, str)
                    and declared_encoding.lower() == "base64"
                ):
                    raise EvidenceError(
                        "%s base64 descriptor has a conflicting encoding" % label
                    )
                data = _decode_body_text(value["base64"], "base64", label)
            else:
                text = value.get("text", value.get("data"))
                data = _decode_body_text(text, value.get("encoding"), label)
            return BodyMaterial(data, embedded_media_type)

        rendered = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return BodyMaterial(
            rendered, media_type or "application/json", reconstructed=True
        )
    if isinstance(value, (bool, int, float)):
        rendered = json.dumps(value, ensure_ascii=False).encode("utf-8")
        return BodyMaterial(
            rendered, media_type or "application/json", reconstructed=True
        )
    raise EvidenceError("%s body must be text, JSON, or an encoded descriptor" % label)


def _material_from_har_post_data(post_data: Any, label: str) -> Optional[BodyMaterial]:
    if post_data is None:
        return None
    if not isinstance(post_data, Mapping):
        raise EvidenceError("%s must be an object" % label)
    media_type = post_data.get("mimeType")
    if media_type is not None and not isinstance(media_type, str):
        media_type = str(media_type)
    if "text" in post_data:
        return BodyMaterial(
            _decode_body_text(post_data["text"], post_data.get("encoding"), label),
            media_type,
        )
    params = post_data.get("params")
    if isinstance(params, list):
        pairs: List[Tuple[str, str]] = []
        for index, item in enumerate(params):
            if not isinstance(item, Mapping) or "name" not in item:
                raise EvidenceError("%s.params[%d] is invalid" % (label, index))
            pairs.append((str(item["name"]), str(item.get("value", ""))))
        rendered = "&".join(
            "%s=%s" % (quote(name, safe=""), quote(value, safe=""))
            for name, value in pairs
        ).encode("ascii")
        return BodyMaterial(
            rendered,
            media_type or "application/x-www-form-urlencoded",
            reconstructed=True,
        )
    return None


def _material_from_har_content(content: Any, label: str) -> Optional[BodyMaterial]:
    if content is None:
        return None
    if not isinstance(content, Mapping):
        raise EvidenceError("%s must be an object" % label)
    media_type = content.get("mimeType")
    if media_type is not None and not isinstance(media_type, str):
        media_type = str(media_type)
    if "text" in content:
        return BodyMaterial(
            _decode_body_text(content["text"], content.get("encoding"), label),
            media_type,
        )
    if content.get("size") == 0:
        return BodyMaterial(b"", media_type)
    return None


def normalize_body(
    material: Optional[BodyMaterial],
    redactor: Redactor,
    *,
    response: bool,
    declared_length: Any = None,
) -> Dict[str, Any]:
    if material is None:
        output: Dict[str, Any] = {"available": False, "raw_included": False}
        if isinstance(declared_length, int) and not isinstance(declared_length, bool):
            output["declared_length"] = declared_length
        return output

    data = material.data
    output = {
        "available": True,
        "length": len(data),
        "hmac_sha256": redactor.digest(data),
        "raw_included": False,
    }
    if redactor.include_raw_hashes:
        output["sha256"] = sha256_bytes(data)
    if material.media_type:
        output["media_type"] = material.media_type
    if material.reconstructed:
        output["reconstructed"] = True
    if response:
        output["redacted"] = True
        return output

    redaction_count = 0
    media_type = (material.media_type or "").lower().split(";", 1)[0].strip()
    if media_type == "application/x-www-form-urlencoded":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = ""
        if text or not data:
            form: List[Dict[str, str]] = []
            for name, value in parse_qsl(text, keep_blank_values=True):
                if is_sensitive_name(name) or looks_sensitive_value(value):
                    value = redactor.token(value)
                    redaction_count += 1
                form.append({"name": name, "value": value})
            output["form"] = form
    elif media_type == "application/json" or media_type.endswith("+json"):
        try:
            parsed = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
        if parsed is not None:
            normalized_json, redaction_count = redact_structure(parsed, redactor)
            output["json"] = normalized_json
    output["redacted"] = True
    output["structured_view_redactions"] = redaction_count
    return output


def _safe_number(value: Any) -> Optional[Union[int, float]]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _normalize_timings(value: Any) -> Optional[Dict[str, Union[int, float]]]:
    if not isinstance(value, Mapping):
        return None
    output: Dict[str, Union[int, float]] = {}
    for key, child in value.items():
        normalized = _safe_number(child)
        if normalized is not None:
            output[str(key)] = normalized
    return output or None


def _normalize_request(
    request: Any,
    redactor: Redactor,
    label: str,
    *,
    har: bool,
) -> Dict[str, Any]:
    if not isinstance(request, Mapping):
        raise EvidenceError("%s must be an object" % label)
    method = request.get("method", "GET")
    url = request.get("url")
    if not isinstance(method, str) or not method:
        raise EvidenceError("%s.method must be a non-empty string" % label)
    if not isinstance(url, str) or not url:
        raise EvidenceError("%s.url must be a non-empty string" % label)

    raw_headers = request.get("headers", [])
    normalized_url, query = redact_url(url, redactor)
    content_type = _find_header(raw_headers, "content-type", "%s.headers" % label)
    if har:
        material = _material_from_har_post_data(
            request.get("postData"), "%s.postData" % label
        )
    elif "body" in request:
        material = _material_from_value(
            request.get("body"), content_type, "%s.body" % label
        )
    elif "body_text" in request:
        material = _material_from_value(
            request.get("body_text"), content_type, "%s.body_text" % label
        )
    elif "postData" in request:
        material = _material_from_har_post_data(
            request.get("postData"), "%s.postData" % label
        )
    else:
        material = None

    output: Dict[str, Any] = {
        "method": method,
        "url": normalized_url,
        "query": query,
        "headers": normalize_headers(raw_headers, redactor, "%s.headers" % label),
        "body": normalize_body(material, redactor, response=False),
    }
    http_version = request.get("httpVersion", request.get("http_version"))
    if http_version is not None:
        output["http_version"] = str(http_version)
    return output


def _normalize_redirect(
    response: Mapping[str, Any],
    raw_headers: Any,
    redactor: Redactor,
    status: Any,
    label: str,
) -> Optional[Dict[str, Any]]:
    redirect_value = response.get("redirect")
    location: Optional[str] = None
    redirect_status = status
    if isinstance(redirect_value, Mapping):
        candidate = redirect_value.get(
            "location", redirect_value.get("url", redirect_value.get("target_url"))
        )
        if candidate:
            location = str(candidate)
        if "status" in redirect_value:
            redirect_status = redirect_value["status"]
    elif isinstance(redirect_value, str) and redirect_value:
        location = redirect_value
    if not location:
        candidate = response.get("redirectURL", response.get("redirect_url"))
        if isinstance(candidate, str) and candidate:
            location = candidate
    if not location:
        location = _find_header(raw_headers, "location", "%s.headers" % label)
    if not location:
        return None
    normalized_location, _ = redact_url(location, redactor)
    output: Dict[str, Any] = {"location": normalized_location}
    if isinstance(redirect_status, int) and not isinstance(redirect_status, bool):
        output["status"] = redirect_status
    return output


def _normalize_response(
    response: Any,
    redactor: Redactor,
    label: str,
    *,
    har: bool,
) -> Dict[str, Any]:
    if not isinstance(response, Mapping):
        raise EvidenceError("%s must be an object" % label)
    raw_headers = response.get("headers", [])
    status = response.get("status")
    if status is not None and (isinstance(status, bool) or not isinstance(status, int)):
        try:
            status = int(status)
        except (TypeError, ValueError) as exc:
            raise EvidenceError("%s.status must be an integer" % label) from exc

    content_type = _find_header(raw_headers, "content-type", "%s.headers" % label)
    declared_length = response.get("bodySize", response.get("body_size"))
    if har:
        content = response.get("content")
        material = _material_from_har_content(content, "%s.content" % label)
        if isinstance(content, Mapping):
            content_type = content.get("mimeType", content_type)
            if declared_length is None:
                declared_length = content.get("size")
    elif "body" in response:
        material = _material_from_value(
            response.get("body"), content_type, "%s.body" % label
        )
    elif "body_text" in response:
        material = _material_from_value(
            response.get("body_text"), content_type, "%s.body_text" % label
        )
    elif "content" in response:
        material = _material_from_har_content(
            response.get("content"), "%s.content" % label
        )
    else:
        material = None

    if material is not None and not material.media_type and content_type:
        material = BodyMaterial(
            material.data, str(content_type), material.reconstructed
        )

    output: Dict[str, Any] = {
        "status": status,
        "headers": normalize_headers(raw_headers, redactor, "%s.headers" % label),
        "body": normalize_body(
            material,
            redactor,
            response=True,
            declared_length=declared_length,
        ),
    }
    status_text = response.get("statusText", response.get("status_text"))
    if status_text is not None:
        rendered_status = str(status_text)
        output["status_text"] = (
            redactor.token(rendered_status)
            if looks_sensitive_value(rendered_status)
            else rendered_status
        )
    http_version = response.get("httpVersion", response.get("http_version"))
    if http_version is not None:
        output["http_version"] = str(http_version)
    redirect = _normalize_redirect(response, raw_headers, redactor, status, label)
    if redirect is not None:
        output["redirect"] = redirect
    return output


def _normalize_state_writes(value: Any, redactor: Redactor, label: str) -> List[Any]:
    if not isinstance(value, list):
        raise EvidenceError("%s must be a list" % label)
    output: List[Any] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise EvidenceError("%s[%d] must be an object" % (label, index))
        normalized, _ = redact_structure(
            dict(item), redactor, preserve_record_name=True
        )
        if isinstance(normalized, dict):
            # State payloads are pseudonymized even when their semantic name is unknown.
            for payload_key in (
                "value",
                "old_value",
                "new_value",
                "previous",
                "next",
                "data",
                "payload",
            ):
                if payload_key in item:
                    normalized[payload_key] = redactor.token(item[payload_key])
        output.append(normalized)
    return output


def _normalize_step(
    step: Any,
    redactor: Redactor,
    label: str,
    *,
    har: bool,
    step_index: int,
) -> Dict[str, Any]:
    if not isinstance(step, Mapping):
        raise EvidenceError("%s must be an object" % label)
    output: Dict[str, Any] = {"step_index": step_index}
    if "request" in step:
        output["request"] = _normalize_request(
            step["request"], redactor, "%s.request" % label, har=har
        )
    if "response" in step:
        output["response"] = _normalize_response(
            step["response"], redactor, "%s.response" % label, har=har
        )
    if "request" not in output and "response" not in output:
        if "state_writes" not in step and "stateWrites" not in step:
            raise EvidenceError(
                "%s must contain a request, response, or state_writes" % label
            )

    started_at = step.get("startedDateTime", step.get("started_at"))
    if started_at is not None:
        output["started_at"] = str(started_at)
    elapsed = _safe_number(step.get("time", step.get("elapsed_ms")))
    if elapsed is not None:
        output["elapsed_ms"] = elapsed
    timings = _normalize_timings(step.get("timings"))
    if timings is not None:
        output["timings"] = timings
    for key in ("label", "event"):
        if key in step and step[key] is not None:
            rendered = str(step[key])
            output[key] = (
                redactor.token(rendered)
                if looks_sensitive_value(rendered)
                else rendered
            )
    if "route" in step and step["route"] is not None:
        output["route"], _ = redact_url(str(step["route"]), redactor)
    state_writes = step.get("state_writes", step.get("stateWrites"))
    if state_writes is not None:
        output["state_writes"] = _normalize_state_writes(
            state_writes, redactor, "%s.state_writes" % label
        )
    return output


def _safe_chain_id(value: Any, redactor: Redactor, fallback: str) -> str:
    if value is None:
        return fallback
    rendered = str(value)
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", rendered) and not looks_sensitive_value(rendered):
        return rendered
    return "chain-%s" % redactor.token(rendered)


def _normalize_har(
    document: Mapping[str, Any], redactor: Redactor
) -> List[Dict[str, Any]]:
    log = document.get("log")
    if not isinstance(log, Mapping) or not isinstance(log.get("entries"), list):
        raise EvidenceError("HAR input must contain log.entries as a list")

    chains: List[Dict[str, Any]] = []
    chain_lookup: Dict[str, Dict[str, Any]] = {}
    for source_index, entry in enumerate(log["entries"]):
        if not isinstance(entry, Mapping):
            raise EvidenceError("log.entries[%d] must be an object" % source_index)
        raw_chain_id = entry.get(
            "_sessionChainId",
            entry.get("_session_chain_id", entry.get("session_chain_id")),
        )
        chain_id = _safe_chain_id(raw_chain_id, redactor, "chain-0")
        if chain_id not in chain_lookup:
            chain = {"session_chain_id": chain_id, "steps": []}
            chain_lookup[chain_id] = chain
            chains.append(chain)
        chain = chain_lookup[chain_id]
        chain["steps"].append(
            _normalize_step(
                entry,
                redactor,
                "log.entries[%d]" % source_index,
                har=True,
                step_index=len(chain["steps"]),
            )
        )
    return chains


def _transcript_chains(document: Any) -> List[Mapping[str, Any]]:
    if isinstance(document, list):
        return [{"session_chain_id": "chain-0", "steps": document}]
    if not isinstance(document, Mapping):
        raise EvidenceError("transcript input must be an object or list")
    if isinstance(document.get("chains"), list):
        return document["chains"]
    steps = document.get("steps", document.get("entries", document.get("transcript")))
    if isinstance(steps, list):
        return [
            {
                "session_chain_id": document.get("session_chain_id", "chain-0"),
                "steps": steps,
            }
        ]
    raise EvidenceError("transcript input must contain chains or steps")


def _normalize_transcript(document: Any, redactor: Redactor) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for chain_index, source_chain in enumerate(_transcript_chains(document)):
        if not isinstance(source_chain, Mapping):
            raise EvidenceError("chains[%d] must be an object" % chain_index)
        steps = source_chain.get("steps", source_chain.get("entries"))
        if not isinstance(steps, list):
            raise EvidenceError("chains[%d].steps must be a list" % chain_index)
        chain_id = _safe_chain_id(
            source_chain.get("session_chain_id"),
            redactor,
            "chain-%d" % chain_index,
        )
        normalized_steps = [
            _normalize_step(
                step,
                redactor,
                "chains[%d].steps[%d]" % (chain_index, step_index),
                har=False,
                step_index=step_index,
            )
            for step_index, step in enumerate(steps)
        ]
        output.append({"session_chain_id": chain_id, "steps": normalized_steps})
    return output


def detect_input_format(document: Any) -> str:
    if isinstance(document, Mapping):
        log = document.get("log")
        if isinstance(log, Mapping) and isinstance(log.get("entries"), list):
            return "har"
    if isinstance(document, (Mapping, list)):
        return "transcript"
    raise EvidenceError("input root must be a HAR or transcript JSON object")


def normalize_document(
    document: Any,
    *,
    hmac_key: bytes,
    source_sha256: Optional[str] = None,
    source_hmac_sha256: Optional[str] = None,
    input_format: str = "auto",
    include_raw_hashes: bool = False,
) -> Dict[str, Any]:
    """Normalize a parsed document. Header, chain, step, and state-write order is retained."""

    if not isinstance(include_raw_hashes, bool):
        raise EvidenceError("include_raw_hashes must be a boolean")
    _validate_json_shape(document)
    redactor = Redactor(hmac_key, include_raw_hashes=include_raw_hashes)
    if input_format not in {"auto", "har", "transcript"}:
        raise EvidenceError("input_format must be auto, har, or transcript")
    detected_format = (
        detect_input_format(document) if input_format == "auto" else input_format
    )
    canonical_source = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if source_hmac_sha256 is None:
        source_hmac_sha256 = redactor.digest(canonical_source)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", source_hmac_sha256):
        raise EvidenceError(
            "source_hmac_sha256 must contain 64 hexadecimal characters"
        )
    if source_sha256 is not None and not include_raw_hashes:
        raise EvidenceError("source_sha256 requires include_raw_hashes=True")
    if include_raw_hashes:
        if source_sha256 is None:
            source_sha256 = sha256_bytes(canonical_source)
        if not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256):
            raise EvidenceError("source_sha256 must contain 64 hexadecimal characters")

    if detected_format == "har":
        if not isinstance(document, Mapping):
            raise EvidenceError("HAR root must be an object")
        chains = _normalize_har(document, redactor)
    else:
        chains = _normalize_transcript(document, redactor)
    step_count = sum(len(chain["steps"]) for chain in chains)
    source: Dict[str, Any] = {
        "format": detected_format,
        "hmac_sha256": source_hmac_sha256.lower(),
        "step_count": step_count,
    }
    if include_raw_hashes and source_sha256 is not None:
        source["sha256"] = source_sha256.lower()
    return {
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "source": source,
        "redaction": {
            "scheme": HMAC_SCHEME,
            "scope": REDACTION_SCOPE,
            "publication_review_required": True,
            "raw_hashes_included": include_raw_hashes,
            "raw_request_bodies_included": False,
            "raw_response_bodies_included": False,
        },
        "chains": chains,
    }


def normalize_bytes(
    source_bytes: bytes,
    *,
    hmac_key: bytes,
    input_format: str = "auto",
    include_raw_hashes: bool = False,
) -> Dict[str, Any]:
    try:
        document = json.loads(source_bytes.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise EvidenceError("input is not UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceError(
            "invalid JSON at line %d column %d: %s" % (exc.lineno, exc.colno, exc.msg)
        ) from exc
    except RecursionError as exc:
        raise EvidenceError("input JSON nesting exceeds the supported limit") from exc
    return normalize_document(
        document,
        hmac_key=hmac_key,
        source_sha256=(sha256_bytes(source_bytes) if include_raw_hashes else None),
        source_hmac_sha256=Redactor(hmac_key).digest(source_bytes),
        input_format=input_format,
        include_raw_hashes=include_raw_hashes,
    )


def build_proof_manifest(
    package: Mapping[str, Any], package_bytes: bytes
) -> Dict[str, Any]:
    source = package.get("source")
    if not isinstance(source, Mapping):
        raise EvidenceError("evidence package has no source descriptor")
    redaction = package.get("redaction")
    if not isinstance(redaction, Mapping):
        raise EvidenceError("evidence package has no redaction descriptor")
    source_hmac_sha256 = source.get("hmac_sha256")
    if not isinstance(source_hmac_sha256, str) or not re.fullmatch(
        r"[0-9a-fA-F]{64}", source_hmac_sha256
    ):
        raise EvidenceError("evidence package has no valid source HMAC fingerprint")
    source_descriptor = {
        "format": source.get("format"),
        "hmac_sha256": source_hmac_sha256.lower(),
    }
    if "sha256" in source:
        source_descriptor["sha256"] = source.get("sha256")
    return {
        "proof_manifest_version": PROOF_MANIFEST_VERSION,
        "source": source_descriptor,
        "evidence_package": {
            "schema_version": package.get("evidence_package_version"),
            "sha256": sha256_bytes(package_bytes),
        },
        "redaction": {
            "scheme": redaction.get("scheme"),
            "scope": redaction.get("scope"),
            "publication_review_required": redaction.get(
                "publication_review_required", True
            ),
            "raw_hashes_included": bool(redaction.get("raw_hashes_included")),
        },
    }


def _read_hmac_key(args: argparse.Namespace) -> bytes:
    if args.hmac_key is not None:
        key = args.hmac_key.encode("utf-8")
    elif args.hmac_key_env is not None:
        value = os.environ.get(args.hmac_key_env)
        if value is None:
            raise EvidenceError(
                "environment variable %s is not set" % args.hmac_key_env
            )
        key = value.encode("utf-8")
    elif args.hmac_key_file is not None:
        key = _read_bounded_bytes(
            args.hmac_key_file,
            max_bytes=MAX_HMAC_KEY_BYTES,
            label="HMAC key file",
        )
    else:
        raise EvidenceError("one HMAC key source is required")
    if not key:
        raise EvidenceError("the HMAC key must not be empty")
    return key


def _write_artifact(path: Path, payload: bytes) -> None:
    descriptor: Optional[int] = None
    temporary_path: Optional[Path] = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=".%s." % path.name,
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as exc:
        raise EvidenceError("cannot write evidence artifact") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def run_self_test() -> None:
    document = {
        "log": {
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://example.test/?token=query-secret&x=1",
                        "headers": [
                            {"name": "X-Duplicate", "value": "one"},
                            {"name": "Cookie", "value": "sid=cookie-secret"},
                            {"name": "X-Duplicate", "value": "two"},
                            {"name": "Content-Type", "value": "application/json"},
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": '{"token":"body-secret","page":1}',
                        },
                    },
                    "response": {
                        "status": 302,
                        "headers": [
                            {
                                "name": "Location",
                                "value": "https://example.test/next?token=redirect-secret",
                            }
                        ],
                        "redirectURL": (
                            "https://example.test/next?token=redirect-secret"
                        ),
                        "content": {"text": "response-secret"},
                    },
                }
            ]
        }
    }
    package = normalize_document(document, hmac_key=b"self-test-key")
    repeated = normalize_document(document, hmac_key=b"self-test-key")
    if package != repeated:
        raise AssertionError("normalization is not deterministic")
    step = package["chains"][0]["steps"][0]
    if [header["name"] for header in step["request"]["headers"]] != [
        "X-Duplicate",
        "Cookie",
        "X-Duplicate",
        "Content-Type",
    ]:
        raise AssertionError("header order or duplicates were not preserved")
    if "sha256" in step["request"]["body"]:
        raise AssertionError("raw body hash was included by default")
    expected_digest = Redactor(
        b"self-test-key"
    ).digest(b'{"token":"body-secret","page":1}')
    if step["request"]["body"]["hmac_sha256"] != expected_digest:
        raise AssertionError("keyed body fingerprint mismatch")
    rendered = serialize_json(package).decode("utf-8")
    for secret in (
        "query-secret",
        "cookie-secret",
        "body-secret",
        "redirect-secret",
        "response-secret",
        "self-test-key",
    ):
        if secret in rendered:
            raise AssertionError("secret remained in normalized evidence")
    if step["response"]["redirect"]["status"] != 302:
        raise AssertionError("redirect status was not preserved")
    manifest = build_proof_manifest(package, serialize_json(package))
    if "sha256" in manifest["source"]:
        raise AssertionError("manifest included a raw source hash by default")
    if manifest["redaction"]["publication_review_required"] is not True:
        raise AssertionError("manifest omitted the publication review gate")
    print("self_test=PASS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize HAR or transcript JSON while preserving protocol order and "
            "pseudonymizing known sensitive fields and recognizable sensitive "
            "values. Publication review remains required."
        )
    )
    parser.add_argument(
        "source", nargs="?", type=Path, help="HAR or transcript JSON path"
    )
    parser.add_argument(
        "output", nargs="?", type=Path, help="Evidence package JSON path"
    )
    parser.add_argument(
        "--input-format",
        choices=("auto", "har", "transcript"),
        default="auto",
        help="Input shape; auto detects HAR versus transcript",
    )
    parser.add_argument(
        "--max-input-bytes",
        type=int,
        default=DEFAULT_MAX_INPUT_BYTES,
        help="Maximum capture size to read (default: %(default)s bytes)",
    )
    key_group = parser.add_mutually_exclusive_group()
    key_group.add_argument(
        "--hmac-key",
        help="Literal HMAC key (prefer --hmac-key-env outside disposable tests)",
    )
    key_group.add_argument(
        "--hmac-key-env",
        metavar="NAME",
        help="Read the HMAC key from an environment variable",
    )
    key_group.add_argument(
        "--hmac-key-file",
        type=Path,
        help="Read exact HMAC key bytes from a local file",
    )
    parser.add_argument(
        "--proof-manifest",
        type=Path,
        help=(
            "Optional evidence proof-manifest v2 path containing the keyed source "
            "fingerprint, redacted package SHA-256, and publication-review flags"
        ),
    )
    parser.add_argument(
        "--include-raw-hashes",
        action="store_true",
        help=(
            "Local-only opt-in for unkeyed source/body SHA-256 values; "
            "do not use for a public package or publication manifest"
        ),
    )
    parser.add_argument("--self-test", action="store_true", help="Run built-in checks")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        try:
            run_self_test()
        except AssertionError as exc:
            print("self_test=FAIL: %s" % exc, file=sys.stderr)
            return 1
        return 0
    if args.source is None or args.output is None:
        parser.error("source and output are required unless --self-test is used")
    if (
        args.hmac_key is None
        and args.hmac_key_env is None
        and args.hmac_key_file is None
    ):
        parser.error(
            "one of --hmac-key, --hmac-key-env, or --hmac-key-file is required"
        )
    if args.max_input_bytes < 1:
        parser.error("--max-input-bytes must be positive")

    try:
        source_resolved = args.source.resolve()
        output_resolved = args.output.resolve()
        if source_resolved == output_resolved:
            raise EvidenceError("source and output paths must be different")
        if args.proof_manifest is not None:
            manifest_resolved = args.proof_manifest.resolve()
            if manifest_resolved in {source_resolved, output_resolved}:
                raise EvidenceError("proof manifest must use a distinct path")
        source_bytes = _read_bounded_bytes(
            args.source,
            max_bytes=args.max_input_bytes,
            label="capture input",
        )
        hmac_key = _read_hmac_key(args)
        package = normalize_bytes(
            source_bytes,
            hmac_key=hmac_key,
            input_format=args.input_format,
            include_raw_hashes=args.include_raw_hashes,
        )
        package_bytes = serialize_json(package)
        _write_artifact(args.output, package_bytes)
        manifest_bytes: Optional[bytes] = None
        if args.proof_manifest is not None:
            manifest = build_proof_manifest(package, package_bytes)
            manifest_bytes = serialize_json(manifest)
            _write_artifact(args.proof_manifest, manifest_bytes)
    except EvidenceError as exc:
        print("evidence_error=%s" % exc, file=sys.stderr)
        return 2

    print("source_format=%s" % package["source"]["format"])
    print("chains=%d" % len(package["chains"]))
    print("steps=%d" % package["source"]["step_count"])
    print("evidence_package_path=%s" % output_resolved)
    print("evidence_package_sha256=%s" % sha256_bytes(package_bytes))
    if args.proof_manifest is not None and manifest_bytes is not None:
        print("proof_manifest_path=%s" % manifest_resolved)
        print("proof_manifest_sha256=%s" % sha256_bytes(manifest_bytes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
