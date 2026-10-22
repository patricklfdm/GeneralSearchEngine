# Actual parent checkpoints for compacted publication

Status: private local Phase 2 storage transaction; complete Phase 2 remains OPEN.
This follows [journal publication](PHASE_2_JOURNAL_PUBLICATION.md) and preserves
the frozen wire records, quorums and global resource ceilings.

## Exact additional statement

A new stable DATA checkpoint may merge the preceding RANGE. For example, the
current certified parent is cut 2 and the new end is cut 3, while the compacted
catalog stores RANGE 0→3. Original SELECTED and BASIS still refer to cut 2.
The complete generation therefore needs a separately endorsed RANGE 2→3.

`MembershipCheckpointPlan` derives that supplemental statement from the actual
original parent cut, catalog and application hash and the exact new applied end.
The end must be the parent's immediate successor. Supplementation is permitted
only strictly inside the same stable RANGE. A direct parent needs no extra
statement; INTENT/FINAL retain their explicit membership edges.

`MembershipAppliedEndFiles` binds the optional statement and local ACK in its
original immutable plan. It forces the complete image/catalog/authority and parent
statement before writing either ACK. The normal checkpoint ACK completes before
the parent ACK. No second mutable quorum accumulator or new application image is
introduced. The two optional files add at most 18 KiB to the reservation charged
against the existing 32 MiB journal. The inventory is bounded to nine names;
uncompacted and membership ends retain the original seven-name layout.

Only completed, guarded local force returns the supplemental `Owned` observation.
The publication request must retain that exact local endorsement. Remote majority
ACKs still require independently supplied actual observations; witness digests,
the normal RANGE ACK or a different owner's ACK cannot substitute for them.

## Recovery and retirement

Each statement/ACK write remains exact-prefix resumable. Every boundary checks
the exclusive owner, original selector/certificate, unchanged promise and observed
ballot fence. An ACK file, including a partial one, requires all corresponding
end files to be complete. A parent ACK additionally requires the complete normal
ACK. Missing or altered members fail before further end writes.

The covering selector binds the original parent. Covered cleanup reconstructs
both statements and ACKs from that parent and the published end, checks every
remaining member before deletion, and keeps `plan.json` until all members are
gone. Interrupted cleanup never creates another application or infers authority
from a partial ACK.

## Qualification and remaining scope

The [evidence index](phase2-evidence/parent-checkpoint.json) records exact source,
JAR, JUnit and raw process hashes. Local integration exercises compacted parents
at cuts 1, 2 and 4, original SELECTED preservation, actual separately forced peer
ACKs, missing/substituted observations, fence revocation, corruption and repeated
recovery. Twelve halt/SIGKILL cases run in 36 fresh JVMs, spanning parent-statement
and ACK writes, selector publication and covered cleanup. Original-first Python
replay derives the new catalog/statements from retained original authority and
peer materializations, then compares exact intermediate bytes and force order.

The bootstrap and older history remain private fixtures. This covers the exact
immediate original parent, not arbitrary older hidden BASIS/floor cuts. Bounded
endorsement renewal for those additional ancestors and stable same-round slots
remain open. No public READY, distributed authentication, power-loss guarantee,
protected CI or cloud acceptance follows from these tests. Independent image
semantics remain the separate typed-core replay obligation.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53ParentCheckpointTest' -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.parent_checkpoint_evidence <v53ParentCheckpointEvidence-directory>
```
