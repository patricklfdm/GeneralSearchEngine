# Phase 3B — receive the original selection and install every selected source

Status: locally qualified component. Phase 3 remains open.

`MembershipSelectedPull` handles the receiving side of an original SELECTED request.
It checks the actual proposer, current local forced grant, view and ballot before
network work. It fetches the referenced SELECTED record from the proposer, checks
local/proposer inclusion and quorum, and rejects a substituted local BASIS before
pulling source files. Each remote BASIS, PROMISE, packet and image is fetched from
that source's own permanent identity. The local source stays pinned at its original
journal owner. The complete ordered selection is independently recomputed before
any selection or installation is forced.

A completed direct source exchange can establish only that contacted original
owner's own frozen BASIS and retained accepted tail. `verifiedOriginalSource` is
available only after all actual source transfers have committed. It does not accept
an untransferred record or an arbitrary caller-created receive object. Serving a
record copied from another voter remains insufficient: source export requires the
owner's exact retained grant and full physical source. No new grant or voting ACK
is created by reading that original. Historical certificate/checkpoint witnesses
still require the explicit capsule verifier; they cannot be derived from hashes
or another peer's copy of a record.

If an exact application image already belongs to the receiver's pinned original
source, the receiving scratch borrows those physical bytes and their existing
reservation. It verifies the root, hash, length, exclusive owner and bytes; it
does not create another physical image or count an unowned hash as a local copy.
Missing images still reserve space and use the normal bounded transfer path.
Closing the export or changing its original image prevents installation.

This reuse corrects a reproduced failure with an original minority tail: its
seven image reservations already occupied the frozen limit, so copying the same
image into incoming scratch failed. The same retained-tail continuation now
passes at seven images, and the progressed-prefix continuation also passes.
No resource ceiling was increased or reservation bypassed. General heterogeneous
prefix/maximum-envelope progress still belongs to subsequent runtime qualification.

The receiver retains all borrowed files and resource reservations through its
actual durable installation. It returns the existing INSTALL_ACK only after the
journal has forced the exact selected state and final fence/deadline checks pass.
A deadline reached after force suppresses the ACK without rolling back durable
state. A lost response can be retried against the exact original installation.
Temporary files are removed by their actual owners; cleanup refuses changed paths
or foreign entries and remains retryable after an I/O failure.

The same original deadline and at-most-three identical transfer attempts apply,
including stricter caller limits. Network waits never hold the journal monitor.
No disk/wire catalog, resource bound, legacy mode, public API or workflow changes.

The final isolated build passes 87 Java tests across eleven suites, including
eleven receiver regressions, related source/activation components and unchanged
V5.0–V5.3 public API inventories. All 557 Python tests pass in normal and optimized
modes. The [receipt](phase3-evidence/selected-pull.json) retains the earlier capacity
failure and the initial reader's incorrect bootstrap-directory assumption separately.

Independent normal, optimized and portable replay verifies the original selection,
123 receiver-side transfer exchanges and all eight selected installations across
three profiles. Fourteen reason-bound negatives reject changed records, identities,
received packets, installed bytes, missing replies and premature acknowledgements.
The earlier initial trace used 150 receiver-side exchanges before exact local image
reuse; it remains historical evidence and is not relabelled as the final runtime.

The qualification binds actual TCP bootstrap/selection/installation at
sizes 3/4/5 to independent original disk, transfer and ACK replay. Progressed-prefix
and retained-tail cases use actual storage with explicit historical observations.
Compacted ancestry acquisition, historical provenance delivery, newer-view discovery,
source rotation, scratch crash recovery, the automatic runtime owner loop,
learner/joint transitions and voting/publication remain separate open obligations.
Installation alone never enables public READY or closes the distributed S/N gates.
