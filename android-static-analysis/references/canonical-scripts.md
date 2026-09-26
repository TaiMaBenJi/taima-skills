# Canonical Script Set

Use this file first when selecting the static-analysis command path. Canonical IDs provide deterministic routing and consistent flag presets.

## Routing Order

1. Match user intent and file type (`apk`, `xapk`, `jar`, `aar`).
2. Apply `script-metadata.manifest.json` routing rules.
3. Execute the `preferred` canonical profile ID.
4. If needed, step through fallback profile IDs in order.
5. Keep `apk-*` wrappers as first choice; use direct script paths as fallback.

## Canonical Script IDs

| Script ID | Path | Family | Wrapper |
|---|---|---|---|
| `static.deps.check` | `scripts/check-deps.sh` | `dependency` | `apk-check-deps` |
| `static.deps.install` | `scripts/install-dep.sh` | `dependency` | `apk-install-dep <dependency>` |
| `static.decompile` | `scripts/decompile.sh` | `decompile` | `apk-decompile [OPTIONS] <file>` |
| `static.api.find` | `scripts/find-api-calls.sh` | `analysis` | `apk-find-apis <source-dir> [OPTIONS]` |

## Canonical Profiles

| Profile ID | Script ID | Wrapper Command | Use When |
|---|---|---|---|
| `static.decompile.jadx` | `static.decompile` | `apk-decompile --engine jadx <file>` | first pass on APK/XAPK; resource decoding required; fast overview |
| `static.decompile.fernflower` | `static.decompile` | `apk-decompile --engine fernflower <file>` | JAR/AAR analysis; complex lambdas/generics; jadx output degraded on specific classes |
| `static.decompile.both` | `static.decompile` | `apk-decompile --engine both <file>` | need side-by-side comparison; jadx warnings/errors present; high-confidence reconstruction |
| `static.api.find.all` | `static.api.find` | `apk-find-apis <sources-dir>` | full API extraction sweep |
| `static.api.find.retrofit` | `static.api.find` | `apk-find-apis <sources-dir> --retrofit` | Retrofit-focused endpoint extraction |
| `static.api.find.urls` | `static.api.find` | `apk-find-apis <sources-dir> --urls` | hardcoded URL discovery |
| `static.api.find.auth` | `static.api.find` | `apk-find-apis <sources-dir> --auth` | auth/token/header extraction |
| `static.deps.check` | `static.deps.check` | `apk-check-deps` | environment readiness verification |
| `static.deps.install` | `static.deps.install` | `apk-install-dep <name>` | install missing required or optional tools |

## Notes

- `static.decompile.jadx` is the default first pass for APK/XAPK.
- `static.decompile.fernflower` is preferred for JAR/AAR and for classes where jadx fails.
- `static.decompile.both` is the deterministic compare mode when output quality is uncertain.
- API extraction profiles are selectors on top of `find-api-calls.sh`; combine with manual source reading for complete docs.
