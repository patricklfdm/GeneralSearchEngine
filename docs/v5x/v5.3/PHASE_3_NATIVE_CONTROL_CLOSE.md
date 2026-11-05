# Phase 3 native cleanup binding and learner listener drain

The [component cleanup reader](PHASE_3_CONTROL_CLOSE_RESOURCES.md) is now connected
to the original short native physical/source/accounting replay. Development
evidence and exact inputs are recorded in the
[index](phase3-evidence/native-control-close.json). Phase 3 remains OPEN.

## Corrected listener lifecycle

`MembershipTransport.close()` called by its own I/O callback cancels work and
returns without waiting for that same worker. Previously, checkpoint and
learner-head endpoint `closed()` returned the resource-release flag alone.
That could advertise completed listener closure while the callback was still
running. The checkpoint owner uses this predicate when allowing a replacement
listener and when checking quiescent custody.

Both endpoint predicates now require resource release **and** the existing
`transport.drained()` predicate: acceptor and workers stopped, channels empty,
and inbound/outbound work counters zero. Callback cancellation remains
nonblocking; the external close path retains its original drain timeout.
No retry, deadline, resource bound, voting or durable-format rule changes.

Two deterministic TCP tests hold the actual cancelled callback after its close
call returns. Both fail on the original implementation and pass with the fix.
The checkpoint test additionally rejects a replacement during the held callback,
then drains externally and successfully opens a replacement. Existing owner-close
and failed-force/store-close regressions pass. These are controlled lifecycle
tests, not process-crash or native joining-history qualification.

## Cleanup records and original session ownership

Joining checkpoint cleanup now records its service, trace and session reservations
through the same bounded recorder. The service interval starts after its transport
close call, at the cleanup-performing critical section. A callback closer may
still be running at RETURNED. The cleanup annotation therefore does **not** claim
listener drain; `closed()` has that separate meaning.

The native collector opt-in `-Dv53.resource.control.close=true` requires the
existing `v53.resource.source.control`, `v53.resource.transitions` and
`v53.transport.connections` flags. It saves the original sidecar alongside the
unchanged resource journal. Independent replay uses:

```bash
python3 -m scripts.v53.native_resource_evidence RAW --control-closes
python3 -m scripts.v53.native_control_close_negatives RAW
```

The strict entry point validates the original native storage, publication,
network, owner accounting and complete source buffers before accepting cleanup
annotations. The source reader emits its response/session/trace associations only
after successful replay. Cleanup then uses those original allocation identities
to check the exact response still held at each session BEGIN and its original
trace. Overlapping sessions cannot borrow one another's response, even when the
borrowed lease is live and ordinary nesting/accounting would accept it.

Old collections remain readable for their previously captured scope. They cannot
pass `--control-closes` without original close observations. Presence of a sidecar
does not silently enable or skip any existing semantic check.

## Retained development results

- A new three-owner native activation and two-slot history passes 96 cleanup
  intervals: 18 services, 39 traces and 39 sessions, with 80 child references.
  It retains all 444 original source-buffer bindings and reaches two concurrent
  sessions on each selected owner. All 13 close-annotation negatives reject for
  their specified obligation after unchanged original validation.
- The actual checkpoint cancellation/replacement test yields six cleanup
  intervals and complete final accounting. Its old authority is a conditional
  fixture; these records are not relabeled as native joining evidence.
- Five selected Java tests pass on the captured source. The two new drain tests
  have retained failing results from the original implementation. Python checks,
  old component negatives and historical native compatibility are recorded in
  the development index.

The new result reports `nativeServiceCleanupIntervalsQualified=true` for this
scope and `listenerDrainQualified=false`. The original buffer reader's broad
`serviceCloseIntervalsQualified` remains false: cleanup scopes do not establish
every external caller's return, every listener drain, or physical custody.

## Remaining obligations

Complete new-source required-four/joining histories, failed-construction and
abnormal-close resource lifetimes, export/task/control ownership, post-handoff
physical custody, combined maxima/headroom and final-source hosted qualification
remain open. Long histories stay deferred to the planned hosted batch. The frozen
544 planned Phase 3 hosted histories and later-phase 3310-case plan are unchanged.
