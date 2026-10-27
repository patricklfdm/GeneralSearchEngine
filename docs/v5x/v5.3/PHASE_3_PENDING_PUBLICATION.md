# Phase 3B — native pending-publication identity

This internal boundary identifies the exact result of a completed native
application before its selector is published. It is a prerequisite for durable
future-target retention, not that retention implementation or permission to send
a publication. Public membership remains disabled.

## Authority and lifetime

`MembershipGrantJournal.pendingPublication` accepts only the latest `Applied`
object returned by this live owner's successful native `applyCurrent`. A copied
tuple, an application produced by another owner, a previous process's result, or
an explicit-observation application cannot create this capability. Reopening must
first run native application recovery, which re-forces the actual certificate
and applied end.

Every capability access rechecks the native lock, original selector, pending
certificate, promise/selection, ballot fence and exact complete applied-end
inventory. It exposes the original parent and next cut/catalog/application,
permanent local identity, and defensive copies of seven original metadata records.
It does not create another physical application image, reserve another image slot, write
files, update the retention ledger, advance publication or return new votes.

The metadata records are the original SELECTOR, PROMISE, SELECTED, CERTIFICATE,
CATALOG, CHECKPOINT and local CHECKPOINT_ACK. These bytes alone do not establish
remote receipt, original source provenance or a checkpoint majority. Future
source transport must also bind the required original capsule and certificate
records. There is no raw-byte constructor or new production disk/wire format in
this batch.

Closing the owner, fencing it with a higher ballot, replacing its application
files or successfully publishing the target invalidates the old capability.
A failed publication with insufficient checkpoint acknowledgements does not
convert the pending target into published authority. A complete real quorum
still uses the existing publication gate.

## Local qualification

The [source-bound receipt](phase3-evidence/pending-publication.json) distinguishes
two isolated builds using identical production source bytes. The first passes
15 selected tests; the supplemental lifecycle build passes two new tests.

- Six actual 3/4/5-voter EMPTY/backup histories yield 24 native pending BARRIER
  targets. Their original bootstrap, grants and phased certificates are derived
  independently before comparing every exposed record and complete applied-end
  file map. Disk contents, publication position and resource usage stay unchanged
  while targets are inspected.
- Two fresh JVMs reconstruct the same target from the original disk, without
  supplied certificates, application images or caller voting observations. Each
  process re-forces its original certificate/end. These are normal restart checks,
  not new halt/SIGKILL or power-loss cases.
- Separate Java tests reject foreign/reconstructed/previous-owner results,
  invalidate handles after higher-ballot fencing, close and identical-byte inode
  replacement, and check defensive metadata copies.
- The additional lifecycle tests exercise a real typed DATA image above a
  published BARRIER and successful quorum publication invalidating a pending
  handle. Their results are Java qualification, not part of the six-history
  independent BARRIER replay.
- Six evidence mutations must reach their exact expected rejection after the
  original passes. Normal, optimized and archive-relocated replay agree. The
  previous native-application process evidence also replays with the generalized
  owner-aware derivation helper.

The first Python replay draft exposed a loop-variable shadowing error and an
omitted directory entry in its expected physical inventory. Correcting those
verifier errors used unchanged Java evidence; no workload was rerun to replace
the original data. The diagnostic record is retained with this batch.

## Required continuation

The future target still needs a bounded durable proof reference, atomic ledger
update/recovery, original-source capture and selected-generation propagation.
The current GSPR ledger continues to reject unpublished anchors. No generic
`required` or ancestry check was weakened. Quorum intent recording must precede
real dispatch; neither this capability nor an application ACK is a substitute.

Automatic owner lifecycle, the genuine offline-survivor bounded continuation,
cross-view pending contexts, learner/joint transitions and the remaining 3B–3E
closure requirements stay open. This batch does not change resource limits,
workflows, V5.2 experiments or release controls. Rollback removes the private
capability and its last-native-result reference; no new persisted bytes depend
on them.
