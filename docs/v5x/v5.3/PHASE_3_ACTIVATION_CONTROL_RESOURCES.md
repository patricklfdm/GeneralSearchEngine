# Phase 3: original activation controls and reply callers

Status: stable native evidence entry added; Phase 3 remains OPEN.

The activation endpoint's CONTROL observation name now includes the original
request digest and a unique allocation nonce, matching its existing WAITER
binding. These are process-local correlation labels, not wire authority. Old
UUID-only control observations cannot be backfilled or accepted by the strict
reader. No wire/storage format, quota, retry count or deadline changes.

Caller cleanup now releases the WAITER before releasing its retired CONTROL
reference under the same registry, keeping the cached bytes charged through
every admitted waiter release. Both releases still precede endpoint caller
drain. The existing retired-control, capacity and close tests remain separate
runtime regressions; the labels themselves establish no physical fact.

## Independent reader

`scripts.v53.activation_control_resources` consumes independently qualified
physical history, exact connected request/response bytes, direct local PUBLISH
observations, original publication transactions and resource transitions. It:

- Binds each control reservation to the exact original request extent, its
  single cache growth to request plus response bytes, and its final release.
- Requires the original caller to hold the task through response completion;
  all duplicates retain their own zero-byte waiter inside distinct original
  handler intervals. Cached request/reply bytes stay charged through every
  associated waiter release, even when the cache outlives its first response.
- Requires original PREPARE promise/basis/grant and SELECTED install boundaries
  inside their control work. Native slot children and all four physical
  publications remain inside their original control and caller custody.
- Preserves failed and unconnected attempts. A lost response with an original
  server reply can share the same cached control; a failed server handler is
  outside this successful-history scope and cannot silently disappear.
- Allows a direct already-published PUBLISH acknowledgement only when the same
  original physical publication completed before that response was offered,
  with its original view, ballot and acknowledgement payload. The request may
  have arrived earlier and waited for the journal writer. The actual publishing
  call still needs its complete physical control/caller interval; a later or
  merely matching certificate cannot replace it.

An iterative bipartite matcher first covers mandatory ordinary calls, then
matches remaining waiters without consuming an ordinary call's only witness
for an optional fast response. It is checked against exhaustive assignments
over 1500 deterministic small interval sets. Neighbours are visited on demand,
without a quadratic relation table or recursive call stack. This proves compatible injective
coverage, not which identical socket scheduled a particular duplicate.

`native_resource_evidence --activation-control` composes the reader with the
existing physical, voting and slot readers. The original-first negative entry
also requires source, export and cleanup authority:

```bash
python3 -m scripts.v53.activation_control_resource_negatives /path/to/original-native-evidence
```

The entry validates the unchanged original before testing any mutation and
checks its complete inventory again afterward. All 20 coherent mutations must
fail for their exact expected reason. They cover wrong extents/bindings,
omitted or invented controls/waiters, reused identities, missing/extra growth,
growth before durable work, early release, missing grant/publication authority
and broken child/publication custody. Raw evidence is never edited.

## Retained evidence and limits

The [development receipt](phase3-evidence/activation-control-resources.json)
records one fresh native two-slot execution, its exact replay and regression
results. That history has 12 cached controls, 14 activation waiters, 15 original
calls including two direct local calls, one fast publication reply, ten slot
children and four original physical publication transactions. Two duplicate
callers share original controls; a further repeat uses the direct published
reply. These are not new durable votes. The original runtime
was executed once; reader corrections replay the same retained evidence.

The first reader attempt incorrectly required publication completion before
socket arrival; the original trace demonstrates the legitimate writer-lock
wait described above. A later negative-driver correction selects an incoming
grant owned by an activation control, rather than an earlier local campaign's
grant. Those intermediate failures remain retained and are not passing evidence.

This qualifies the observed stable activation CONTROL/WAITER roles. It does not
qualify interrupted handlers, arbitrary retired-cache schedules, joining and
failure histories, every other runtime allocation, simultaneous physical maxima
or the final-source cohort. The complete 544-history plan, exact Phase 3
coverage and phase closure remain OPEN.
