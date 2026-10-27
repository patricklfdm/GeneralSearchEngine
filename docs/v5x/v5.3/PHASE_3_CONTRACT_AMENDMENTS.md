# V5.3 Phase 3 contract amendments

## A04 — explicit current-target retention intent and acknowledgement

V5.3 remains unpublished. The original Phase 0/1 catalog had 24 storage and 21
wire kinds (45 syntax fixtures). Phase 3 adds two **internal** wire kinds to the
same unpublished minor version 3: `RETENTION_INTENT` (22) and `RETENTION_ACK` (23).
The original 45 fixture frames, existing schemas and all resource ceilings remain
unchanged. Earlier source-bound closure receipts retain their original catalog
and counts; this amendment does not reissue those historical results.

The missing contract is durability of a peer's possible endpoints before its
installation is dispatched. STATUS, HEARTBEAT, source transfer completion and
transport success cannot acknowledge this action. The dedicated request uses the
existing exact root, view, permanent sender/recipient, ballot, trace and sequence
envelope. Its payload binds the original installed SELECTED digest, permanent
target identity and exact lower/upper cut/catalog/application anchors. Both new
frames retain a 32 KiB maximum; neither introduces a storage kind or increases
the existing JOURNAL, CONTROL, staging or two-endpoint-per-peer bounds.

The logical intent hash covers the canonical payload, allowing different current
voters to acknowledge the same intent with their own correlated envelopes. It is
not a signature or an installation certificate. Each voter independently checks
the installed selection and promise, current ballot fence and authenticated
current target, then conservatively merges under the native storage lock. It
cannot remove an older local possibility based on a received claim. A complete
real-copy observation may already have narrowed that voter's knowledge; a late
duplicate must not regress it. A third unresolved endpoint refuses.

The ACK binds that logical hash and the receiver's exact durable ledger revision
and digest. The request does not bind a global ledger revision: different voters
legitimately hold different conservative knowledge, and unrelated peer updates
must not change the identity of an otherwise identical intent. Lost-response
retry repeats the same frame up to the existing three-attempt maximum within
one original deadline. A fresh PREPARE observed before the reply fences it,
including when the ledger force has already completed.

The sender records locally and obtains distinct governing acknowledgements
(both majorities for a joint view) before returning an in-memory permit. The
permit rechecks the exact native owner, ballot, target and original deadline
before dispatch. A partial quorum, malformed reply, expired deadline or closed
owner cannot grant permission. The ledger is the durable state; the permit and
ACK set do not survive a new owner or election. New selection inherits original
forced snapshots through the previously qualified GSRP/GSRS paths.

### Deliberate scope boundary

This component handles a same-view target already authenticated as the current
generation at each acknowledging voter. It does **not** interpret an applied-end
candidate as an installed generation. Future-publication retention, autonomous
owner scheduling, cross-view pending contexts, learner eligibility and the full
offline-survivor continuation still require their real protocol paths. Current
network qualification exercises stable 3/4/5-voter groups; the joint-majority
predicate alone does not establish joint-transition runtime qualification.

Rollback before publication removes the two new messages and their internal
driver/endpoint methods, and restores the earlier catalog/fixture inventory.
It must not reinterpret a retention ACK as an existing protocol message. Existing
V5.0–V5.2 readers, public factories, workflow and release pins are unaffected.

## A05 — native future-target retention acknowledgements

The two new control kinds are FUTURE_RETENTION_INTENT (24) and
FUTURE_RETENTION_ACK (25), each at most 32 KiB including the unchanged 1.3 header.
All previous 47 record/wire fixtures, commands, resource limits and read-token
bytes remain exact. The syntax inventory is now 24 records plus 25 wire kinds.
This amendment does not claim completed quorum dispatch or public runtime.

A logical intent binds the installed SELECTED digest, original CERTIFICATE,
permanent intended recipient, original parent, prior possible recipient endpoint
and exact next applied target. Envelope root/view/ballot/proposer are checked
against the native owner. Every acknowledging voter uses its own forced native
applied result and original selector/application ACK; received hashes never
create application authority or substitute another voter's GSFT. An otherwise
correlated request before local native application returns NOT_READY without
writing any intent.

Before publication, the receiver records the target in its own existing GSFT
transaction. The prior endpoint must equal its single authenticated current
possibility. Different unresolved lower endpoints refuse before any write and
return CAPACITY_EXCEEDED and require later verified complete-copy reconciliation; no oldest/newest guess
replaces the two-endpoint limit. Incoming recording may name the receiver itself
as the intended target. The outgoing self-dispatch prohibition remains separate.

After exact certified publication, an identical request uses the existing
ordinary covered-target ledger transaction. The ACK discriminates FUTURE from
CURRENT and binds the logical intent plus the exact durable store digest and
revision. Existing real-copy narrowing is preserved. A different certificate,
selection, native target or unverified parent refuses. The original ballot is
checked after force and again immediately before acknowledgement; interrupted
ACK delivery never clears the durable intent.

The [native recording qualification](PHASE_3_FUTURE_QUORUM.md) now covers bounded
wire retries and governing-quorum accounting, original-first stable network
histories, receiver restart recovery and explicit complete-copy reconciliation.
The returned recording has no dispatch method. Required next work: actual dispatch
bound to the specific intended operation, native voter/application endpoint
integration, automatic reconciliation and the complete joint/runtime qualification.
Individual ACKs alone grant no send permission. This amendment is not a Phase 3
closure receipt. Rollback before publication removes the two new kinds and this
internal recording path, restoring the previous catalog without reinterpreting ACKs.

## A06 — exact remote publication acknowledgement

`PUBLISH_ACK` (26, at most 32 KiB) explicitly acknowledges the existing PUBLISH
certificate after the receiver has forced its complete selected publication and
finished covered application/retention cleanup. The payload binds original
certificate, SELECTED, full published cut/catalog/application and local generation
digest. It is neither an application ACK nor a quorum certificate, and cannot
narrow retained peer possibilities without a separate verified complete copy.
All earlier 49 fixtures remain exact; the inventory is 24 records and 26 wire kinds.

A future-recording quorum can dispatch only its own exact PUBLISH to its intended
permanent recipient. The native owner, original ballot, pending application and
local retained target are checked before each attempt and immediately before the
transport writes. Up to three identical I/O/deadline attempts share the original
budget. Closing, fencing, malformed acknowledgements and rejection do not grant
permission to retry a different operation. A higher rejection is observed locally.

The receiver scope is minted from actual completed native application. Original
checkpoint ACKs are obtained from their permanent owners, with both old/new
majorities where applicable; expected hashes never count as observations. Reverse
transfers remain available while publication waits. Duplicates share the one
bounded publication operation, then recheck its actual selector and ballot before
replying. A higher ballot after force prevents acknowledgement without undoing
publication. Local recording/dispatch scope does not survive a new owner.

This amendment opens implementation qualification; it is not whole Phase 3 or
joint-transition acceptance. Autonomous ownership, native incoming votes/application,
learner transitions and restart dispatch reconciliation remain required. Rollback
before release removes the new internal message and typed path together, restoring
the prior catalog without changing legacy wire/token formats or limits.
