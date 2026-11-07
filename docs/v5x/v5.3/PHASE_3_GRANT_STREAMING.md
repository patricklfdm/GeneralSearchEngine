# Streaming original grant observations

This development batch removes the legacy grant-copy collector's 256 MiB
bottleneck for an explicitly selected `VERIFIED_DURABLE_BACKUP` /
`SEGMENTED_BACKUP` execution. It is preparation for a large native history,
not a completed maximum-image or combined-resource qualification.

## Caller-owned limits

| Boundary | Existing JSON entry | Explicit segmented backup entry |
| --- | --- | --- |
| Individual file | 64 MiB | 64 MiB |
| Replica copy | 256 MiB | 512 MiB, matching the existing physical owner reader |
| Members / path depth | 512 / 8 | 512 / 8 |
| Grant captures | 64 | 64 |
| Cumulative grant payload | 256 MiB | At most the existing 128 GiB whole-original allowance |

The last allowance is shared with every other retained family, wire segment,
metadata file and observation. The complete segmented verifier still inventories
the whole original before and after validation. This is not a new allowance for
each family. The small-backup hosted transport limit and the native resource
profile are unchanged; neither selects larger admission merely because a
capture is large.

`V53GrantCapture` takes explicit source/layout arguments from the joining helper.
Its old constructor remains JSON. `V53CaptureFiles` scans the bounded tree before
opening payloads and hashes through a 1 MiB buffer. Copies retain the original
v1 metadata and event schema. The collector checks original identities, exact
tree membership and hashes after copying, and checks copied bytes independently.
It borrows existing membership file descriptors so reading a live lock cannot
release the writer's POSIX lock. Links and special files are rejected.

The independent Python collector uses a deferred `physical_snapshot.Snapshot`
only under the same explicit caller policy. An immutable limits object allows
the grant tree's existing member/depth bounds without changing the ordinary
physical reader's 256-member / depth-4 defaults. Inventory metadata does not load
payloads; each semantic read checks the pinned file, and a final complete hash
check includes files not used by the semantic consumer. Mutable metadata returned
to callers cannot alter the pinned identities.

Preparation, required-four physical replay, learner handoff, ballot, network,
export and maintenance readers propagate the caller policy to their grant
collection and snapshot reads. Evidence never chooses that policy. Empty and
JSON readers retain their original bounds and receipts. The separate grant-copy
negative driver applies its caller policy to the original and all twelve exact
rejections; an unrelated failure cannot count as a successful negative.

## Development evidence

The [development index](phase3-evidence/grant-streaming-development.json) retains
logs, source-file hashes and original inventory hashes. The principal checks are:

- Real legacy and verified-backup writer fixtures each capture two complete
  grants and retain the writer lock, checked from a separate JVM. Independent
  collection and twelve negative mutations pass for each original.
- A retained complete EMPTY history's 26 grant copies produce identical rows
  through the legacy and deferred collectors. This is a component comparison;
  the history remains an EMPTY original and is not admitted as a backup cohort.
- Java inventories 320 MiB under a 32 MiB heap; Python inventories and rechecks
  320 MiB under a 160 MiB address-space ceiling. These are sparse-file component
  probes, not application images or whole-reader peak-memory measurements.
- A mutation after semantic inspection is rejected by the final original-byte
  check. Link, special-file, extent, depth, member, aggregate and explicit-policy
  rejection checks preserve fail-closed behavior.

All replay uses disposable mutation copies and leaves retained originals intact.
The initial focused Python run exposed a compatibility issue in the new limits
object: the existing depth-zero boundary test must reach the original directory
depth check. That was corrected; its failed log is retained. Final targeted tests
cover the corrected implementation. The larger Python discovery run also passed;
it began before the final negative-driver keyword propagation, which is covered
by the final focused run and actual original-derived negatives.

## Remaining work and rollback

The [object-pool follow-up](PHASE_3_CAPTURE_OBJECTS.md) now covers source-retirement
and publication-resource streaming collection under explicit segmented policy.
Semantic derivation may still materialize application images. The maximum physical
snapshot bound and whole-reader memory need further work before a maximum-image
native execution can be accepted. The full default-
staging history, 150-negative gate, simultaneous resource ownership and final-
source execution remain unqualified. All five Phase 3 closure gaps remain open.

Rollback removes the explicit grant policy, streaming helper and propagated
reader arguments together. Existing JSON constructors, event/metadata schemas,
originals and frozen runtime/resource limits remain intact. No production Java,
POM, workflow, paid-cloud behavior or V5.2 evidence changes in this batch.
