# Phase 3 — profile control exports and retention majorities

This follows [profile content export authority](PHASE_3_PROFILE_EXPORTS.md).
The shared control reader previously interpreted each local/remote pair as a
complete retention quorum and expected exactly two old head confirmations. That
fits its three-node original; four/five-node profiles require more voters.
The new profile adapter derives those obligations from the actual topology and
original INTENT certificate, retaining the existing byte and force checks.

## Original quorum before export

Each remote retention reply is bound to the original local SELECTED, PROMISE,
catalog request, joining identity, current endpoint and expected remote ledger
bytes/revision. Its original receiver force sequence must precede the reply.
The local ledger must be forced once before the first request in that recording.

Replies are grouped by their original sender and trace. Their view, ballot,
payload, owner generation and fencing boundary must agree. Voters are distinct:
duplicate, local-as-remote and foreign voters are rejected. Only delivered ACKs
before the original fence can count. The permit starts at the earliest delivery
that supplies both governing majorities, not at the first remote ACK or at an
unnecessarily late extra reply. ACKs from another trace cannot fill a quorum.

The resulting recording endpoints must exactly equal those needed by the
original pre-JOINT learner exports. This complete healthy fixture prescribes two
such endpoints; neither an unused recording nor an unrecorded export is accepted.
Every learner content session remains bounded by its original permit lifetime.

The old owners required to confirm the retained learner head come from the
original INTENT certificate's proof voters. Every query must address the actual
profile joiner and follow its retained-owner handoff. The resulting confirmation
must be durably recorded by that original old owner. Preparation hints and
retention fragments remain bound to their exact original grants; the declared
fragment count follows that original old cohort.

## Composition and negative evidence

```bash
python3 -B -m scripts.v53.joining_profile_control_evidence /path/to/original \
  --profile 4-REPLACE --qualify
```

The complete physical continuation, attempted network and content authority gates
run first. All remaining root, INTENT metadata, preparation, retention fragment
and completion sessions must be accounted for. Exact total content/session counts
must agree with the original transport reader. A valid control result does not
establish maintenance/ledger composition or complete profile/process qualification.

Fourteen control negatives use disposable copies while protecting all physical
inputs. Broken transcripts, unrelated errors, missing required mutation targets
and accepted mutations fail qualification. The closed-owner mutation targets the
shared endpoint-lifetime check now also enforced by the preceding content reader;
its rejection stage is recorded explicitly. The other thirteen cases must pass
both preceding gates before their exact control rejection can count.

The [receipt](phase3-evidence/profile-controls.json) records the frozen reader,
historical original provenance, measured tests, original-first negative results
and independent extracted-archive replay. Conditional tests cover all five
ADD/REPLACE profile identities, three old head confirmations, four/five-voter
quorums, separate joint sides, duplicate/foreign/undelivered/fenced replies,
mixed traces/intents, original endpoints and qualification isolation. They are
not evidence of five new native executions.

The first ADD replay exposed an adapter error before negative qualification:
an old voter's pending checkpoint read was mistakenly included when deriving
required learner recording endpoints. That pending listener precedes ordinary
native joining ownership and has its own separately checked authority. Restricting
the recording derivation to actual learner requests corrects the classification;
the pending export still passes its original byte/force/lifetime gate. The failed
original replay and a regression that fails before the correction are retained.

The second ADD replay identified two original frozen BASIS source sessions that
cross a generation switch. They are not learner aliases: source capture and
retirement already bound their separate authority. The adapter now classifies
against the generation that issued the first offer and requires a full-session
generation lifetime only for actual learner aliases. A paired regression accepts
that independently authorized source transfer and still rejects a learner
transfer crossing the same boundary. Both failed attempts and their reader
manifests remain available; the original transcripts were not changed.

Measured validation: all 1,822 V5.3 Python tests pass, including twenty-one new
conditional boundary tests. Retained 3-REPLACE and historical 3-ADD each pass all
fourteen exact control negatives. Their full compositions account for 502 and 686
committed contents respectively, including the eight control exports that the
preceding content gate deliberately leaves unqualified. The existing full
same-view composition also passes. These are three retained histories, not new
native executions of the larger profiles.

All three results are identical after extraction and replay with Python assertions
disabled. The 51,472,822-byte archive retains 25,992
files, original producer metadata, all three reader attempts and both failed ADD replays.
Original and relocated inventories remain unchanged.

## Remaining closure and rollback

The complete current-source seven-profile cohort remains deferred together with
whole-history process/fault qualification. This adapter qualifies the declared
healthy profile histories; interrupted or retried retention transactions need
their own continuous-ledger and fault derivation. It does not renew deadlines or
manufacture a successful reply.

Larger-profile maintenance copies, continuous peer/learner/future ledgers,
combined resource bounds and frozen S/N mapping remain open. Phase 3 remains OPEN.
Runtime Java, persisted formats, workload/limits, POMs and workflows are unchanged.
Rollback removes the adapter and reverts the shared helper extraction while
retaining original evidence and the profile regression diagnostic. No native or
paid-cloud workload is rerun or triggered in this batch.
