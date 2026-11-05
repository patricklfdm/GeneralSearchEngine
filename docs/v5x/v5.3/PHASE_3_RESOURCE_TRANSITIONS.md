# Observed resource transitions and transient reservation peaks

Fixed publication or transport callbacks can miss a reservation created and
released between callbacks. `MembershipResourceObservations` adds an optional
bounded accounting journal to `MembershipResources`, enabled only by an explicit
internal constructor argument before its first reservation. Existing constructors
keep observation disabled. Capacity checks, staging/queue limits, completion
headroom, persisted files and wire formats are unchanged.

The journal records each successful accounting mutation under the same resource
monitor: reservation, extent growth, pending claim, claim commit/cancel, generation
reload, storage transfer/replacement, group expansion/rollback and release. It
retains exact removed/added unit-owner extents, the usage counters and a continuous
sequence. Pending claims consume a category slot while their bytes remain owned
by the original learner. Every group expansion has an explicit original boundary;
rollback must restore that exact state. Temporary successful reservations before
a later capacity refusal remain visible in the peak.

Observations perform no I/O or external callback. Immutable snapshots contain
bounded deltas rather than a complete lease table per event. Observation overflow
is sticky and preserves the prefix. An observation failure marks the trace failed;
it cannot enter an owning operation's rollback path after an atomic handoff. Both
failed and truncated traces are refused by qualification, even if all leases were
eventually closed. This is diagnostic failure isolation, not a retry or suppressed
runtime capacity error. Default runtime calls incur only the disabled-observer
guard; no global observer or public configuration is introduced.

## Independent reader

`scripts.v53.resource_transitions` reconstructs every active charge from the
ordered deltas. It independently computes metadata, staging, queue bytes, category
counts, pending-claim counts and completion headroom using the frozen limits.
Recorded usage must equal those derived totals at every step. A pending claim
requires its one original learner; commit moves category without duplicating
bytes. Growth, transfer, reload, replacement and release must have their allowed
delta shapes. An expansion cannot overlap/interleave, lose its start/end, or
restore merely a smaller total instead of the exact original lease set.

Canonical JSON, bounded input, typed integers, original removed extents, unique
owner/category keys, sequence continuity, final usage and complete close are
mandatory. Native JVM UTF-16 owner ordering/length is retained. The result reports
observed charged peaks; it does not infer physical bytes, deletion authority,
unobserved resource owners or a whole-runtime peak from one budget's observations.

```bash
python3 -m scripts.v53.resource_transitions "$ORIGINAL_TRACE_JSON"
```

## Development evidence and next integration

Eight new Java regressions exercise all 19 event kinds, concurrent updates,
pending claims, completion handoff, reload, atomic replacement, expansion refusal,
overflow and deliberate diagnostic failure after a committed ownership switch.
Six complete original component traces independently replay 210 transitions;
the two incomplete traces are refused. The failed expansion's 100-byte transient
staging peak remains visible even though its final usage is zero.

Fourteen Python tests additionally reject missing/duplicated sequences, forged
counters, foreign releases, duplicate owners, invalid claims, incorrect rollback,
capacity/headroom violations and mislabeled live snapshots. Related resource
readers and Java ownership regressions are retained with exact source/report
hashes in the [development index](phase3-evidence/resource-transitions.json).
The initial test-fixture aliasing failures and an initial diagnostic invocation
without `PYTHONPATH` are recorded, not counted as production defects or successes.

The next integration must attach these journals to every actual old/joining
budget in the required-four producer, bind them to original owner lifetimes and
physical/transport boundaries, and reject omitted budgets. Neither that complete
native run nor its physical peak qualification is claimed here. The complete
required-four network/export/maintenance/ledger entry, whole-runtime resources,
frozen coverage and final-source admission/execution remain open. The twelve
hosted subsets / 544 planned histories are unchanged. No workflow, push or paid
cloud action is part of this batch.

Rollback removes the optional constructor/journal and accounting observation
calls together with the new component test/reader and documentation references.
No existing durable format or authority decision depends on these observations.
