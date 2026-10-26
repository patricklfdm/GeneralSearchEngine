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
