# Phase 3B — native current-target retention quorum

This batch implements a dedicated quorum-recording path over the actual native
retention ledger and existing TCP endpoint. It remains internal. The
[A04 amendment](PHASE_3_CONTRACT_AMENDMENTS.md) specifies the two new unpublished
messages; it preserves every previous fixture byte and resource ceiling.

## Native authority and force boundary

`MembershipRetentionIntent` freezes the exact original selection, permanent target
identity and two authenticated endpoints. `MembershipGrantJournal` requires the
actual installed selection and its still-current promise, the exact current
upper target, original ancestry and governing identities. The proposer is the
installed ballot's proposer. A received map or reported progress is insufficient.

The receiver conservatively merges into its own ledger, under the actual writer
and existing byte ceiling. It forces the candidate, rename and parent before an
ACK can escape. A duplicate that changes no possible endpoint does not allocate
a new revision. A later genuine complete-copy observation may narrow uncertainty;
an older duplicate cannot undo it. Foreign roots, identities, changed selections
and forged anchors reject before changing files. An observed higher ballot after
force still prevents the ACK, leaving the durable uncertainty in place.

`MembershipRetentionQuorum` binds the actual owner's shared resource accounting,
forces locally, then sends bounded concurrent requests to distinct governing
voters. IO/deadline retries repeat the identical frame at most three times within
the original deadline. Once remaining peers cannot form a governing quorum, the
round fails without waiting for the whole budget. Malformed responses fail rather
than becoming retryable availability failures. Response correlation, intent hash
and exact local durable revision/digest are checked before counting an ACK.

The in-memory permit checks the owner, ballot, exact target and original deadline
again before invoking dispatch. It is unusable after fencing or close. Cancellation
also cancels a future returned after close, and the round is single-use. The
messages use the existing trusted-private-network TCP assumptions; this is not a
TLS/authentication upgrade. Joint majority arithmetic is implemented, but this
batch's real network histories qualify stable groups only.

## Qualification and retained evidence

The source-bound [receipt](phase3-evidence/retention-quorum.json) records the exact
build snapshots, scripts, logs and byte inventories. Evidence is retained under
`target/v53-retention-quorum/`.

- Four actual public-bootstrap/election/BARRIER histories cover stable 3/4/5
  voters plus a three-voter lost durable ACK with the other peer unavailable.
  Native TCP carries the requests and replies. The sender repeats the exact
  request and obtains the required distinct majority before its recorded callback.
- Ten halt/SIGKILL cases reuse one separately initialized native history and
  interrupt prefix write, force, rename, parent force and pre-ACK return. Five
  live lock probes check exclusive ownership. Fresh processes retry the original
  request and confirm duplicate stability after recovery.
- Independent Python replay first derives bootstrap files, original grants,
  selected generation, all first-publication phases and reclamation. Only then
  does it check every new ledger byte, wire frame, majority, retry and dispatch
  ordering, plus complete interrupted/recovered file maps. Nine mutations must
  reach their exact expected rejections after the original evidence passes.
- Additional Java-only checks cover exhausted attempts, the original deadline,
  malformed acknowledgements, cancellation during future registration, invalid
  identity/anchor/request, wrong resource owner and force-to-ACK fencing. These
  checks are not mislabelled as independently replayed network histories.

The initial isolated build failed while writing test request evidence because
node IDs containing hyphens were used as JSON keys. That failure, its original
files and logs remain retained. The corrected test writes explicit row objects.
The final source/build receipt distinguishes this correction from the production
implementation and does not count the failed build as successful.

## Required continuation

The permit currently invokes a recorded test callback; it is **not yet wired to
an autonomous production installation/publication loop**. The upper endpoint must
already be the authenticated current generation at every acknowledging voter.
Future publication targets cannot be supplied by pretending applied-end state is
already current. The owner must next establish that separate proof boundary,
maintain bounded possible endpoints across genuine offline survivors and election
turnover, and connect actual dispatch/observation.

Cross-view pending contexts, learner ADD/REPLACE, complete joint FINAL, generalized
publication and the remaining 3B–3E fault/closure gates remain open. No public
runtime, protected CI, cloud experiment, power-loss qualification or full Phase 3
acceptance is implied. Rollback is specified by amendment A04.
