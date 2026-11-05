# Original receiving reservations and forced floor handoff

The required-four resource entry now derives receiving SOURCE, LEARNER and
APPLICATION reservations from the original transfer sessions. It first admits
physical/network/export/maintenance evidence and all four continuous ledgers.
A transfer ID is matched to its original receiver, peer, session, chunks and
commit. A journal total or another same-sized file cannot supply expected bytes.

For each CAPSULE, the receiving lease must be acquired after the original offer
arrives and before the first chunk request. It must carry the exact original
packet size through the original commit delivery. APPLICATION leases must be
acquired after the final packet chunk arrives, before the packet commit is sent,
and before requesting the image offer. The image digest and size come from the
original packet and full transferred image bytes, not resource observations.

Learner metadata growth uses the complete authorized original generation: its
manifest and every non-image member, including `source.gscp`. The original
metadata transfer must complete before growth; growth must precede the recorded
reservation callback. Metadata and received images remain charged through the
source directory force. Each learner charge must then participate in the existing
atomic GENERATION_COMMIT, SOURCE_COMMIT or TRANSFER operation; received images
must participate in TRANSFER. Releasing a staged learner or image in place of
these handoffs is rejected. The lower accounting reader independently checks the
complete operation delta, pending claims and byte conservation.

For every remote floor copy, the original maintenance correspondence identifies
its exact `retained-current-packet` transfer. Its receiving SOURCE lease stays live
through `FLOOR_COPY_DIRECTORY_FORCED`, then releases no later than the corresponding
`FLOOR_COPY_HANDED_OFF`. Copy storage and the original local pin are separately
checked by the [floor reader](PHASE_3_FLOOR_RESOURCE_BINDING.md). This checks the
overlap between receiving scratch and forced copy storage without assigning a
lease based on a matching byte count.

All receiving leases in this successful required-four profile must be present
and complete. The full mutation journal exposes extra temporary leases and any
release/reacquire gaps between callbacks. UUID SOURCE owners derived from original
BASIS captures are distinguished from receiving transfer IDs, and collisions are
rejected. This identification does not qualify those persistent bases' complete
storage lifetimes.

## Validation

Twenty-one conditional regression tests cover original byte derivation, strict
original generation authorization, all three learner handoff operations,
resource categories, basis/transfer separation, exact event checkpoints, missing
originals and original-first admission. These fixtures do not qualify native
execution. The negative driver retains nineteen mutations of journals and
checkpoints, including wrong sizes, foreign transfer IDs, late image reservation,
metadata growth ordering, early release and lifetime gaps. Arithmetic and totals
are recomputed; each mutation must fail for its exact declared reason. Original
files, wire bytes, event rows and the derived expectations remain unmodified.

The retained full required-four original at Java source `f0b60e1d` is reused;
no Java or native workload is rerun for this Python-only reader. The independent
receiving diagnostic binds 165 transfers (159 SOURCE, three LEARNER and three
APPLICATION), 1074 event checkpoints, 117 remote floor handoffs and 26 distinct
persistent BASIS owners. Complete physical/network/export/maintenance and all
four ledger replay pass on that same original, followed by all nineteen exact
receiving negative rejections. Complete replay and negatives took 457.7
seconds. All 164 related Python/contract tests pass. The original inventory and
1128 Java/resource input hashes are unchanged. Reports and source hashes are
retained in the [development index](phase3-evidence/receive-resource-binding.json).

```bash
python3 -m unittest scripts.v53.test_receive_resource_evidence
python3 -m scripts.v53.receive_resource_negatives "$ORIGINAL"
```

## Scope and remaining work

This qualifies receiving reservations through the named transfer/metadata/floor
boundaries, plus atomic handoff conservation. It does not establish individual
post-handoff learner file custody: equal-size images in one atomic transfer cannot
be assigned to destination owners merely by size. Direct receiving-file creation,
delete and parent-force captures, persistent BASIS storage, other control/storage
owners, simultaneous physical peaks, maximum-capacity completion and final-source
execution remain separate obligations. Bootstrap before the observed lifetime
also remains outside this reader's scope.

No limits, production Java, durable/wire formats, workflows, POMs or paid-cloud
behavior change. Phase 3 remains OPEN; the twelve hosted subsets and 544 planned
histories are unchanged. Rollback removes the receiving reader, negatives, tests
and its native-entry call together; the original evidence remains intact.
