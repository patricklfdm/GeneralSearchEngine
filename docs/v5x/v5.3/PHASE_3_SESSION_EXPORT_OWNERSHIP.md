# Phase 3 session-owned export handles

[Joining request binding follow-up](PHASE_3_JOINING_EXPORT_REQUESTS.md) adds a
separate first-request check. UUID-only historical joining handles retain this
earlier ownership scope and are rejected by that new gate.

The later [direct-owner follow-up](PHASE_3_DIRECT_EXPORT_OWNERSHIP.md) qualifies
the six local borrows on a new original. The original described here remains
PARTIAL; its missing observations are not backfilled.

The [native cleanup reader](PHASE_3_NATIVE_CONTROL_CLOSE.md) now observes the
actual CONTROL handles that a source session owns through its exporter. The
[development index](phase3-evidence/session-export-ownership.json) records the
source hashes, original execution and independent replay. Phase 3 remains OPEN.

## Ownership contract

All eleven production `MembershipTransferExport` implementations explicitly
declare the handles released by their `close()` operation:

| Export | Handles owned by the session through the export |
| --- | --- |
| Source, record, vote, current prefix | Its own CONTROL reservation |
| Learner ROOT | ROOT metadata and the nested current-prefix borrow |
| Learner prefix | The nested current-prefix borrow |
| Joining retention, joining intent | Metadata and the nested current-prefix borrow |
| Joining preparation | The export's copied metadata reservation |
| Joining completion, joining checkpoint | The export's own metadata reservation |

The preparation publication, original journal, source storage and generation
remain owned by their existing owners. In particular, ending a preparation
session does not close the shared publication. A conditional fixture verifies
that a second independent session can still read it.

The observer records `ATTACHED` after successful session construction. It reads
the export's immutable handle list outside the accounting monitor, then records
names under that monitor after checking the actual resource-pool identity.
Already-revoked handles remain identifiable: a valid owner may release an export
between reference validation and observation. A released handle from another
pool is rejected even if its name matches a local reservation.

Observation is opt-in and bounded by the existing resource and close recorders.
Missing, failed or truncated observations cannot qualify. Observation failure
does not change runtime cleanup, resource limits, voting, durable bytes or
deadlines. Existing observation configurations remain unchanged. No public API,
workflow, POM, paid experiment or hosted dispatch is changed by this batch.

## Two different release boundaries

The cached response releases before the session metadata. Export cleanup runs
after that metadata release and must finish before the cleanup-performing
`session.close()` returns. The reader checks these separately; it does not
incorrectly require export release before metadata release. A missing normal
return still fails even when final usage is zero.

The new reader checks attachment order, unique original handles, valid export
groups, immutable reservation extents and release before the actual close return.
Nested ROOT/retention/intent groups require their prefix borrow. It reports any
export allocations that are not attached to a session. It does not infer their
ownership from size, time proximity or a final zero counter.

## Observed scope and retained gap

One new public-bootstrap, actual TCP activation/two-slot history passed its
physical, publication, network, owner-accounting and source-buffer preconditions.
Its 39 sessions own 39 export reservations: two source, sixteen record, thirteen
vote and eight prefix exports. All declared handles release within their actual
session close interval. Twelve exact mutations reject after original validation.

The same resource journals contain **six unattached exports**: two source and
four prefix reservations held by local operations. They are not network-session
children. Their exact identities and lifetimes remain in the receipt. The
extended native result is therefore **PARTIAL**, including at the enclosing
native accounting entry point. Strict `session_export_evidence.replay` rejects
this original with `session export unclaimed allocation`; a successful subset
or successful negative checks cannot promote it to full qualification.

The first strict replay failure is retained. The later inspection result preserves
the gap rather than ignoring allocations or assigning them to unrelated sessions.
This native history does not exercise every joining exporter. The conditional
preparation test and synthetic nested-group tests are not native joining evidence.

Local validation: 25 Java tests (seven new, plus one actual TCP history) and 120
related Python tests (fifteen new) pass. The initial test compilation error and
an intermediate mutation-driver fixture failure are retained with the successful
results. No complete reactor or long hosted cohort was rerun.
The previous native close capture also replays successfully with its original
96 cleanup intervals and original scope; no new export coverage is assigned to it.

## Reproduction and next work

The native collector adds `-Dv53.resource.export.ownership=true` to the existing
publication/resource/source/close/connection observation flags. The reader uses
an explicit option; old captures cannot silently gain export qualification:

```bash
python3 -m scripts.v53.native_resource_evidence RAW --control-closes --export-ownership
python3 -m scripts.v53.session_export_negatives RAW
```

Inspect the receipt's status and inventory. For this original both commands
produce `PARTIAL`; the latter separately reports `negativeQualification=PASS`.
These are development inspection commands, not a new full qualification gate.

Next: bind the six direct local borrows to their actual activation/publication
owners, exercise nested and joining export groups in complete native histories,
then compose failed constructors, abnormal closes, physical custody and resource
peaks. Final-source cohort admission and hosted execution remain pending. The
544 planned Phase 3 hosted histories and later Phase 5's 3310 S cases are unchanged.
