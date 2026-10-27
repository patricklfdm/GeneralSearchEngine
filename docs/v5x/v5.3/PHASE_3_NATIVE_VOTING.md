# Phase 3 — native incoming phased voting

This batch connects real incoming ACCEPT and PROOF to the exclusive native
storage owner. It remains an internal, explicitly driven protocol component;
certificate/application controls, automatic scheduling and public membership
are not enabled. [A07](PHASE_3_CONTRACT_AMENDMENTS.md) defines original-payload
and phased-receipt transfer semantics without changing any disk/wire fixture.

## Authority and bounded lifetime

A voting scope comes from the native owner's actual installed selection, ballot
and parent. The proposer cannot use a newer incoming ACCEPT as an implicit grant.
The receiving endpoint acquires the original ACCEPT, ENTRY and payload over the
bounded transfer service, and separately obtains the proposer’s original ACCEPT
receipt even for an empty BARRIER, before forcing its own ACCEPT. PROOF processing validates
the exact own ACCEPT and both governing majorities, then contacts each named
remote voter's permanent identity for its original durable receipt.

Receipt bytes are the existing witness-hash preimage. Computing those bytes,
reading a received hash, or copying a record into a capsule never establishes
an observation. Export is restricted to the owner's complete active vote and is
rechecked on every offer/read/commit. A pending candidate alone cannot serve it.
A complete retained vote from an earlier installed round is still recovery
evidence, but cannot produce a current-round observation or ACK. The native scope
requires the vote's ballot, SELECTED and selector to match its current installation.
The new round must first force its own successor vote. A native three-voter
re-election regression preserves the original old vote and checks this boundary;
that regression is Java qualification, separate from the independent TCP matrices.
The endpoint's independent transfer service permits reverse pulls while its one
writer is waiting for remote evidence. Source buffers remain charged through the
actual durable write. Waiters, control storage and original deadlines remain bounded.

After a force with a lost ACK, a fresh owner can acknowledge the identical phase
from its own recovered vote. No new remote observation or application is required.
A higher ballot after force prevents ACK without erasing the retained vote.
Identical in-flight controls share completion; an exhausted identical request
retains its failure for that scope. This does not introduce automatic retry of
indeterminate application work or an autonomous recovery loop.

## Qualification boundary

Actual TCP histories start receiving voters without the tested ACCEPT and then
force ACCEPT/PROOF in stable groups of 3, 4 and 5, for BARRIER and nonempty DATA.
The original-first reader derives bootstrap, selection, any prerequisite barrier,
exact payload/entry/votes and unchanged published files. It checks every original
transfer and all phase ACKs, including force-before-response ordering. Negative
variants reject substituted payloads, votes, identities, receipts, missing
original-owner observations and incomplete transfers.

Receiver halt/SIGKILL tests interrupt ACCEPT and PROOF after candidate force and
immediately before ACK. A fresh JVM recovers the actual files, explicitly receives
two identical requests, returns equal ACKs and performs no new remote pull or write
after READY. Independent replay checks original requests, source responses,
interrupted/recovered bytes and exact resume logs. The sender is explicit: this
matrix does not qualify autonomous loss detection or redispatch.

The [local receipt](phase3-evidence/native-voting.json) records 28 passing Java
tests, including six real TCP histories and eight halt/SIGKILL recovery cases;
671 Python tests and two focused tests with assertions disabled also pass.
Independent original-first replay and relocated archive replay reject all 158
evidence mutations. The retained within-batch counterexample fails when the
current-round binding is removed. These results qualify only the scope above.
Full 3C/3D/3E acceptance, all seven learner/joint profiles, native certificate and
application ingress, autonomous owner lifecycle and maximum combined headroom
remain required. No S-family acceptance row is closed by this component alone.

The receipt lookup is SHA-256 of canonical `{schema: "gse-v53-vote-observation/1.3",
receipt: <receipt SHA-256>}`. SOURCE_OFFER and subsequent chunks/commit bind the
receipt SHA-256 itself. A plain receipt hash is not an attestation lookup, and a
normal payload selected by its own hash cannot satisfy the distinct receipt
digest. This separates evidence acquisition from ordinary content possession.
