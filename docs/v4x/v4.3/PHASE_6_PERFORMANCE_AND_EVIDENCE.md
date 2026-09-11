# GeneralSearchEngine V4.3 Phase 6 performance and evidence contract

- **Status:** Canonical evidence accepted; append-only registration under protected review
- **Canonical source:** `1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6`

Phase 6 measures the accepted `(1,2)` implementation. It may add benchmark-only
instrumentation and a manual cloud workflow; it may not change production reopen,
fallback, checkpoint, backup, restore, migration, cleanup, or retrieval behavior.

## Frozen identities

- artifact schema: `gse-v43-fast-reopen-evidence-v1`;
- cloud-plan schema: `gse-v43-fast-reopen-cloud-plan-v1`;
- aggregate schema: `gse-v43-fast-reopen-evidence-set-v1`;
- suite: `v4.3-fast-reopen-suite-v1`;
- preset: `v4.3-fast-reopen-v1`;
- eventual append-only baseline: `v4.3.0-fast-reopen-cloud`.

## Required matrix

Every member records these ten cells against one retrieval oracle:

1. published `4.2.0` forced canonical rebuild;
2. current `(1,2)` forced full rebuild;
3. complete warm reopen;
4. one corrupt structured component and partial fallback;
5. one corrupt text component and partial fallback;
6. corrupt catalog and full fallback;
7. complete-warm checkpoint plus committed-WAL recovery;
8. restored target cold first and warm second;
9. migrated target cold first and replacement-host warm second;
10. continued mutation, dynamic index drop/create, checkpoint and reopen.

Forced rebuild uses benchmark-only deletion of non-authoritative derived members. It
does not add a public or production switch. Checksums, sequences, selected retrieval
queries, fallback counts, derived bytes read, canonical/derived/directory/temporary
bytes, heap, GC, CPU, process I/O and explicit OS-page-cache state are evidence.

## Scale, topology, and thresholds

Production members use 100,000 documents, 16 tokens per document, four built-in
indexes, 10,000 mutations, a 1,800-second measurement window and a 5,400-second
maximum member runtime. Each serial member uses Standard `c3d-standard-30`, one
200-GiB `pd-balanced` primary disk, one transient 200-GiB target disk and one
auto-deleted 100-GiB `pd-balanced` boot disk. Peak use is 30 vCPU, 400 GiB of data
disk and 500 GiB of provisioned disk including the boot disk. The complete-run cost
ceiling is USD 25.

An experiment or failure drill has one member and Actions retention. Canonical has
three independent serial members and GCS retention. Every canonical member must have
`complete-warm median / current-forced median <= 0.65`; the canonical set median must
be `<= 0.50`. The evidence reports uncontrolled OS cache honestly and makes no
memory-mapping claim.

## Source, replacement, and cleanup proof

The exact protected-master SHA is validated before OIDC. A source VM creates the
published control, canonical store, canonical-only backup, restore and migration
targets. The source VM is deleted before a fresh replacement VM opens both retained
disks and completes fallback, WAL, lifecycle and long-run cells. Both VMs and both
disks must be absent before a member passes and before the next slot begins.

GCS staging and retention are confined to
`v4.3-fast-reopen/<source>/<run>-<attempt>/<profile>/member-<slot>/`. A passing cleanup
receipt proves source/replacement VM deletion, primary/target disk deletion and
staging-object deletion. Failed evidence remains bounded and cannot be registered.

## Admission order

Local smoke, independent backup inspection, Python/schema tests, fake experiment /
canonical / failure-drill plans, cloud-member dry-run, Phase 5 regression and exact
CI must pass first. The workflow remains manual and paid execution requires explicit
operator confirmation. Experiment evidence precedes canonical evidence; registration
is a separate reviewed append-only change after three-member validation.
