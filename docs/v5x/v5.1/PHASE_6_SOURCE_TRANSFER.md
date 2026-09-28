# V5.1 Phase 6C3C11 — bounded initial-source transfer

**Status:** implementation candidate based on accepted PR #241, master
`87e0cdda3f38dbadce149e54eb1cc45f0f634e28`, exact-master CI
[36388477710](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36388477710)
attempt 1 (all 27 jobs). This source requires its own protected Linux qualification
and exact-master acceptance. Full 6C and paid admission remain open.

## Transfer boundary

The [owned bootstrap coordinator](../../../scripts/v51/guest_owned_bootstrap.py)
can now use [binary delivery](../../../scripts/v51/guest_source_delivery.py) after
all three packages are authenticated and before any receiver import. The producer
still runs through the explicit `qualification-shared-source-paths` adapter. Its
preparation and controller access to its export remain local qualification;
producer-side remote command admission/download and native IAP remain future work.
The new receiver does not use those producer paths.

The controller splits each existing bootstrap archive part into at most 1 MiB
requests. Its closed descriptor binds the original six-file inventory, complete
part and chunk digests, configuration, source, bundle, attempt, node and package
manifest. Authenticated SSH carries metadata in arguments and binary bytes on
stdin; source bytes are never interpolated into shell code or JSON strings.
The installed package additionally binds the exact instance, disk, guest access,
original boot identity and deadline. Packaged code is imported only after the
complete installed package has been verified.

The [receiver](../../../scripts/v51/guest_source_transfer.py) retains one consumed
transfer directory per package. It reassembles the original archive, verifies every
part, and streams the six expected members without extracting them. Only then can
bootstrap import consume this receiver-local archive. The import request contains
`sourceTransferSha256` and `descriptorSha256`, with no producer folder. The original
shared-path entry remains available for earlier qualification, with unchanged
validation; binary mode never falls back to it.

Bounds are explicit: six files, 64 MiB total expanded source/topology, the existing
32 MiB per-member limit, 65 MiB compressed allowance including archive overhead,
64 KiB metadata and at most 65 chunks. Chunk staging plus the assembled archive
uses at most 130 MiB before import. Import checks member names and exact declared
sizes before writing, and then checks the complete inventory and digests. Extra
members, excessive expansion, altered bytes, links and changed bindings reject.
Public authority and filesystem-bound seals are produced locally as before and
are never transferred.

## One original deadline, consumed writes

All source calls and later import/seal calls use the original package deadline
inside the existing 600-second owned preparation budget. Each request is checked
against the retained boot-bound ticket; reconnect cannot renew it. The existing
4096 connection bound also covers source operations.

The controller forces an intent before begin, every chunk and finish, and submits
each once. The receiver claims each operation exclusively before reading/writing.
Lost responses permit only queries. An incomplete claim stays uncertain until the
original deadline, and corrupt or truncated chunks leave retained failure bytes.
Neither state permits a repeated mutation. Queries rehash retained chunks and
assembled parts before reporting completed transfer. Controller late responses,
changed inventories, package tampering and reboot fail closed.

All three transfers must complete before the first import; all imports precede
local seals; matching source/manifest/genesis identities precede any service
launch. Fresh provider/host/mount observations bracket each transfer in addition
to existing import, seal and launch boundaries. Failure returns to existing
retention, failed-attempt charging and exact-ID cleanup.

## Qualification and retained evidence

The existing owned-bootstrap CI gate now selects `--source-transfer`. It preserves
its 720-second outer guard, original 600-second preparation, independent native-UID
mount views, actual SSH package delivery, public bootstrap, three idle service
launches/stops and modeled provider cleanup. No additional job or timed workload
cell is added. It drops completed source begin/first-chunk/finish replies, requires
one write each, one absence precheck and three recovery queries, then removes the producer export paths
before any import. Existing lost import/seal/service replies remain exercised.

[The standalone source gate](../../../scripts/v51/guest_source_qualification.py)
uses real pinned loopback SSH, one authenticated package, actual published V4.4
source preparation and a public candidate bootstrap seal. It removes producer
paths before import and queries every lost completed source response. It requires
no privileged namespace. This shared-host, one-receiver evidence complements the
three independent-path owned gate; it does not replace that protected check.
Portable tests additionally force multiple chunks using incompressible bytes;
those synthetic bytes make no Java backup-validity claim.

Controller retention adds at most 69 files per member: descriptor, receipt,
begin/finish intents and up to 65 chunk intents, each bounded at 256 KiB (descriptor
64 KiB). Six fresh-check files cover transfer entry/exit. Unknown files and links
reject. The existing owned artifact includes receiver bytes, partial claims,
source exports, authority, cleanup and accounting records; private SSH keys stay
outside it. The standalone artifact records source and build binding separately.

```bash
python3 -m unittest scripts.v51.test_guest_source_transfer
python3 -m scripts.v51.guest_source_qualification target/v51-source-ssh \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)"
python3 -m scripts.v51.guest_owned_qualification target/v51-owned-bootstrap \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)" \
  --bootstrap --source-transfer --allow-sudo-namespace
```

`paidCloud=false`, `fullRemoteQualification=false` and
`engineWorkloadExecuted=false` remain mandatory. Bootstrap JVMs execute, but no
frozen timed window or fault cell is run here. Next connect producer command and
collection transport, then complete owned workload windows, faults and independent
physical history/backup/restore validation. Trusted preflight, separate V5.1 cloud
configuration/workflows and exact-request user approval remain later gates.
