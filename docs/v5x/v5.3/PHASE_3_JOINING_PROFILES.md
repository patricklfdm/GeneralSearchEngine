# Phase 3 — native joining profile prefixes

The same native execution path can now start the five joining profiles:
`3-ADD`, `4-ADD`, `3-REPLACE`, `4-REPLACE`, and `5-REPLACE`. It runs public bootstrap,
actual old-majority activation, RESERVE/PREPARE, TCP source acquisition, typed
learner READY, maintenance, SEAL, original INTENT phases and JOINT publication.
Every run retains its original directories, identities and attempt; no prepared
fixture supplies the resulting INTENT history.

This batch's new entry point deliberately ends at **JOINT**. It is not the
complete `3-ADD` entry point already qualified through FINAL and cold reopen.
The other profiles still need that continuation and the complete physical,
network, process and frozen S/N mapping gates. REMOVE has no joining learner and
remains a separate execution family. Phase 3 remains open.

## Separate majority rules

Only the first `floor(oldSize / 2) + 1` old voters are online. REPLACE removes the
last, offline old voter; the new permanent identity is `node-(oldSize + 1)`.
These choices are fixture topology, not a production membership policy.

| Profile | Online old voters | Target voters | Does the old set alone satisfy the JOINT checkpoint? |
| --- | --- | --- | --- |
| 3-ADD | 1, 2 | 1, 2, 3, 4 | No: the new view needs three |
| 4-ADD | 1, 2, 3 | 1, 2, 3, 4, 5 | Yes |
| 3-REPLACE | 1, 2 | 1, 2, 4 | Yes |
| 4-REPLACE | 1, 2, 3 | 1, 2, 3, 5 | Yes |
| 5-REPLACE | 1, 2, 3 | 1, 2, 3, 4, 6 | Yes |

The actual checkpoint verifier tests this distinction. Every profile still forces
and retains the real learner's eligible new-side ACK. It does not turn that ACK
into an old-side ACCEPT/PROOF vote, and the test does not require an unnecessary
joining ACK to appear in a minimal overlapping checkpoint. The native test helper
now records future retention for **every selected old peer** before dispatching
any of their publications, rather than only handling node 2. The original two-voter case has the same order.
Production code, quorum definitions, protocol bounds and frozen plans are unchanged.

## Execution and independent replay

```bash
# One complete prefix, one fresh source/build and output directory.
python3 -B -u -m scripts.v53.joining_profile_run target/joining-prefix-4-add \
  --profile 4-ADD --maven /opt/maven/bin/mvn

# Optional identical producer source, but always new disks/history/build/output.
python3 -B -u -m scripts.v53.joining_profile_run target/joining-prefix-3-replace \
  --profile 3-REPLACE --source-from target/joining-prefix-4-add \
  --maven /opt/maven/bin/mvn

# Re-read original retained bytes; no native measurement is rerun.
python3 -B -m scripts.v53.joining_profile_evidence /path/to/original/raw \
  --profile 4-ADD --qualify
```

The driver copies immutable source, builds offline, selects exactly one JUnit
method/profile and checks its single non-skipped result. It retains source,
toolchain, build, process exit, logs and raw evidence. Progress is emitted every
minute. The driver never automatically retries a failed execution. It then invokes the reader from that same
source copy. A successful scoped result is still `PARTIAL`, with FINAL/cold and
Phase 3 flags false. An existing output is never overwritten.

The reader takes the profile explicitly. Producer PASS/profile labels do not
supply authority. It independently derives bootstrap and each catalog transition,
checks original ACCEPT/PROOF certificates, selected bases, per-owner applied ends,
typed image/receipt and joining ACK, then verifies every published checkpoint and
both majorities. Every offline old owner must retain its exact prior bytes.
The round lifecycle retains original installation, slot and readiness checks.

The pending snapshot stage requires original typed/pending roots and rejects
premature placement/native roots. It cannot pass a placed or native gate.
Original-first negatives remove an applied/published slot, change the pending ACK,
change an applied catalog or change an offline owner. Each must fail for the
exact expected reason; an invalid original never counts as successful rejection.
A separate original-copy check changes producer labels and confirms they do not
change the derived REPLACE history; an explicitly wrong reader profile is rejected.
This is semantic replay, not a claim of force/transport/process qualification.

## Validation and remaining execution

The first `3-REPLACE` execution reached JOINT but the new pending snapshot mistakenly
called the placed-original reader, which requires a custody decision not yet
created at this stage. The collector now resolves pending original paths directly,
without creating or reading a placement/custody decision. A focused filesystem
regression checks exact copies, absence of custody and unchanged original files.
The first `4-ADD` producer exhausted the inherited 12-minute fixture endpoint
lifetime; its server failures explicitly record the original endpoint deadline.
Only this new prefix entry now uses the existing 20-minute fixture lifetime,
fixed once at owner construction. RPC/retry/source budgets, legacy entry points
and production/frozen parameters are unchanged. The obsolete collector-only
correction run was stopped after identifying this bound, with its partial
evidence retained. Failed producers remain separate evidence; final-source executions start
fresh histories rather than resuming or stitching a failed stage.

Actual local results and source/build hashes are recorded in
[the batch receipt](phase3-evidence/joining-profile-prefixes.json). The `3-REPLACE` producer completed all nine slots and its semantic replay with
five exact negatives. The later `4-ADD` execution reached an applied INTENT but
exposed a second helper defect: recording node 3's future intent after publishing
node 2 loses an old-view recorder. Production `MembershipSlotDriver` already
records every target before dispatching any publication. The test helper now
matches that order; a shorter real four-node TCP view-switch regression checks
both recording quorums before either publication and all three published owners.
Its SEALED setup is a conditional fixture, not whole joining evidence.

The qualified REPLACE history and the latest helper regression have separately
recorded sources/builds. All five complete current-source prefix invocations,
including the corrected 4-ADD rerun, are deferred to the hosted cohort, as allowed
by the development plan. No failed history becomes accepted because the short
regression passes. Existing complete
`3-ADD` evidence is regression-replayed separately and is not relabeled as a new
current-source native execution.

Whole independent profile histories may run on separate hosted runners. A
single prefix/continuation's source, lease, history and original disks must stay
together; do not split its stages to reduce wall time. Hosted acceptance still
requires a fixed source/build, all profiles, original-first replay and the
unchanged S/N mapping. No workflow is added or dispatched by this batch.

## Next implementation boundary

Extend the post-JOINT part of `V53JoiningIntentExportTest` to use the actual old
selected set for head confirmations, governing-floor copies, retention seed
preparation and owner reopen. The existing `1 - voter`, two-copy loops and fixed
node-4 continuation assertions are specific to the original 3-ADD history.
They must not silently govern the larger or replacement cases.

In overlapping profiles a correct activation may select only old voters, because
that set already satisfies both majorities. Do not force a joining vote into a
minimal selected set or weaken the verifier to accept arbitrary sources. Retain
actual joining initialization and separately exercise its subsequent participation
or newer-view adoption, while deriving publications from the actual selected set.
Generalize the complete original physical/network readers together with those
executions before promoting any FINAL/cold/profile qualification flag.
