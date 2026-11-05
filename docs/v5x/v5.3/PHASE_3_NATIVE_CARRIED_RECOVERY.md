# Phase 3 — native carried DATA cold recovery

A new whole-group process fixture starts from actual original DATA ACCEPT,
PROOF, certificate and applied end, followed by native TCP selection of that
same entry. It stops node 1 at four carry boundaries using `Runtime.halt(73)`
or SIGKILL. All three owners live in that child, so no original follower remains
alive to complete the work after death. A second JVM opens the same replica,
application and scratch directories and makes no client submission.

The original implementation failed after reopening the carried certificate
cleanup cut: a new ballot was attempted while the old applied staging and vote
still belonged to the inactive generation. The safety guard correctly refused
that authority change. The original failed process history is retained under
`target/v53-native-carried-recovery/original-failure.json`.

The native node now completes local carried acceptance before exposing its
listener. Recovery reads the exact entry and payload from the already installed
selection and uses the existing typed acceptance/derived retirement path. It
does not choose another entry, create a proof or application ACK, publish data,
or restore READY. An observed higher ballot still fences the operation. The
original certified source remains available after the local vote transfers.

A follow-up run exposed seven occupied application slots at reopen. The source
capture could not reserve its real image while empty application completion
buffers remained reserved. A strictly newer grant now releases only absent
replay/end buffers after fencing the old ballot. Existing staged files keep
their reservations; the next ACCEPT/application must reserve completion again.
Reopening a superseded vote also reserves only its remaining publication slot;
the constructors continue to charge every actual retained application file.
The next installation also requires the older inactive generation to retire.
The pre-grant maintenance path now permits an already transferred DATA/BARRIER vote,
binding its exact digest, selector, promise and selection throughout the work.
Ordinary published-only maintenance retains its prior empty-vote rule. Both the
outgoing proposer and an incoming PREPARE use the pre-grant path. Every deletion
still needs complete governing copies and the existing retirement plan; the
permission alone grants no deletion authority. A changed vote, grant or higher
observed ballot invalidates the retained permission.
Context-changing commands retain their existing context and published-maintenance
rules; this ordinary application recovery permission does not cover INTENT/FINAL.

After carried ACCEPT transfers, ordinary floor maintenance can use this same
permission to retire superseded sources before the new PROOF/application. This
keeps the following cold recovery inside the frozen seven-image limit. A source
with an unresolved tail must retain its original ACCEPT, ENTRY and payload in
the installed packet and preserve the exact successor vote. The original source
retirement planner, forced decision, journal replacement and deletion order
remain mandatory. The completed floor is released only after retirement.

The carried-slot and interrupted-node readers now derive
this earlier retirement from original source packets, grants, installed
selection and successor bytes. They still compare full inventories, typed
application contents and durable force order. New proposed entries cannot use
the carried-vote permission. Historical replay results obtained before this
correction remain historical; they do not qualify the changed runtime.

The candidate witness catalogue is rebound to these exact rejection locations:
three source-retirement mutations now reject `applied-1` instead of `applied-2`.
The catalogue delta contains 30 reason changes across nine archive units,
including the separately owned round lifecycle checks. All nineteen chosen
witnesses, their conditions, the twelve subsets, 544 histories, 238 execution
groups and 478 archives remain unchanged. The Phase 5 acceptance plan is
unchanged. The earlier source-audit receipt keeps its original catalogue digest;
it is not rewritten as evidence for this source.

No resource count, deadline, persistent format or quorum rule changes.

The fixture retains child stdout, stderr, exact exit status, held/released replica
locks, both lives, original physical snapshots and wire observations. Failure
snapshots include actual resource counts. The successful producer must recover
one logical DATA application followed by a fresh barrier, with zero client
resubmissions and a clean owner/resource shutdown.

The final narrowed source passes seven targeted Java regressions: three
acceptance/fencing/reservation checks, both carried INTENT/FINAL histories, a
whole-group halt after application force, and the applied DATA round. The
INTENT and FINAL tests additionally compare original source and journal bytes
between installation and application. Independent replay of those two histories
and the DATA round passes 30, 30 and 33 exact negatives respectively. The
reader/unit suite passes 111 tests; the separately selected catalogue/witness/
cohort suite passes 76 tests after the catalogue binding update.

The earlier candidate, before restricting the new permission to DATA/BARRIER,
passed all eight whole-group halt/SIGKILL producers, four carried BARRIER
histories with 104 negatives, and an interrupted single-node history with 34
negatives. Its broader context permission was rejected during review; those
results remain separately source-bound and are not described as complete
final-source execution. Failed intermediate runs and the original regression
are retained. See the [development receipt](phase3-evidence/native-carried-recovery.json)
and `target/v53-native-carried-recovery/validation-summary.json` for exact source,
report and raw-history bindings.

The new whole-group Java fixtures are development regressions, not independent
process-history qualification. They are not yet added to the twelve-subset
final-source cohort. A dedicated original-first reader, negative mutations and
complete source-bound cohort admission remain required before claiming this
process family or Phase 3 complete. No hosted workflow or paid cloud ran.

The next process qualification must bind both actual child lives, original
directories, exit/lock observations, each cut's physical files, cold local
acceptance and the later original-wire campaign. It must reject changed entry
or payload, missing source succession, stale readiness, invented client retries
and altered process observations. A passing producer alone cannot satisfy that
obligation or replace final-source hosted execution.
