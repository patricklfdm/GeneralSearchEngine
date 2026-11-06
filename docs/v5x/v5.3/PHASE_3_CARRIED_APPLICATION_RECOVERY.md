# Phase 3 — carried membership application recovery

Phase 3 remains **OPEN**. This batch adds four native process axes: INTENT and
FINAL, each with `Runtime.halt` and external SIGKILL after the leader's
`APPLY_ACK_DIRECTORY_FORCED`, before publication. These are separate from the
eight existing ACCEPT/PROOF rename axes. The same admitted four-owner REMOVE
prefix, original replica directories, complete group death and fresh processes
are used. An application ACK is not publication authority.

## Two reproduced capacity failures

The original FINAL/SIGKILL execution failed while retiring the superseded applied
end after selection. Two generations, three retained source images and the old
applied image occupied six of the seven frozen APPLICATION slots. Replay then
reserved both input and output and exceeded that limit. These were distinct real
owners, not a duplicate accounting label.

After correcting that demand, both FINAL/SIGKILL and INTENT/halt passed the old
failure point but failed during FLOOR maintenance. Two generations and three
sources already occupied five slots; three copied governing images required
eight. Existing local-original pinning covered four copies over two sources but
did not cover three copies over three sources. All three failed originals and
their stderr remain retained; a failed producer earns no positive qualification.

## Runtime correction

Only a decoded, verified INTENT or FINAL can reserve one full 64-MiB replay input.
The typed core preserves its application bytes and creates no output for these
commands. DATA, BARRIER, unknown entries and unresolved pending accepts keep the
conservative input/output pair. Retained scratch cannot change its demand;
control scratch containing output or backup staging is rejected without erasure.
A failed upgrade releases only newly acquired leases, preserving the original
input. Acceptance reserves for the proposed verified entry, rather than a prior
entry. Public formats and the seven-image ceiling are unchanged.

Maintenance now uses the existing local-original pin when two generations plus
the minimum image count of the retained sources and offered floor copies would
exceed seven. The original selected generation remains charged. All remote
copies, original identities, forced files and the complete governing quorum are
still required. Existing copied floors cannot change representation. A pin must
survive close/reopen and be released before replacing its generation. Extra
images or other occupied slots still undergo normal capacity admission.

The focused regression also exposed an obsolete Phase 2 test expectation: it
required the departing joint voter to fail FINAL application. Under the already
adopted A09/A11 contracts it may retain a `Departure`, but cannot endorse the
successor. The test now checks that exact completion type, unchanged application
bytes/sequence, empty voting result, rejection of endorsement access and absence
of `ack.gsr`. The runtime authority rule is unchanged.

## Independent evidence

The [application reader](../../../scripts/v53/native_carried_application_evidence.py)
first validates original process observations. It reconstructs the admitted
prefix, the leader-only application end at death, cold-open preservation, new
frozen source containing the original entry/vote/proof/certificate/payload, and
retirement of the superseded derived end. It then derives each new application
and publication through the fresh stable barrier. An old ACK cannot become the
new ballot's ACK. Expected snapshots are derived independently of the observed
snapshot bytes. The old ACCEPT/PROOF reader continues to reject this distinct axis.

Nine negative variants alter the original entry, old ACK/certificate/catalog,
invent a peer ACK, change cold-open bytes, lose the retained original certificate,
change the new ACK or alter the published peer ledger. The unmodified history
must pass before mutations receive credit. These checks qualify retained snapshot
bytes and original process boundaries, not every intermediate force or TCP event.

Publication and replay resource readers accept the smaller reservation only when
the independently admitted original membership command permits it. They retain
full ownership, extent and continuous-lifetime checks. Historical conservative
two-slot traces remain valid and retain their original source scope.

## Focused validation

- 30 distinct focused Java tests pass across two invocations. The first ran 26
  tests with one obsolete departing-owner expectation; the final five-test run
  passes the corrected expectation, two adjacent departure checks and both
  predeclared native process cases. DATA recovery still applies its original
  command exactly once before a fresh barrier. Three-source/three-copy pinning
  passes close/reopen alongside the four-copy and invalid-pin regressions.
- 285 related Python tests pass; the 12 new reader/resource tests also pass with
  assertions disabled.
- Both native originals pass independent process and complete retained-snapshot
  replay, nine exact negatives each, and relocated original replay with assertions
  disabled. Four fresh group JVMs preserve the exact death/lock boundaries and
  reach a fresh stable barrier after the new ballot's application/publication.
- Two short real control applications retain 46 exact scratch callbacks and
  complete one-slot resource lifetimes. Both pass nine exact negatives each and
  reproduce identical results after relocation with assertions disabled. These
  are conditional protocol fixtures, not new native history qualification.
- All 385 historical evidence indexes and the frozen acceptance-plan hash remain
  unchanged. The original capacity failures and the obsolete-test failure remain
  retained separately from passing evidence. No full reactor suite is claimed.

Focused native entry:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  '-Dtest=V53NativeCarriedApplicationProcessTest#killFinalApplicationAck+haltIntentApplicationAck' \
  -Dsurefire.failIfNoSpecifiedTests=false test
python3 -B -m scripts.v53.native_carried_application_evidence \
  general-search-engine-replication/target/v53-native-carried-transition-process/run-<id> \
  --qualify
```

The current-source validation and exact retained paths are recorded in the
[development index](phase3-evidence/carried-application-recovery-development.json).
Complete force/wire replay for these new axes, all other process axes, internal
core/DATA interruption, full seven-family native capture, simultaneous resource
maxima and final-source hosted admission remain open. There is no new hosted
subset, relaxed frozen limit, cloud run or release qualification in this batch.
