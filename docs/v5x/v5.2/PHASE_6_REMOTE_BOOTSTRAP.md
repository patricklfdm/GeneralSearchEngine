# V5.2 Phase 6Y receiver-local bootstrap and collection

**Status:** local preparation and immutable authority relocation are qualified
against published V5.1 and candidate V5.2 JARs. No voter is started, no network
connection is opened and no provider is called by this qualification. It does not
establish three-host runtime readiness, cloud admission or complete measurement.

## Explicit topology

`remote_topology.py` and `V52RemoteTopology` implement the same closed JSON input:
three ordered node identities, canonical nonzero group UUID and canonical IPv4
host/port pairs. A `local-no-gcp` placement accepts loopback endpoints only. An
`owned-private-hosts` placement requires three distinct RFC 1918 addresses. Both
reject duplicate endpoints, DNS names, metadata-service/public addresses, IPv6,
unknown fields, reordered/missing nodes and ports outside 1024–65535. Inputs are
bounded to 4 KiB regular files; duplicate JSON keys and symbolic links reject.

An address in an allowed range is not ownership evidence. A future admitted guest
entry must compare these exact endpoints with the leased instances' independently
observed identities. The logical suite's one-voter-per-host requirement still
needs actual host evidence; local loopback tests cannot satisfy it.

The original local `V52MeasurementConsumer` and its default loopback preparation
remain unchanged. The new helper constructs remote configurations with the same
core builder, protocol bounds and M01/M02/M03 options. It does not expose arbitrary
runtime tuning or change production Java.

## Bootstrap at the receiver

A verified immutable V4.4 seed backup is the only application source distributed
to receivers. `V52RemoteBootstrap` calls public bootstrap plan/apply at each local
root. Manifest/genesis/source identities must agree across the three receivers;
filesystem-dependent seals are generated locally and remain distinct as required.

The public bootstrap API prepares all three offline voters. After completion,
only the assigned voter remains at its live path. Never-started sibling authority
and the coordinator receipt move to `unstarted-bootstrap` for diagnostics. No
seal bytes are rewritten. An already consumed node, operation or archive path
rejects a second invocation, including an interrupted earlier preparation. The
future guest command claim must still prevent re-entry after response loss.

This stage does not copy a live replica directory across hosts or add a repair
path. It does not start the engine, replay a business call or change source backups.

## Immutable collection mapping

`remote_bootstrap_evidence.EvidenceLocation` requires all three independently
retained receiver bindings. Each names its original local root and exact manifest
and genesis digests. The collected package is inventoried before inspection. The
validator inspects each node's unchanged authority bytes against that node's
original sealed path and verifies the node identity, inventory and group digests.

This mapping is for offline inspection only. It does not allow opening downloaded
files as live voters. Original collection and a fresh unpacked relocation must
produce exactly the same independent physical result. Wrong original paths must
fail at `copied/stale seal path`; another rejection is not counted as the intended
negative result.

## Qualification and remaining work

The new entry is part of the existing V5.2 measurement verification script:

```bash
python3 -m unittest scripts.v52.test_remote_topology
python3 -m scripts.v52.remote_bootstrap_qualification target/v52-remote-bootstrap/run-1
```

Five topology tests cover valid placement, malformed fields/addresses/ports,
duplicate endpoints, distinct-host requirements and file/parser bounds. Three
collection regressions reject missing/changed inventories, altered receiver
bindings and inventory-resealed authority that differs from the independent
manifest/genesis binding. A separate
Java/Python parity matrix has 20 inputs per compiled family: two accepted and 18
rejected. Real public bootstrap prepares six receiver authorities across the two
families, independently inspects all six, verifies duplicate invocation rejection,
and replays collected/relocated bytes. Six wrong-root negative checks reject at
the required category. Voters started: **0**.

Retained receipts are under `target/v52-remote-bootstrap/` in the isolated worktree.
The runtime JARs are byte-identical copies of the successful build from
`493837abb0b76b2699ddab7de174eeb722b8a4f0`; the bootstrap helpers are newly compiled
from this stage. These are separate identities, not a claim that that older build
contained the new harness. No extra reactor rebuild was needed for unchanged
production classes.

Next connect persistent, bounded guest command ownership and the public consumer,
then qualify actual separate-process execution, faults and complete collected
history replay without GCP. The existing local cohort continues against its own
unchanged freeze. Exact-master protected CI and fresh cloud/provider admission
remain operator-controlled steps after the accumulated local development is pushed.
