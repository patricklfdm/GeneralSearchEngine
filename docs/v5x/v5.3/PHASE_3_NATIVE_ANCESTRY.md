# Phase 3B — native activation across unequal compacted histories

Status: locally qualified. The [source/build/evidence receipt](phase3-evidence/native-ancestry.json)
binds the final corrected sources and complete original-first replay. This component
does not close Phase 3 or enable public membership operations.

## Fixed originals and missing history

The first complete eligible quorum fixes the exact source owners, BASIS records,
packets and accepted tails before missing-ancestry I/O begins. The driver cannot
replace one source inside that ballot merely because obtaining its proof is slow.
The selected receiver independently reconstructs the same decision.

When the longest source lacks a directly represented lower cut, a local source
uses its actual current generation's authenticated supplemental ancestry. A remote
source supplies its complete read-only current prefix, exact generation manifest
and ancestry file. Its current packet and original BASIS packet may differ when
an unpublished accepted tail exists. Verification therefore authenticates the
current prefix first and projects only its proven history onto the unchanged
original BASIS packet. A cut comparison or bare digest is not sufficient.

Each required lower anchor must have exactly one verified bridge. Historical
ACKs remain copied historical proof; they do not become new voting observations.
All sources, images, guards and the original deadline remain live through the
selected installations. Lost transport responses use the existing finite identical
retries; an exhausted required source needs a fresh ballot and the existing failed
peer rotation. Invalid proof, fencing or deadline expiry cannot silently reselect.

## Installation and physical lifetime

Install other selected remote voters before the longest remote original, and
install the proposer last. Otherwise replacing the longest generation can revoke
a prefix export while another receiver still needs its original ancestry. This
ordering retains the normal revocation rule rather than extending old generations'
authority. Only the selected longest packet's exact image inventory is installed;
the union of all older/newer source images is not a valid materialization.

A sealed internal image-borrow interface admits only the actual source export or
a complete receiving owner. A read-only prefix can reuse its already received
original's images without another physical copy. Packet bytes are still separately
received and bound to the exact original manifest.

An unpublished local vote reserves completion capacity. Receiving a lower source
must also be able to reuse an identical image in a complete older local BASIS.
The existing export pins that backing source against retirement until its original
expiry/close. It checks the actual source inventory, hash, length, inode and owner.
These extra local images never enter its remote references or chunk inventory;
they provide neither old voting authority nor a new source receipt. Incomplete
captures and retiring sources are unavailable for this borrow.

No SOURCE/APPLICATION counts, byte budgets, time limits or durable/wire formats
change. Extra prefix scratch uses the existing outgoing `source-UUID` layout or
the incoming selected set's unused local source slot, preserving bounded recovery.

## Qualification obligations and retained failures

- Twelve actual public-bootstrap histories cover 3/4/5 voters, EMPTY/backup and
  either a lower proposer or lower follower. Publish BARRIER everywhere and DATA
  on the other majority, then reopen actual owners and activate through TCP.
- Two additional histories retain a real unpublished DATA acceptance on the
  longest source, in both directions. Installation and reopening must preserve it
  without publishing its application effect or creating another vote.
- Five deterministic proof faults exercise a lost reply, exhausted original,
  malformed manifest, higher promise and original deadline expiry. Physical borrow
  tests cover full seven-image capacity, incomplete originals, corruption, inode
  replacement, foreign roots, close/expiry and retirement exclusion.
- Independent replay reconstructs original publication/votes and typed images
  before deriving grants, source packets, selection, every transfer, installation
  and reopened file. Only bounded byte-identical control retries may share one
  exchange; changed/excess retries reject, and duplicate force events still reject.
  Original-first normal/optimized/portable replay and all exact evidence mutations
  are required before this batch is qualified.

The evidence workspace `target/v53-native-ancestry/` retains the original missing
bridge rejection, lost local historical keys, union-image refusal, concurrent
longest-generation replacement, draft compilation error, accepted-tail image
capacity failure, and the oracle's initial rejection of valid identical control
retries. Intermediate passes are not substituted for corrected-source qualification.

## Completed local qualification

The corrected-source matrix completed all fourteen histories. Independent replay
verifies 32 selected installations and 864 source exchanges across the twelve
unequal-cut profiles, plus four installations and 72 exchanges across the two
unpublished-tail profiles. All 22 normal and 27 tail mutations reject for their
intended reasons. Normal, Python `-O` and unpacked portable replay agree on the
same unchanged original bytes. These are explicitly invoked campaigns with
same-JVM native reopen; they do not establish autonomous runtime recovery.

The complete isolated 17-suite Java build passes 144 tests with zero failures,
errors or skips. All ten related component/crash replay qualifications pass against
their new original evidence. All 622 Python tests pass normally and under `-O`;
documentation contract/link and exact source/build/raw hash checks pass. The normal,
optimized and portable claims above describe the new matrix; related component
replays are separately reported in the receipt with their own validation scope.

## Remaining Phase 3 work

Campaigns here are explicitly invoked. Autonomous election/discovery/adoption,
repeated maintenance, cross-view pending contexts, learner ADD/REPLACE and joint
completion, generalized publication and the full Phase 3 distributed/process audit
remain open. These component tests do not close an S family or claim protected CI,
paid cloud, public READY, or fresh-process qualification for these new histories.

Rollback removes automatic ancestry composition and its internal borrow extensions,
restoring explicit-proof adapters. Persisted formats and previous evidence remain
unchanged. No POM, workflow, V5.2 Runner, remote push or release change is included.
