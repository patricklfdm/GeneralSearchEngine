# Phase 3 — typed installed successor

The [A19 contract](PHASE_3_CONTRACT_AMENDMENTS.md#a19--typed-receipt-for-an-installed-learner-successor)
connects an installed successor to the actual core semantic decoder and a forced
LEARNER receipt for its exact current PREPARING revision. The previous owner stays
live and its files remain intact. A second sidecar owns the new backup and receipt;
closing a child does not pretend its retained bytes disappeared.

The 16 KiB compact plan binds original source and receipt digests plus the captured
configuration digest. Reopening reconstructs these values from the checked source
and actual configuration, checks the original plan, then repeats semantic decoding
before exposing a receipt. Missing/partial plans and changed originals are refused
unchanged. Exact partial backup/receipt writes can resume under a complete original
plan. Source, old typed and new typed paths remain disjoint; the original reserved
core path must be unchanged.

Both backups use separate APPLICATION reservations from the same parent. Parent
reopen accounts for the retained new backup before exposing a typed capability.
The worst-case private metadata is 2,036 KiB under the unchanged 2 MiB MISC lease.
This owner cannot create another generation marker or a third source slot. It has
no ballot, voting journal, matching INTENT or autonomous READY sender.

Focused components cover the five joining shapes, interruption/resume, shared
capacity, lifecycle revocation and preserved malformed originals. Conditional
fixtures do not establish distributed history. The native smoke independently
certifies PREPARE revisions 1 and 2, installs revision 2, rejects preparation for
revision 1 against that source, decodes/forces revision 2 and reopens identical
originals before cancellation. Its separate evidence reader checks the existing
installation history plus every typed-extension file and its exact force order.

Results and source identities belong in
[the evidence receipt](phase3-evidence/successor-typed.json). Full process-death
matrices stay in the [hosted queue](PHASE_3_DEFERRED_ACCEPTANCE.md). Repeated refresh,
old-source/backup retirement, cancellation cleanup, matching INTENT, all seven
transitions and full Phase 3 acceptance remain OPEN. No V5.2 experiment or workflow
is changed by this batch.

## Focused native observation

The five-slot native history completes in 366.1 seconds under its original
600-second test deadline. Both source acquisitions retain 31 observed exchanges
and nine original source files. Independent physical replay derives revision 2's
receipt and rejects all eight exact typed-extension mutations. Thirteen related
Python tests and the documentation contract pass. Component totals and the
portable replay archive are recorded in the linked receipt after collection.

These are finite observations for one native ADD history. They do not establish
latency guarantees, autonomous submission, fresh-process crash recovery or
completion of the full Phase 3 matrix. Conditional component profiles remain
separate from the actually certified TCP history.

The immutable component build passes 19 Java methods with zero failures, errors
or skips in 1381.9 seconds. Native and component tests share all 485
production/resource/POM inputs with the committed implementation. Original and
portable optimized replay have identical results; all retained archive members
are checked against their SHA-256 inventory.
