# Maximum application pressure followed by an admitted membership transition

Status: **implementation and small-image diagnostic validated; maximum-image
execution pending**. Phase 3 and all five closure gaps remain OPEN.

The subsequent [source-bound execution entry](PHASE_3_MAXIMUM_TRANSITION_EXECUTION.md)
now provides a manual-only three-job pipeline and dedicated large-runner
capacity checks. Its orchestration and diagnostic transport are validated;
the complete maximum-image workload has not run.

This reuses the [Phase 2 native maximum image](PHASE_2_MAXIMUM_APPLICATION.md).
Its typed backup, 1024 documents, 32-byte request-ID administration and exact
67,108,832-byte image limit are unchanged. The calibration and one-byte-over
refusal now live in one shared test helper. The historical Phase 2 result is
not reclassified as a current-source Phase 3 result.

## One continuous original

`V53MaximumTransitionQualification` performs public offline admission of five
voters, then drives the actual storage journals through the following sequence:

1. Initial campaign, BARRIER and another campaign. During the original owner's
   `FLOOR_BEFORE_RETURN`, retain its seven distinct image files, two generations,
   five SOURCE reservations, JOURNAL and MISC reservations.
2. While those files and reservations remain live, feed one actual original
   packet to `MembershipSourceReceive.learner` using that same resource pool.
   Packet completion must refuse the eighth APPLICATION reservation with the
   exact `resource ownership/count` reason. No application chunk is written.
   Retain the packet, failed receiver charges and the original authority hashes.
3. Close the receiver. Its packet/scratch disappear and the original usage is
   restored exactly; original authority hashes must be unchanged.
4. Continue the same five-voter history through RESERVE, PREPARE, READY, SEAL,
   INTENT, the surviving four-voter campaign and certified FINAL. The removed
   voter adopts FINAL, retains its original hidden-source ancestry and refuses
   a new vote. BARRIER, RETIRE, another BARRIER and a fresh campaign finish at
   slot 10 in stable generation 1. Four actual owner reopens and a typed image
   read require the unchanged document state and sequence 41.

The receiver is a synchronous storage probe with a fixed test clock, not an
admitted learner, network session or timing measurement. Its lifetime ends
before the membership operation starts; it is not artificially held across
FINAL. Large originals remain in the journal history, but this does not claim
that FINAL runs at the exact earlier seven-image peak. Full metadata pressure,
the SOURCE count-six envelope, CONTROL/WAITER concurrency, process death and
automatic public-runtime completion remain separate obligations.

## Independent replay and historical compatibility

`maximum_transition_evidence.py` derives each original bootstrap, grant,
selection, vote, certificate, checkpoint, generation, floor and retirement
snapshot. It validates all original observations, exact call ordering and
durability callbacks before accepting the receipt. Every survivor's final
image must equal the admitted image. The refused packet must be byte-identical
to the independently reconstructed floor's original packet; its declared
image size, original authority hashes and exact before/refused/closed charges
must match. The seven retained image files must be distinct, complete files
with link count one. A reservation total alone cannot qualify them.

The new reader explicitly uses the already implemented typed selected-prefix
closure and retains both first-slot endpoints plus the publisher's local
sources. At adoption it separately retains the departing owner's original
hidden source proof. These hooks preserve the old cross-view reader defaults
and the historical maximum-image reader. An absent proof is never filled in
from a candidate output or receipt.

After the complete original passes, sixteen decoded-record mutations exercise
packet identity, reason, authority inventory, ordering, missing close,
category/count/byte accounting and leaked resources. Each requires its exact
expected rejection; unrelated failures cannot count as successful negatives.

## Explicit execution

The class name ends in `Qualification`, so normal `*Test` discovery does not
start this long experiment. Use the pinned qualification toolchain and run
the full method explicitly after development. The existing maximum fixture
needed a 4 GiB Java heap; allow substantial disk space for physical copies.
No full-source or hosted-cohort acceptance is conferred by these component
commands alone.

The completed diagnostic retained 1,028 `.image` file copies. Substituting the
maximum extent for those copies alone projects about **64.25 GiB**, excluding
other backup files, active owner directories and temporary workspace. This is
a capacity-planning estimate, not a measured maximum run. Do not dispatch this
whole history to a hosted job without sufficient disk and execution time;
final-source execution must preserve its continuous history. The original
component batch added no job. The subsequent execution entry above supplies
the manual workflow; it has not been dispatched.

```bash
mvn -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -DargLine=-Xmx4g \
  -Dtest=V53MaximumTransitionQualification#maximumImageRefusalThenRemovalCompletes test
```

Use the **exact new directory** printed as `v53MaximumTransitionEvidence`:

```bash
python3 -m scripts.v53.maximum_transition_evidence /absolute/path/to/run-UUID --qualify
```

For a short plumbing diagnostic, select
`V53MaximumTransitionQualification#smallImageDiagnosticTraversesSameRemoval`
and pass `--diagnostic --qualify` to the reader. Its receipt and result remain
`DIAGNOSTIC`, with `maximumBytes=false`; the default maximum reader rejects
its layout. Do not replace a failed full run with this diagnostic.

## Current validation and remaining work

One local small-image execution completed all ten slots. Its same original
passes complete replay and all sixteen receiver mutations. The image was
881 bytes; peak accounting was 35,754,364 metadata bytes, 71,385 staging bytes
and sixteen leases. These are measured diagnostic values, not extrapolated
maximum-image evidence.

The diagnostic took 281.7 seconds and retained 10,110 files (35,254,274 bytes),
unchanged after normal and optimized-Python replay. All 75 related Python tests
and 34 optimized-mode tests pass. The fifteen existing receiver tests pass:
fourteen ran in the sandbox; its local-TCP test was blocked from opening a
socket and then passed unchanged outside the sandbox. Source-plan inspection,
documentation contracts, Python compilation and whitespace checks pass.

The first diagnostic reached the real resource refusal but failed while
serializing path-keyed hashes with the constrained JSON writer. The corrected
writer emits ordered path/hash rows. That failed original is retained. The
successful original also exposed the historical reader differences described
above; intermediate failed replays remain retained and were corrected by
deriving current rules from original inputs, without rerunning the workload
or broadening historical acceptance. Logs, hashes and validation summaries
are under `target/v53-maximum-transition-entry/`.

Maximum execution and independent replay on the final source remain pending,
followed by source/build/toolchain-bound cohort admission. This component adds
no Required check or paid-cloud action; its supplementary execution workflow
is documented separately. The existing catalogue's
566 histories, 260 execution groups, 500 archives and 544 selected jobs are
unchanged. Rollback removes this qualification and its reader/tests/docs,
restores the shared seed helper inline and removes the two reader hooks; no
runtime Java, resource limit, POM or wire/storage format is changed.
