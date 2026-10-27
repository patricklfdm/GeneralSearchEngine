# Phase 3B — complete original future proofs in selection plans

Status: **LOCAL COMPONENT QUALIFICATION**. This is the representation and
verification boundary required by selected future ownership; native selection
still refuses unresolved future references before SELECTED. It does not establish
durable installation, continued voting, quorum dispatch or complete Phase 3.

## Complete selected originals

The GSRS recovery intent already records every selected original BASIS, indexed
source envelope and GSRP snapshot. Its reader now requires the exact separately
indexed GSFT bytes for each referenced pending target. The wrapper and proof must
both occur in that same original envelope, match its root/permanent owner, and
bind the original accepted tail and parent. Missing, substituted, foreign or
oversized proof refuses; checksums or copied hashes are not new force observations.

Generation materialization includes every selected proof as its own indexed object.
The longest source can have no future proof at all; selecting its prefix must not
lose obligations held only by shorter or equal-prefix sources. Copies returned
from the intent cannot mutate its retained bytes. No new remote ACK is constructed.

An unpublished target must match the selected carried entry and original parent.
Different claimed results for that same target refuse. Already-covered targets,
original parents and conservative peer lower endpoints enter the required ancestry
set and must be authenticated by the installed prefix. Unpublished results are
never presented as published ancestry or inserted into the ordinary peer ledger.
The original ledger's root, view and permanent identity validation still runs.

## Bounds and current runtime boundary

GSRS framing and its six-source maximum are unchanged. Each GSFT remains at most
3 MiB and is stored separately, preserving the 8 MiB object limit. The complete
packet and generation must still pass their existing 32 MiB limits. This does not
claim that six worst-case proofs plus every other maximum necessarily fit: an
oversized complete materialization refuses rather than raising the limits.

The existing pre-SELECTED guard remains active for actual native decisions.
Creating or replaying a complete proposed generation is not an installation ACK.
The follow-up must atomically own these proofs across installation/reopen, old
staging retirement, carried reacceptance/application/publication, source retirement
and another campaign. It must project pending obligations without recursively
nesting earlier election histories, promote them before publication compaction,
and reserve complete source/completion headroom before real dispatch.

## Evidence boundary

The native proposal fixture starts with public stable-three EMPTY bootstrap,
actual first BARRIER ACCEPT/PROOF/certification and all three forced application
ends. Nodes 1 and 2 retain different peer intentions. Node 3 allocates the next
ballot and wins the equal-prefix longest-source tie despite having no future proof.
Proposals for nodes 1 and 3 must retain both exact originals. Their actual native
journals remain unchanged after the unresolved-future refusal.

The independent reader `scripts.v53.selected_future_evidence` derives original
bootstrap, certificate, applied ends, local future files, fresh PROMISE/BASIS,
GSRS, complete generation files and proposed selectors before comparison. Only
fresh source UUIDs are observed. It validates originals before mutating evidence
and requires exact rejection reasons. This is a plan replay, not crash recovery
qualification. A separate native Java case covers a longest prefix which already
published the target, preserving its original ancestry without inventing a tail.

The [source-bound receipt](phase3-evidence/selected-future-proof.json) retains the
actual snapshots and original failure records. Twelve Java tests pass in the final
regression snapshot. The three proposal tests are repeated in a later snapshot
with identical production Java and an added conflicting-result negative; these
are overlapping checks. The independent reader agrees normally, under `-O` and
after relocation, and rejects twelve exact evidence mutations. Thirteen focused
Python regressions pass in both modes. No full reactor test or new crash matrix
is claimed for this proposal boundary.

The first build failed compilation on a shadowed lambda parameter. A later native
test run passed, but independent replay found its newly introduced fixture had
omitted durable ballot allocation. The corrected fixture calls `reserveCounter`
before PREPARE; original failed evidence remains separate.

The complete [Phase 3 checklist](PHASE_3_ENTRY_PLAN.md) remains OPEN.
