# Session Contract Playbook

Use this reference when:

- the page mentions `sessionid`, login, or per-user answers
- fetch and submit appear to need the same account state
- one request works anonymously while another fails without login
- one authenticated session can still switch current tenant, shop, org, locale, supplier, or workspace context without a fresh login
- login succeeds but business data still depends on an extra activation or scope selection

## Core rule

Session state is a protocol contract, not a browser convenience.
Page text is not proof that a cookie enters the signer preimage.
Account login is not automatically the same gate as business-context activation.

## Working method

1. verify whether the data request depends on login, submission depends on login, or both
2. treat page warnings about `sessionid` or login as hypotheses only; prove them from wire behavior
3. capture the same business route with and without the claimed cookie or header
4. record whether the answer is account-bound
5. if the account can still change tenant, role, shop, supplier, or data-range after login, read `references/multi-context-session-playbook.md`
6. keep fetch and submit on one explicit session chain when the answer or permission is account-bound
7. expose required session inputs in the collector instead of hiding them inside a browser profile
8. separate list or detail collection from submit-account requirements when the wire shows they diverge
9. when durable cookies are reused, re-validate the active business identity before scraping

## Layer checklist

When login is only the first gate, name these layers explicitly:

- account authentication
- tenant or product space
- role or merchant type
- data-range or resource scope

A home page that loads is not proof that every required layer matches the task.

## Common traps

- assuming login is irrelevant because one endpoint works once without it
- assuming every request needs login because the page text says so
- treating account cookies as a universal key for every business page
- hardcoding a rotating session cookie into a signer preimage without fixed-sample proof
- mixing anonymous collection with account-bound submission without documenting the boundary
- blaming the signer when the only missing piece is the account chain used at submit time
- exporting cookies after login but before business-context validation
- sharing one session across concurrent context switches

## Delivery rule

The collector should expose the required session inputs and document whether the result is account-bound.
If list collection is anonymous and only submit needs login, encode that split explicitly.
If business identity has multiple mutable layers, document the activation order and the final identity reread used as the acceptance gate.
