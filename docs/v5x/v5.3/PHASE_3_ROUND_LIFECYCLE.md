# Native serialized round lifecycle

Status: locally qualified for the explicit bounded scope below. This is a Phase 3B/3D integration batch,
not full Phase 3 closure or public membership enablement.

`MembershipRoundDriver` owns one bounded native invocation: actual activation,
completion of an exact selected prior-ballot entry when present, a fresh
current-ballot BARRIER, and serialized stable DATA/CONTROL/BARRIER submissions.
The caller supplies an operation payload; the driver derives the actual parent,
index, authority and ballot from its live journal. It does not replay an
indeterminate client mutation or restore readiness from durable files.

## Authority and lifetime

- The original outer start is passed into activation and every slot. Source
  rotation, carried recovery and later submissions cannot renew that deadline.
  Existing five-second default request and 180-second test round limits remain.
- READY is internal and diagnostic. Admission and `readiness()` recheck the
  original selected decision, current ballot, exact expected published cut,
  unchanged stable authority and the actual live endpoint scope. A retained
  selection cannot revive an abandoned or expired scope. Higher ballots fence
  further service even when a preceding publication was durable.
- Startup completes the exact selected carried entry before creating the fresh
  barrier. The actual native publication ACK precedes readiness. Failure at that
  boundary does not manufacture a successful client result or allow reuse.
- One round owner and one executing call are admitted. Control records and each
  materialized payload are reserved before use. Child slot tasks drain before
  their activation scope and parent reservation can be released. Close prevents
  further admission, interrupts the caller and cancels child network work.
- An authority change cannot continue through this stable service path. Learner
  ADD/REPLACE, joint FINAL and new-stable activation require the forthcoming
  transition/election owner. The durable transition is not undone on refusal.

## Qualification boundary

The new tests drive actual native TCP activation rather than preinstalling a
selection for the round owner. Stable BARRIER/DATA and retained-APPLIED/fresh
BARRIER histories are retained separately. The independent reader first invokes
the unchanged strict physical/network validator on a projection omitting only
the new round result file. It then binds lifecycle events to exact original
selection/entry bytes and local publication ACKs, and checks serialized order and
the fresh current-ballot barrier. Originals must pass before evidence mutations.

Other directed cases cover duplicate/busy ownership, expiry without renewal,
close during installation/slot work, higher-ballot fencing at readiness,
abandoned endpoint scope, and failure after durable publication but before
readiness. These live tests do not claim process-crash or restart qualification.
The [source-bound receipt](phase3-evidence/round-lifecycle.json) records 30 final
Java tests, 683 Python tests, two original native histories and 50 exact negative
mutations. Both histories and all negatives replay identically using archived
readers outside the checkout under optimized Python. The earlier nine-test
lifecycle trial and initial reactor-command mistake remain retained separately.

## Remaining Phase 3 work

The enclosing automatic election/discovery/adoption lifetime, repeated campaigns,
maximum combined headroom, real learner lifecycle, all seven joint profiles and
complete adversarial process/network replay remain OPEN. This round is bounded
and caller-started; it is neither an election timer nor a public service runtime.
Phase 4 API enablement, protected CI, V5.2 predecessor integration and paid cloud
acceptance remain separate gates. No wire/storage format or frozen limit changes.
