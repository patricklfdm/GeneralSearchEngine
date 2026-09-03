# GeneralSearchEngine V4.1 Phase 6 operational evidence

Phase 6 supplies scale, performance, source-loss and replacement-host evidence for
the already implemented V4.1 operations. It adds no production API, storage-format or
retrieval-semantic change.

## One evidence path

The benchmark-only `V41OperationalEvidenceProbe` owns two independently executable
stages. The source stage loads the frozen corpus in bounded batches, performs the
frozen pre-backup mutation count, records exact state, starts a writer-ordered live
backup, measures reads and one post-cut write while the backup is active, and checks
the resulting bundle structurally and semantically. The restore stage independently
verifies the transported bundle, restores it as a new history, scans every document,
checks retrieval and post-cut exclusion, performs the frozen continued mutations,
checkpoints, closes, reopens, repeats the complete checksum and runs the bounded
restored-store measurement.

The local runner executes both real stages and removes the source store between them.
The paid runner uses the same JAR and Python validators on two separate VMs. It uploads
an immutable tar plus SHA-256 and source properties to GCS, deletes and verifies
absence of the source VM and source disk, deletes all local source copies, downloads
the transport into a fresh workspace, independently parses it, and only then creates
the replacement VM and restore disk. Source and restore data disks never coexist, so
the frozen 500-GiB regional quota remains safe.

Before the first paid Compute resource, the member writes, reads, compares and deletes
a payload-free permission probe under its exact unique transport prefix. This proves
that the environment-bound service account has the `storage.objects.create`,
`storage.objects.get` and `storage.objects.delete` authority required by the complete
lifecycle. Delete authority is granted only for the
`v4.1-operational-safety/` object prefix. Both VMs block project-wide SSH keys and use
instance metadata, so the workflow never needs to modify project SSH metadata.

## Frozen matrix

| Control | Value |
|---|---|
| Evidence schema | `gse-v41-operational-evidence-v1` |
| Set schema | `gse-v41-operational-evidence-set-v1` |
| Suite / preset | `v4.1-operational-safety-suite-v1` / `v4.1-operational-safety-v1` |
| Eventual baseline | `v4.1.0-operational-cloud` |
| Profiles / members | experiment `1`, canonical `3`, failure-drill `1` |
| Scheduling | serial independent members |
| Machine | Standard `c3d-standard-30` |
| Source / restore disks | separate `pd-balanced` `200 GiB`; never concurrent |
| Filesystem | `ext4`, mount options `defaults` |
| Corpus | `100,000` documents, exactly `16` tokens/document |
| Mutation elements | `10,000` before backup, `1,000` after restore |
| Measurement | `1,800` seconds per member for every profile |
| Maximum member runtime | `5,400` seconds |
| Complete-run ceiling | USD `25` |

Canonical and failure-drill sets require GCS retention. Experiment evidence may use
Actions-only final retention, but every real source-loss member still uses a temporary
GCS transport object and proves that object is deleted. GCS is never live WAL,
checkpoint or store authority.

## Evidence and cleanup

The final member bundle records source impact, backup duration/bytes/observed peak,
independent structural identity, semantic document count, restore/first-open/
checkpoint/second-open timing, retained bytes, heap, disk bytes and restored-read
throughput. Logs are bounded and document payloads, credentials and OIDC material are
excluded.

Every successful receipt independently records deletion of source VM, source disk,
replacement VM, restore disk and temporary GCS transport. The aggregate set requires
distinct backup content identities and new histories across members, identical frozen
configuration, one exact protected-master source, ordered slots, passing checksums and
complete cleanup. Only a three-member canonical set is registration eligible.

## Paid-run boundary

The manual workflow is `.github/workflows/v41-operational-evidence.yml`. Before it may
run, its exact protected-master commit must pass CI, local smoke and fake-cloud gates
must pass, the OIDC provider must explicitly allow this workflow from
`refs/heads/master`, the prefix-limited transport delete role and permission probe
must pass, quota must accommodate one `c3d-standard-30`, and the operator must
explicitly confirm the paid run. Experiment runs validate plumbing first; canonical
execution and append-only registration follow only after review.
