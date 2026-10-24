# Mixed original ballots and bounded covered completion

Status: local storage-sequence qualification **PASS**. Phase 2 remains **OPEN**.

This extends [covered protected contexts](PHASE_2_COVERED_CONTEXT.md) using actual
public offline bootstrap for 3/4/5 voters with EMPTY and verified-backup sources.
The initial certified ENTRY originates in ballot 2. A majority reaccepts it in
ballot 3 while the minority retains its original ballot-2 certificate. Ballot 4
then selects and installs the higher ACCEPT while preserving those different
originals and their exact context/floor bindings.

The first source-retirement attempt correctly refused deletion of the minority's
ballot-3 source: its old governing floor still pins that source. The corrected
sequence keeps it until a newer floor allows retirement. The next execution
showed why ordinary maintenance must reclaim this extra source as well as the
immediately preceding one. Both development failures remain retained.

## Two bounded completion paths

Three voters have enough space to retain the old minority context through
ballot-5 covering installation. After forcing that selector, the owner clears
the exact original vote/context. Explicit inactive retirement and floor release
then allow a new floor to reclaim both older sources. Ballot 6 publishes a BARRIER
and typed inspection confirms the original DATA was applied exactly once.

Four/five voters require three floor copies. With the additional pinned source,
the attempted protected capture exhausts the seven-image reservation limit.
The retained run4 shows `CAPACITY_EXCEEDED` / source-retention refusal before a
new PROMISE is written. This is not permission to delete pinned bytes or enlarge
the frozen limit. The extended scenario checks each affected voter twice, requires
`NOT_SUBMITTED`, unchanged disk bytes and zero leases after close, and checks that
the live owner remains fenced by its higher volatile observation.

After reopening the unchanged durable ballot-4 store, the caller completes only
the exact selected successor ACCEPT. This legitimately supersedes its original
vote and releases the old context/floor. A complete ballot-4 floor then authorizes
the older source's retirement. With that headroom restored, ballot 5 captures and
installs the majority's published prefix, maintenance completes, and ballot 6
continues. These four profiles use successor acceptance before the covering
installation; they are not evidence that an over-capacity protected context can
be carried unchanged into another round.

This is an explicit local storage sequence, not an automatic runtime retry policy.
It does not roll back a durable promise, retry an indeterminate mutation, lower
the ballot allocator, or relax a floor/source reference. General maximal-size
admission and coordinated lifecycle policy remain closure obligations.

## Exact successor authority for source retirement

A fifth retained execution exposed a missing composition rule: after the exact
ballot-4 successor was forced and the old context was legitimately removed,
source retirement still only recognized an identical installed ACCEPT or a live
old context. It refused the older ballot-2 ownership even though a validated,
forced current successor now carried that same selected entry.

The owner now supplies that exact loaded successor to both retirement planning
and each saved-decision revalidation. The existing successor predicate binds the
current selector, promise, selected entry, non-regressing ballots and unchanged
original ACCEPT bytes. The owner first performs ordinary vote verification;
a proposed, missing, partial or foreign vote cannot authorize deletion. Current
and floor sources stay pinned; every original byte and ancestry check remains.
The decision format and resource limits are unchanged. Four deletion boundaries
are each interrupted twice. Missing or corrupt successor bytes are refused twice,
both before planning and after the original journal group was pruned. The saved
invalid/refused stores remain identical. The test restores exact original bytes
to demonstrate completion; production does not repair missing authority.

## Independent evidence

The reader derives admitted initial authority, actual votes, mixed source
captures, immutable selections, generation bytes, retained original contexts,
old/new floors and exact source retirement. It checks all saved inventories,
capacity-refusal outcomes, force ordering and continued publication. It first
validates the originals, then runs specified corruptions and portable replay.
Typed application execution remains a Java check; Python authenticates the saved
images and metadata rather than reimplementing the engine.

The completed gate has six profiles, 40 node publications, twelve exact capacity
refusals and 32 Python tests. Mixed-chain replay rejects 23 specified mutations;
source-successor recovery rejects ten. Normal, optimized and relocated replay
agree. Two targeted reactor packages completed 30 Java test executions (including
one repeated test method). The final package also reran all 22 existing
covered-context process cases / 66 workers and their twenty portable evidence
negatives on the corrected production classes. That process matrix is a regression,
not fresh-process qualification of the new successor-source route.

The [evidence index](phase2-evidence/covered-context-mixed.json) retains all seven
development attempts, source maps, JARs, JUnit reports and original raw inventories.
Of 707 production classes, three have the described logic change; the outer
source-retirement file class has only debug metadata differences and identical
`javap -c -p` output. All other production classes match the preceding batch.

Remaining work includes process qualification for this mixed chain, hidden-endpoint
process recovery, maximal byte/lifetime profiles, complete cross-view storage and
the final S/N mapping. See the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
