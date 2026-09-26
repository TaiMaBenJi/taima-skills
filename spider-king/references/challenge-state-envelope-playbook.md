# Challenge State Envelope Playbook

Use this playbook when entry HTML and challenge JavaScript seed environment-bound state before business replay works, when a business response itself returns a machine-readable refresh contract that must be consumed before retry, and when several later fields appear to share one encoded envelope family.

## Contents

- [When to route here](#when-to-route-here)
- [API-body challenge HTML variant](#api-body-challenge-html-variant)
- [Core idea](#core-idea)
- [Fast execution path](#fast-execution-path)
- [High-value checks](#high-value-checks)
- [Dual gate note](#dual-gate-note)
- [Common traps](#common-traps)
- [Delivery guidance](#delivery-guidance)
- [Minimal handoff notes](#minimal-handoff-notes)

## When to route here

Route here when one or more of these symptoms appear:

- first-page HTML plus challenge JS must run before token or business requests stabilize
- a business endpoint returns a machine challenge, subcode, or refresh tuple that must be consumed before retrying the same request family
- a derived cookie, storage item, or preflight token appears after challenge execution and gates later requests
- URL query, form body, response body, and cookie all look structurally related
- the same target uses a version marker, checksum, custom alphabet, dynamic prefix, or inner encrypted payload across several fields
- a business preflight or token endpoint returns the same encoded family as the later business endpoint
- decrypting one field is not enough because another field still needs current state bytes, storage state, or challenge output

## API-body challenge HTML variant

Also route here when:

- a business JSON API returns `Content-Type: text/html` with challenge chrome such as inline bootstrap state, meta tags, and a linked challenge script
- the first request has no long verifier param and fails; the second request carries a long URL-bound param and succeeds
- app-layer request signing may exist in parallel but is not automatically the same gate as the HTML challenge

In this variant, prefer:

1. same-session challenge harvest
2. local challenge executor if needed
3. Python replay of the rewritten URL or derived cookies

Do not begin with deep reverse of an unrelated short signer only because it writes a similar-looking parameter name.

## Core idea

Challenge output is protocol state, not decoration.
A response-side refresh tuple is part of that protocol state, not a generic error payload.
When one target reuses the same envelope family across URL, body, response, and cookie, separate packet framing from inner crypto and prove both.

## Fast execution path

1. Freeze one fresh two-stage trace.
   Save:
   - entry HTML
   - challenge script URLs or inline challenge code
   - linked config JS or encrypted bootstrap blobs when present
   - initial cookies
   - post-challenge cookie and storage state
   - one failing business response that carries refresh fields when present
   - one preflight token request and response when present
   - one business request and response

   Keep all of those artifacts on one session chain unless reuse is separately proven.
   Do not splice entry HTML, initial cookies, challenge scripts, generated cookie state, preflight tokens, and business replay from neighboring sessions just because their shapes still look compatible.
   If the failure page points to a config asset or encrypted bootstrap variable, freeze that asset on the same session chain too instead of redownloading it later from a detached client because the URL looked static.
   If the same business route first returns a machine challenge and then succeeds after local refresh, freeze that fail -> refresh -> success triplet before searching for alternate endpoints.
   Before broad environment patching, pagination scaling, or runtime-shrink work, prove one minimal business replay on that exact fresh chain.

2. Separate seven proof layers.
   Keep these as distinct questions:
   - bootstrap-config decode
   - environment model
   - state transition
   - packet framing
   - key normalization
   - inner cipher
   - business plaintext or decoded JSON

3. Map the envelope family once.
   For each related field, record:
   - wire field name
   - version marker or fixed prefix
   - checksum scope
   - alphabet or byte remap
   - state-derived prefix or slice
   - inner encrypted segment
   - payload anchor or parser rule

4. Prove state dependency explicitly.
   Check whether the URL param, body field, or cookie can be rebuilt from business plaintext alone, or whether they also need current state bytes, storage state, challenge outputs, or a response-side refresh tuple from the immediately previous failure.

5. Validate the family with small checkpoints.
   Use exact checks such as:
   - cookie length or segment count
   - token length or format
   - checksum OK
   - expected prefix length
   - JSON anchor found
   - expected schema keys present

## High-value checks

- Verify whether several fields share one custom alphabet or packet prefix instead of independent encoders.
- Verify whether the business response itself acts as the refresh oracle: same URL fails with a machine challenge, local refresh consumes that tuple, and the same URL then succeeds.
- Verify whether the checksum covers plaintext, ciphertext, framed body, or the whole outer packet.
- Verify whether the response payload starts at byte zero or only after a fixed or state-derived prefix.
- Verify whether a linked config JS or short bootstrap blob hides encrypted config that later expands into keys, ivs, salts, cookie names, or compatibility constants.
- Verify whether the apparent AES key or iv is direct, sliced, concatenated, wrapped, XOR-masked, length-decorated, or otherwise normalized before use.
- Verify whether the preflight token response uses the same decode chain as the later business response.
- Verify whether the environment-bound cookie is just a stored token or a structured packet with several typed segments.
- Verify whether the server returns only seed fields while the decisive replay token remains locally derived and must be merged back into the same cookie or header bundle.
- Verify whether session-like or fingerprint-like cookies are locally minted from UUID variants, fingerprint vectors, or config-derived constants instead of server-issued as opaque values.
- Verify whether an accepted bundle hash, version tag, or compatibility token is an embedded constant rather than the digest of the file you just fetched locally.

## Dual gate note

App signer gates and challenge verifier gates can be independent:

- browser XHR may require both
- challenge-retry replay may require only the verifier artifact
- recovering one gate never proves the other

Record both gates separately in handoff notes.

## Common traps

- treating the cookie as a copied browser value instead of a reproducible protocol artifact
- treating an application-level challenge subcode as a generic failure and hunting a new endpoint before retrying the same route with refreshed state
- mixing entry HTML, cookies, challenge code, generated state, or preflight tokens across sessions because each artifact still looks fresh in isolation
- leaving the fresh challenge chain to chase offline environment patches before one minimal live replay is proven
- proving only the inner cipher and missing the outer version, checksum, or alphabet layer
- assuming the URL param and body field are unrelated when they are siblings in one packet family
- parsing decrypted bytes as JSON immediately when the real payload starts after a prefix
- assuming business plaintext alone can rebuild the request while hidden state bytes still affect the outer envelope
- updating only the derived token while leaving its seed, timestamp, version, or name fields stale, or updating the seed fields without regenerating the dependent replay artifact
- using the right entropy class but the wrong structure, such as a plain UUID where the client inserts check digits, prefixes, or fixed-width segments
- recomputing a compatibility hash from local asset bytes when the runtime actually uses an embedded id or normalized constant

## Delivery guidance

Preferred delivery shape:

1. Python collector with explicit staged bootstrap: entry, local challenge execution, preflight token when needed, business request, local response decode
2. tiny local JS helper only for unrecovered challenge or packet-family logic when Python porting is not yet cheaper
3. no browser dependency in the final path

When the route itself returns a machine refresh contract, the staged path may be:

`business request -> parse refresh tuple -> local refresh helper -> retry same request -> local response decode if needed`

## Minimal handoff notes

Report these items explicitly:

- which challenge output becomes protocol state
- which response-side refresh tuple, if any, must be consumed before retrying the same route
- which bootstrap config fields or normalized constants drive keys, ivs, checksums, or minted cookie structure
- which cookie, storage item, token, or header is derived from that state
- which fields belong to the same envelope family
- exact packet-family order: version, checksum, alphabet, prefix, cipher, payload anchor
- which later fields still depend on current state bytes
- which artifacts, if any, were proven reusable across sessions
- which fixed checkpoints prove local reconstruction is correct
