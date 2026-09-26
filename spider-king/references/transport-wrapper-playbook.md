# Transport Wrapper Playbook

Use this reference when:

- business code builds one param but the wire sends another
- `token`, `sign`, `m`, `f`, or payload fields are rewritten before send
- `$.ajaxSetup`, interceptors, fetch wrappers, or request middleware mutate headers or bodies

## Core rule

The canonical mutation point is where the wire payload changes, not where the business code first creates placeholders.

## Recognition signals

- UI code builds `token`, but the network sends `m`
- query params or body fields appear only after wrapper execution
- headers are injected in `beforeSend` or fetch middleware
- request serialization differs from the visible input object
- the candidate blob looks right, but replay only works after moving it to a different header, cookie echo, query param, or wrapper-owned field

## Working method

1. diff business-layer params against the final network payload
2. inspect wrappers before digging deeper into business code
3. record exactly which fields the wrapper adds, rewrites, deletes, or relocates
4. prove the final transport slot of each decisive artifact, not just its value shape
5. rebuild the wrapper logic locally
6. verify the final serialized payload, not just the intermediate object

## Common traps

- reversing a decoy param that never reaches the wire
- signing decoded values when the site signs URL-encoded values
- assuming visible JSON is the final signed payload
- treating a plausible blob as correct while leaving it in the wrong transport slot

## Delivery rule

Reproduce the transport-layer mutation locally and keep the decoy field out of the final collector.
