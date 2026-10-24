# Protected context capture and rebinding

Phase 2 remains **OPEN**. The private local owner can now capture a fresh grant
while one original pending context is retained, after its old generation and
predecessor source have retired. The current installed generation and governing
floor remain unchanged. Later selected installation and continuous bounded source
reclamation remain separate work.

## Exact local transaction

The specialized PREPARE path checks the complete original context, exact backing
grant/source, installed selection, current floor, eligible proposer and idle
storage transactions. It derives a packet from current plus original packet
objects/images, retaining the exact original ENTRY, payload, ACCEPT, PROOF and
certificate. It does not recursively accumulate previous backing inventories.

Before PROMISE it reserves the new packet/images and conservatively checks journal
space for PROMISE, BASIS and one maximum context candidate. Within the same owner:

1. Force the new PROMISE and exact capture intent.
2. Finish and force the exact source packet/images, then force BASIS.
3. Reconstruct the same original against that separately sealed source and replace
   the context with the new backing PROMISE/BASIS/packet identity.
4. Force the context rename's parent, then delete and force the capture-intent
   removal. Recheck fencing before returning the explicit grant.

The original vote, selector, certificate and generation metadata stay byte-identical.
A volatile higher observation may fence the return after durable progress; it does
not roll back the original or lower the durable promise. An exact duplicate grant
requires a complete transferred backing. A PROMISE interrupted before its capture
intent still requires a fresh ballot and never fabricates an original BASIS.

## Recovery and refusal

The [deferred inventory resolver](PHASE_2_CAPTURE_INVENTORY.md) admits complete
backing bytes first. `reconstructStored` and `rebindStored` validate the same original
from verified bytes without constructing a `Source`/`Owned` force observation.
They derive the pending source and exact next context before recovery writes.
A well-formed but stale context candidate therefore refuses without filling source
prefixes or appending BASIS. A red regression reproduced the earlier ordering
mistake before that check was moved forward.

Reopen resumes source/BASIS/context completion before ordinary vote recovery. An
already renamed context deterministically reconstructs the same protected packet;
it does not depend on an unavailable previous active context file. Missing/corrupt
originals or nonmatching candidate prefixes refuse. Once BASIS writing has started,
lost source bytes cannot be repaired from a partial prefix. Reopen issues no grant
ACK; a separate exact PREPARE call is required.

The general context transaction gate remains in place for unrelated operations.
In particular, the newly captured grant is not installed, cannot authorize an
acceptance under the earlier selection, and cannot bypass floor/source references.
Resource and on-disk format limits remain unchanged.

## Local evidence

The retained clean history captures ballots 22 and 23 over the same ballot-20
original and ballot-21 installed generation. Physical image reservations rise from
five to six to seven; the next capture refuses before PROMISE without leaking
leases or invalidating the owner. A separate small-journal case checks completion
headroom before admission.

Thirty-four source, BASIS, context and intent boundaries are interrupted by injected
`IOException`, then recovery is interrupted again at a source-parent force. Final
reopen preserves the exact old vote and backing and produces no grant; explicit
duplicate PREPARE then returns the original new BASIS. Independent lock probes
check all 34 live owners. This is repeated exception interruption, **not** a new
halt/SIGKILL or power-loss qualification.

The independent replay first validates retained original context/retirement/source
evidence. It derives the exact protected packet, BASIS, replacement context and
every first/second interruption inventory. It checks source/BASIS/context force
ordering before the explicit return, unchanged vote/floor/generation bytes, portable
relocation and exact-reason mutations. Optimized Python replay must give the same
result. The [evidence index](phase2-evidence/context-capture.json) records source,
build, original failures, raw hashes and the focused regression results.

Historical bootstrap/remote observations remain conditional fixtures. These local
captures do not qualify a distributed campaign, later generation installation,
slot reuse or repeated steady-state reclamation. Intermediate backing retirement,
floor replacement and maximal old/joint/new lifetime are still required by the
[Phase 2 closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
