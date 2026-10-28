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

## A07 — original pending payload and phased-vote receipt transfers

The existing bounded `SOURCE_OFFER(kind=RECORD)` channel may carry the original
pending ENTRY payload or the canonical witness-hash preimage. RECORD already
carries bounded unframed ancestry metadata; this does not introduce a new wire or
disk kind. All 50 fixtures remain byte-identical. The payload is bounded by the
existing 8 MiB frame allowance; the canonical receipt is at most 2 KiB. BARRIER
uses its verified empty payload locally and never advertises a zero-length offer.

A receipt contains exactly root, permanent voter/storage identity, ACCEPT or
PROOF phase, and original record digest. Computing it is only a content reference.
The native owner serves it only from its actual complete active pending vote,
under the exact installed selection, current parent and unfenced original ballot.
Candidate files and copied capsule objects cannot attest a vote. A matching
original-owner transfer must complete before the receiver creates an observation;
fetching an ACCEPT or PROOF GSR record alone never suffices. Higher ballot,
selection/publication replacement, changed physical files, expiry or owner close
revoke the borrow. PROOF receipts require this owner's actual forced PROOF.

An incoming ACCEPT from the exact proposer pulls its original ACCEPT, ENTRY and
payload plus the proposer’s own ACCEPT receipt, validates the native journal
context, and forces the local vote before
ACK. An incoming PROOF requires this receiver's own ACCEPT and obtains every
named remote ACCEPT witness from that witness's permanent owner. The pre-existing
quorum rules validate both governing sets. No certificate or application is
created by a PROOF_ACK. The exact already-forced phase can be acknowledged after
reopen without recreating observations, forcing a different record, or applying it.

Transfers and the single bounded voting writer remain independent. Original
buffers stay reserved through their durable use; waiting controls use the existing
64-waiter budget. Identical active controls share completion. Source I/O/deadline
retries remain at most three attempts on the exact request and original deadline;
failed identical controls retain their failure within the scope. Corrupt data,
invalid context and changed authority do not authorize a different retry.
The owner must poll/close the finite scope; automatic lifecycle integration remains
open. Removing this unpublished path requires removing both receipt production
and consumption together; generic historical record transfer remains read-only.

The receipt lookup is SHA-256 of canonical `{schema: "gse-v53-vote-observation/1.3",
receipt: <receipt SHA-256>}`. SOURCE_OFFER and subsequent chunks/commit bind the
receipt SHA-256 itself. A plain receipt hash is not an attestation lookup, and a
normal payload selected by its own hash cannot satisfy the distinct receipt
digest. This separates evidence acquisition from ordinary content possession.

A carried original from a previous installed round is not a current vote receipt.
Native observation and duplicate ACK require the active vote's original ballot,
SELECTED and selector to match the current voting scope; the old original remains
retained for recovery until a separately validated successor replaces it.

## A08 — exact native certificate/application ingress

`APPLY` (27) and `APPLY_ACK` (28), each at most 32 KiB, are internal controls in
unpublished 1.3. All earlier 50 frames, commands, read-token bytes, storage kinds
and resource ceilings remain unchanged. The new syntax inventory is 24 storage
and 28 wire kinds. Historical source-bound receipts retain their earlier counts.

The request binds the original CERTIFICATE and installed SELECTED. Its envelope
must name the exact current proposer, permanent recipient, root, view and ballot.
The receiver must already own its actual current ACCEPT and PROOF; copied records
and carried prior-round votes cannot satisfy that requirement. On first certificate
admission it fetches the original certificate, validates both governing majorities,
and obtains each named ACCEPT and PROOF observation from that original voter.
Only then may it force its own certificate and perform native typed application.

The ACK binds certificate, SELECTED, actual checkpoint statement and the receiver's
own forced checkpoint acknowledgement. It does not publish the selector, authorize
future-target dispatch, prove another peer applied, or enable public service. Those
steps retain the existing future-recording and checkpoint-quorum requirements.
The same bounded writer owns vote/application requests while the independent
transfer service permits reverse original-owner pulls. Invalid input refuses
before certificate force; original deadlines, three identical source I/O attempts,
waiter/control accounting, fencing and close behavior remain in force.

After a lost reply, a live exact completed application can acknowledge without
reapplying. After restart, its own forced certificate permits idempotent native
application recovery without fresh historical observations; receiving the same
request is explicit, not an autonomous redispatch claim. A new selection or higher
ballot fences both work and acknowledgement. A prior slot's cached application
cannot answer a new slot's request. No complete Phase 3 gate closes here.

Rollback before publication removes these two internal message kinds and their
typed ingress together; no existing ACK is reinterpreted as an application ACK.

## A09 — nonvoting completion of an original FINAL

An original joint voter that is absent from the FINAL successor still owes an
exact local application result. It must not issue a successor CHECKPOINT_ACK.
The unpublished applied-end inventory now has two explicitly typed completions:
its existing endorsed form and a departing form containing only plan.json,
selector.gsr, certificate.gsr, catalog.gsr, statement.gsr and application.image.
The canonical plan binds every other file by ordered name, length and digest.
No new storage/wire record kind, acknowledgement sentinel or resource allowance
is introduced. Existing endorsed bytes and force ordering remain unchanged.

The departing form requires exact permanent identity registration, an original
FINAL from a joint parent that includes this node only on its old side, and the
immediate stable successor consisting of that parent's new set. Original entry,
certificate, statement, parent cut/catalog/application and successor hashes must
agree. The original owner must still authenticate the certificate and semantically
replay the application; this inventory's shape cannot establish that authority.
A learner, unrelated nonvoter, changed incarnation or already-removed stable node
cannot use the departing form. Eligible successor voters retain mandatory ACKs.

Every metadata/image file is forced, then the end and parent directories are
forced before a nonvoting completion returns. It creates no CHECKPOINT_ACK,
ancestor acknowledgement, observation or service readiness. Reopen validates exact
original prefixes and re-forces the same end; changed plans, unexpected ACKs,
missing/corrupt complete state, revoked ownership and changed inodes reject.
Derived staging retirement still requires exact covering authority and preserves
its original vote. The existing acknowledgement-only API continues to refuse a
departing identity before writes; the native journal has not switched APIs yet.

This is the storage prerequisite for the original departing-proposer/follower
failure. GSFT representation, native APPLY responses, successor checkpoint quorum,
published generation/reopen and runtime removal fencing must be integrated and
qualified separately before the full path is enabled. A component pass does not
close Phase 3. Before release, rollback removes this typed completion path and
its reader together; legacy formats and existing endorsed histories are unchanged.

## A10 — exact nonvoting future proof

The unpublished private GSFT 1.3 frame now discriminates three inventories:
empty (zero records), endorsed (the original ten records), and departing FINAL
(the same first nine records without ack.gsr). The existing framing, record
order, checksum, metadata, revision chaining and three-MiB maximum are unchanged.
The original empty and endorsed encodings remain byte-identical.

Nine records are accepted only for the exact A09 old-only FINAL owner, with its
permanent catalog identity, immediate joint-to-stable parent, original phases,
certificate, entry, statement and image identity. An eligible owner without its
ACK and a departing owner with an ACK both reject. This structural check never
creates a voting observation; native owners must still authenticate their own
original certificate and complete end before recording or dispatching a target.
The applied-end reader requires matching completion kind and an exact nonvoting
inventory when reopening that target. Unexpected ancestor ACKs remain forbidden.

Inherited GSFS references retain the original GSFT owner's identity, bytes and
digest; the capturing owner does not become the voter or original completer.
This batch qualifies the representation, inheritance and real applied-end
reopening under conditional historical authority. Native application/wire,
publication and removal fencing still require their own complete integration.
The unchanged stable native future/source/selected-proof regressions are listed
in the source-bound receipt. No successor checkpoint quorum or Phase 3 closure
is inferred from these component results.

Before release, rollback removes the nine-record reader/writer variant and its
independent reader together; it must not synthesize a tenth record for a retained
nonvoting proof. Previously produced nonvoting test evidence stays historical.
