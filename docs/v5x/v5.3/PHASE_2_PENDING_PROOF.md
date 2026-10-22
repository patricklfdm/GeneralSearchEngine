# Phase 2C5b — original pending PROOF over actual ACCEPT quorums

Status: local component qualification PASS. Phase 2 and the public runtime remain open.

## Local phased authority

The same exclusive `openVoting` owner now exposes a private `proveCurrent` operation.
It requires the exact actual local ACCEPT, unchanged installed SELECTED/PROMISE,
root, governing view, parent, index, ballot, ENTRY and payload. Before the first
PROOF write, every receipt must match an actual ACCEPT `Owned` observation with the
permanent voter/storage identity and exact applied parent. Distinct ordered voters
must form both applicable majorities. Receipt hashes by themselves cannot admit a
new proof. Existing certificate validation retains its strict ownership checks.

The first PROOF fixes its exact acceptance witness set. Another valid same-ballot
quorum cannot replace it; an exact duplicate returns the same local observation.
A duplicate ACCEPT preserves the forced PROOF and refuses any pending candidate,
including a zero-byte candidate created before the first PROOF write.

## Original bytes, recovery and limits

An optional original framed PROOF follows the existing private container's payload.
Original SELECTOR/PROMISE/SELECTED/ENTRY/ACCEPT/payload bytes remain unchanged.
The existing candidate write/force, parent force, atomic replacement and parent
force sequence applies, with separate PROOF evidence events. This adds neither a
frozen record/wire kind nor a new application encoding or resource lease.

A complete candidate must still match the actual active ACCEPT before recovery.
A partial candidate requires the original request and ACCEPT quorum observations.
A complete stored PROOF is the exclusive owner's durable attestation that those
observations were checked before writing; reopen verifies its original frame and
quorum structure and reseals the actual files. It does not manufacture new remote
observations. Inode substitution, malformed originals and higher observed ballots
cannot return success for an old PROOF request.

ACCEPT admission reserves space for a complete subsequent PROOF replacement and
the next maximum PROMISE/BASIS in the shared **32 MiB JOURNAL**. Future source
admission reserves one maximum PROOF plus its index row under the unchanged
**32 MiB source packet** limit. Exact PROOF admission rechecks the whole composed
source. The fresh PREPARE source preserves the original PROOF, ENTRY, payload and
ACCEPT; BASIS continues to identify the owned ACCEPT.

## Qualification scope

New local voter directories physically prepare, install and ACCEPT the same entry.
Each peer is reopened under its actual exclusive owner before the PROOF driver
uses its observation. The independent Python checker reconstructs selected
installation, every pending container, witness receipt, complete source packet and
exact force/return order from original bytes. It checks both majorities and rejects
changed peer ACCEPT bytes or omitted peer/PROOF forces.

Completed matrix: **45 scenarios / 342 fresh JVMs** (3/4/5 stable, joint and new-stable clean profiles;
halt/SIGKILL at nine PROOF boundaries; repeated death at seven recovery and two
active-reseal boundaries). Every successful scenario captures the proof through a
fresh PREPARE and independently reopens it. All **12 exact negatives** and relocated replay
passed after validation of unmodified evidence, in **277.078 seconds** overall.

The initial certified prefix and application images remain explicit historical
fixtures. This is actual local storage qualification, not network ACK delivery,
public bootstrap, application publication, power-loss testing or cloud acceptance.

## Retained results and reproducibility

The reactor passed **256 Java tests**. One later focused test passed actual
same-parent higher-ballot selection/install/reaccept: a proof held by node 2
remains byte-exact in its original frozen source even when the selected longest
source comes from node 1 without that proof. This gives **257 distinct Java tests**
across the two commands, including nine pending-PROOF tests. The **32 focused
Python/build tests** passed normally and under `-O`. The unchanged prior 42-case
ACCEPT artifact also passed independent replay.

Development retained one test compilation error, a real zero-byte candidate
regression (corrected without weakening the assertion), and the initial evidence
checker wrongly applying one voter's 80-file cap to the whole multi-voter group.
The checker now retains the original per-voter bound and an explicit six-voter
bound. Its original successful physical execution replayed unchanged after that
correction. Failed development runs are not counted as acceptance.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.pending_proof_qualification target/v53-pending-proof-new
```

[Source/build/evidence index](phase2-evidence/pending-proof.json).
Raw evidence and development logs remain under `target/v53-pending-proof/`.
The receipt binds the parent HEAD plus exact then-uncommitted checkout/JAR/class
bytes; it is not relabelled as clean-HEAD protected CI.

## Remaining integration

CERTIFICATE persistence/validation using real PROOF-quorum observations, complete
application/sequence/catalog publication, same-round contiguous progress,
INTENT termination, covered-tail and partial-request retirement, maximal lifetime
completion headroom and complete bootstrap/reopen remain required before closure.
