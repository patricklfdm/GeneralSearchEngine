# V5.3 Phase 3 contract amendments

## A34 — bounded read-only queries of a forced learner head

Append `LEARNER_HEAD_QUERY` (31) and `LEARNER_HEAD_ACK` (32), both at most
32 KiB, to the unpublished 1.3 catalog. The existing 54 frames, nine command
payloads, read token and all resource ceilings are unchanged. No storage format
changes in this amendment.

The learner listener can be constructed only from a live sealed prepared/current
head. It checks the actual forced selection/handoff and cancellation state before
answering and again before writing. Only exact original voter identities from
that head's verified source may query. The envelope binds root, original view,
permanent identities, learner correlation ballot, fresh trace and sequence 1.
The payload binds the complete original membership request; the reply binds its
hash and the exact cut/catalog/application endpoint. The correlation ballot is
not observed or allocated as a vote. Transport identity checks retain the
existing trusted-private-network assumption; there is no new TLS claim.

A source probe derives its request from its actual native retained ledger and
checks the same storage resource owner. It never records another offer merely
to ask about progress. One query reserves 128 KiB CONTROL for bounded request,
reply and binding metadata; transient IO/deadline failures may retry the exact
frame at most `min(3, maxRetryAttempts)` times under the original deadline.
Malformed/cross-bound/permanent replies are refused without retry. The source
independently authenticates the endpoint through its current original ancestry.
Close cancels a pending exchange and retains accounting until active submission
exits. Results cannot be used after close, deadline, original-owner failure or
terminal publication invalidates the reservation.

This is a read-only distributed component. An ACK does not narrow a durable
ledger, modify a vote, create matching INTENT, or authorize source export. Durable
discharge authority through frozen/selected sources remains a separate required
boundary; singleton ledgers still cannot erase stale-source obligations. See
[the head-query protocol](PHASE_3_LEARNER_HEAD_PROTOCOL.md). Full Phase 3 is OPEN.

## A33 — process-local forced learner-head observation

Only a live sealed prepared/current typed head can construct an observation of
its exact request, permanent learner and source endpoint. Its original selection
or handoff must already be forced, and all original checks remain live. Capture
reserves 32 KiB of the actual learner CONTROL pool. Close, supersession, changed
original bytes or cancellation prevents further use; this is not a transferable
remote acknowledgement or a new voter capability.

The native source owner may narrow its local plan after checking that exact
observation and its original ancestry. Keep the observed endpoint and all later
uncertain offers; do not regress on late old observations. The head may have
been served by another source owner, so a local offer-list entry is not the
authority. Identical plans are idempotent. Persist using the existing journal
candidate/replace/parent-force transaction and recheck before return; pending
slot and uninstalled-selection boundaries are unchanged.

No wire or disk format changes. Conservative selected-source merging remains
unchanged: distributed confirmation must still preserve discharge authority
across stale frozen sources and bound the two-endpoint union. It cannot infer
confirmation from a singleton ledger. Full remote/all-profile/process and
independent replay gates remain open. See
[the local boundary and qualification](PHASE_3_LEARNER_HEAD_OBSERVATION.md).

## A32 — consume live learner recording before source export

An enabled learner-retention owner now serves reserved prefix, ancestry and
complete-generation requests only after its actual installed proposer obtains
A31's forced recording from a current majority. The first source request starts
one bounded recording inside the prefix service's original deadline. All traces
for that permanent learner share the result, including a failed result; new
traces cannot restart an exhausted quorum. The registry retains one accounted
64 KiB control entry and uses the existing shared request/queue limits.

The original root/request/reader/alias/correlation is checked before recording.
The capability binds the exact journal owner, storage resource pool, learner,
selected endpoint and ballot. Export creation, reads and references check it
under that same journal lock. The service also checks before returning a reply,
including the final exact retry after the export/session has closed. A changed
ballot, endpoint, expired original budget or close refuses further responses.
A frame already returned before fencing is not recalled; its endpoint was already
quorum-retained before exposure.

Close cancels the shared quorum before draining entry monitors. Concurrent
requests waiting for the same result are woken, late exchanges are cancelled,
and metadata stays accounted until the active recording task exits. Network
waits never hold the journal or registry monitor. Nonvoting readers cannot bypass
the recording by using ordinary prefix aliases; original ROOT discovery remains
read-only metadata. Legacy fixture owners retain their prior explicit mode.

This connects the existing activation endpoint automatically for enabled owners;
it does not enable a public automatic learner runtime. Serving is restricted to
the original stable installed proposer. There is no follower forwarding, forced
head acknowledgement/narrowing, matching local INTENT or new voting eligibility.
Wire/storage formats, frozen resource limits and workload profiles do not change.
Full native cancellation, all-profile/process and independent physical replay
remain separate gates. See [focused export validation](PHASE_3_LEARNER_RETENTION_SERVING.md).
Rollback removes the serving connection and restores refusal for retained-mode
exports; durable A31 obligations must remain intact.

## A31 — original-round nonvoting learner retention acknowledgements

Add internal `LEARNER_RETENTION_INTENT` (29) and `LEARNER_RETENTION_ACK` (30),
each at most 32 KiB with the unchanged unpublished 1.3 framing. The catalog now
contains 24 storage and 30 wire kinds. All 52 earlier frames, commands, read-token
bytes and resource ceilings remain exact. No legacy retention message gains a
second meaning.

The request binds the installed SELECTED, complete original ADD/REPLACE request,
permanent joining identity and exact endpoint (cut/catalog/application). The
normal envelope binds root, view, original proposer ballot, sender/recipient,
trace and sequence. Each acknowledging voter independently requires its own
installed round and authenticated current endpoint, the same original stable
configuration, a nonvoting joining identity, and no pending application slot or
maintenance. Received endpoint hashes cannot substitute for local authority.

Under the native writer lock, the receiver adds the endpoint to its bounded
learner ledger without dropping an older possibility. A third endpoint or a
different operation refuses. An identical request is idempotent. Only after the
candidate force, active replacement and parent force may it return an ACK binding
the logical request digest and its own durable revision/ledger digest. Ballot
checks after force and immediately before return prevent a fenced ACK; the
already forced obligation survives a lost response or later fencing.

The proposer records locally and counts distinct current voters, then uses up to
three identical I/O/deadline attempts per peer within one original deadline.
Malformed, unrelated, exhausted, fenced, expired or closed rounds cannot produce
a recording. Close cancels a future even if it is returned by the exchange only
after cancellation. All control reservations use the actual native owner's pool.
No learner identity counts toward a majority.

The returned recording is temporary and bound to this owner, selected endpoint,
ballot and deadline. It does not survive a new owner/election. The durable ledger
does survive, through exact frozen-source capture and selected-source merging.
This first implementation deliberately supplies no export capability: the
source-transfer path remains closed in the new mode until it consumes the exact
live recording under the same lock. It also provides no learner-head confirmation,
narrowing, matching INTENT, joint-voter eligibility or autonomous scheduling.

The native focused network test and source-bound receipt document their actual
execution separately. Full all-profile/process/physical qualification remains in
the deferred Phase 3 queue. Rollback before publication removes these two kinds
and their recording path, restoring the previous catalog without reinterpreting
an ACK. V5.0–V5.2 runtimes, workflows and release pins remain unchanged.

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

## A11 — nonvoting native application reply and FINAL publication

The internal APPLY_ACK payload keeps its exact certificate, selection and
statement fields. Its acknowledgement field is now a nullable hash in unpublished
1.3: eligible successor voters must return their actual forced CHECKPOINT_ACK;
only an exact A09 departing original owner returns null. The field is never
omitted, replaced with a sentinel digest or treated as a successor vote. The
native owner binds the reply to its actual typed completion. The sender derives
the expected recipient-specific result from the authenticated plan and permanent
identity, then compares the entire correlated payload; its expectation itself
is not an observed ACK. All 51 other record/wire fixtures, commands and read-token
bytes remain unchanged; the total stays 24 records and 28 wire kinds.

The native journal carries the typed completion into pending retention and
publication. An old-only FINAL owner exports its exact checkpoint statement but
no successor ACK. Publication on that node collects actual ACKs exclusively from
the new eligible set. All future-target recordings still require both original
joint majorities before the first publication send; the removed node's null
application reply cannot relax this requirement.

A published generation may retain the removed local owner only after its full
original selection coverage verifies and the terminal membership certificate
proves that owner's exact FINAL. Initial installation, unrelated nonvoters,
changed incarnations, later stable slots and a selection excluding the local
owner do not receive this exception. Reopening the exact final generation retains
known removal; it creates no next-round eligibility or readiness.

The [native qualification](phase3-evidence/native-departure-round.json) now covers
actual removed-proposer/follower TCP histories, independent physical replay and
the serialized transition regression on the same source. Fresh-process native
interruption and all-seven-profile closure remain open. Conditional generation
reopen tests do not substitute for those obligations. No full Phase 3 acceptance
is claimed.
Before release, rollback restores the original non-null APPLY_ACK schema together
with the journal, sender, publication and generation changes; do not reinterpret
a retained null acknowledgement as a vote.

## A12 — reservation-scoped first-contact ROOT discovery

Unpublished 1.3 now gives the existing ROOT-discovery permission a concrete
first-contact representation. A new node has only the operator-supplied root,
complete change request and permanent identity. It must not fabricate a local
voter generation to contact the group. The contact transport has no listener and
cannot adopt a voter catalog or send voting/service controls.

An initial CHUNK REQUEST uses the SHA-256 of canonical
`{schema:"gse-v53-learner-root-reference/1.3", root, learner, request}` as a lookup
alias. `learner` is the exact node/storage/host/port identity; `request` is the
complete existing root/number/expected/kind/target command object. This alias is
not an authority record, ROOT record hash, admission token or receipt. SOURCE_OFFER
returns the complete original ROOT frame hash and extent; subsequent CHUNK and
TRANSFER_COMMIT use the existing sequence, whole-file and chunk digest rules.
ROOT is bounded to its existing 16 KiB record maximum. No record/wire kind, schema
layout, frozen resource ceiling or HELLO.rootRecord meaning changes.

The serving exclusive native owner must have the matching current certified
pre-joint ADD/REPLACE reservation in RESERVED/PREPARING/READY/SEALED. The joining
identity must equal its permanently registered target and be outside the current
voters. Request view is the original expected configuration; the ballot-shaped
correlation is exactly counter 1, joining node and its storage UUID. This read path
never observes, allocates, promises, votes, installs or applies that correlation.
Unknown senders may only cause a lookup in the owner's independently verified
current catalog; received identity fields are never inserted into the directory.

ROOT borrowing shares the native owner's existing six-prefix-export registry,
small CONTROL accounting, original deadline and generation-replacement revocation.
It does not pin a new image or create an unbounded alternate export registry.
Every chunk checks the original live owner and generation. Session completion
keeps only the existing bounded exact-final-reply marker. Cancellation or changed
reservation cannot reopen the old export under the same trace. Client transport
retries are identical, limited to three or the stricter configured count, and
retain the original deadline. Protocol/capacity/closed failures do not retry.

The receiving node verifies full ROOT bytes, embedded root checksum, group and
history identities and resource contract. That result alone is not certified
learner admission. Complete live reservation/capsule, original generation and
ancestry acquisition, exact forced admission before directory creation, image
and readiness receipt, matching local INTENT before voting, all five ADD/REPLACE
profiles and full Phase 3 remain required. Public learner factories stay disabled.

The first-contact byte/link tests, actual native TCP, owner revocation and shared
export headroom have passed their local gates. The [qualification record](PHASE_3_LEARNER_ROOT.md)
separates those results from complete learner admission and joint voting.
Before release, rollback removes this alias route, contact-only constructor and
root client/export together. Existing ordinary peer transfer bytes are unchanged.

## A13 — complete reservation-scoped learner source acquisition

The unmaterialized learner may obtain a read-only STATUS hint using its existing
exact root/expected-view/identity correlation. This hint is only a location; it
cannot establish a certified reservation, new voter, promise or public readiness.

Complete source aliases use SHA-256 of canonical
`{schema:"gse-v53-learner-source-reference/1.3", root, learner, request, cut, scope}`,
where scope is prefix, ancestry or generation. Every field binds the original
request/identity and hinted cut. The serving native owner requires the exact
current pre-joint ADD/REPLACE reservation. The wrapper borrows the existing native
prefix exporter, six-export registry and original deadline; generation replacement
and cancellation invalidate unfinished exports. This adds no record/wire kind.

The source receiver begins with verified ROOT bytes and operator contact routes,
without a fabricated MembershipCapsule or voter owner. Its incoming source packet
uses the one-LEARNER slot, and application images retain their existing seven-image
budget. An identical lost exchange is retried at most three times under the same
original deadline; permanent failures stop immediately. Closing cancels pending
work and closes transport even when owned scratch cleanup refuses foreign bytes.

Only a completed original download can issue the existing private RetainedCopy
and GenerationCopy provenance. The full verified catalog must authenticate the
exact still-active request, joining identity, original expected configuration and
contacted current voter. Original manifest, all members, ancestry and coverage
are verified against the same source/cut/root/request/deadline. No historical
witness becomes a fresh ACCEPT/PROOF observation. No admission or voter directory,
readiness receipt, service read, or voting message is created by acquisition.

A subsequent separately qualified admission transaction must force the original
plan before directory creation. Typed materialization/readiness revision and
full matching INTENT-before-vote remain required. Rollback removes the scoped
export, read-only learner pull/transport/coordinator and reader together; ordinary
voter transfer encoding and storage remain unchanged.

## A14 — forced original learner admission plan

This unpublished additive companion format is `GSLP 1.3`, kind `1`, flags `0`,
with a 48-byte header and a complete maximum of 65,536 bytes. The header contains
magic/version/kind/flags/body length followed by SHA-256 of the first 16 header
bytes and canonical JSON body. It does not change any GSER/GSRP kind, old release
format, transport bound or public API declaration.

The exact `gse-v53-learner-plan/1.3` body has `schema`, original `root` frame,
`learner`, complete `request`, original `source` identity, `cut`, original
`generation` frame, complete ordered `files` inventory and two filesystem `paths`
bindings (operation, replica). Each file row has `path`, `size`, `sha256`; the
inventory includes the original generation frame itself. Embedded frames use
canonical Base64. Paths bind the existing real parent, file store and parent inode;
replica and operation paths are absent, normalized and disjoint at planning.
Receiving scratch must also be disjoint from both destinations.

The production planner requires the exact live source acquired under A13, checks
its certified pre-joint reservation and original inventory, and rechecks that
source throughout plan force. The operation directory owns `operation.lock`,
`learner.next.gslp` and eventually `learner.gslp`. Force the complete candidate,
force its directory, atomically rename, and force the active file and directory
before returning the reviewed summary. One bounded MISC lease accounts the plan;
no second LEARNER or application image copy is created by planning.

Resume takes the original reviewed summary and reads the original retained plan.
A complete candidate can be re-forced and renamed. Missing/partial original plan
bytes, foreign inventory, nonmatching redundant candidates, changed parent/inode,
links or an occupied replica path are preserved and refused. A valid candidate
cannot repair a corrupt active plan. Exact redundant candidate cleanup occurs only
after the active original has been re-forced. Closing releases the exclusive owner
and reservation; it never deletes the operation directory.

Decoding/resealing this plan establishes only original plan persistence. It is not
a fresh proof observation or a retained-source capability. The source's immutable
inventory is bound, but source bytes are not duplicated into this metadata plan;
subsequent learner admission must retain and validate the full original source
and typed image before publishing any readiness receipt. A later CANCEL or new
PREPARE revision must still be checked during preparation/joint eligibility.
No replica authority directory, allocator, local promise, voting record, readiness
receipt, public read or joint vote is created here. Complete nonvoting store,
revision/image/receipt and matching locally forced INTENT remain required.

## A15 — original nonvoting learner source retention

The unpublished additive `GSLP 1.3` companion adds kind `2`, flags `0`, maximum
262,144 bytes, using A14's 48-byte header/checksum. The exact canonical body has
`schema: gse-v53-learner-retention/1.3`, `plan` (the original A14 frame digest),
`staging` (the original five-field parent binding), `directoryKey` and ordered
`files`. Each row repeats the plan's exact `path`, `size`, `sha256` and adds the
original physical inode `key`. This changes no public API, GSER/GSRP encoding or
resource ceiling. It is an implementation contract, not a qualification claim.

While the original source owner is live, complete its received directory with
every original generation member. Grow the existing single LEARNER lease before
writing metadata, force every member and the directory, and verify the complete
original inventory. The source voter's PROMISE/SELECTED records remain that
source's historical records; they never become fresh learner votes. Existing
application-image reservations and inode handles transfer to the admission owner
without a second learner/image reservation or release/reacquire race.

The operation owner expands its existing MISC lease within the unchanged 2 MiB
ceiling to cover plan/candidate/retention/local admission metadata. Before writing
the retention candidate, detach receiver cleanup so an interrupted decision never
deletes its original source. Force `learner-source.next.gslp`, force its parent,
atomically rename to `learner-source.gslp`, and force the active decision and parent
before creating the nonvoting replica directory. An absent or incomplete decision
is preserved and refused; it cannot be recreated from caller parameters.

The replica owns `replica.lock`, original `root.gsr`, its joining `node.gsr`,
`learner/` and `learner-admission.gslp` (the exact retention decision). Move the
complete original staging directory atomically into `learner/`; force that
directory and both parents before forcing the admission marker last. There is
no cross-filesystem copy fallback. Original source inodes and hashes are pinned;
exact partial local root/node/admission metadata can be completed only from the
persisted original plan/decision. No allocator, local promise or voting journal
is created. The complete exclusive owner alone can authenticate the sealed
StoredCopy capability; the capability supplies no fresh vote observations.

Resume validates the original reviewed plan, decision, complete source and any
partial local metadata before resealing/removing redundant decision files. Exactly
one original source location must exist: staging or retained. Missing, duplicate,
linked, replaced or foreign originals are refused and preserved. While a move is
incomplete, its original staging parent must remain available for the directory
force. A completed original admission marker permits later removal of that parent;
if it still exists it must retain its original binding. Exclusive owners and
resource reservations are reacquired before completion; close preserves all data.

This is durable nonvoting storage only. The complete original reservation may
later be cancelled or superseded, and retained historical bytes do not establish
current eligibility. Typed application materialization, exact PREPARE revision,
readiness receipt and full matching locally forced INTENT must still precede any
joint vote. Public learner factories remain disabled. Rollback must refuse the
new retained companion rather than reinterpret it as a voter or delete it.

## A16 — typed learner backup and forced readiness record

The original nonvoting store may own one typed preparation sidecar at
`operationDirectory.resolveSibling(".gse-v53-learner-" + planDigest)`.
The exact parent/path binding and directory inode are retained. The sidecar is
disjoint from the operation, replica and live materialization directories and is
exclusively locked through an empty `preparation.lock`.

`preparation.json` and candidate `preparation.next.json` are canonical ASCII JSON,
each bounded to 256 KiB. Their exact fields are `schema` =
`gse-v53-learner-typed/1.3`, `plan` (original admission digest), `source` (original
packet digest), `receipt` (canonical base64 of the exact GSER LEARNER bytes),
`configuration` (`application` and `core` descriptors), `path`, `materialization`
(the existing five-field path bindings), and `directoryKey`. This is local private
metadata; no new GSER/GSRP family or public format is introduced.

Reserve one APPLICATION slot at the unchanged 64 MiB ceiling before writes, from
the parent store's existing resource owner. Force the plan candidate and parent,
atomically seal it and force the active plan and parent. `backup/` contains only
the three exact original core backup members. Force members and directories,
perform the actual typed semantic read and verify history, then force
`learner.gsr` and its parent last. Only the complete live owner exposes readiness
bytes; these bytes alone never grant local voting rights.

Resume requires the original directory, bindings and complete original plan or
candidate. Partial backup/receipt bytes are repairable only as exact prefixes of
that plan's originals, with semantic decoding repeated before receipt access.
Missing/partial plans, incompatible configuration and foreign/linked bytes are
preserved and refused. Closing the child releases its lock but retains the
parent's image reservation. Parent reopen conservatively reserves that image
before writes whenever the deterministic sidecar exists. Parent close closes the
child before releasing original sources and reservations; it preserves disk bytes.

The original MISC reservation remains 2 MiB. Its bounded metadata sum is 1,444 KiB,
as detailed in [typed learner preparation](PHASE_3_LEARNER_TYPED.md). Source/image
limits and frozen timing budgets are unchanged. This does not settle successor
PREPARE/revision replacement, cancellation retirement, locally forced matching
INTENT or joint activation. Rollback must refuse retained typed metadata rather
than reinterpret it as a voter or silently erase it.

## A17 — prepared learner generation selection and bounded refresh

After the A16 semantic decode and forced receipt, the live typed owner may select
its exact retained source as an immutable **nonvoting** local generation. Before
writing, reserve one of the existing two GENERATION slots while retaining the
original LEARNER byte/staging reservation. Pending claims count toward the limit;
they do not reserve duplicate bytes or release the receiving owner. Cancellation
or source close revokes an uncommitted claim.

Force canonical ASCII `prepared.json` (at most 16 KiB) in the existing typed
sidecar. Its exact fields are `schema` = `gse-v53-learner-prepared/1.3`, `root`,
`identity` (joining identity), `plan` (original admission digest), `typedPlan`
(digest of `preparation.json`), `source` (original packet digest), `receipt`
(digest of the GSER LEARNER frame), and `location` (original replica directory's
`learner` child). No source file moves or original inode changes. Only after file
and directory force may the original metadata lease atomically change from
LEARNER to GENERATION. Metadata bytes stay charged, while receiving staging and
the unique LEARNER count become available. There is no release/reacquire gap.

The marker requires a complete original typed receipt. A partial marker may be
completed only as the exact prefix of those original derived bytes. An altered
marker is refused unchanged. Reopening the parent conservatively accounts the
source as LEARNER until the typed owner repeats semantic verification and forces
selection again; a marker alone is not an in-memory capability. Closing either
the typed or parent owner revokes refresh access. Reopen can therefore refuse for
capacity before any selection, even when the preceding process had selected it.

The private refresh capability uses the parent's **same** resource pool and
checks live ownership around receiving. The complete successor must match the
root, original reservation, request and contacting voter, and retain the exact
original certified terminal anchor (or an authenticated checkpoint endpoint).
A higher index alone is insufficient. Receiving a new copy neither replaces the
original admission plan nor reuses initial admission to install a second store.
That installation, bounded old-source retirement, cancellation, matching locally
forced INTENT and joint eligibility remain subsequent lifecycle requirements.

The MISC maximum becomes 1,460 KiB (A16's 1,444 plus this 16 KiB marker), within the
unchanged 2 MiB lease. GENERATION, LEARNER, APPLICATION, aggregate byte bounds and
production timing limits stay unchanged. Rollback must refuse unknown selection
metadata, never reinterpret it as authority or delete the retained originals.

## A18 — installed original learner successor

One original received successor may be retained beside the original learner at
`operationDirectory.resolveSibling(".gse-v53-learner-successor-" + planDigest)`.
This private directory is disjoint from replica/operation directories, the typed
sidecar, receiving scratch and the configured live core. It contains an empty,
exclusively owned `successor.lock`, `install.json` and its optional exact candidate
`install.next.json`, one original `source/` directory, and `selected.json`.

The canonical ASCII install plan is bounded to 256 KiB. Its exact fields are
`schema` = `gse-v53-learner-successor/1.3`, `plan` (original admission digest),
`previous` (`source`, `cut`, `catalog`, `application` from the predecessor),
`receipt` (predecessor's LEARNER frame digest), `path`, `directoryKey`, `staging`,
`sourceKey`, `source` (actual supplying voter identity), `generation` (canonical
base64 of that voter's original GENERATION), and `files` (sorted original
`path`, `size`, `sha256`, `key` entries). Both path fields use the existing five
field original path binding. The plan never changes a remote voter's identity
into the learner's identity or manufactures a remote durable-copy observation.

Require the receiver to use the parent's exact resource pool, then transfer its
existing complete file/lease owners to the parent and
force the original candidate and directory. Reserve the second generation count
before sealing/installing, force the active plan and move the exact original
source directory atomically. Force both original move parents and the source
directory. Revalidate the certified source and original ancestor, then force the
canonical selection and parent before committing the LEARNER-to-GENERATION lease
conversion. `selected.json` is bounded to 16 KiB, with exact fields `schema` =
`gse-v53-learner-successor-selected/1.3`, `plan` (install-plan digest), `root`,
`identity` (learner), `generation` (original source manifest digest) and `location`
(the retained `source` path). No new GSER/GSRP kind or local voter journal exists.

A complete original candidate may be sealed on recovery. Missing/partial install
plans are preserved and refused, never reconstructed from a new peer or caller.
Only an exact partial selection may be completed. Existing active and redundant
candidate plans must both be complete and byte-identical. Every source directory
and file retains its original inode and bytes. Parent reopen reserves the retained
candidate as a local GENERATION plus its APPLICATION slots, even before the typed
predecessor is reopened; it exposes no selected-state capability at this point.
The original source is still conservatively LEARNER until A17 revalidation and
selection. A matching live typed predecessor then revalidates and forces the new
selection. Parent close closes this owner and releases its process reservations;
closing a typed handle alone does not release retained successor bytes.

The maximum MISC metadata sum is 1,988 KiB: A17's 1,460 KiB plus two 256 KiB plans
and one 16 KiB selection. Original and successor together consume at most the
existing two GENERATION slots. There is no repeated-install bypass; another
successor requires explicit bounded retirement/replacement. Old-source retirement,
new-revision typed receipt, cancellation cleanup and matching forced INTENT remain
required follow-up work. A selected capsule is not a floor-copy acknowledgement,
public readiness, joint vote or complete Phase 3 acceptance. Older private readers
are not a recovery route for this new sidecar; preserve it and use its original
plan under the new owner. Public APIs remain disabled.


## A19 — typed receipt for an installed learner successor

An A18 selected original successor may supply an exact PREPARING revision to the
existing typed semantic reader. Both the original prepared owner and selected
successor remain live. The source packet, active request, joining identity,
current revision and original application image must match; an earlier revision
cannot supply the later receipt. This creates a nonvoting readiness record only.

Use the deterministic private sibling
`operationDirectory.resolveSibling(".gse-v53-learner-ready-" + planDigest)`.
Require the same reserved live-core path as the predecessor and disjoint source,
operation, replica, old typed and new typed paths. Reuse A16's exclusive lock,
original candidate/active plan, three exact backup members, semantic decode and
receipt force order. Reopening requires the original complete plan (or complete
candidate), repeats semantic decoding and only completes exact original prefixes.
No `prepared.json` is accepted in this second sidecar, and `retainGeneration()`
refuses before writing: its source already occupies the second generation slot.

The new canonical ASCII plan/candidate are each at most 16 KiB. Their fields are
`schema` = `gse-v53-successor-typed/1.3`, `plan` (initial admission digest), `source`
(selected successor packet digest), `receipt` (exact GSER LEARNER frame digest),
`configuration` (digest of the canonical `application`/`core` descriptor), `path`,
`materialization` (original five-field bindings) and `directoryKey`. Configuration
and receipt bytes are independently re-derived from the live input and actual
core configuration before comparison; hashes never replace semantic validation.
Bound a plan with a 4,096-byte directory identity placeholder, and bound the
LEARNER frame to 16 KiB before reserving an image or creating any new directory.

Reserve a separate APPLICATION slot at the unchanged 64 MiB bound in the same
parent resource pool. Child close/failure does not release the retained backup.
Parent reopen conservatively reserves it whenever the deterministic new sidecar
exists, even before a typed handle opens it. Parent close closes the new typed
child before its successor's resources. Closing either predecessor or parent
revokes access to the new receipt. Original source, predecessor backup and new
backup remain retained; no unforced retirement or reservation sharing is allowed.

MISC's worst-case sum is 2,036 KiB (A18's 1,988 plus two 16 KiB plans and one
16 KiB LEARNER frame), within the existing 2 MiB lease. No resource count, timing
limit or format family is increased. This supports one installed successor's
typed receipt, not repeated revision installation or voting. Bounded retirement,
matching locally forced INTENT, autonomous READY and complete Phase 3 remain due.


## A20 — forced learner ownership handoff before physical retirement

An A19 typed successor may force a bounded original ownership handoff while both
its predecessor and current typed owners remain live. This is a source capability
handoff, not deletion, a new vote, or an automatic READY submission. Capturing the
record and all candidate/active force cuts recheck both typed owners; close or
mutation before commit fails and preserves the original files.

The A18 successor directory additionally permits `head.next.json` and `head.json`,
canonical ASCII JSON of at most 4 KiB each. The exact fields are `schema` =
`gse-v53-learner-head/1.3`, `plan` (initial admission digest), `installed` (original
successor install-plan digest), `source` (successor packet digest), `generation`
(original GENERATION frame digest), `receipt` (current LEARNER frame digest),
`previousFiles` and `currentFiles`. Each files field is a sorted list of exact
`path`/`sha256` rows. Paths include `.` and `backup`, plus every required original
member. A directory fingerprint hashes canonical `{key, directory:true}`; a file
fingerprint hashes canonical `{key, bytes, sha256}`. Here `key` is the original
filesystem identity text, `bytes` is its length, and the inner `sha256` hashes its
bytes. Relative paths are values, never JSON object keys. No unknown members or
redundant typed candidate files are accepted at capture or revalidation.

Bind the current receipt to the independently verified source's exact PREPARING
revision, and the compact typed plan to that source and receipt. Force the
candidate and its directory, atomically rename it to the active head, then force
the active file and directory. Only afterwards close both old typed handles and
return a separate source view. Those closed handles remain revoked; the new view
uses the parent lock and original head instead of reviving an old handle. Parent
close still revokes the new view and releases process reservations.

Parent reopen validates the exact original head, source and typed-member
fingerprints. A committed original head can be re-forced to expose only the
certified source; exposing a typed receipt still requires actual semantic
materialization/reopen. A complete candidate alone grants no head capability: it
needs explicit matching predecessor/current typed preparation before sealing.
Partial/missing/mismatched originals are refused without reconstruction. When
active and redundant candidates coexist, both must be complete and identical.

All original files and reservations remain retained in this step. Reopen still
conservatively accounts the original source as LEARNER until its existing
selection path runs; this handoff does not free the receiving or generation slot.
Physical retirement must subsequently validate and force every removal before
releasing its reservation, and update recovery to permit only those authorized
missing originals. Bounded repeatable refresh therefore remains open.

Worst-case private MISC is 2,044 KiB (A19's 2,036 plus two 4 KiB head files), under
the unchanged 2 MiB limit. No resource count, wire/GSER kind or production timing
limit changes. Prior private readers are not a recovery path for head-bearing
stores; preserve the original metadata and use the matching reader.

## A21 — original predecessor retirement after forced handoff

After A20, the promoted head may retire the initial source and initial typed
backup. Add one canonical ASCII `retire.json`, at most 4 KiB, inside the original
successor directory. Exact fields are `schema` =
`gse-v53-learner-retirement/1.3`, `plan` (initial admission digest), `retention`
(original source-retention decision digest), `head` (active head bytes digest)
and `headKey` (active head's original filesystem identity). The active head must
be complete with no redundant candidate. Both typed handles closed by A20 remain
closed; an independently reopened predecessor handle prevents retirement.

Force the complete retirement file and successor directory before any deletion.
A partial original decision is preserved and refused. A complete decision found
after restart must match the original admission, retention and head. It permits
only missing members of the exact covered old inventories; it is not proof of a
current source or of prior successful deletion. The original source's staging
location must remain absent. Every remaining old member must have its original
inode, bytes and name, and every remaining directory its original identity. Extra
members, symlinks, replacements and altered bytes refuse without further removal.

Reopen requires complete original replica ROOT/NODE/admission files and active
operation decisions. It does not reseal or repair them in retirement mode. Under
the exclusive operation, replica and successor locks, independently validate the
retained current capsule, exact initial terminal ancestry, selected GENERATION,
current LEARNER receipt and both original typed inventories (allowing only covered
missing predecessor members). Re-force the active head and retirement decision
before resuming removal. Never reconstruct an absent capsule or mint a Floor.Copy
from a plan, receipt or path.

The immutable initial admission's GENERATION and exact source-packet digest supply
the old terminal anchor when old physical files are gone. This is only an ancestry
constraint for the independently verified current source. Summary/path ownership
checks need not repeatedly decode that old capsule; they still validate original
bytes and filesystem identities. Old-source access is revoked in retirement mode.

Delete covered old source files and old typed files, then their empty directories,
in bounded bottom-up order. Recheck current-source ownership and both remaining
inventories around every deletion cut. Force each surviving deletion parent, and
finally the replica directory and old typed directory's parent. Only then release
old source/image and old typed-backup reservations. Before that point, failures
retain conservative leases; fresh-process recovery reserves the original source
leases and any remaining typed backup before removal.
Parent close releases process leases but is not evidence that files were deleted.
Repeated completed retirement rechecks and re-forces the same decision.

MISC's worst-case sum is exactly 2,048 KiB (A20's 2,044 plus one 4 KiB marker).
No resource, timing or wire/GSER limit changes. The current source, current typed
backup, admission and successor metadata remain intact. This recovers one old
slot; alternating repeated refresh, cancellation cleanup, matching forced INTENT,
native/process-death retirement qualification and complete Phase 3 remain due.

## A22 — live current typed head for subsequent acquisition

After A21 has removed and forced the initial predecessor and released its leases,
the promoted source may be semantically reopened through the actual typed reader.
That live typed owner can issue an internal current-head acquisition capability.
An installed but unpromoted successor, an unreclaimed handoff, a plain capsule or
receipt value, and an old/closed typed handle cannot issue it. Cold reopen must
finish original retirement recovery and directory forcing before issuing it.

Use a sealed internal head interface implemented only by the existing selected
initial typed owner and the new current typed owner. Both authorize acquisition
through the same native learner client, original resource pool, single LEARNER
receiving slot, original deadline and exact-parent ancestry check. No caller can
supply a replacement budget or make a capability from historical record bytes.
Closing the typed owner or parent, changing original source/receipt bytes, or
invalidating the forced retirement revokes the acquisition. Receiver cleanup must
release only receiving resources while preserving the retained current head.

Reject scratch paths overlapping the operation, replica, live-core reservation,
current source sidecar, original source staging path, current typed sidecar or
retired predecessor typed path before creating scratch. Current-head refresh is
not initial admission: `plan`, `admit` and the first-successor installer refuse it.
Installing its verified received copy requires the separate reusable-slot owner;
this interface does not create that owner or authorize overwriting old plans.

No new persistent member, reservation category, byte limit, wire kind or public
API is introduced. The typed current head is nonvoting and its receipt remains
bound to its retained revision while a later revision is fetched. Native repeated
installation, matching forced INTENT and full Phase 3 remain open.


## A23 — bounded inactive learner slot

Only an A22 live current typed head after complete A21 retirement can install the
first inactive rolling slot. The first pair uses the retained A18/A19 source and
backup as slot A and the fixed sibling paths
`operationDirectory.resolveSibling(".gse-v53-learner-slots-" + planDigest)` and
`operationDirectory.resolveSibling(".gse-v53-learner-slot-b-" + planDigest)` for
slot B's owner/source and typed backup. Never allocate per-revision directories.
This amendment enables only pending installation; active-head replacement,
alternation and old-slot deletion require the subsequent selection contract.

The slot root permits exactly empty exclusively owned `slots.lock`, `b.json`,
optional identical `b.next.json`, `b.installed.json` and `source-b/`. Each canonical
ASCII plan is bounded to 256 KiB, with exact fields `schema` =
`gse-v53-learner-slot/1.3`, `plan` (initial admission digest), `slot` = `b`,
`sequence` = `1`, `anchor`, `path`, `directoryKey`, `staging`, `sourceKey`, `source`,
`generation` and `files`. The original anchor contains the active A20 `head` digest,
its current `receipt` digest, the terminal `previous` (`source`, `cut`, `catalog`,
`application`) and the original `core` path binding. Path bindings, source voter
identity, canonical original GENERATION and sorted path/size/hash/inode inventory
follow A18's exact validation. Neither a receipt nor this plan is a Floor.Copy.

Validate same-pool ownership, current ancestry, original reservation, all disjoint
paths and bounded metadata before creating a new path or detaching received files.
Keep the current source/backup live. Force the complete original slot plan, reserve
the second GENERATION count, seal the plan, move only the received original source
and force source and both move parents. Independently verify its capsule and
ancestry before forcing `b.installed.json` and its parent and committing the
LEARNER-to-GENERATION lease conversion. This marker is at most 16 KiB with exact
fields `schema` = `gse-v53-learner-slot-installed/1.3`, `plan` (slot-plan digest),
`generation` (original manifest digest) and `location`. It grants no current-head
selection or deletion authority.

Missing or partial plans fail unchanged, and unknown/replaced source or metadata
members fail before recovery force. Complete original candidates may be sealed;
only an exact original partial installed marker may be completed. Cold open
reserves the retained source as the second GENERATION plus its image leases, and
any pending typed backup at its full APPLICATION bound. A live matching current
typed owner is then required to finish installation. No new receiving transfer or
caller reconstruction repairs a retained decision. Parent close revokes both
sources and closes children; child close alone retains physical ownership charges.

Reuse A19's compact typed plan/candidate, actual original-image semantic decoder,
exclusive lock and exact receipt force order at B's fixed typed path. The supplied
revision must match the installed certified PREPARING revision. This typed owner
cannot become a current head, perform the old initial handoff or select an initial
generation. A pending slot blocks another acquisition before transport creation.

Completed A21 retirement leaves at most 908 KiB of original active metadata.
B adds two 256 KiB plan names, one 16 KiB installed marker and three 16 KiB typed
records (plan/candidate/receipt): **1,484 KiB** total, within the original 2 MiB
MISC lease. Redundant A18/A20 plans and old typed members must be absent before
entry. Two GENERATION slots and seven APPLICATION slots remain unchanged; capacity
refusal preserves an owned pending candidate for explicit recovery. Do not charge
absent initial images alongside both actual slots: read-only pending validation
comes first, then original retirement re-forcing and release of conservative old
charges, then pending reservation before exposing a view. Never share/discount
retained images merely because their bytes match. Maximum combined-resource qualification
is still required; this amendment does not claim that every larger image set fits.

No public API, GSER/GSRP family, root identity, quorum, retry count or time budget
changes. Native multi-revision execution, all five joining shapes, halt/SIGKILL,
independent replay, cancellation and matching INTENT remain closure requirements.


## A24 — first rolling head selection and covered seed retirement

A23's installed B remains pending until its actual typed owner and the live A22
current owner force a separate original handoff. The slots root additionally
allows `head.next.json` or `head.json`, each at most 16 KiB. Exactly one is allowed:
a complete candidate alone is not selected, and unexpected coexistence fails.
The canonical ASCII record has exact fields `schema` =
`gse-v53-learner-slot-head/1.3`, `plan` (B plan hash), `source`, `generation`,
`receipt`, `headKey`, `seedFiles`, `previousFiles`, `previousTyped`, `currentFiles`.
`headKey` is the original candidate inode identity, captured after exclusive file
creation and preserved by rename. Replacing that file with identical bytes does
not create a valid cold selection or deletion authority.

Every inventory is sorted and bounded by format-derived paths; each row contains
only `path` and `sha256`. The fingerprint covers file inode, length and digest or
directory inode/type. Seed metadata includes its original root, lock, install plan,
installed marker, A20 head and A21 retirement. Old source paths come from the
validated A18 plan; typed paths are the exact A19 plan/lock/receipt and three-member
backup. Decisions never supply arbitrary deletion paths. Bind B's original plan,
source and GENERATION, exact revision-bound typed receipt and original typed
members, while checking the old source and both live typed owners at write cuts.

The acquisition deadline guards installation through its last return cut. Clear
that acquisition-only guard when installation exits; a retained durable owner
must not depend on a subsequently closed download connection. Its ordinary cut
callback, current-head validation and original-member checks remain in force.

Bound the prospective record before creating its candidate. Force complete
candidate bytes, atomically rename the same original to the active name, then
force that file and its parent before exposing B as current or releasing old
handles. A failure after rename conservatively revokes old capabilities; no new
live current capability is returned until forcing completes. A complete retained
candidate can resume only with the same current A and pending B typed owners.
Empty, partial, changed, copied or mismatched originals fail without repair.

After selection the seed metadata owner retains A's original lock and leases,
while its typed/source capabilities are revoked. Independent B capsule/ancestry
verification no longer requires A's deleted source bytes. The active head covers
only exact original old source/typed members. Cleanup accepts covered missing
members to resume an interrupted deletion, rejects unknown or replaced members,
and never removes B or the immutable seed metadata. Keep both generations and
backups charged until every old member is gone and surviving parents are forced.
Only then release A's GENERATION/APPLICATION charges, keeping its metadata lock.

Cold selected recovery validates B, its original selecting inode, complete typed
receipt/member identities and seed metadata before any recovery force/deletion.
Do not call legacy source recovery against a partly deleted A. Re-force the active
head, re-force initial retirement parents and release their conservative absent
charges, reserve B and conservative A ownership under the original pool, then
finish covered A retirement. Capacity refusal exposes no current capability and
preserves files. Semantic reopening of B through the real core decoder remains
necessary before it can issue a typed current-head capability. All children and
borrowed/cold locks remain bound to the original admission owner.

Two 16 KiB head names increase the conservative metadata bound from 1,484 to
**1,516 KiB**, within the unchanged 2 MiB MISC lease; actual active/candidate names
are exclusive in this first-selection contract. Two GENERATION and seven
APPLICATION limits remain unchanged. This first B selection does not permit
another acquisition or alternating overwrite: reusable A/B plans, replacement
selectors, cancellation, locally forced matching INTENT and complete native and
process-death qualification remain subsequent work. No voting rights, public API,
wire family, quorum, timing limit or retry policy changes.


## A25 — original durable vacancy before alternate-slot reuse

A24's in-memory seed-retired flag is not a persistent reuse boundary. Add the
exact canonical ASCII `cleared.next.json` / `cleared.json` pair in the same
exclusively owned slots root, each at most 16 KiB and never coexisting. The record
has exact fields `schema` = `gse-v53-learner-slot-cleared/1.3`, `plan` (B plan hash),
`head` (A24 head hash), `headKey`, `clearKey`, `previousFiles`, `previousTyped`,
`seedFiles`. The last three are hashes of the exact original sorted fingerprint
arrays in that selecting head. `clearKey` captures the exclusively created
candidate's own inode and remains unchanged across its atomic rename.

Only an independent valid, forced current head plus complete absence of its
covered old source and typed roots can write this record. First finish covered
removal and force both surviving parents. Bound the prospective record before
creating its candidate; force complete original bytes, atomically rename the
same inode, and force the active file and parent. Only then release old seed
GENERATION/APPLICATION leases and issue the corresponding typed current-head
capability. The marker grants no vote, matching INTENT or public READY.

Cold open validates the full current source, typed originals and selecting head,
then the vacancy binding and original inode before any recovery force. Empty or
partial records, copied inodes, different head bindings, two record names at once,
and recreated old roots fail unchanged. A complete original candidate or active
record is re-forced only after the current head and both absence parents. This
forced original state may then waive the conservative old seed reservations;
missing directories alone may not. A pre-A25 retained head with no vacancy still
follows A24's conservative accounting and covered cleanup, producing the new
record only after those forces. No recovery write reconstructs a partial record.

The original fixed old paths remain absent in this batch. A later inactive-plan
contract must explicitly bind this vacancy before placing a new source or typed
backup there. New acquisition and alternate installation remain blocked until
that path is implemented; neither the marker nor a caller map bypasses ownership.
Across subsequent cycles, an old vacancy must never authorize cleanup for a new
selected head. Its head and inode binding is part of that boundary, not a global
boolean or an append-only per-revision log.

Two additional 16 KiB names bring the conservative metadata envelope to
**1,548 KiB**, within the unchanged 2 MiB MISC lease. Existing two GENERATION and
seven APPLICATION limits, deadline guards and retry policies remain unchanged.
Complete multi-cycle, maximum-resource, all-profile, native and halt/SIGKILL
qualification remains required before Phase 3 closure.

## A26 — reuse of the cleared A paths under one slot owner

Retain the single slots lock and immutable admission/seed metadata roots. Split
current and pending image data/resources inside that owner; a source or typed
view is bound to the exact image descriptor. Permit one next source only after
an independently valid forced B head, forced original A25 vacancy, released old
seed leases and absence of any pending plan. Current acquisition still requires
the actual owned typed B preparation; a caller receipt/map is insufficient.

The first reused image is A, sequence 2, at the old seed `source/` and typed paths.
Its metadata names are `a.next.json`, `a.json` (256 KiB each) and
`a.installed.json` (16 KiB) in the existing slots root. Do not overwrite the legacy
seed `install.json`. The canonical `gse-v53-learner-slot-reuse/1.3` plan has the
same thirteen fields as the original B plan plus `vacancy` and `planKey`.
`vacancy` has exact fields `head`, `headKey`, `cleared`, `clearKey`, binding the
current head and complete active vacancy's original bytes and inodes. `planKey`
is the exclusively created candidate's own inode, unchanged across atomic rename.
`anchor` binds B's head/receipt/core and terminal cut/catalog/application. Original
source/generation inventories retain native ancestry/reservation verification.

Bound the prospective plan before creating its candidate. Force its complete
original bytes, rename the same inode, force the active plan and parent, move
only the exact retained source, and force destination plus both relevant parents
before installed-marker completion and receiving-to-generation resource transfer.
No current selector is overwritten. Pending A remains nonvoting and cannot issue
another acquisition or become current. Further sequences and replacement-head
selection remain unimplemented, rather than silently wrapping a sequence.

Cold entry reads the current B and pending A originals before any recovery force.
Only a complete original active vacancy may authorize already-reused paths; a
vacancy candidate never does. A complete pending plan resumes from its original
staging or destination, exactly one location with original inodes and bytes.
Incomplete/copy/foreign plans and unknown names refuse unchanged. A repeated
old-retirement request validates the original vacancy and pending reuse binding,
then skips the covered old-file traversal entirely. It must never delete the new
A image or waive its charges. The legacy seed lock and metadata remain owned.

The conservative metadata maximum is **1852 KiB**: A25's 1548 KiB plus one
256 KiB plan allowance, one 16 KiB installed marker and two 16 KiB typed records.
The selected B head forbids `b.next.json`; the old two-plan allowance plus the new
one covers current B and pending A active/candidate. The typed allowances cover
B's active plan/receipt and A's plan/candidate/receipt. This remains within the
unchanged 2 MiB MISC lease. Two GENERATION/seven APPLICATION limits and existing
source deadlines remain unchanged. Complete alternating selection/retirement,
all-profile/max-resource and process-death qualification still gate Phase 3.

## A27 — replace the selected learner head and retire B

Use the same `head.next.json` / `head.json` names and 16 KiB bound for the first
replacement selection (A, sequence 2). The canonical
`gse-v53-learner-rolling-head/1.3` record has the ten original head fields plus
`slot`, `sequence`, `previousAnchor`, `previousPlan`, `priorVacancy`.
`previousAnchor` is B's original head/receipt/core and native terminal binding;
`priorVacancy` is the exact four-field vacancy binding in A's original plan.
`previousPlan` fingerprints the slots root inode and original `b.json` and
`b.installed.json` bytes/inodes. Source/typed fingerprints cover only B's known
members, while `currentFiles` covers the exact A typed members. The new record
binds its own exclusively created candidate inode. No previous head or vacancy
is embedded recursively.

Unlike first selection, old active HEAD and new candidate HEAD_NEXT may coexist.
The actual B typed current owner and exact pending A typed owner must agree before
candidate force. After complete candidate force, atomically replace HEAD with
that same inode and force active file/parent before returning selected A. Old B
handles become unusable at replacement; an incomplete force path exposes neither
an alternate old head nor an unforced new current capability. Partial candidate
bytes are preserved/refused. A complete retained candidate can only resume under
both actual typed owners. Cold recovery never treats it as an automatic selection.

Cold selected-A entry binds A's original plan to the new head's previous anchor,
verifies its native source and exact current typed records, and binds B's retained
plan/installed metadata to `previousPlan`. Reject an extra B plan candidate: the
retirement decision does not authorize a later installation. Validate covered
old inventories and the original prior vacancy before recovery force. Only the
selected original head permits covered B source/typed members to be absent.
B's plan and installed marker remain until the next reuse protocol covers their
replacement. They also provide the conservative resource manifest after partial
deletion. No source or typed paths may be taken from arbitrary record strings.

After covered B deletion and parent forces, create the next original A25-shaped
clear record for this new head. Its candidate may coexist with the exact prior
active vacancy bound by this selector. Force the new candidate, atomically replace
the old clear name with its inode, and force the active clear and parent before
releasing B leases. An already-original new clear is re-forced before waiving old
charges on cold recovery. The old vacancy never waives B charges or authorizes a
new acquisition by itself. Preserve every original partial/copy/foreign decision
and refuse before recovery writes. Current A remains independently verified.

This record fits the existing head-pair allowance; the conservative MISC bound
stays 1852 KiB of 2 MiB. Two GENERATION and seven APPLICATION limits are unchanged.
Subsequent inactive-plan replacement, repeated cycles, cancellation/matching
INTENT, all-profile/max-resource and original native/process-death qualification
still gate Phase 3 closure.

## A28 — bounded alternating learner plans

After the selected head's original vacancy is forced and its previous leases
released, allow the next sequence at the opposite fixed slot: odd B, even A.
Sequence 1 and sequence 2 retain their original schemas. Sequence 3 onward uses
`gse-v53-learner-slot-rolling/1.3`, adding only `replaces` to the fifteen A26 fields.
That exact fingerprint list covers the slots root and the inactive slot's old
plan and installed marker; it must equal the current head's `previousPlan`.
The next sequence is exactly current + 1, with overflow refused before creating
any candidate or detaching a transfer. No history chain, new directory, third
generation or additional image allowance is introduced.

Create the inactive candidate exclusively, bind its own inode, and force its
complete original bytes before atomically replacing the covered old plan with
that same candidate inode. The old installed marker may coexist only while its
exact fingerprint matches `replaces`. Force the active plan and parent, delete
only that covered marker, and force the directory before placing the new source.
Recovery also forces that parent when interrupted after deletion. Never append
new installation bytes to an old marker. New installed bytes retain the existing
original-prefix completion rule, exact new plan digest and fixed destination.

Before plan replacement, both covered old metadata files must still exist and
the new source must still be at its original staging location. Afterwards, the
old marker, absent marker, or original new marker prefix are distinct states;
an old marker cannot coexist with an already-moved new source. Partial candidate
plans, copied inodes, missing pre-replacement metadata and foreign replacement
fingerprints refuse before recovery forces and are preserved unchanged.

Cold recovery selects the current image from the original head's validated slot
and sequence. The other image is either the exactly previous sequence (retiring)
or exactly next sequence (pending), never both. A retiring plan's original
fingerprint in the current head authorizes reading its historical anchor. A
pending replacement's complete original active vacancy and exact `replaces`
authorize the already-retired metadata to be replaced. No old source/typed deletion
runs in this latter state; its newly owned files remain charged and untouched.
Selected native ancestry, current typed receipt, prior inventories and all root
identities are still validated before any recovery force.

The A27 replacement-head and A25 vacancy protocols apply at every sequence with
the same bounded names. Each selection still needs both actual typed owners;
old views revoke on atomic head replacement, and new current acquisition waits
for covered removal, parent forces and the new original vacancy. The metadata
envelope remains 1852 KiB within 2 MiB MISC, with two GENERATION and seven
APPLICATION units unchanged. This generalizes implementation; finite conditional
component histories do not close native, process-death, maximum-resource,
all-profile, cancellation, matching-INTENT or autonomous Phase 3 qualification.

## A29 — read-only progress for prepared learners

Keep the original learner ROOT and source aliases restricted to active pre-joint
reservations. Add `gse-v53-learner-progress-reference/1.3` as a separate derived
lookup alias, not a persisted record, grant or enrollment token. Bind ROOT,
complete joining identity, complete original request, current cut and one of
`prefix`, `ancestry`, `generation`. The verified source catalog must still retain
the exact prepared operation. Its prepared stable view proves that the reader
was the joining identity, rather than an old voter. Missing, retired, unprepared,
foreign or changed operations refuse. Terminal results never permit re-enrollment.

The contact client uses its live prepared/current typed owner and original ROOT;
STATUS is only a hint. Download and authenticate the complete original generation,
including its ancestry, under that owner's same resource pool and one original
deadline. Verify the exact prepared-owner terminal anchor before exposing progress.
The source must be an exact current voter identity. Publishing a different cut,
closing either owner or exhausting the original budget revokes the exchange.
Only transient transport IO/deadline failures retry identical frames, within the
existing attempt and deadline bounds. Protocol, integrity and capacity errors do
not renew the budget or become a new experiment.

A progress client remains outbound-only and rejects voting requests even when
its joining identity appears in the remote joint/new view. Progress and enrollment
pulls cannot share a mixed prefix/generation pair. The admission completion API
refuses progress pulls. No source is moved into the learner authority, no local
INTENT is forced, no receipt is replaced, and no existing learner data is deleted
by this route. Live source access expires with the complete transfer owner. Already checked
historical bytes remain pure data, not a live installation/cleanup capability. Reading a
certified CANCEL or remote INTENT is a prerequisite for the later durable
cancellation/eligibility transaction, not that transaction itself.

No persisted schema, resource bound, public API or normative phase exit is changed.
The native full-history, process-death, all-profile and original-first evidence
gates remain required, as do locally forced matching INTENT, durable cancellation
recovery and autonomous continuation.

## A30 — original-proof-bound learner cancellation retention

Extend A29 with an explicit terminal retention transaction, separate from ordinary
admission and read-only progress. Only a complete authenticated source whose exact
retained operation is CANCELLED may enter it. Require the same live prepared or
current typed owner, complete request/identity, shared resource pool and proven
ancestor. The progress completion method refuses non-CANCEL states. Neither a
remote result digest nor a timeout authorizes this transaction.

Persist `gse-v53-learner-cancellation/1.3` as bounded canonical local JSON, in one
fixed sibling of the operation directory. Bind the original admission plan digest,
request, joining identity, prepared source/cut/catalog/application, current source
voter, exact original source inventory/inodes and both path bindings. Detach the
existing received-file leases before writing. Force the original plan before the
source move; force all original source members, source directory and both move
parents before exposing CANCELLED. The transaction creates no voting generation,
new readiness receipt, local INTENT, journal vote or retirement/deletion grant.

Any retained cancellation directory stops further acquisition/install/promotion,
including an incomplete original transaction. Reopen only the exact historical
store/typed owner for explicit cancellation recovery. Missing/torn typed originals
are refused rather than completed from arguments. Before cancellation recovery
writes, reserve the original receiving/image categories and independently recheck
the full retained materialization and terminal ancestry. Complete original plans
can be resealed; torn or missing plans and changed/copied/missing originals are
preserved and refused. Close revokes the handle and releases reservations without
removing evidence or reopening preparation.

Use the existing one LEARNER slot and separately charged application images.
Two at-most-64-KiB decision files add 128 KiB to A28's conservative 1852 KiB MISC
envelope: 1980 KiB remains below the frozen 2 MiB. No third generation, eighth
image, new wire record, public API or relaxed resource/time bound is introduced.
The original remote acquisition deadline and same-frame retry rules still apply;
local explicit recovery does not start a new transfer or fabricate original bytes.

This component transaction does not close native cancellation or Phase 3. Full
native histories, process death, maximum-resource qualification, original-first
independent evidence and autonomous integration remain required. INTENT eligibility
still requires its own matching image/receipt and locally forced INTENT protocol.
