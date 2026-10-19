# V5.2 Phase 6AP bound receiver execution

The [host/process domains](PHASE_6_HOST_PROCESS_DOMAINS.md) now connect to receiver
placement, package delivery, service preparation, retained restart, partition
control and portable evidence validation. The private-host backend retains the
existing whole-history controllers; it does not copy or reschedule their work.
There is no paid entry point or provider allocation in this stage.

## Placement and source

`remote_bound_receivers.Placement` accepts three externally owned pinned SSH
routes, receiver roots, expected host domains and installed Python receipts. It
requires the full source/checkout/Java identity and exact descriptor/payload bytes.
It checks each retained route against its actual owned credential file and each
installation against the expected host boot/user. Its receiver factory chooses
the existing UNTIMED, M01–M03 or M04 class for all 33 frozen names.

The base controller now exposes placement hooks. Local mode still reserves its
three loopback ports and uses its original roots. Bound mode supplies the explicit
private peer topology and guest roots without allocating controller-local peer
ports or writing to guest paths locally. Only its collected output and original
source staging are local. One Placement can be consumed by one original history;
a preparation failure does not permit a second history or retry on those paths.
Every later history needs fresh roots on the same independently owned resources.

Inputs are copied before use. Preparation rechecks the pinned route, and the
delivery endpoint compares its captured host-key bytes to the expected pin before
the first guest exchange. Changing a file after selecting a route cannot silently
retarget bootstrap. Installed source is mandatory in bound mode; a controller
checkout fallback rejects before transport creation.

## Complete guest/evidence chain

Closed local/bound execution markers are selected from the expected host domain,
not from a truthy flag or arbitrary string. Receiver capsules carry the exact
domain map beside the original immutable JAR/helper/backup inputs. Bootstrap
descriptors, installed-source records and live guest checks agree on the receiver
boot/user, source, topology and path. The guest verifies that chain before launch.

The same scope selection reaches the original service launch claim, terminal
observation, bounded archive export, SIGKILL/retained generation 2, partition ACK
barriers and their retained validators. Exact M01–M04 profiles, original outcomes,
finite decoder/resource limits, local clock order and independent physical/query
replay remain mandatory. No public operation or workload retry is added.

`remote_identity.location` now accepts private placement only with explicit host
domains, matching pinned routes, installed Python, delivered receiver inputs and
voter lifecycle evidence. Each component is independently validated before the
physical inspector consumes the collected authority. Bare private addresses,
mixed scope markers, missing components, mismatched sources or host substitution
still reject. The direct local launcher cannot interpret bound guest paths as
local filesystem paths.

## Validation and remaining authority

The new unit regressions exercise all 33 controller selections, same immutable
inputs, source/history identity, single consumption, host and key substitution,
source-context requirements and rejection before guest side effects. Existing
local-mode regressions remain required. One old test initially expected the later
local-topology rejection; its unbound private input now fails earlier for missing
host domains. The updated test separately retains malformed-profile rejection.
Original failure logs are retained under `target/v52-remote-python/bound-backend-*`.

All 538 V5.2 Python tests and 21 CI-related tests pass, including 14 new bound-host
regressions. The installed-helper entry also passes its 88 unit tests. The real
four-history SSH gate then passes on implementation commit
`2649555919b50f0a73330d30d2d5bff661c95617`, checkout hash
`d32938e08560b84e1c05242c73c61ce14273094cdb603456b7786e2b2554b946`:

| Complete history | Seconds | Original reads / updates | Stopped service/JVM pairs |
| --- | ---: | ---: | ---: |
| candidate-minimum-untimed-smoke | 144.814 | 11 / 3 | 3 |
| m03-p4 | 110.291 | 5 / 4 | 3 |
| leader-sigkill-retained-restart | 144.717 | 4 / 4 | 4 |
| follower-snapshot-carried-token | 145.976 | 4 / 4 | 3 |

Total wall time is 546.553 seconds. All 24 original reads, 15 updates and 338
evidence mutation rejections pass, including original and relocated validation;
all 13 service/JVM pairs stop. This run uses installed isolated Python inputs and
local pinned SSH. It does not establish independent-host or full cloud acceptance.
No failed workload was rerun to obtain this result.

The original receipt is retained at
`target/v52-installed-histories/run.8wHsmE/evidence/receipt.json`, SHA-256
`7913335a5ca29ed1f6d2fe9a713e25a61c35f3040cd6be81246c31d382747302`.
The source index, test logs and result summary are under
`target/v52-remote-python/bound-backend-*`. The later documentation commit does
not replace the execution source. Earlier Phase 6AN and Phase 6AK receipts also
remain bound to their own source and scope. Protected exact-source CI and actual
independent-host qualification remain pending.

The caller must still independently admit and retain provider/lease authority,
prepare the exact three instances and mounted storage, own and recheck the SSH/IAP
routes for the whole history, and handle cleanup/retention. This backend creates
no tunnel, VM, disk or firewall and grants no paid admission. All component/local
receipts keep `qualifiedMeasurement=false`, `fullRemoteQualification=false` and
`paidCloud=false`. Whole owned-member/aggregate orchestration and a dedicated
exact-master/full-CI plus fresh-provider entry remain required before the user
merges and manually triggers cloud experiments.
