# tests/fixtures

Static test artifacts committed to the repository so the integration-test
suite is fully self-contained and reproducible.

## testapp — the integration-test binary

`testapp` is a small x86-64 ELF executable compiled from `testapp.c`. It
exercises libc imports (malloc, free, printf, strlen, …) and string literals
used by the test-suite's string-search assertions.

**Rebuild** (requires GCC on an x86-64 Linux host):

```sh
gcc -O0 -m64 -o tests/fixtures/testapp tests/fixtures/testapp.c
```

## dex/ — DEX/Dalvik (Android) fixtures

Raw `classes.dex` files extracted from small, real-world, CC0-1.0-licensed
Android APKs, used to reproduce DEX/Dalvik-loader-specific behavior (class
namespacing, `string_data`/`strings` symbols, class-descriptor xrefs) that a
native binary can't exercise. Each is the unmodified `classes.dex` pulled
from the upstream APK's zip container — no Ghidra project files.

| File | Source | License | SHA-256 (dex) |
|---|---|---|---|
| `detectresolution-classes.dex` | [Septillion/Detect-Resolution-Android v1.1.2](https://github.com/Septillion/Detect-Resolution-Android/releases/tag/v1.1.2) — Java + AndroidX, unminified | CC0-1.0 | `2763d45ce16ee29e5ab91d262d0ba4fe8492c07ea4c4e360e628785a5db04b01` |
| `wifi-seeker-classes.dex` | [atomofiron/android-wifi-seeker v2.2.1](https://github.com/atomofiron/android-wifi-seeker/releases/tag/v2.2.1) — Kotlin, R8-minified | CC0-1.0 | `c969647681f46a263922e8f5a340883df55995a293874ee3f4a87d0623aad051` |

**Regenerate:**

```sh
curl -fsSL -o /tmp/a.apk https://github.com/Septillion/Detect-Resolution-Android/releases/download/v1.1.2/detectresolution1.1.2.apk
unzip -p /tmp/a.apk classes.dex > tests/fixtures/dex/detectresolution-classes.dex

curl -fsSL -o /tmp/b.apk https://github.com/atomofiron/android-wifi-seeker/releases/download/v2.2.1/wifi-seeker-v2.2.1.apk
unzip -p /tmp/b.apk classes.dex > tests/fixtures/dex/wifi-seeker-classes.dex
```

Verify the SHA-256 sums above still match before committing an update.
