# Symptom Heuristics

Use this file when the target is fresh, the symptom is still broad, or you need a quick family match before picking a more specific playbook.

Treat a target as belonging to a familiar family when one or more of these symptoms appear:

- page code mentions one endpoint but the wire uses another
- business code builds `token`, `sign`, or `m`, but transport wrappers rewrite it before send
- the page renders a loading shell or SSR frame with `200 OK`, but the hydration blob is empty and the real business data arrives only on a later API
- the response says `ok`, `success`, or `error=false`, but the business payload is missing or a subcode still signals rejection
- the transport is GraphQL, WebSocket frames, protobuf, msgpack, or another structured envelope rather than plain JSON
- standard helper names such as `md5`, `btoa`, `atob`, or `sha1` produce nonstandard output
- the first request returns JavaScript, cookies, offsets, or font files instead of business data
- the top page URL stays fixed and shows no obvious form, but the real auth or business flow actually lives inside an iframe or embedded frame
- the page is public, but a bootstrap endpoint still returns a public key, config blob, nonce seed, or wrapper contract before list requests work
- the page works in a fresh anonymous profile, but replay becomes flaky once logged-in cookies or unrelated account state leak into the session
- a hidden field with a server-looking name such as verification token, request id, or page id is appended by page code and any fresh format-conforming value seems accepted
- a browser-captured blob matches the expected shape, but replay only succeeds after moving it to a different transport slot such as a custom header, cookie echo, or wrapper field
- one minimal in-page or host-runtime request automatically acquires extra signer params, cookies, or headers that are missing from the same request shape when sent directly from Python
- a prehandle or bootstrap call returns session ids, work factors, asset URLs, answer schema, movement bounds, or other challenge config that the client mostly relays rather than derives
- verifier `get/load/prehandle` returns one-round token, image URLs, callback ids, or random keys, and final verify fails whenever any of them are reused from another round
- entry HTML plus challenge JS must run first to seed environment-bound cookie, storage state, or preflight token before business replay stabilizes
- local helper output stays much shorter, simpler, or more repetitive than browser output even after seeding cookie, storage, script, or resource state
- a callback or SDK init reports success, yet the decisive token field stays empty until a later network response or state write lands
- one page bootstrap writes a page-scoped cookie or storage value, while a later request computes a separate request-scoped header, param, or token
- JSONP, callback wrappers, or other non-JSON framing must be stripped before the payload becomes usable
- the code branches on environment probes such as `Object.keys(window)`, `Reflect.ownKeys`, `getOwnPropertyDescriptor`, `Function.prototype.toString`, `JSON.stringify`, or `document.all`
- the runtime touches `canvas`, WebGL, `getComputedStyle`, layout metrics, or similar native surfaces before the decisive field appears
- page HTML plus offline-loaded scripts can seed cookies, signed URL suffixes, or XHR wrapper state without full rendering or gestures
- changing only the UA major version, parser timing, or timer mode changes bootstrap order, cookie output, or token output
- standard clients die at H2 reset, TLS EOF, handshake timeout, or early disconnect, while impersonated transport, HTTP/1.1, or a mobile or app UA passes
- a bootstrap runtime exposes one synchronous getter or object method after init even though later timers or DOM probes still throw
- a challenge or bootstrap script self-issues XHR or fetch with the real wrapped body, binary payload, or decisive headers
- a top-level SDK init dies inside axios, fetch, adapter glue, or telemetry setup, yet a smaller inner export or serializer still returns the exact blob family you need
- only one page fails, often the last page
- early pages replay through one route family, but later pages pivot to a different pagination endpoint, static path, or `/ui` route even though the visible pager looks uniform
- inline `onclick`, `tagname`, template strings, or hidden pager metadata carry replay-critical URLs or params, and DOM-parsed values no longer match the raw source because of entity decoding, broken escaping, or legacy markup
- the page text says login or `sessionid` matters, and the answer differs per account
- the site ships a tiny side script or `.wasm` that looks unrelated but actually seeds signing state
- visual assets arrive as sprite sheets, RGBA cutouts, padded masks, or answer geometry whose preprocessing changes solver confidence more than signer code changes
- the business body fields decode cheaply with a fixed XOR, hex, or base64 variant while the real pain remains a separate environment-bound signer on the outer request
- one prompt image, text hint, or challenge string defines click order while a different background image defines hit geometry, and final verify packages both into encrypted coordinates
- the API returns strings, hints, glyphs, or fonts instead of the final numeric payload
- the response body is encoded, compressed, protobuf, msgpack, or split across multiple layers before it becomes usable data
- URL query, body field, response body, and cookie appear to share one packet family: version marker, checksum, custom alphabet, state-derived prefix, or the same inner cipher
- GET replay only fails when query ordering, empty-field preservation, or URL encoding diverges from the frontend-built sign input
- the same request succeeds once and then dies unless some hidden refresh state is regenerated
- a track blob, collect field, verifier sidecar, or similar behavior payload is formally present but only loosely enforced on one public or demo route
- list APIs work anonymously, but detail or submit APIs still reject without a different permission boundary
- a human-facing detail page loads fine, but the real full text still arrives through the same parse or wrapper endpoint with a different method, cfg, or identifier
- bootstrap or current-user endpoints mint a fresh session cookie successfully, yet the first real business route still returns a permission denial
- login or bootstrap returns a grant token, redirect handle, or async follow-up URLs, but the target backend still redirects to login until extra post-auth session exchanges run
- relative action paths only work when resolved against the effective entry origin, while hardcoded sibling hosts yield CSRF or credential-looking failures
- one authenticated session can switch the active tenant, shop, org, or workspace by mutating one context field while leaving the main session cookie unchanged
- sending the body as a library-native form dict or JSON fails, while replaying the exact frontend-style urlencoded bytes succeeds
- OCR or template matching finds a correct gap or click location on a restored or padded image, yet verify still fails until that position is mapped into the display or submission coordinate space
- list output contains stable ids that can feed a second-stage detail collector more cheaply than rerunning the search
- empty filter values do not reproduce the visible tab because the page injects category or mode state before send
- a trigger only starts an async side channel, and the usable code, token, approval link, or artifact arrives later through mail, SMS, webhook, queue, or delayed callback
- the same previously understood request starts returning password-like, field-like, or user-facing validation errors only after tight pacing or repeated attempts
- a login or pairing step returns a ref, QR seed, public key, or client identifier before business frames become readable
- the target keeps one long-lived WebSocket alive with auth, ack, heartbeat, or reconnect frames that must stay in order
- media metadata arrives in one place, but the actual file replay or decryption needs a separately derived key
- a challenged landing route fails, but a sibling auth, identity, or business route bypasses the same gate cleanly

- the page text says login or `sessionid` participates in signing, but the business list route already returns full data with no session cookie
- a helper is named `sm3`, `md5`, or `sha*`, standard libraries miss the fixed sample, and environment checks select alternate constants
- an obfuscator-style string table rewrite changes nothing until member-map objects are expanded and hex keys are normalized
- Python digest parity fails only on some pages because `ROTL(x, 0)` or another uint32 edge case is wrong
- login cookies exist and the home page opens, but list or export data belongs to another tenant, shop, supplier, or data range
- a context switch returns HTTP 200 or success, yet a final identity reread still shows the previous scope
- operators choose a display name, while activation requires a live authorization code or resource value with exactly one match
- concurrent workers share one session and keep switching shops or suppliers, then read each other's data
- RSA or password-login errors look like bad credentials until ciphertext encoding length or alphabet is checked
- short-lived login handoff tickets were saved as durable cookies and later fail replay
- an export or report create returns HTTP 200, but history gains no new task id
- polling immediately finds a successful task whose time range or fields belong to an older run
- regenerate or retry works, while first-create still fails or creates nothing
- downloaded file opens, yet column count is lower than the requested custom field set
- a mailbox or SMS code is accepted only when taken after a fresh send baseline, and code length differs by scene
- risk or signature errors disappear only after method, content-type, or body placement is aligned with the signer input
If the symptoms match, reuse the methodology even when the exact site and parameter names differ.

## Contents

- [JSON API returns full challenge HTML](#json-api-returns-full-challenge-html)
- [Same param is sometimes short and sometimes long](#same-param-is-sometimes-short-and-sometimes-long)
- [Impersonation changes which wall you hit](#impersonation-changes-which-wall-you-hit)

## JSON API returns full challenge HTML

If a business data route responds with HTML challenge chrome, linked challenge scripts, or inline bootstrap blobs:

- do not stop at "endpoint blocked"
- treat it as challenge-state bootstrap on the business route
- harvest redirect URL or cookies on the same session chain
- route to `references/challenge-artifact-harvest-playbook.md` and `references/local-challenge-executor-playbook.md`

## Same param is sometimes short and sometimes long

If one field name shows disjoint length bands across research and live success samples:

- assume dual writers until proven otherwise
- compare success wire shape before packaging a generator
- route to `references/dual-writer-param-playbook.md`

## Impersonation changes which wall you hit

If plain clients get one verifier wall and impersonated clients get JS challenge HTML or a cleaner route:

- fix transport admission before deep algorithm work
- keep the admitted profile on the whole challenge and replay chain
- route to `references/transport-pre-gate-playbook.md` when transport fails first
