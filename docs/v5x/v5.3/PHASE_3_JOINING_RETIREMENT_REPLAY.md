# Native joining retirement and ownership replay

`scripts.v53.joining_retirement_evidence` extends the independently derived
[placement](PHASE_3_JOINING_PLACEMENT_REPLAY.md) through predecessor retirement
and the immutable native ownership handoff. It uses the same original `df22c398`
`3-ADD` execution; no workload was rerun, combined or retried. The
[batch receipt](phase3-evidence/joining-retirement.json) binds source, original
inputs, tests and relocated replay.

## Derived transition

The reader reconstructs all 46 deletions from the ten declared custody roots.
Only predecessor payloads are removed. Original empty lock files, the unique
typed preparation/LEARNER proof and the installed replica survive. Directories
are deleted after their children in the fixed root/depth/name order. A recorded
delete list cannot introduce a live generation or omit predecessor payloads.

All eleven predecessor reservations are calculated from the derived PREPARE,
SEALED and INTENT sources and dormant voter files. Equal image contents in
different owners remain separately charged. The original typed backup keeps
its full 64 MiB completion reservation. Pending-journal and staging companions
retain their complete envelopes even after their files are deleted; current
disk usage cannot replace the original accounting.

The reader derives the retirement decision/completion, then the native handoff
with its four exact reservations: application image, installed generation,
32 MiB grant journal and 2 MiB immutable metadata. It checks the immutable
metadata extent, original path bindings, exact fingerprints, all nine sidecar
families, absence of every retired member, and 33 surviving original inode keys.
Twenty-four files compare byte-for-byte with independently derived contents.
Recorded paths and keys remain observations; replay never opens those paths or
substitutes inodes from a downloaded copy.

The 22 negative variants must first pass the preceding placement reader and
then fail for the declared new reason. Mutations include wrong deletion lists,
undercharged or aliased reservations, forged completion/ownership records,
retained predecessor payloads, missing live typed proofs, replaced original
inodes, changed absent-root paths and unowned sidecar files. Downstream hashes
are refreshed for changed retirement records, so checksum consistency alone
cannot satisfy the new derivation.

```bash
python3 -B -m scripts.v53.joining_retirement_evidence <original-raw-directory> --qualify
```

## Scope and remaining work

The native snapshot was collected **after** joining retention initialization and
its own grant/cold reopen. This reader derives the preceding ownership handoff;
it does not treat those later bytes as original native authority. Allocator
replacement and appended grant bytes, the three initialized ledgers and their
transaction, and newly captured sources still need physical derivation from the
original old-voter joint preparation. They are excluded from the 24-file byte
comparison. The original grant inode is nevertheless preserved.

Continue with SEALED learner confirmation, original old-majority maintenance and
joint source freezing, then derive initialization, own grant and cold reopen.
Joint recapture, FINAL/new-stable installation, complete force/network ordering,
fresh complete send/arrival observations, process cuts, all seven profiles and
frozen requirement mappings remain required. This batch qualifies only
`joiningRetirementPhysicalQualified` and `nativeOwnerHandoffPhysicalQualified`;
native initialization, complete physical/network/process and Phase 3 flags stay
false. Runtime Java, POMs, workflows, persisted formats and frozen limits are
unchanged.
