# Phase 3B — current-view incoming activation endpoint

The private `MembershipActivationEndpoint` connects actual incoming PREPARE,
SELECTED and source-transfer requests to the journal, original-record pull and
selected-state receiver. One control worker runs separately from source handlers,
so reverse requests can progress while the receiver waits for original bytes.
The endpoint borrows the journal and link; its owner must close the endpoint and
transport before the journal. It is not the automatic campaign scheduler or public
membership runtime.

## Authority and lifetime

- A current-view PREPARE checks root, full permanent identities and the proposer
  before observing its ballot. This observation does not wait for the writer
  monitor and can fence a force already in progress. It grants nothing. The
  receiver fetches and verifies the proposer's actual original PROMISE before
  forcing its own PROMISE/BASIS and exposing that source.
- A source pull's correlated REJECT with a valid higher promised ballot also
  fences the journal and revokes the scope. Foreign or uncorrelated replies fail
  validation before that observation. The correction has a retained failing
  regression against the earlier endpoint that only propagated the read failure.
- The highest admitted scope retains its first start time even after expiry.
  An identical or changed request cannot reopen that same expired ballot. A new
  higher ballot is required. Registering a local campaign inherits its actual
  original start and the stricter of the endpoint/campaign budgets.
  This scope/deadline retention is in memory for this endpoint lifetime; process
  restart/session recovery remains part of the open 3B recovery obligation.
- One retained control task accounts for its request/reply. Identical in-flight
  requests share that task and exact result. A different concurrent control gets
  a correlated CAPACITY_EXCEEDED rejection; there is no unbounded control queue.
  Failed exact requests retain their failure rather than starting another set of
  source retries. Each source exchange still has at most three attempts and the
  caller's stricter retry limit.
- SELECTED fetches the original decision and each selected source from its actual
  owner, recomputes the decision, and returns INSTALL_ACK only after local durable
  installation and final scope checks. Historical witnesses and ancestry remain
  explicit verified inputs; the endpoint does not infer them from received hashes.
- A periodic expiry task revokes scopes without requiring another network request.
  Higher-ballot replacement, expiry and close cancel tracked pending network
  futures and release transfer exports. Network waits and export closure occur
  outside the journal monitor. Close drains the control worker before releasing
  the owned empty scratch directory; foreign files are preserved and reported.

The incoming budget starts **before** waiting for the journal snapshot. A retained
regression restores the earlier, incorrect post-wait start and observes one source
I/O after the request's original budget has elapsed. The corrected path must issue
zero source requests. Timeouts here remain finite protocol limits, separate from
soft experiment time/cost budgets.

## Qualification

The source-bound [receipt](phase3-evidence/activation-endpoint.json) records 76 final
Java tests in ten suites (twelve endpoint tests), 560 Python tests in both modes,
ten exact evidence negatives and retained earlier failures. Independent replay
checks 213 source exchanges, ten control exchanges and eight installations.
Real TCP histories at stable
sizes 3/4/5 use the endpoint for reverse original-PROMISE retrieval, source dispatch
and selected installation. The campaign driver still explicitly starts the round
and submits its bounded calls; these histories do not establish automatic election.

Independent replay derives original promises/bases and complete installed files
from the offline bootstrap and journal bytes. It then checks every expected TCP
source exchange against those bytes and exact full identities, as well as the
original PREPARE/PROMISE and SELECTED/INSTALL_ACK controls. Original-first exact
negative mutations and relocated replay are required. It does not substitute a
callback's success for the physical installation check.

Concurrency tests cover task sharing, bounded refusal, an unavailable or altered
original record, higher fencing, pending-network cancellation, expiry without new
traffic, inherited local deadlines, writer-lock delay, foreign scratch and orderly
close. The initial test run's two exception-type assertion failures and the first
red-test compile mismatch remain retained separately from corrected validation.
An intermediate incremental build was also disqualified: restoring an older
source timestamp left the red-test bytecode in place, as confirmed by `javap`.
Final qualification therefore uses a second fresh isolated checkout with no prior
classes; neither a source hash alone nor that stale build counts as final evidence.

## Remaining Phase 3 work

The automatic outgoing campaign/failure-source rotation loop, authenticated
historical provenance and compacted ancestry transport, newer-prefix discovery and
adoption, abandoned scratch restart recovery, learner/joint transitions, carried
voting/publication and complete distributed qualification remain open. The endpoint
does not enable public READY, close an S/N family, change frozen formats/resources,
or qualify heterogeneous maximum-envelope performance.

Rollback removes this private endpoint and its read-only journal/context adapters;
there are no public factory, durable-format, workflow, cloud or release changes.
