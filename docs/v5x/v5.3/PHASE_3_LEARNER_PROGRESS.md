# Phase 3 — prepared learner progress

The original learner discovery/enrollment route ends when the source applies
CANCEL or INTENT. Reusing that route would either prevent recovery or silently
weaken enrollment checks. This batch adds a separate bounded read-only route,
specified by [A29](PHASE_3_CONTRACT_AMENDMENTS.md).

`MembershipLearnerProgress` holds a live prepared/current typed owner. Its ROOT
comes from the original retained source, and a STATUS reply supplies only a
candidate cut. The client downloads the complete capsule, images, generation and
ancestry using the existing transfer machinery. Both the complete original request
and the current owner's exact proven ancestor must match before returning.

`MembershipLearnerProgressAccess` checks the source's retained operation, full
joining identity, original stable prepared view and current source voter. The
derived reference also binds the exact current cut and requested scope. Missing or
retired operation detail fails closed; a watermark, timeout or rejection does not
prove cancellation. The original ROOT/enrollment aliases keep their existing rules.

The new route shares the ordinary prefix-export registry, transfer limits, exact
frame retries, original deadline and resource pool. One receiving learner slot
remains charged while progress is live. Closing or changing the original owners
revokes access. There is no listener, ballot allocation, vote, installation,
receipt replacement, local INTENT force or authority-file deletion. In particular,
`completeLearnerSource` refuses these downloads, and a generation pull cannot mix
progress with an enrollment prefix.

## Focused validation

`V53LearnerProgressTest` covers all five ADD/REPLACE profiles at PREPARING, READY,
SEALED, JOINT, FINAL and post-FINAL BARRIER, plus cancellation from PREPARING and
READY. It compares every received generation member to the original owner,
checks unchanged authority files, and checks bounded same-frame retry, permanent
refusal, expiry, caller close, missing/retired/foreign operations and mixed-mode
rejection. These histories contain explicitly conditional voter observations.

`V53LearnerProgressNetworkTest` combines actual TCP with an actual typed learner
backup/receipt. CANCEL, JOINT and COMPLETED sources retain independently checked
supplemental ancestry back to that prepared owner. The local receipt and authority
remain unchanged. A higher valid prefix without that ancestor is rejected; closed
typed ownership and voting/enrollment requests through a progress client are also
rejected. Historical sources/endorsements are conditional fixtures, so these tests
do not establish native distributed cancellation or joining-voter eligibility.

Final focused validation passed **57 Java tests** (nine new, 48 existing),
with no failures or skips. The documentation contract and its unit test also pass.

Exact executions, source hashes and preserved failed fixture attempts are recorded
in [the component receipt](phase3-evidence/learner-progress.json). The new fixture
uses ordinary compacted ranges and separate ancestry; it must not split a stable
era into adjacent RANGE entries or attach ancestry to an unselected bare generation.
Initialization failure closes its original owner before subsequent tests run.

## Remaining protocol work

The next implementation boundary is a durable, original-proof-bound local
cancellation/INTENT decision, with crash recovery, bounded placement, receipt
matching and force-before-eligibility rules. A downloaded proof alone authorizes
none of those actions. Actual native source transitions, full-size resources,
halt/SIGKILL, independent original-first replay and autonomous learner/round
integration remain in the [acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).
Phase 3 remains **OPEN**; no hosted workflow or paid experiment ran in this batch.
