# Phase 3 complete observed export allocation coverage

The original [session content reader](PHASE_3_SESSION_CONTENT_EXTENTS.md),
[direct-operation reader](PHASE_3_REQUIRED_FOUR_DIRECT_EXPORTS.md) and
[published-prefix probe reader](PHASE_3_PUBLISHED_PREFIX_PROBE.md) now compose
through one exact allocation inventory. Phase 3 remains OPEN.

## Bindings, not receipt counts

Each reader publishes in-memory bindings only after all of its original content,
operation interval, ownership and release checks succeed. A binding includes the
original node and allocation owner, scope, export role, content/request digest,
independently derived extent and validated lifetime. Nested prefixes receive
separate bindings. Failed readers publish nothing; a duplicate or cross-scope
collision rejects the entire attempted publication into the shared map.

The final reader reconstructs the complete export inventory from the admitted
resource journal and close/attachment observations. The binding keys must match
that inventory exactly. Every allocation must have one scope, the exact original
digest and extent, and the same complete lifetime. Missing/foreign keys, equal
counts with different owners, late end points or reassigned scopes fail. A final
zero resource total cannot replace an allocation's content/lifetime proof.

Bindings are produced inside the admitted native call. This is not a new input
JSON format that can replace original physical/network authority. The binding
hash in a receipt identifies the computed set; it does not confer authority.

## Strict native entry

```bash
python3 -m scripts.v53.native_resource_evidence "$RAW" \
  --profile 5-REPLACE-required-four --complete-exports
```

The option enables source-control, cleanup, export ownership, all successful
session content extents, direct operations and the published probe together.
The existing complete physical/history/continuous-ledger preconditions still
run first. Publication generation custody is also mandatory in the native
resource composition. Historical modes remain available for scoped replay;
they do not silently opt into or claim complete export coverage.

An observed constructor rollback without independent native content qualification
cannot be ignored or relabeled as a successful session/probe. The complete
required-four producer's existing invalid-constructor probes reject before
allocation, as documented in the session-content audit; the separate conditional
rollback histories retain their own scope. Any new allocated failure path must
obtain its own independent binding before this strict gate can accept it.

Complete *observed export allocation* coverage does not mean every failure path
or all CONTROL work is qualified. Receipts retain the number of other CONTROL
allocations and keep whole-runtime, failed-constructor, all-failure-path and
Phase 3 claims false. Remaining non-export CONTROL/WAITER, full physical custody,
simultaneous resource maxima and final-source cohort execution remain required.

## Validation

Fourteen new tests exercise all ten session families with direct and single or
nested probe scopes, complete key equality, exclusive ownership, transactional
proof publication, original-first failure and strict-option admission. They also
reject laundering rollback allocations as probes and preserve the distinction
between complete export coverage and other CONTROL work. The adjacent Python
suites pass 366 tests.

Two unchanged actual conditional joining-handler captures pass their original
physical/content precondition and the new inventory reader: one preparation
allocation and a retention allocation with its nested prefix. Eighteen exact
proof mutations reject. Their outer status remains PARTIAL; this is not a new
complete required-four execution or final-source qualification.

The [development index](phase3-evidence/export-allocation-coverage.json) retains
source/report hashes. Local results are under
`target/v53-export-allocation-coverage/`. No production Java, frozen format,
resource bound, deadline, POM, workflow or paid-cloud change is included.
