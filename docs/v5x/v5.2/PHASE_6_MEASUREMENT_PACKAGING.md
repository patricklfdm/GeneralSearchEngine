# V5.2 Phase 6F large measurement packages and prepared targets

**Status:** locally qualified package/replay infrastructure. No formal M01–M04
window, cloud run or new production runtime is claimed by this stage.

## Closed package profile

The predecessor package remains limited to 4,000 files. New measurement packages
have a separate profile; they do not change the old global constants or bypass
old validators. One package contains one continuous history with its source,
artifact, process and original-path identities intact.

| Bound | Value |
| --- | ---: |
| Files, including inventory | 400,000 |
| Directories | 4,096 |
| Expanded bytes, including inventory | 4 GiB |
| Compressed bytes | 4 GiB |
| One regular member | 256 MiB |
| Inventory JSON | 64 MiB |

The count accommodates three previously bounded 131,072-chunk inventories plus
other history files. Three maximum 512 MiB chunk stores and 128 MiB reference
streams consume 1,920 MiB, leaving space for authority, artifacts and the inventory.
The separate per-node 8 GiB decoded-trace and 4 MiB row bounds remain unchanged.
Stored package size does not authorize unbounded decompression of logical traces.
These are implementation ceilings; the complete execution plan must bind this
profile before formal measurements.

The archive uses ordinary USTAR files and directories. It rejects links, special
files, sparse/GNU/PAX extensions, traversal, duplicate paths, file/directory
conflicts, unlisted/missing files, altered sizes and hashes. Extension types reject
before their claimed payload is read; a regression uses a claimed 1 GiB extension
with no body. No `extract`/`extractall` path execution is used. Extraction requires
a fresh target, validates the first bounded inventory, checks each streamed member
and then checks the complete extracted inventory. Empty directories can be retained
but carry no replica authority.

`EvidenceLocation` validates the complete downloaded package and the exact retained
authority inventory before invoking the physical storage inspector with the
**recorded original paths**. It does not authorize running copied voters or replace
physical proof with a package hash. Existing smoke replay can select this explicit
package profile while retaining all source/JAR/process/history/query checks.

## Real evidence replay and CI integration

`measurement_bundle_foundation` first validates a retained real three-JVM history.
It copies those bytes, adds 4,001 labelled package-admission fixture files, packages
them and repeats actual physical/V4.4 query replay before and after relocation.
The fixture files are not runtime observations, requests, or claimed measured data.
The original evidence and inventory remain unchanged.

Standalone replay at `target/v52-measurement-bundle/development-2` passes with 4,481
files, 11 original reads, three original updates and 14 precise negatives in each
of baseline/raw/relocated replay. The predecessor package rejects this file count.
The complete required short consumer gate also invokes this qualification after
all five modes pass; its final receipt cannot pass if packaging or replay fails.
It reuses the existing evidence upload and does not change job/Required identities.

The first standalone attempt rejected the legitimate `$` character in Java nested
class filenames. The closed path alphabet and round-trip test now cover those
names. The initial path unit test also exposed `.` as an empty-component path;
that case now rejects. Both failed outputs remain retained.

## Prepared-target correction

The first integrated execution retained a `candidate-minimum` read returning
`NOT_READY`. Its target still served application sequence 1 when the short driver
started; during the eighth query it installed the three prepared updates and moved
to sequence 4. Waiting only for the original setup token was insufficient for this
**no-mutation integration window**. No failed request was retried or discarded.

Preparation now confirms the three updates on the actual read/write targets before
offering that short query stream. Strong modes require the leader; stale/minimum
also require their selected follower. Requiring publication on every follower was
tried and failed against published V5.1: its followers do not provide local reads
and may retain proven authority without the new application-publication behavior.
That failed attempt is preserved too; no V5.1 behavior or timeout was changed.

Independent replay binds the required target set, confirmed update indices,
sequence 4, exact observed status responses and their ordering before the first
query. Removing a prepared observation rejects. Deterministic tests cover an old
setup cut, recovery-in-progress, a failed voter and preparation that never catches
up. This preparation is not a leadership lease and cannot suppress a later failure.
Formal M01 has concurrent mutations and must retain legitimate recovery/read
outcomes under its separately frozen acceptance rules.

## Validation and remaining boundary

The final complete local gate is recorded at
`target/v52-measurement-runtime/run.oupfL5/evidence`. All five short modes pass
55 reads/15 updates and 62 negatives per location, 124 raw/relocated rejections.
Its final package qualification additionally replays the candidate-minimum history
without rerunning its workload. The final receipt and hash summary under
`target/v52-measurement-bundle` are the authoritative completion records.

All 94 V5.2 Python tests pass. Eighteen relevant tests also pass under Python 3.11;
forty predecessor trace/history/artifact/runtime-format tests pass. Existing CI
inventory, documentation contract, local links, shell and whitespace checks pass.
No new reactor, hosted acceptance or performance result is inferred from them.

Next complete the streaming measured validator and M02–M04 schedules, freeze the
full machine execution plan, then run the unshortened measured histories. The
smoke validator still has its separate 64 MiB decoded limit for in-memory negative
mutation; the larger package must not silently turn that into a full-window oracle.
Continue under the [local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
