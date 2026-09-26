import base64
import importlib.util
import json
import sys
import urllib.parse
from pathlib import Path


EXAMPLE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = EXAMPLE_DIR / "scripts" / "pure_abogus_template.py"
VECTORS_PATH = EXAMPLE_DIR / "fixtures" / "primitives-vectors.json"
STANDARD_BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def load_template():
    spec = importlib.util.spec_from_file_location("pure_abogus_template", TEMPLATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def input_bytes(case):
    if "input_hex" in case:
        return bytes.fromhex(case["input_hex"])
    if "input_repeat" in case:
        repeat = case["input_repeat"]
        return (repeat["text"] * repeat["count"]).encode("utf-8")
    return case.get("input_utf8", "").encode("utf-8")


def reference_custom_base64(data, alphabet):
    standard = base64.b64encode(data).decode("ascii")
    return standard.translate(str.maketrans(STANDARD_BASE64_ALPHABET, alphabet))


def main():
    module = load_template()
    vectors = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    failures = []

    def check(name, actual, expected):
        if actual != expected:
            failures.append(f"{name}: expected {expected!r}, got {actual!r}")

    for name, alphabet, expected in (
        ("BASE64_ALPHABET", module.BASE64_ALPHABET, vectors["alphabets"]["base"]),
        ("ABOGUS_ALPHABET", module.ABOGUS_ALPHABET, vectors["alphabets"]["abogus"]),
        ("SIGN_ALPHABET", module.SIGN_ALPHABET, vectors["alphabets"]["sign"]),
    ):
        check(f"{name}.value", alphabet, expected)
        check(f"{name}.length", len(alphabet), 64)
        check(f"{name}.unique", len(set(alphabet)), 64)

    for case in vectors["sm3"]:
        check(
            f"sm3.{case['name']}",
            module.sm3_digest(input_bytes(case)).hex(),
            case["expected_hex"],
        )

    for case in vectors["stream"]:
        check(
            f"stream.{case['name']}",
            module.bdms_stream_transform(input_bytes(case), bytes.fromhex(case["key_hex"])).hex(),
            case["expected_hex"],
        )

    for index, case in enumerate(vectors["sign_value"]):
        check(
            f"sign_value.{index}",
            module.generate_sign_value(case["cursor"], case["mode"], case["ua"]),
            case["expected"],
        )

    custom = vectors["custom_base64"]
    check(
        "custom_base64.frozen",
        module.encode_abogus_payload(bytes.fromhex(custom["input_hex"]), module.ABOGUS_ALPHABET),
        custom["expected"],
    )

    for size in (0, 1, 2, 3, 12, 48, 256):
        data = bytes(index % 256 for index in range(size))
        for name, alphabet in (
            ("base", module.BASE64_ALPHABET),
            ("abogus", module.ABOGUS_ALPHABET),
            ("sign", module.SIGN_ALPHABET),
        ):
            check(
                f"base64.{name}.{size}",
                module.encode_abogus_payload(data, alphabet),
                reference_custom_base64(data, alphabet),
            )

    smoke_value = (module.ABOGUS_ALPHABET * 3)[:192]
    check("shape.valid-smoke", module.is_abogus_shape_smoke(smoke_value), True)
    check("shape.only-padding", module.is_abogus_shape_smoke("=" * 192), False)
    check("shape.interior-padding", module.is_abogus_shape_smoke("A=" * 96), False)
    check("shape.invalid-char", module.is_abogus_shape_smoke("!" + smoke_value[1:]), False)
    encoded_url = "https://example.invalid/?" + urllib.parse.urlencode({"a_bogus": smoke_value})
    check("url.roundtrip", module.extract_abogus_from_url(encoded_url), smoke_value)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(f"primitive vectors: ok ({vectors['metadata']['scope']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
