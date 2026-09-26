# Crypto Patterns

Use this file when signatures, encryption, or helper outputs look suspicious.

## Contents

- [Standard-looking helpers that are often not standard](#standard-looking-helpers-that-are-often-not-standard)
- [Fast recognition checklist](#fast-recognition-checklist)
- [Fixed-input validation loop](#fixed-input-validation-loop)
- [Cross-runtime porting loop](#cross-runtime-porting-loop)
- [Modified standard digest family](#modified-standard-digest-family)
- [JS to Python bitwidth traps](#js-to-python-bitwidth-traps)
- [RSA ciphertext encoding is part of the contract](#rsa-ciphertext-encoding-is-part-of-the-contract)
- [Signature, key-exchange, and national-crypto formats](#signature-key-exchange-and-national-crypto-formats)
- [Common failure modes](#common-failure-modes)
- [Delivery rule](#delivery-rule)

## Standard-looking helpers that are often not standard

- `md5`
- `sha1`
- `sha256`
- `sm3`
- `btoa`
- `atob`
- `hmac`
- `aes`
- `rsa`
- `sm2`
- `sm4`
- `ecdsa`
- `ecdh`
- `xxhash`
- `murmurhash`

## Fast recognition checklist

- length matches a common digest size
- alphabet matches hex, Base64, URL-safe Base64, or a custom alphabet
- padding matches a standard encoder
- output changes with timestamp, page, or session state
- helper reads DOM, globals, or side-script state
- output is digest plus a short suffix digest, checksum nibble, or version fragment
- a UUID, nonce, or session value looks standard at first glance but contains an inserted fixed-width segment, prefix, or checksum-derived fragment
- the apparent key, iv, seed, or hash source comes from slicing, concatenating, trimming, or decorating a config field instead of using it directly
- a named national or textbook digest fails fixed-input parity while still producing the expected bit length

## Fixed-input validation loop

When request signatures also depend on method and body serialization, the fixed sample must freeze those exactly. A signature that validates against a nearby regenerate route is not proof for first-create if method or body placement differs. The signer must cover the real method and the real serialized query or body used on the wire.

1. freeze a tiny input such as `"abc"`
2. freeze a live input such as a captured timestamp
3. compare browser output with local output
4. compare intermediate strings, not only final digests

## Cross-runtime porting loop

When porting JS logic to Python or another runtime:

1. freeze the same config blob, timestamp, nonce, UUID source, and fingerprint vector
2. compare normalization outputs first, such as compact JSON, sliced key material, prefixed payloads, or checksum inputs
3. compare the final cookie, token, or sign output only after the intermediate forms match
4. keep one deterministic parity vector before trusting live traffic
5. when a browser-only branch exists, reproduce that branch locally before porting constants into Python

## Modified standard digest family

Treat `md5`, `sha*`, and `sm3` names as untrusted labels until fixed samples match.

Locate the implementation first, then diff against the standard algorithm in this order:

1. IV or initial chaining value
2. round or message constants such as `Tj` / `K`
3. string-to-bytes or packing helpers, including per-byte masks
4. compress-step masks that replace modular arithmetic
5. expand, FF/GG, P0/P1, padding, and final hex encoding

Working method:

1. freeze one captured preimage and one wire digest
2. search for environment branches such as `typeof X === "function" && String(X) === "function X() { [native code] }"`
3. record the browser-branch constants and helpers separately from any Node or fallback branch
4. port the browser branch first; do not average branches
5. keep standard parts only after each has matched on the fixed sample

Do not promote one challenge's constants into a global "modded SM3" recipe. Preserve the checklist and the parity method, not the one-off IV table.

## JS to Python bitwidth traps

These are recurring port failures when a JS digest is moved into Python:

- `>>> 0` becomes `& 0xFFFFFFFF`; apply the mask after every arithmetic step that JS would force into uint32
- `ROTL(x, n)` must normalize `n %= 32` and treat `n == 0` as identity. Naively writing `((x << n) | (x >> (32 - n)))` breaks when `n == 0` because Python `x >> 32` is `0`, while JS `x >>> 32` is equivalent to `x >>> 0`
- `~x & z` with a bounded positive `z` usually needs no special case beyond a final `& 0xFFFFFFFF`
- per-byte masks such as `& 0xfe` must apply to every emitted byte, not only the first code unit
- mask-before-shift order matters; preserve `sum & mask` versus `(sum >>> 0) & mask` exactly as the page does

Minimum port self-check:

1. one fixed preimage from the live request
2. browser or Node-branch digest
3. Python digest
4. at least one intermediate word or masked byte string when the final hex still disagrees



## RSA ciphertext encoding is part of the contract

When a login or bootstrap page ships an RSA modulus and exponent:

1. parse the current page values; do not assume they are stable forever
2. encrypt with the page's padding scheme, commonly PKCS#1 v1.5 for legacy forms
3. encode the ciphertext exactly as the page does before putting it into the wire field

Encoding traps:

- the page may require hex, Base64, URL-safe Base64, or another alphabet
- a 2048-bit RSA ciphertext is 256 bytes; hex is 512 characters, while standard Base64 is shorter
- wrong encoding often surfaces as a fake business error such as bad password or system exception

Fixed-input method:

1. freeze modulus, exponent, plaintext password or placeholder, and the page's ciphertext
2. match encoding and letter case before blaming the account
3. keep the verified encoder next to the collector's login path

## Signature, key-exchange, and national-crypto formats

Treat the primitive name and the wire representation as separate claims.

### SM2 and SM4

- Distinguish SM2 signatures from SM2 public-key ciphertext. A pair of signature integers is not a `C1C3C2` or `C1C2C3` ciphertext.
- Record the SM2 curve, public-key prefix and point encoding, user-id input when signing, ciphertext component order, and final hex/Base64 framing.
- For SM4, freeze mode, key bytes, IV, padding, plaintext encoding, and output alphabet. `ECB` versus `CBC`, zero padding versus PKCS#7, and text keys versus decoded key bytes are independent dimensions.
- Require one published known-answer vector for the primitive and one captured envelope vector for the application-specific framing.

### ECDSA and ECDH

- For ECDSA, record curve, message-versus-prehash input, hash, deterministic or random nonce behavior, low-S normalization, and whether the wire value is ASN.1 DER or fixed-width raw `r || s`.
- For ECDH, record curve, compressed or uncompressed public-key encoding, peer-key validation, shared-secret width, KDF, salt/info/context, and the exact slice used as the downstream key.
- A matching shared secret does not prove a matching envelope. Compare KDF output, nonce/IV construction, authenticated data, tag placement, and ciphertext encoding separately.

### Non-cryptographic hash families

For xxHash, MurmurHash, and similar checksums, freeze algorithm variant, seed, input bytes, signed/unsigned interpretation, bit width, byte order, avalanche output, and final text encoding. Do not infer a cryptographic authenticity guarantee from a checksum-shaped field.

### Hybrid envelope checklist

When a payload combines symmetric encryption with RSA, SM2, ECDH, or another key wrapper, split and verify:

1. normalized plaintext bytes
2. generated or derived content key
3. nonce or IV
4. ciphertext and authentication tag
5. wrapped key or ephemeral public key
6. component ordering and length prefixes
7. final JSON, protobuf, hex, Base64, or custom-alphabet envelope

Keep keys and captured ciphertext task-local. Promote only the layout and verification method.

## Common failure modes

- standard Base64 library used against a patched alphabet
- standard MD5 or SM3 used against a custom string-to-word packing step
- URL-encoding mismatch before hashing
- wrong timestamp precision
- hidden page or session state included in the input
- correct hash function applied to the wrong JSON serialization, item order, or compactness rule
- standard UUID or random hex used where the protocol expects a structurally constrained local identifier
- apparent key or iv used directly when the page normalizes it through slice, concat, trim, or wrapper removal first
- recomputing an accepted bundle or version hash from current file bytes when the client actually uses an embedded compatibility id
- standard library digest used because the name matched, while IV, round constants, or compress masks were rewritten
- Python ROTL or uint32 truncation that only fails on some pages or some `j` values
- RSA ciphertext encoded with the wrong alphabet or case after a correct encrypt step

## Delivery rule

Do not call crypto "done" until fixed-input self-checks are in the collector and any cross-runtime port has at least one deterministic parity vector.
