# Native Transport Profile Playbook

Use this playbook only after `transport-pre-gate-playbook.md` proves that the
target route is transport-gated and the closest available client backend cannot
express the browser profile that admits the route.

## Contents

1. Entry gate
2. Evidence authority
3. Capture contract
4. Canonical profile model
5. Backend selection ladder
6. Source-to-runtime translation
7. Native helper contract
8. Verification gates
9. Randomness and profile coherence
10. Version drift and maintenance
11. Common traps
12. Delivery record

## Entry gate

Do not build a native transport merely because a target mentions JA3, JA4, a
CDN vendor, or browser fingerprinting. Enter this playbook only when all of the
following are true:

- a clean browser baseline reaches meaningful application semantics
- a plain client and at least one closer impersonation backend reach a
  different branch or die before application semantics
- the decisive difference is narrowed to TLS, ALPN, negotiated HTTP version,
  HTTP/2 behavior, or connection reuse rather than cookies, signer state, or
  payload bytes
- packet or runtime evidence identifies a profile surface that the current
  backend cannot express
- a route-local native adapter remains smaller than browser-backed delivery

Record the blocked route family and keep the exception route-local until wider
evidence proves that every route needs it.

## Evidence authority

Resolve transport evidence in this order:

1. repeated live packet captures from the real browser build
2. live browser network and connection diagnostics
3. candidate-backend packet captures
4. actively shipped browser configuration and runtime feature state
5. source code for the exact browser, TLS library, and platform build
6. library documentation, presets, and fingerprint databases
7. names, remembered hashes, blog posts, and vendor folklore

Source explains runtime. It does not overrule runtime. An implemented cipher,
named group, or extension enum is not proof that the browser advertises it.
Policy, platform support, feature flags, enterprise configuration, and library
build options can all change the emitted ClientHello.

## Capture contract

Freeze a capture manifest before implementation:

- browser family, exact build, release channel, operating system, and CPU
- target host, route, timestamp, network path, and proxy path
- whether a proxy tunnels CONNECT or terminates and rebuilds TLS
- cold connection, reused connection, and resumed-session status
- negotiated TLS version, ALPN, and HTTP version
- raw capture path and hash
- whether ECH, GREASE, extension permutation, or experiment flags were active

Capture at least three clean cold connections from the same browser build.
Use them to classify each field as:

- stable and exact
- stable in membership but variable in order
- variable by defined browser-family behavior
- connection-state dependent
- route or origin dependent
- unknown

Do not call ordinary browser variation random. Preserve only variability that
repeated captures prove.

## Canonical profile model

Store the target profile as structured data rather than one JA3 or JA4 string.
Include only observed fields and preserve raw ordering.

### Identity

- browser family, build, operating system, and architecture
- declared User-Agent family and relevant request identity
- proxy mode and whether TLS remains end to end

### TLS ClientHello

- legacy version and supported versions
- cipher-suite membership and order
- extension membership and order
- supported groups and key-share order
- signature algorithms and certificate signature algorithms when present
- ALPN offerings
- compression methods, EC point formats, padding behavior, and record limits
- GREASE values and slots
- ECH or ECH GREASE behavior when observed
- session ticket, PSK, and resumption-dependent changes

The `signature_algorithms` ClientHello extension is observable unless the
relevant ClientHello fields are protected by the negotiated ECH path. Do not
drop it on the assumption that TLS 1.3 encrypts every signature surface.

### HTTP/2

- SETTINGS identifiers, values, and wire order
- connection and stream window behavior
- WINDOW_UPDATE values and timing
- pseudo-header order
- priority signaling or its explicit absence
- first request and early follow-up ordering when admission depends on it
- header compression behavior only when evidence proves it matters

### Connection behavior

- ALPN result and fallback behavior
- connection pooling and origin coalescing
- session resumption
- redirect connection reuse
- proxy tunnel reuse

JA3, JA4, and HTTP/2 fingerprint strings are derived diagnostics. Keep them in
the manifest for correlation, never as the sole source of truth.

## Backend selection ladder

Choose the nearest backend that can express the proved profile:

1. an existing maintained browser-family impersonation profile
2. narrow route-local options on that backend
3. a maintained native TLS backend with explicit TLS and H2 controls
4. a small patched native backend when one proved field is otherwise missing
5. a browser engine only as an analysis oracle, not final replay

Prefer NSS when exact Firefox runtime behavior is required and a maintainable
embedding exists. Prefer a BoringSSL-family backend when it can reproduce the
observed wire profile with fewer patches. The library name is not evidence of
browser parity; the emitted packets are.

Do not manually serialize TLS records or HTTP/2 frames when a maintained engine
can express the required behavior. Add a patch only for a field proven both
decisive and unavailable.

## Source-to-runtime translation

When reading browser or TLS-library source:

1. pin the exact source revision and build configuration
2. identify the implementation table
3. trace default enablement, policy filtering, platform filtering, and feature
   flags
4. locate ordering logic and state-dependent insertion points
5. map protocol identifiers to the destination backend's accepted names
6. record unsupported values and whether omission changes admission
7. confirm the translated profile in a packet capture

Treat backend compatibility separately from browser truth. A curve or cipher
name rejected by one backend does not mean the browser omits that protocol ID.
Conversely, a backend accepting a name does not prove that the target browser
sends it.

Keep exact browser-version vectors in task-local evidence or a versioned test
fixture. Do not promote them into universal skill doctrine.

## Native helper contract

The preferred final shape remains a Python collector with a small local native
transport package. A Rust plus PyO3 helper is one valid implementation, not a
requirement.

Expose a requests-like minimum API:

- `Session` with connection and cookie reuse
- `request`, `get`, and `post`
- query, bytes, form, and JSON bodies
- ordered or duplicate headers when the protocol requires them
- proxy, redirect, compression, certificate verification, and body limits
- separate connect and total hard timeouts
- response status, final URL, headers, bytes, text, JSON, and HTTP version

Keep the profile explicit and immutable for the lifetime of a pooled session.
Do not silently rebuild the client on every request; that destroys connection,
ticket, cookie, and H2 state.

If the user defines a suspicious-latency or honeypot threshold, cap native
connect, request, and local-helper stages at that threshold and abort without
retrying it away.

### Diagnostics

Expose non-secret diagnostics sufficient to prove the backend in use:

- backend and TLS-library version
- selected profile identifier and profile hash
- whether the profile was modified
- negotiated TLS, ALPN, and HTTP version
- new versus reused connection
- proxy mode without credentials
- elapsed time and timeout cap
- typed handshake, H2, proxy, and body-limit failures

Never log proxy credentials, cookies, authorization values, session tickets,
or raw secret-bearing request bodies.

### Packaging

- pin the Rust, native library, PyO3, and build-tool versions that affect ABI or
  wire behavior
- build a wheel for the required Python and platform ABI
- keep native binaries inside the package rather than relying on developer
  machine paths
- load the packaged backend from a clean process and clean virtual environment
- record backend version and wheel hash in the proof manifest
- test missing-library and wrong-architecture failures explicitly

## Verification gates

Pass every applicable gate before calling the profile complete.

### Gate 1: deterministic construction

- the same fixed profile produces the same normalized stable fields
- GREASE values may differ only in proved slots
- no request-time randomizer changes ciphers, ALPN, or H2 behavior without a
  captured browser-family rule

### Gate 2: packet parity

- capture the candidate backend on the same network path
- compare raw TLS and H2 fields, not just summary hashes
- explain every remaining mismatch as observed variability, route state, or a
  deliberate unsupported field
- use `scripts/transport_profile_diff.py` for normalized structured comparison

### Gate 3: neutral diagnostics

- use a neutral TLS diagnostic endpoint only to inspect what left the client
- do not treat matching a public fingerprint database as target acceptance
- confirm that a CONNECT proxy did not terminate and replace the ClientHello

### Gate 4: target admission

- run a negative control with the known-failing plain stack
- run the candidate profile on the same route and application request
- repeat fresh-process and fresh-connection acceptance at least two to three
  times
- verify real business content, not status code, body size, or a different
  challenge family alone

### Gate 5: session behavior

- prove cold connection, connection reuse, and resumption separately when used
- verify pagination or route pivots on the same session chain
- verify redirects and sibling routes do not silently switch profiles

### Gate 6: delivery

- run the final Python collector without browser automation or browser profiles
- install and import the wheel in a clean environment
- preserve hard timeouts, bounded bodies, proxy behavior, and diagnostics
- save the capture manifest, normalized profile, profile diff, wheel hash, and
  repeated replay evidence

## Randomness and profile coherence

Random fingerprints are not automatically realistic. Independent randomization
of cipher membership, extension order, groups, ALPN, or H2 settings can create a
combination no real browser build emits.

Use this rule:

- reproduce one coherent browser-family profile first
- preserve only variability observed across repeated captures
- tie correlated fields to one versioned profile
- keep proof mode deterministic
- isolate any research randomizer from the production collector

ALPN is an offered protocol list, not a percentage switch. Negotiated HTTP/2 or
HTTP/1.1 follows the offered list, server policy, and connection state. Do not
flip it per request merely to change a summary fingerprint.

## Version drift and maintenance

Treat a browser upgrade as a profile migration:

1. capture the old and new browser builds on the same route
2. diff stable and variable fields
3. identify which source or backend revision explains the delta
4. update a new versioned profile instead of mutating the old one in place
5. rerun packet, target, session, and clean-wheel gates

Do not claim a browser version from an unverified source URL or remembered
release string. Record the installed binary version and capture provenance.

## Common traps

- copying an implementation enum as the emitted cipher or group list
- matching one JA3 hash while extension slots, ALPN, or H2 still diverge
- declaring universal optimal cipher counts, request intervals, proxy classes,
  response sizes, or per-IP limits from one target
- treating every small `200` response as rate limiting rather than comparing
  response family and business anchors
- randomizing correlated fields independently
- rebuilding the native client per request and losing session behavior
- letting a proxy terminate TLS while attributing its fingerprint to the client
- shipping a wheel that loads only from the original build tree
- widening a route-local profile exception to every collector request
- calling transport admission full application success

## Delivery record

Report:

- blocked route family and negative control
- browser build and capture hashes
- stable fields and proved variable fields
- selected backend and why closer options were insufficient
- remaining profile mismatches and their evidence
- proxy termination or tunnel result
- target admission repetitions
- session reuse and pagination result
- wheel path, hash, backend version, and clean-install result
- final browser-free collector path

