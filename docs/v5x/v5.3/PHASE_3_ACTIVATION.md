# Phase 3A — private durable activation

Status: **LOCALLY QUALIFIED**, 2026-10-25. Phase 3 remains open under the
[entry/checklist](PHASE_3_ENTRY_PLAN.md). This batch does not enable public service.

`MembershipActivation` drives one campaign over the real exclusive
`MembershipGrantJournal` writer. Allocation and the proposer's original grant are
forced before any PREPARE can leave the controller. Verified PROMISE sources enter
the first complete eligible quorum, including the proposer and both old/new
majorities. The original SELECTED bytes are forced once. Later sources cannot
change that set or its highest accepted next entry.

The selected receivers validate the existing PREPARE and SELECTED envelopes,
original proposer PROMISE, source references and expected selection before writing.
An INSTALL_ACK is constructed only after that receiver has actually forced the
selected generation and selector. The proposer also installs locally. Every
selected identity must acknowledge the exact selection and cut before the controller
returns `votingSelection`; a smaller majority cannot substitute for a missing
selected voter. The storage writer independently rechecks its live grant, current
view and observed ballot at that boundary.

The internal INSTALLED state authorizes subsequent protocol work only. It does
not certify an entry, publish an application, establish a service read barrier or
declare public READY. A carried accepted entry retains its original bytes and must
be resolved before the later current-ballot stable BARRIER.

## Lifetime and refusal

- Every exchange binds root, authority, full permanent identities, ballot, trace,
  sequence and exact payload. Three total attempts reuse identical bytes and the
  original campaign deadline; the INSTALL stage does not reset it.
- At most five PREPARE and five SELECTED headers are retained for correlation.
  Delayed higher-ballot REJECTs still fence the campaign after selection. An old
  non-higher rejection cannot undo an already completed earlier exchange.
- Control frames reserve the existing shared queue budget; success, abandonment,
  exhaustion and close release their leases. The controller borrows verified
  source/image staging from its owner and does not create another physical source
  set. Network staging lifetime integration remains Phase 3B.
- Timeout, source-selection/storage failure, active rejection and retry exhaustion
  require a fresh campaign. Nothing erases forced promises, selections or sources.
  A deadline crossed during selection leaves the forced decision on disk but
  returns no installation authorization.
- Foreign/malformed/stale-correlated messages cannot contribute a vote or ACK.
  Storage checks remain authoritative even if a higher observation arrives between
  controller callbacks. No application operation is retried by this component.

## Evidence and limits

`V53ActivationTest` drives actual public offline bootstrap and independent local
owners at stable sizes 3/4/5. It retains original bootstrap bytes, selected storage,
wire frames and force observations. It also tests conditional old/joint/new sources
for all seven profiles, one-sided joint majority, missing selected installation,
late/duplicate/corrupt replies, higher fencing, queue capacity, deadlines, close,
injected installation failure and original carried entries.

The conditional joint sources use the existing fixture endorsements; they do not
claim real ADD/REPLACE learner delivery. Actual stable-size paths use real owner
grants/installations. Neither path authenticates a real socket or simulates power
loss. S02/S07/S09/S10 and the complete S/N inventory remain pending their owning
distributed qualification.

The independent Python reader reconstructs every installed file from the original
bootstrap and exact fresh grants, requires untouched unselected voters, correlates
both message phases and checks force ordering. It validates original evidence
before ten specifically classified mutations. Source/build/test hashes, local
JUnit reports, portable replay and retained failed attempts belong in the batch
receipt; they are not protected CI or cloud evidence.

## Retained qualification

The [batch receipt](phase3-evidence/activation.json) binds the actual inputs,
two runtime JARs and retained logs under `target/v53-phase3-activation/`.
An isolated fresh source copy avoids the externally rewritten shared build output
seen during Phase 2. All 1,025 Java/resource/POM build inputs were compared with
the working source after the test run.

- **104 Java tests / 14 suites** passed, including 11 new activation tests,
  related allocation/grant/selection/installation/adoption tests and V5.0–V5.3
  public API inventories. This is a focused reactor package, not the full CI suite.
- **533 V5.3 Python tests** passed in normal and optimized mode.
- Independent replay passed in normal, optimized and relocated directories, each
  including the same **10 exact negative results** after the original passed.
  The original three-profile evidence contains 463 files and 580,763 bytes.
- Contract and local-link checks passed without changing frozen formats, bounds,
  public declarations, workflows, POMs or predecessor runtime logic.

The first Java run failed while writing a diagnostic JSON object with node IDs as
keys, which the repository's JSON key grammar rejects. The recorder now uses an
array of explicit node/event rows. The original failure log/JUnit and incomplete
raw output are retained; it is not reported as a successful activation run.

Next is Phase 3B: real transport/source ownership and discovery, timeout/source
rotation and process/network qualification. Learner lifecycle, joint automatic
completion and the later public READY/read path remain open.
