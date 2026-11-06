# Original file-to-custody resource binding

The [joined handoff reader](PHASE_3_JOINED_HANDOFF_RESOURCES.md) checks category,
byte extents and uninterrupted ownership. Its ordinary resource deltas cannot
identify a swap of two equal-size image reservations: both removed/added sets
would still match. File ownership needs the actual predecessor/successor pairs.

## Observation and independent derivation

When resource observations are enabled, `MembershipResources.transferStorage`
records the committed handle map under its existing monitor. Each row has at
most 32 pairs and is bound to the exact resource transition sequence. Recording
is bounded by the existing observation limit; failure or truncation is sticky
and cannot roll back ownership or prevent release. No I/O or external callback
is added under the monitor. Pools with observations disabled allocate no transfer
recorder.

The opt-in fixture property `v53.resource.storage.transfers=true` retains a
separate `storage-transfer-captures` collection. Its index binds every original
owner to the same root, events digest and complete resource-journal digest.
Existing resource v1 JSON, persisted storage, protocol messages and limits do
not change. Missing sidecars are not synthesized from older deltas.

`native_resource_evidence --joined-files --profile 5-REPLACE-required-four`
first admits the complete semantic, physical, network, export, maintenance and
resource history. It then independently derives:

- The original source sessions at cuts 4, 8 and 9 from exact source bytes,
  sender/recipient identities and the pre-custody interval. A later native
  recovery can transfer identical bytes; it cannot substitute for these sessions.
- Each predecessor's exact category, owner and reserved extent, including the
  full typed-backup reservation and pending journal/completion headroom.
- Each regular placed file's original identity, size and digest, and its
  predecessor and custody successor. Equal content in distinct inodes remains
  separately charged. Files with no owner or bytes exceeding the owning
  reservation are rejected.
- The actual predecessor/successor map at the forced atomic custody switch.
  The existing handoff reader separately requires continuity through all
  deletion forces and atomic native replacement.

These are conditional readers of admitted originals, not acceptance of a
producer-supplied mapping. The reader derives its expected pairs from original
transfer sessions and physical placement; the sidecar supplies the observed
actual pairs. Ordinary accounting replay intentionally cannot distinguish two
alternative equal-byte pairings; the independent file binding can.

The placement/admission records are created after the custody switch. Their
mapping explicitly marks `createdAfterCustody`: the predecessor reserved their
completion space, but these files did not exist under that predecessor. The
binding checks their actual placed bytes against the retained successor charge.

## Local verification

The new complete local required-four producer reached FINAL, the stable BARRIER
and cold reopen in 1,459 seconds. It retained 65 placed files, eleven predecessor
leases, three post-custody completion records, and four distinct image files
sharing one content digest. The optional transfer collection occupies 4,878 bytes.
The first sandbox launch could not open local sockets; that failure and the later
permitted local execution are both retained. These are development observations,
not a final-source cohort result.

**Complete resource qualification of that original failed.** The initial replay
stopped at the exact PREPARE retry described below. With that reader corrected,
the same original passed its network and ledger stages but stopped at
`native source resources request coverage`: eleven client attempts lacked an
original request-digest resource binding. Three were ROOT discovery, five were
the direct INTENT fixture exchanges, and three were the sealed-progress metadata
pull. The conditional placed-file mapping passes, but it does not override either
failure or earn the thirteen original-first negative credits.

The correction uses the existing `source-request-<digest>-<allocation UUID>`
identity in `MembershipLearnerDiscovery` and `MembershipJoiningIntentPull`.
The fixture's direct INTENT helper also reserves its real request buffer through
submission and completion. The production changes preserve reservation extents,
release scopes, attempts, deadlines and all wire/durable bytes. The original
resource reader stays strict; missing bindings are not guessed from byte sizes.

All 65 targeted Java tests pass, including the actual prepared-owner TCP path,
retry/exhaustion release and the new fixture request lease. The ROOT regression
fails on the earlier implementation. The 545 related Python tests, 39 checks with
Python assertions disabled, and 35 planning/contract tests pass. Original raw
bytes, both failed replays and their distinct source/build manifests remain
retained in the [development index](phase3-evidence/joined-file-resources.json).

The corrected producer must still collect a new complete history and pass the
unchanged original-first entry below. Per the deferred long-acceptance plan, that
roughly 24-minute workload is queued for the later source-bound hosted batch; it
is not run again here and is not recorded as successful on the corrected source.

The focused producer is one complete history, without splitting its lifetime:

```bash
mvn -o -B -ntp -f reactor/pom.xml \
  -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53JoiningIntentExportTest#requiredFourVotersCompleteReplacementFinalAndStableBarrier \
  -Dv53.joining.requiredFour=true -Dv53.publication.resources=true \
  -Dv53.resource.transitions=true -Dv53.transport.connections=true \
  -Dv53.resource.storage.transfers=true test

# Use the new v53NativeDispatchEvidence path printed by that execution.
python3 -B -m scripts.v53.joined_file_negatives <original-evidence-directory>
```

The negative entry validates the unmodified complete original before requiring
all 13 exact rejections, including a successor swap between equal-size images
that preserves both charge sets and every byte total. Other mutations cover
missing owners, switches and pairs, sequence/type drift, incomplete recorder
flags, foreign handles and changed extents. Originals are never rewritten.

## Original PREPARE retry replay

The first complete replay of this new original exposed an existing reader
assumption: every PROMISE response had to correspond to a new grant capture.
The original node-1/node-6 counter-8 request was instead retried with identical
request and response bytes. Node 6 forced the grant once; the first response was
offered but did not reach the caller, and the retry delivered that same grant.
This is the endpoint's existing exact-duplicate behavior. The failed replay is
retained, and the workload is not rerun to avoid it.

`joining_network_evidence.grants` now binds all exact duplicate replies to that
single original force chain. It uses earliest request arrival, independently of
response order, and still requires the original trigger before capture, local
capture before every send, and durable peer capture before every reply. Changed
request/response context and missing or duplicate force callbacks still reject.
The count of bound grants remains a unique-peer count.

Selection and preparation hints require an actually delivered matching promise
before their decision. Failed socket attempts and later duplicate deliveries
cannot become earlier ACKs or additional voters. The selection journal uses the
first qualifying delivery for each selected peer. Connection causality, terminal
failures, source bytes and durable-force validation remain mandatory.

Focused regressions reproduce the original rejection, cover response reordering,
changed retries, force loss, and missing/late deliveries. The corrected replay
uses the unchanged raw history and compiled runtime; only its reader provenance
changes. That replay exposed the separate missing request-binding problem above.
Neither missing originals nor a failed original is negative-test credit.

A separate complete physical/network replay of the unchanged original passes
with this reader, followed by eight exact in-memory rejection cases, including
loss of the original trigger, altered retries and absence of a delivered promise.
This establishes the network correction's scope, not full resource qualification
of the original with missing client bindings.

## Remaining scope

This binding covers the exact placed-file snapshot and actual custody switch.
It does not observe every intermediate file write, OS-lock release interval,
joining-owner shutdown call, process death or simultaneous runtime byte maximum.
The whole original accounting journal must still close at zero, but a zero
balance cannot invent an explicit close call. Reserved completion space is not
reported as bytes physically present in the snapshot.

The existing 566-history / 260-group catalogue is unchanged. Historical evidence
indexes remain intact, and old originals without the new sidecar retain only
their earlier scope. Complete final-source execution and all five
[Phase 3 closure gaps](PHASE_3_QUALIFICATION_AUDIT.md) remain OPEN.
