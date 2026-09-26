# Multi-Context Session Playbook

Use this reference when a target is not finished after account login, because the same account still has mutable business context.

Typical symptoms:

- login succeeds, but list or export data belongs to the wrong shop, tenant, supplier, org, or data range
- UI selection of a Chinese or localized label must be converted into protocol codes before activation
- a switch or update API returns HTTP 200 or `success`, yet the final page still shows the previous context
- concurrent jobs that share one session start reading each other's context

## Contents

- [Core rule](#core-rule)
- [Identity layers](#identity-layers)
- [Two success gates](#two-success-gates)
- [Silent incomplete activation](#silent-incomplete-activation)
- [UI labels are not protocol ids](#ui-labels-are-not-protocol-ids)
- [Handoff artifacts versus durable cookies](#handoff-artifacts-versus-durable-cookies)
- [One session chain, final jar export](#one-session-chain-final-jar-export)
- [Pre-collection identity probe](#pre-collection-identity-probe)
- [Concurrency rule](#concurrency-rule)
- [Failure classes](#failure-classes)
- [Delivery checklist](#delivery-checklist)

## Core rule

Login proves who the account is.
Business activation proves which context that session is allowed to act as.

These are different success gates.

> Login success is not business-identity success. Opening a home page is not proof that the target data range is selected.

## Identity layers

Model the session as stacked mutable layers. Names vary by product; the layering does not.

1. `account`: authenticated principal
2. `tenant` or product space: which business world is active
3. `role` or merchant type: which operator class is active
4. `data-range`: which shop, supplier, warehouse, org unit, or scoped resource is active

A durable collector must name each required layer, the endpoint that sets it, and the final field used to verify it.

## Two success gates

### Gate A: account login

Prove only that the account chain completed:

- login form or bootstrap parsed when dynamic
- credentials or token exchange accepted
- short-lived handoff artifacts consumed when required
- account-level cookies or tokens now exist on one session chain

Do not export credentials or call the task complete at Gate A if Gate B is required.

### Gate B: business-identity activation

Prove the final active context matches the task config:

- tenant or product space
- role or merchant type
- data-range type and value when the API distinguishes them
- any secondary scope the business page actually uses

Fail closed if any required layer is missing, ambiguous, or stale.

## Silent incomplete activation

Some platforms accept a partial update without a hard error.

Common shape:

- tenant looks correct
- role looks correct
- data-range type or value was omitted or only partially submitted
- final session still has an empty, default, or previous data-range

Treat this as a first-class failure mode, not as "probably fine".

Working method:

1. freeze the exact activation payload that the successful UI path sends
2. separate type fields from value fields; both may be required
3. do not trust only the switch API envelope
4. reread identity from an authoritative final surface such as a business page bootstrap blob, session introspection endpoint, or equivalent
5. compare every required layer to the task config before saving cookies or starting collection

## UI labels are not protocol ids

Display names are for humans. Protocol activation usually needs codes, resource ids, or authorization values.

Working method:

1. use the operator-facing label only to locate a candidate in a live authorization or enumeration response
2. submit the protocol id returned by that live response
3. require an unambiguous match count of exactly one
4. stop on zero matches: usually missing authorization or renamed label
5. stop on multiple matches: do not silently pick the first row

Never copy another account's resource value or a historical id unless the current authorization response still returns it for this account.

## Handoff artifacts versus durable cookies

Login responses may return short-lived transfer material such as:

- one-time tickets
- secondary tokens
- async continuation URLs
- parent or cross-domain redirects

These are session handoff artifacts.

Rules:

- consume them on the same session chain that will own the final jar
- follow the minimum redirect and async sync set required by the wire
- do not store handoff artifacts as long-lived collector credentials
- export cookies only from the final validated session state

## One session chain, final jar export

Final cookies are usually the accumulation of many steps:

1. login-page seed cookies
2. login POST cookies
3. async or cross-domain sync cookies
4. business proxy or auto-login cookies
5. session-update cookies
6. final business-page cookies

Therefore:

- keep login, handoff, activation, and final identity reread on one HTTP session object
- do not create a fresh empty client for each hop unless you intentionally fork contexts
- export from the final cookie jar after Gate B passes
- if local cookie reuse is supported, re-validate identity on reuse instead of assuming the file still matches the intended context

## Pre-collection identity probe

Before the first business scrape or export on a reused session:

1. run one cheap identity check
2. confirm tenant, role, and data-range against the task config
3. stop immediately on mismatch
4. do not continue and later guess ownership from payload content

Collection code should consume an already validated context. It should not silently repair the wrong shop mid-run.

## Concurrency rule

One mutable business context per session.

If the task must cover multiple shops, suppliers, or data ranges:

- create one session per context
- activate and validate each session independently
- do not share one jar across workers and keep switching context underneath them

Shared switching is a data-mix bug factory.

## Failure classes

Classify stop conditions instead of infinite retry:

- `network_error`: limited backoff may be acceptable
- `captcha` or interactive challenge: stop for a dedicated verifier path or human handling
- `need_verify:*`: stop and report the required verification mode
- `protocol_activation_failed:*`: re-check authorization and activation payload; do not high-frequency replay
- `identity_mismatch`: refuse to export or scrape
- `cookie_export_invalid`: keep the previous durable file if a refresh candidate fails validation

High-frequency retries after activation or verification failures increase risk without repairing protocol gaps.

## Delivery checklist

Call a multi-context login flow done only when:

1. Gate A and Gate B both pass
2. every required identity layer is explicit in code and reports
3. final identity was reread, not only inferred from a switch response
4. UI labels were resolved through live authorization with unique matches
5. handoff artifacts stayed short-lived
6. durable cookies were exported from one validated session chain
7. pre-collection identity probe exists for reuse paths
8. concurrency assumptions are documented
9. delivery remains browser-free; local helpers may mint login security params, but Python owns live HTTP
