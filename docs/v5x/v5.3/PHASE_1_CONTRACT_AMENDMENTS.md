# Phase 1 implementation review amendments

The Phase 0 closure at `1a7c2b6` is historical local research acceptance. Its retained
hashes are not reissued for these changed declarations. Phase 1 is separately
operator-authorized on the isolated local branch, without push or runtime enablement.

## A01: separate variable-membership status

Actual source review found that `AutomaticReplicationStatus` requires exactly two
peers and the fixed-three genesis/promise representation. The Phase 0 declaration
`MembershipSearchEngine extends AutomaticReplicatedSearchEngine` could not represent
4/5 voters or a six-identity joint view without weakening that published constructor.

Reopen the D08 public-surface choice before this unpublished API is implemented:
`MembershipSearchEngine` instead extends `DurableSearchEngine`, declares its own
`start()` and `leadershipStatus()` using `MembershipReplicationStatus`, and explicitly
retains the V5.2 `read(options, callback)` capability and tokens. The new status
carries an optional exact membership view and full promised proposer identity;
no view is invented for a stopped handle. Its counter zero means no promise; a
real 1.3 promise may start at one. A historical proposer need not remain a current
voter. At most five remote peer observations are represented; these are diagnostic,
not quorum authority. A ready local leader must match its exact promised identity
and current voter role. The old status, old interface and old factories retain
all reviewed descriptors and validation.

The new interface cannot be assigned to `AutomaticReplicatedSearchEngine`.
Applications opting into membership use the new capability explicitly, while
common durable/search code continues to accept its existing parent interface.
No shipped API is removed. New reflection fixtures plus the old inventory tests
cover the boundary; 3/4/5-node declaration cases check the variable-size status.

## A02: pure declaration details

- Discovery seeds are an ordered, distinct list of zero to five remote full
  identities. They supply addresses, never membership authority; no local identity
  may be repeated. Empty seeds allow a later already-bootstrapped local open.
- `MembershipBootstrapPlan.absentTargets` lists both authority and materialization
  directories for each of three to five targets, in target order. Operation and
  optional source directories must be syntactically disjoint from all these paths.
  Normalization is pure. Symlink/ownership/existence checks await actual admission.
- Identity hosts use lowercase DNS, decimal IPv4 without leading zeros, or
  compressed lowercase IPv6 (longest zero run, first tie). No DNS lookup occurs;
  aliases are an operator concern. Existing endpoint constructors remain unchanged.
- Constructor validation checks value consistency, not authentic storage/certificates.
  A caller-constructed view, plan or result does not become authority by passing a
  constructor. Contextual byte verification and durable admission are separate gates.
- During Phase 1, `build()` returns a stopped handle, all asynchronous operations
  fail with `UnsupportedOperationException`, and no read callback executes.
  Local data/progress queries needing an opened runtime and all offline operations
  are likewise unavailable. `schema()` and stopped/closed leadership diagnostics
  remain pure; `close()` is idempotent. No bootstrap/history is created.

## Coordinate boundary

Only current reactor/consumer coordinates advance to `5.3.0-SNAPSHOT`. Current
source-bound regression inventory admits that explicit version and requires the
new executed suites in addition to the V5.2 read prerequisites. Historical release
allowlists, published fixtures, V5.2 cloud input identity, measurement candidate
versions, exact source/attempt evidence and active Runner checkout are unchanged.
V5.2 paid/measurement gates intentionally do not accept 5.3 artifacts as 5.2 evidence.

## A03: explicit bounded inventory packing

The Phase 0 contract required a complete inventory-checked capsule file but did
not specify the container bytes or resolve its digest self-reference. The separate
[GSCP 1.3 packet contract](PHASE_1_SOURCE_PACKET.md) now defines the header, ordered
index, separate materializations and nonrecursive capsule/index/transfer digests.
It preserves the frozen 24 storage and 21 wire frame schemas and byte fixtures.
Passing the container checks does not establish capsule authority; the full
range/edge/endorsement walk and frozen-source selection remain required.
