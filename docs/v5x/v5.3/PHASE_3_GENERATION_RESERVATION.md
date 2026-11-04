# Phase 3 — retain partial generation charges on refused expansion

Phase 3 remains **OPEN**. This correction preserves process-local accounting for
an actual incomplete generation when its installation cannot acquire additional
capacity. It does not establish simultaneous native maximum-resource qualification.

## Reproduced failure

At baseline `a9f25529`, `MembershipGenerationFiles.reserve(plan)` closed its existing
leases before requesting the complete plan. After an interrupted manifest force,
reopen charged that partial manifest. If other application reservations filled the
seven-image limit, resume failed while reserving the new image and closed the newly
acquired generation lease too. The original manifest still existed unchanged.

The deterministic original regression observed metadata fall from 35,661,112 to
35,659,531 bytes and generation count fall from two to one after refusal. The
missing 1,581 bytes were the retained partial manifest. The journal correctly
poisoned its writer after the failure, but the shared budget no longer described
all files owned until that journal actually closed. An isolated replay of both
unchanged disk regressions against the two baseline production classes reproduces
the failure independently; the image case also loses 30 staging bytes and one
application slot. Its original files and logs remain retained.
Poisoning a writer does not
itself retire its files or release other users of the shared resource pool.

## Corrected reservation transaction

[`MembershipGenerationFiles`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipGenerationFiles.java)
keeps original generation and application handles and asks
[`MembershipResources`](../../../general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/MembershipResources.java)
to extend them with any missing image handles under one resource monitor.

- Successful admission preserves old handles, grows required extents, and adds
  only absent parts. Existing completion-image maximum reservations never shrink.
- Failed admission restores all original extents and removes only new handles
  acquired within that unsuccessful transaction. Other owners cannot observe an
  intermediate release or partial expansion.
- Metadata, completion headroom, staging, count, original-owner and duplicate-owner
  checks still apply. No file, selector, vote or certificate changes on refusal.
- The failed journal remains poisoned. A fresh owner can resume the same original
  selection after competing pressure has gone; the fix does not retry a client
  command or authorize a different generation.

The format, seven-image/two-generation limits, shared staging ceiling and all
protocol deadlines are unchanged. Existing exact-plan installation, adoption,
publication and retirement guards still decide authority.

## Verification scope

[`V53GenerationReservationTest`](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53GenerationReservationTest.java)
contains two actual disk interruption/resume regressions and three resource
transaction tests. The disk cases use existing authenticated conditional fixtures:
one retains the partial manifest at image-count refusal; the other retains an
already written image at metadata-headroom refusal. Both compare every original
file hash before/after refusal, require unchanged usage until close, and complete
the exact original install after reopening with available capacity. Competing
pressure is explicit accounting pressure, not invented physical copies or voters.

The transaction cases exercise rollback after both growth and a new successful
reservation, byte/count failures, duplicate names, foreign/closed handles and
preservation of an existing 64 MiB completion reservation. These assertions are
regressions, not independent hosted evidence or additional S-matrix rows.
The extended publication regression exposed an earlier stale expectation:
`V53PublicationLifetimeTest` required omitted caller ancestry to fail even though
commit `892193ea` already permits exact verified local ancestry inheritance. The
unchanged baseline fails that same assertion. The corrected test still rejects
missing proof when local ancestry is absent, keeps duplicate/unowned/changed
proof and fencing negatives, then verifies inherited original bytes and the
unchanged selected decision. No production ancestry policy changes in this batch.
The original extended-run failure remains retained; only that corrected method
needs a follow-up execution, not a retry of already successful long histories.

See the [development receipt](phase3-evidence/generation-reservation.json) for
commands, source hashes, retained failure and completed checks.

This adds no hosted subset or planned history: the catalogue remains twelve
subsets and 544 planned histories. Final-source execution, transient transport
resources, admitted FINAL/publication under full combined pressure and the
phase-wide gate remain open. The separate floor non-handoff and retirement
reservation paths still need the same refusal-lifetime audit; this correction
is limited to inactive generation installation and its publication reservation.

Reproduce the short new regression class without running a cloud experiment:

```bash
/opt/maven/bin/mvn -o -B -ntp -f reactor/pom.xml \
  -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtest=V53GenerationReservationTest test
```

Rollback reverts the two production files and this regression/navigation addition.
That would restore the reproduced undercount; retain the failing log and do not
interpret an older successful workflow as validation of the corrected runtime.
