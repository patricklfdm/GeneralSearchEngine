# Phase 3 hosted review: 276dcdf5

This review covers all five completed attempt-1 runs at
`276dcdf5641560098da1d2228672a49a9e57a34a`. The audit retained all 376 jobs,
their steps, artifact listings, all 17 failed job logs and 11 selected artifact
ZIPs verified against their API SHA-256 digests. A dependent replay/aggregate
failure is not another independent original failure.

| Cohort / run | Jobs successful | Result and primary failures |
| --- | ---: | --- |
| [Joining processes 43491014287](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43491014287) | 235 / 242 | Groups 027/109 exhausted Maven Central HTTP 429 setup retries; group 006 seed download ECONNRESET; group 096 original replay rejected a first-object failed COMMIT |
| [Joint-floor 43491014104](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43491014104) | 66 / 66 | All 32 originals, 32 replays, preparation and aggregate succeeded |
| [Carried transition 43491014583](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43491014583) | 34 / 34 | All 16 originals, 16 replays, preparation and aggregate succeeded |
| [Carried DATA 43491014195](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43491014195) | 21 / 26 | APPLIED and CERTIFICATE exhausted PUBLISH requests; their replays and aggregate failed |
| [Automatic 43491013915](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43491013915) | 3 / 8 | Competition poisoned its writer after capture fencing; higher-ballot restart exhausted DATA PUBLISH requests |

Joining execution groups contain three whole original histories. Carried DATA's
eight crash/process originals passed, including the previously failing cleanup
SIGKILL case. Success at this source is not acceptance of the corrected source.

## Corrections

Joining preparation now retains its checksum-verified Maven installation in a
tar archive, preserving executable modes. Each original downloads that exact
run/attempt/source artifact. Existing toolchain admission hashes the installed
Maven binaries against the immutable seed before executing a history. This
removes the 120 independent distribution downloads, without introducing a mutable
cross-run cache or a concurrency cap. GitHub artifact downloads can still fail;
the observed ECONNRESET is not claimed to be repaired by this change.

The Joining reader previously allowed a failed TRANSFER_COMMIT only after a
previously committed object. The retained group-096 original instead completely
received the first manifest, then lost COMMIT when its original owner switched
generation. The reader now requires those exact original bytes, the offer and
chunk sequence, permanent identities, original generation lifetime and bounded
identical failed attempts. It records received bytes but **zero committed objects**
and no generation copy. Unit negatives reject changed bytes, kinds and lifetimes.

Native grant capture now completes an already-started recoverable original under
the existing writer monitor when a higher ballot is merely observed. An incoming
higher PROMISE cannot write while that monitor is held. The old response remains
fenced after the complete durable capture; the next campaign can use the same
healthy writer. I/O, integrity and callback failures still poison the owner.
This distinguishes normal competition from storage failure without inventing a
grant, changing journal formats or returning a stale ACK. A deterministic test
injects the higher observation at 25 capture/return boundaries and checks the
old response refusal, exact durable basis, next campaign and drained resources.

The corrected local competition produced another explicit original trajectory:
one local grant, one unanswered PREPARE and bounded reverse first-object requests,
then an incoming higher PREPARE. The old requests never gained a response, remote
grant or selection. Its new reader branch binds the actual higher request to its
proposer's original promise, receiving owner's durable grant and recorded LOSS.
Complete physical/publication/network/export/lifecycle replay precedes seven
copied-claim negatives. The 20 applicable export and 12 lifecycle negatives also
run; unavailable negatives remain explicitly inapplicable. Retiring an unexported
old source does not manufacture an exported retired-journal mutation target.

PUBLISH handling removes consecutive duplicate fresh-owner inspections without
removing the checks before authentication, publication or ACK return. Both sides
of the pre-return callback still validate the owner, ballot, selector and exact
request. The request timeout, three attempts, operation budget and frozen
workloads are unchanged. The retained deadline traces show reverse transfer
progress while requests expire, but do not prove a GitHub scheduling cause.
This cost reduction is not a claim that every hosted deadline failure is solved.

The coverage catalogue hash changes with the new explicit negative branch. The
frozen acceptance plan, Required CI workflows and paid-cloud behavior do not
change.

## Local verification and remaining work

The unchanged failed group-096 history passes its complete original authority,
physical, export, network and ledger replay after the reader correction. This
does not replace a fresh same-source hosted original and its complete negatives.

The new capture test fails against the original downloaded `276dcdf5` journal
classes and passes against the correction. The capture/journal suite passes all
23 tests. Native competition, higher-ballot restart, four publication-lifetime
tests and all four carried DATA profiles pass: ten tests without retries. All
four DATA originals independently pass physical replay. Competition additionally
passes all 39 applicable composed negatives while preserving its original files.

All 4,717 V5.3 Python tests pass. The documentation contract, source-selector
audit, changed local links, workflow YAML, seven shell blocks and whitespace
checks pass. A local Maven archive round trip preserves hashes/executable modes;
the wrapper reuses the restored installation without a distribution download.

Nine additional publication/reopen tests pass, including higher observation at
the ACK pre-return boundary; the core and replication packages rebuild. The first
sandboxed TCP attempt was blocked by `SocketException: Operation not permitted`;
it is retained separately from the successful approved loopback execution.
Fresh-process capture recovery passes all 66 clean/halt/SIGKILL/repeated-recovery
cases, 14 exact negatives and relocated replay in 113.253 seconds. This verifies
the private capture transaction, not power loss or public runtime qualification.

Final source checks and the corrected-source hosted reruns are recorded in the
local review directory.
The two previously green families must run again because native Java changed.
All earlier failed originals remain retained and failed. The complete final-source
cohort, maximum-host admission and actual coverage obligations remain open;
this review does not close Phase 3.

Raw API records, original ZIPs, hash inventory, local test/replay results and
diagnostic recordings are retained under `target/v53-action-review-276dcdf5/`.
Temporary signed artifact-download references there must not be published.
