# Phase 3 — actual overlapping receiving-copy bounds

Phase 3 remains **OPEN**. This batch exercises actual current-generation,
PROMISE-source and receiving files under the same native resource owner. It adds
physical evidence to the earlier accounting-only resource tests. It does not
claim the full simultaneous metadata maximum or transition-completion reserve.

## Native histories

[`V53CombinedReceiveResourcesTest`](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53CombinedReceiveResourcesTest.java)
creates nine independent public offline bootstraps: stable sizes 3, 4 and 5,
each with three pressure modes. Every case opens an actual bootstrapped journal,
forces PROMISE/BASIS, exports that original capsule and application image, then
uses the same `MembershipResources` for the owner and complete receive files.
The first receiver uses the learner staging category. Other receivers use source
staging. These are real duplicate physical files, not distinct voters, a selected
quorum or an admitted learner operation. No protocol authority is fabricated.

Let `P` be the encoded original source packet length and `I` the original image
length. The live owner has one current image and one PROMISE-source image, charged
`P + 2I` staging bytes. Five complete receiving copies bring this to `6P + 7I`.
The original journal and miscellaneous completion reservations stay charged too.

| Mode at each size | Complete receiving copies | Required refusal |
| --- | ---: | --- |
| `image-count` | 5, including one learner | An eighth image fails after its packet arrives; no application file is created |
| `shared-short` | 4, including one learner | The next packet fits, but its image exceeds the shared limit by exactly one byte |
| `shared-exact` | 5, including one learner | All complete files exactly fill shared staging; the next packet fails before its file is created |

Failed packet validation retains the original packet's resource charge until its
owned scratch is deleted. Closing only the failed receiver must restore the
pre-attempt usage, leaving every successful copy live. The actual journal then
forces counter 3 while all successful receiving copies remain charged. The
fixture records the actual allocator write, file-force, rename, directory-force
and before-return callbacks, with live resource usage at each point. This
checks existing allocator work, not FINAL, application publication or recovery
completion under maximum pressure. Draining the copies returns usage to the
live-owner baseline; closing the owner releases every process-local lease.
Durable files survive owner close and are not described as freed disk space.

Receiving clocks are explicitly fixed at zero for this storage-bound experiment.
The original export retains its normal 60-second limit. This is not timing or
network evidence. No production code, timeout or resource limit changes.

## Independent physical replay

[`combined_receive_evidence.py`](../../../scripts/v53/combined_receive_evidence.py)
first reconstructs all nine bootstraps, grants and exports using the existing
original-source reader. It derives packet/image bytes and sizes, generation
metadata and PROMISE/BASIS control charges from those files. It then requires
every ordered snapshot to contain the exact complete copies, failed packet or
empty scratch appropriate to that stage. The live counters must equal those
derived copies and reservations; a producer's total is not the expected value.

The physical authority snapshots must remain exactly original through refusal
and failed-receiver cleanup. After the allocator operation, only the exact
counter-3 record may differ. Successful files, rejected packet bytes, unchanged
grant/source/generation files and final scratch deletion all remain inspectable.
The reader requires all seven allocator callbacks in order and unchanged resource
charges throughout. These callbacks observe the native force path, not power-loss
recovery or physical hardware durability.
The nine original bootstrap plans must be distinct. Scope, byte limits, rejection
reasons and ordered stage inventories are exact, including integer types.

Qualification validates the entire original before copying it for 21 negative
mutations. Mutations cover undercharged packet/image/control bytes, invented
leases, early release, missing/changed/extra physical files, altered authority,
a missing counter update, missing/reordered force callbacks, resource release
during force, incomplete histories, relaxed limits and wrong rejection reasons.
An unrelated validation error cannot count as a successful rejection.
Original inventories are rechecked afterward.

## Development evidence and remaining scope

The initial fixture passed all nine pressure histories plus eight existing
resource tests: nine JUnit tests, zero skips/failures/errors, 63.522 seconds
including compilation. Its first independent replay passed 18 exact negatives.
After adding actual allocator callbacks, a fresh recorded source execution passed
the same nine histories and eight resource tests in 63.824 seconds (the matrix
itself took 49.80 seconds). Its reader passed all 21 exact negatives, including
the three force-observation mutations. Relocated replay under Python `-O`
produced the identical result and preserved the original inventory.

In a separate source copy of the initial fixture, changing only the native
application count from seven to eight caused the first image-count assertion to
fail because the forbidden eighth image was accepted. That failure and its raw
incomplete receipt remain retained. It is a deliberate sensitivity check, not a
retried original or a runtime correction. The complete V5.3 Python suite and
focused normal/optimized checks are recorded separately below.
The [development receipt](phase3-evidence/combined-receive-resources.json) retains
source, toolchain, commands, logs, raw inventories and further reader checks.
These are development originals, not final-source hosted cohort members.

The complete 384 MiB metadata envelope, two selectable generations with all
selected sources, transition FINAL/publication completion, native interrupted
rotation, and overlap with an admitted learner operation still need their
own simultaneous histories. This batch neither replaces those obligations
with accounting sums nor marks `combined-resources` closed. It adds no hosted
subset and changes neither the eleven-subset catalogue nor its 512 planned
histories. Final-source execution remains pending.

Reproduce the whole nine-case native method in a fresh recorded source/build;
do not filter cases or combine partial executions:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtest=V53CombinedReceiveResourcesTest test
python3 -B -m scripts.v53.combined_receive_evidence "$ORIGINAL" --qualify
```

Rollback removes this test, its independent reader and navigation references.
Retain originals, including deliberately weakened negative executions. No
production rollback is needed.
