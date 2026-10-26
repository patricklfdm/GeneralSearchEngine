# Phase 3B — read-only complete current-prefix acquisition

This is the original byte-acquisition batch. The later
[retained-copy component](PHASE_3_RETAINED_PROVENANCE.md) adds a typed complete-copy
verification path; the strict explicitly supplied verifier described below remains
available. This batch's original evidence and qualification scope are unchanged.

Status: component implementation and local qualification on the V5.3 development
branch. This extends [STATUS discovery](PHASE_3_DISCOVERY.md) with complete bytes;
full historical provenance, autonomous discovery/adoption and Phase 3 closure remain
open. The frozen protocol, formats and acceptance matrix are unchanged.

## Why the existing source grant is insufficient

A frozen BASIS belongs to a real PROMISE and a specific voting configuration. An
older-view process must be able to fetch a newer retained prefix without first
obtaining a vote under its obsolete view. Requesting PREPARE just to retrieve that
prefix would conflate read-only discovery with election authority.

The first CHUNK request names the digest of the exact STATUS cut. The source serves
only its actual selected current generation. The offer identifies the complete
source packet, then the receiver obtains every indexed application image using
the existing offer/chunk/commit protocol. No wire kind or on-disk format is added.

## Ownership and correlation

`MembershipPrefixExport` borrows the journal's actual generation, reserves bounded
CONTROL metadata and exports indexed packet/image files only. There is no extra
physical generation or promise. Each chunk is read under the journal monitor with
owner, file identity, checksum and original deadline rechecks. Switching the current
generation revokes the borrow; an old reader cannot prevent adoption or retirement.
The actual journal permits at most six such live borrows and reclaims expired or
replaced ones before admission. Owner close releases all of them.

Historical permanent identities are authenticated against the root-bound directory;
they need not remain voters. Request view/ballot are immutable correlation fields
for that one session, not a grant and not a higher-ballot observation. The existing
`MembershipTransferService` and `MembershipSourceSession` own finite traces, exact
last-response replay, capacity and close/expiry. Their original voting-source mode
continues to require the exact configuration and ballot.

The activation endpoint dispatches the current-cut reference separately from its
PREPARE/SELECTED scope. It works without creating or reviving a campaign. Service
replacement, timeout, endpoint close and physical generation change cannot continue
an old transfer. All responses stay bound to the original sender, recipient, root,
view, ballot, trace and exchange sequence.

## Receiving and verification

`MembershipSourcePull.prefix` snapshots the actual local owner/fence and shares its
resource accounting. Identical transport IO/deadline failures may be retried at most
three times under one original deadline. Explicit rejection, protocol/capacity/
closed errors, cancellation, fencing and expiration do not acquire a new budget or
start a substitute measurement.

The existing receiving files reserve the complete offered extent before accepting
chunks. Read-only transfer bindings have an explicitly absent grant pair; they do
not invent a BASIS UUID or digest. Packet root and cut must match the hint, every
image must match its indexed length/hash, and all receiving files stay owned until
close. The original frozen-source receiving mode still requires real PROMISE/BASIS.

A completed download is untrusted evidence, not an Owned observation, voting ACK,
read barrier or READY. `verifiedPrefix` requires the separate complete historical
verifier and checks that it returned this exact root, cut and packet. It never
calls adoption or creates observations from witness hashes. The original-source
API rejects these read-only downloads.

## Local qualification and limits

The source-bound [receipt](phase3-evidence/prefix-discovery.json) records completed
builds, tests and independent replay. Real loopback TCP cases start with public
offline bootstrap and an actually voted/published BARRIER at stable sizes 3/4/5.
They preserve the original plan, every voting/publication storage cut, typed image,
STATUS/source transcript, received packet/images and unchanged final authority.
The independent reader reconstructs those physical originals before checking the
exact transfer and negative mutations. Portable replay does not require original
absolute locations.

Separate conditional-fixture tests use actual adopted joint/final generations and
an older-view reader, including a removed reader. Historical certificate forces in
those fixtures remain explicit assumptions; those tests do not prove a distributed
membership transition. Missing historical observations still reject the download.
Fault tests cover lost offer/data/commit replies, finite retries, nonretryable errors,
fencing/deadline, cancellation, selector replacement, writer wait, changed scratch/
source files, correlation drift and bounded borrow cleanup.

Remaining work includes full historical ACCEPT/PROOF provenance without relying on
unavailable former voters, compacted cross-view ancestry acquisition, automatic
verified adoption/fresh election, receiving image reuse at maximal combined lifetime,
repeated-round maintenance, learners and joint completion. No public automatic
membership, protected CI, cloud execution or release is claimed.

## Rollback

Remove the internal prefix exporter, endpoint dispatch and read-only modes of the
existing transfer/receiver classes, retaining the prior frozen grant path. No
persisted file or public API depends on this addition. Keep this batch's original
source/logs/evidence as historical qualification rather than reassigning it to a
later implementation.
