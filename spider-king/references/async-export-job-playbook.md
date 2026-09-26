# Async Export Job Playbook

Use this reference when the business path is not a single list request, but an asynchronous export, report, download, or batch-job pipeline.

Typical symptoms:

- the UI creates a background task, then later offers a download
- HTTP 200 on create does not mean a new task appeared
- polling accidentally reuses an older successful task
- first-create and regenerate or retry look similar but are not the same protocol
- download needs a secondary code, mailbox password, or encrypted archive
- incomplete field sets still produce a file that looks downloadable

## Contents

- [Core rule](#core-rule)
- [Default state machine](#default-state-machine)
- [Four parameter classes](#four-parameter-classes)
- [Read-only probes before create](#read-only-probes-before-create)
- [Create-success criteria](#create-success-criteria)
- [Task isolation](#task-isolation)
- [Create versus regenerate](#create-versus-regenerate)
- [Signing and serialization](#signing-and-serialization)
- [Polling](#polling)
- [Download, side channel, and artifact gates](#download-side-channel-and-artifact-gates)
- [Completeness gates](#completeness-gates)
- [Cookie invalidation boundary](#cookie-invalidation-boundary)
- [Delivery checklist](#delivery-checklist)

## Core rule

An export collector is a state machine, not one signed GET.

> HTTP 200 is not create success. The newest historical row is not automatically this run's task. A readable file is not automatically a complete export.

## Default state machine

Climb these stages in order. Prove each stage before automating the next.

1. read-only probes: count, schema or field catalog, permission check
2. optional pre-create history snapshot of known task ids
3. create or submit the export job with exact method, query, body, and content type
4. prove a new task id exists and matches this run's filters
5. poll status until terminal success or failure
6. download precheck
7. secondary verification or async side-channel material when required
8. download bytes
9. decrypt or unpack when required
10. parse records
11. completeness gates before persistence
12. bounded cookie or session refresh only on explicit auth failure

Do not start with the full chain on a live account. Validate read-only stages and offline helpers first.

## Four parameter classes

Classify every moving part before designing the signer or hardcoding values.

1. **Business parameters**  
   Operator filters and export choices: date range, report type, selected fields, file type, dimension.

2. **Static application parameters**  
   Stable app or channel constants that the page always sends for this product surface.

3. **Server or SDK issued parameters**  
   Tokens, web ids, task download tokens, or other values returned by prior endpoints or local SDK helpers. Refresh them from their writer path.

4. **Per-request dynamic parameters**  
   Nonces, timestamps, fingerprint slots, and request signatures that change each call.

Judgment cues:

- survives page refresh: likely session or app static
- changes every request: likely dynamic or signed
- changes when body changes: signature may cover body serialization
- can be fetched from a prior endpoint: do not invent it
- deletion causes risk or auth failure: admission or session material

## Read-only probes before create

Before any create call:

1. prove the filter query that defines the business slice
2. fetch available export fields or schema when the product supports custom columns
3. check whether export is currently allowed
4. snapshot current historical task ids when history is visible

If the filtered count is zero, short-circuit without creating a job.

## Create-success criteria

Accept create only when at least one hard proof holds:

1. the create response returns a new task id, or
2. history gains a task id that was absent from the pre-create snapshot

And the accepted task must match this run's business condition, such as:

- time range
- report type or dimension
- file type
- selected field set

Reject these false positives:

- HTTP 200 with no new task
- empty success envelope
- regenerate or retry route evidence used as first-create proof
- signing against a different method or body than the live request

## Task isolation

Never select work by "first row" or "most recent success" alone.

Selection priority:

1. task id returned by the create response
2. otherwise a task id absent from the pre-create set
3. require condition match against this run's filters and field set

Forbidden:

- reusing a pre-create successful task because it is convenient
- accepting a task whose filters or field set differ
- treating regenerate-of-old-task as proof of first-create protocol

## Create versus regenerate

First create, regenerate, retry, and download may share a path family and still differ in:

- method
- whether filters live in query, JSON body, or form body
- which fields the signer covers
- whether a prior `task_id` is required

Capture first-create separately. Do not promote regenerate traffic into the create contract until wire evidence shows they are identical.

If first-create method or body placement is still unproven, keep that boundary open in reports. A working historical regenerate path is not enough.

## Signing and serialization

When a local helper mints risk or signature params:

1. Python owns live business HTTP
2. the helper only returns the dynamic params or rewritten URL materials it must produce
3. fixed-input checks cover the same method and serialized body or query the wire uses
4. host and path must not drift across the helper boundary
5. missing required session fingerprint or cookie slots should fail loudly

If create fails with risk language after a plausible signature, first re-diff method, content-type, body placement, and the exact string covered by the signer.

## Polling

Poll with explicit limits:

- max attempts
- sleep interval
- terminal success and failure codes

Keep using the isolated task id. Do not re-query history and silently switch to another row mid-wait.

## Download, side channel, and artifact gates

Download precheck may return:

- direct file metadata
- a secondary verification challenge
- an auth or risk page disguised as 200

For async side channels such as mailbox or SMS:

1. record cursor, latest message id, or timestamp baseline before triggering send
2. trigger the product-specific send endpoint
3. accept only fresh messages after the baseline
4. distinguish scene-specific code shapes; a login code length or sender is not automatically valid for download

After bytes arrive:

1. verify magic or content type expected for the artifact family
2. decrypt or unpack with the material bound to this run
3. parse records locally
4. apply completeness gates before storage

## Completeness gates

At minimum compare:

- requested field count versus downloaded column count when custom fields were requested
- required business key presence
- row count sanity against earlier probes when available

If the file is readable but thinner than requested, fail closed and do not persist.

This catches:

- dropped field arrays in create serialization
- wrong historical file
- default-column fallbacks

## Cookie invalidation boundary

Normal export should not start by driving a login UI.

On explicit auth-failure signals only:

1. stop the current business attempt
2. invoke the external login or cookie refresh path once under a lock if multi-worker
3. reload durable cookies
4. retry the current unit a bounded number of times

Do not merge full login automation into the export collector's steady state.

## Delivery checklist

Call an async export collector done only when:

1. the state machine is explicit end to end
2. parameter classes are named and regenerated from the right writers
3. first-create method and body placement are proven or explicitly unproven
4. create success uses new task proof plus condition match
5. polling cannot select historical pollution
6. signer coverage matches real method and serialization
7. side-channel baselines prevent stale code reuse
8. artifact format and field-completeness gates block bad files
9. cookie refresh stays out of band and bounded
10. delivery remains browser-free; local helpers may mint request params only
