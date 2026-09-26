# Offline Inline-Deob Playbook

Use this reference when:

- browser DevTools or `js-reverse` become unstable because of anti-debug code
- the page embeds large inline scripts instead of loading all logic from external files
- a signer depends on a packed payload such as `eval(atob(...))`
- a standard hash does not match the in-page result even though the function name looks familiar
- a request parameter contains unusual delimiters or unicode separators
- an external obfuscator.io-style bundle needs local string-table recovery before the signer is readable

## Contents

- [1. When to stop fighting the live page](#1-when-to-stop-fighting-the-live-page)
- [2. Extract the page structure first](#2-extract-the-page-structure-first)
- [3. Inline payload recovery pattern](#3-inline-payload-recovery-pattern)
- [4. String-table and rotate-IIFE recovery](#4-string-table-and-rotate-iife-recovery)
- [5. Legacy hash warning](#5-legacy-hash-warning)
- [6. Unicode delimiter safety](#6-unicode-delimiter-safety)
- [7. Practical delivery rule](#7-practical-delivery-rule)

## 1. When to stop fighting the live page

If any of these occur, switch to offline extraction instead of repeatedly poking the live runtime:

- debugger loops or `setInterval(debugger, ...)`
- console floods from anti-debug code
- MCP evaluation calls time out repeatedly
- reverse tools disconnect after page load
- one browser family cannot start because the other already owns the profile directory

Fallback path:

1. save the full HTML
2. extract all inline scripts
3. save relevant external assets
4. deobfuscate and test locally

If only one browser tool family can own the target, keep that family for wire evidence and finish static recovery offline with Node or Python. Do not invent a second live browser just to satisfy ceremony.

## 2. Extract the page structure first

Before decoding anything, record:

1. script tag count
2. inline script order
3. external script order
4. whether the page monkey-patches `$.ajax`, `fetch`, or XHR before the packed code runs

Do not assume script count is cosmetic. Some pages derive offsets from values such as:

- `$('script').length`
- DOM node counts
- element attributes
- query-string flags

These values can directly change the decoded payload.

## 3. Inline payload recovery pattern

Common sequence:

1. a giant encoded string is assigned to `window.a`
2. a loop transforms each character with an index-based offset
3. the result becomes a base64 string
4. `atob(...)` yields a second-stage script
5. `eval(...)` runs the real logic

Recommended workflow:

1. extract the encoded string and decoder
2. reproduce the exact offset math locally
3. recover the base64 payload
4. base64-decode it to the second-stage source
5. isolate only the signer or crypto section needed for replay

## 4. String-table and rotate-IIFE recovery

Use this when the saved asset is a single-line or string-table-heavy bundle:

1. preserve the raw file bytes before any rewrite
2. extract the string-array function, decoder function, and rotate IIFE with brace-aware matching that respects escaped quotes
3. run only that decoder surface locally to dump index-to-string mappings
4. rewrite in two passes:
   - expand member-map objects first
   - replace decoder(hex) call sites second
5. normalize hex keys: if the dump uses `"c7"`, match source `0xc7` by stripping the `0x` prefix
6. beautify when line-oriented reading is required; one-line files make naive line numbers useless
7. stop once the preimage, helper, or wrapper boundary is recoverable

If evaluate-style tool output was written through a JSON-serializing file path, decode the JSON string before treating the file as JavaScript source.

## 5. Legacy hash warning

Do not assume that `md5`, `sha1`, `sm3`, or similar names mean standard library equivalence.

Things to verify:

- custom `chrsz` or string-width settings
- custom string-to-word conversion
- little-endian vs big-endian assumptions
- patched constants or altered rounds
- hex encoding order
- environment-specific constant tables selected by native-function checks

If the page ships a self-contained hash implementation, preserve that implementation first. Only replace it with a standard library version after proving the outputs match on fixed inputs.

## 6. Unicode delimiter safety

If a request value contains unusual separators, keep them explicit.

Examples:

- use `\\u4e28` instead of pasting a display glyph
- use escaped strings in generated JS and Python output
- avoid trusting terminal or shell display for correctness

Why this matters:

- console output can replace the character with `?` or another glyph
- copied values can be silently corrupted by encoding
- a valid hash plus a broken delimiter still fails server validation

## 7. Practical delivery rule

For pages like this, prefer:

1. offline deobfuscation to recover the true signer
2. isolated `signer.js` that preserves the bundled hash or decoder
3. Python or Node collector that calls the isolated signer

This is usually more stable than trying to keep a hostile browser runtime alive.
