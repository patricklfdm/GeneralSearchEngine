# V4 durable evidence workspace

This directory is the local download and review workspace for V4 single-node durable
benchmark and failure evidence. Experiment, canonical, replacement-VM failure-drill,
quota-failure, cleanup, and checksum bundles are ignored by Git and remain outside
Maven `target/`, so a clean build does not remove them.

Keep each downloaded artifact directory unchanged while validating its checksums,
source commit, profile, member status, cleanup proof, and aggregate set. Do not combine
files from different workflow runs or attempts. A failed or quota-limited attempt is
part of the local audit history and should remain distinguishable from accepted
evidence.

Git contains only stable, curated conclusions and content identities. The accepted
Phase 6 evidence is recorded in
[`docs/v4/PHASE_6_CANONICAL_REVIEW.md`](../../docs/v4/PHASE_6_CANONICAL_REVIEW.md),
[`docs/v4/PHASE_6_CHECKLIST.md`](../../docs/v4/PHASE_6_CHECKLIST.md), and the
append-only
[`docs/v4/cloud-benchmark-baselines.json`](../../docs/v4/cloud-benchmark-baselines.json).
The release boundary is recorded in
[`docs/v4/RELEASE_CHECKLIST.md`](../../docs/v4/RELEASE_CHECKLIST.md).

For GCS-retained canonical evidence, the immutable object generation and registered
set digest are the durable remote binding. This ignored directory is a local mirror,
not the only authoritative copy. Do not force-add raw evidence or credentials to Git.
