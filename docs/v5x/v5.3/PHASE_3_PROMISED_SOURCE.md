# Phase 3B — received original source to fixed selection

Status: locally qualified component. The complete Phase 3 gate remains open.

`MembershipPromisedSource` binds an actual authenticated PROMISE reply to the
current original PREPARE, exact peer/storage/endpoint, root/view/ballot, correlation
and the received original BASIS digest. The activation controller retains the
original outgoing request, so unrelated or delayed messages cannot authorize a
source. Complete received packet/image files must still have their exclusive
owner and original deadline throughout verification.

The reply is an observation that this peer forced the referenced frozen BASIS
and its own retained accepted tail, as required by the PREPARE handler. It is not
a new ACCEPT, PROOF, installation ACK or checkpoint endorsement. The validator
constructs only those peer-local basis/tail observations after matching the reply
and original records; it does not manufacture historical witness observations
from packet hashes. Historical capsule/certificate/checkpoint provenance remains
an explicit verifier input, and that verifier cannot substitute another packet.

The controller passes only this fully bound source into its existing fixed quorum
selection. It rechecks the original campaign deadline and higher-ballot fence
before allowing the source to contribute. A source-verification failure abandons
the campaign without replacing its forced grants. A retained accepted entry keeps
its original bytes and must remain the first selected entry.

The activation controller borrows the received files until every selected node,
including the proposer, has completed its actual durable installation. It rechecks
their physical ownership on subsequent campaign actions. Closing a borrowed source
abandons the campaign without changing its already-forced selection. Once all
installations complete, the controller releases the borrow; the caller can close
the scratch without invalidating the installed selection. This is not public READY.

## Local qualification

The final isolated build passes 53 Java tests across eight suites, including ten
new source-binding tests and the V5.0–V5.3 API inventories. The lifetime regression
first fails on the earlier implementation, which allowed use after receive closure;
its final correction and actual-installation handoff both pass. The first test
compilation error, earlier successful component run and red regression are retained
separately in the [receipt](phase3-evidence/promised-source.json).

Actual TCP histories begin at public offline bootstrap for sizes 3/4/5. Five
PREPARE/PROMISE exchanges, fifteen reverse proposer-record exchanges and 75 complete
source exchanges produce the original fixed 2/3/3 source selections. Independent
replay derives original disk, wire and received-file bytes. Sixteen reason-bound
negative mutations, optimized replay and archive relocation pass. The raw histories
stop before installation; the separate installation lifetime test uses actual
storage operations through the in-process adapter.

Historical capsule validation still requires explicit real observations. A progressed
source is rejected without its checkpoint witnesses; valid packet bytes and a matched
PROMISE cannot manufacture those witnesses. The accepted-tail regression preserves
the original minority entry. Correlation changes, substituted prefixes, closure,
higher promises and deadline expiry cannot produce a new valid selection.

This integration does not close the production provenance owner or the complete
network installation path. In particular, a stale node that has not observed the
remote history still needs real authenticated historical evidence; a valid PROMISE
is not a substitute. Full newer-prefix discovery/adoption, compacted ancestry
exchange, end-to-end receiver installation over the network, source rotation, restart scratch
cleanup, learners, joint transitions and generalized publication remain required.
