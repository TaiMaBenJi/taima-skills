"""Example primitive scaffold for a Douyin BDMS a_bogus Python implementation.

This is not a complete generator. Copy it into a target workspace only after
the BDMS version and a fixed trace are known, then implement packing, field
building, and request glue from verified target evidence.
"""

import re
import urllib.parse


BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-/"
ABOGUS_ALPHABET = "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe"
SIGN_ALPHABET = "ckdp1h4ZKsUB80/Mfvw36XIgR25+WQAlEi7NLboqYTOPuzmFjJnryx9HVGDaStCe"
SM3_IV = [0x7380166F, 0x4914B2B9, 0x172442D7, 0xDA8A0600, 0xA96F30BC, 0x163138AA, 0xE38DEE4D, 0xB0FB0E4E]


def _rotl32(value, bits):
    value &= 0xFFFFFFFF
    return ((value << bits) | (value >> (32 - bits))) & 0xFFFFFFFF


def _sm3_p0(value):
    return value ^ _rotl32(value, 9) ^ _rotl32(value, 17)


def _sm3_p1(value):
    return value ^ _rotl32(value, 15) ^ _rotl32(value, 23)


def sm3_digest(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    message = bytearray(data)
    bit_len = len(message) * 8
    message.append(0x80)
    while len(message) % 64 != 56:
        message.append(0)
    message.extend(bit_len.to_bytes(8, "big"))
    state = SM3_IV[:]
    for offset in range(0, len(message), 64):
        block = message[offset:offset + 64]
        words = [int.from_bytes(block[index:index + 4], "big") for index in range(0, 64, 4)]
        for index in range(16, 68):
            words.append(_sm3_p1(words[index - 16] ^ words[index - 9] ^ _rotl32(words[index - 3], 15)) ^ _rotl32(words[index - 13], 7) ^ words[index - 6])
        ext = [words[index] ^ words[index + 4] for index in range(64)]
        a, b, c, d, e, f, g, h = state
        for index in range(64):
            if index < 16:
                ff = a ^ b ^ c
                gg = e ^ f ^ g
                tj = 0x79CC4519
            else:
                ff = (a & b) | (a & c) | (b & c)
                gg = (e & f) | ((~e) & g)
                tj = 0x7A879D8A
            ss1 = _rotl32((_rotl32(a, 12) + e + _rotl32(tj, index % 32)) & 0xFFFFFFFF, 7)
            ss2 = ss1 ^ _rotl32(a, 12)
            tt1 = (ff + d + ss2 + ext[index]) & 0xFFFFFFFF
            tt2 = (gg + h + ss1 + words[index]) & 0xFFFFFFFF
            d = c
            c = _rotl32(b, 9)
            b = a
            a = tt1
            h = g
            g = _rotl32(f, 19)
            f = e
            e = _sm3_p0(tt2)
        state = [left ^ right for left, right in zip(state, [a, b, c, d, e, f, g, h])]
    return b"".join(value.to_bytes(4, "big") for value in state)


def encode_abogus_payload(payload, alphabet=BASE64_ALPHABET):
    output = []
    data = bytes(payload)
    for offset in range(0, len(data), 3):
        chunk = data[offset:offset + 3]
        b0 = chunk[0]
        b1 = chunk[1] if len(chunk) > 1 else 0
        b2 = chunk[2] if len(chunk) > 2 else 0
        output.append(alphabet[b0 >> 2])
        output.append(alphabet[((b0 & 3) << 4) | (b1 >> 4)])
        output.append(alphabet[((b1 & 15) << 2) | (b2 >> 6)] if len(chunk) > 1 else "=")
        output.append(alphabet[b2 & 63] if len(chunk) > 2 else "=")
    return "".join(output)


def bdms_stream_transform(data, key):
    state = [255 - index for index in range(256)]
    cursor = 0
    for index in range(256):
        cursor = (cursor + state[index] * cursor + key[index % len(key)]) % 256
        state[index], state[cursor] = state[cursor], state[index]
    i = 0
    cursor = 0
    out = bytearray()
    for value in data:
        i = (i + 1) % 256
        cursor = (cursor + state[i]) % 256
        state[i], state[cursor] = state[cursor], state[i]
        out.append(value ^ state[(state[i] + state[cursor]) % 256])
    return bytes(out)


def generate_sign_value(cursor_value, mode_value, ua, alphabet=SIGN_ALPHABET):
    key = [int(cursor_value / 256), cursor_value % 256, mode_value % 256]
    encrypted = bdms_stream_transform(ua.strip().encode("utf-8"), bytes(key))
    return encode_abogus_payload(encrypted, alphabet)


def is_abogus_shape_smoke(value):
    """Reject obvious garbage; this does not validate the BDMS algorithm."""
    if len(value) != 192 or not re.fullmatch(r"[A-Za-z0-9+/=_-]+", value):
        return False
    if "=" in value[:-2] or value.count("=") > 2:
        return False
    return len(set(value.rstrip("="))) >= 16


def extract_abogus_from_url(url):
    parsed = urllib.parse.urlparse(url)
    values = urllib.parse.parse_qs(parsed.query).get("a_bogus")
    return values[0] if values else ""


# Keep the production implementation in the target workspace's pure_abogus.py.
# This template intentionally includes only the core primitives plus constants.
# The notes are maintenance hints, not a complete packing/field specification.
