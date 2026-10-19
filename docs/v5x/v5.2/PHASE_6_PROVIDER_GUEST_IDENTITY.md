# V5.2 Phase 6AS attempt access and fresh provider identity

This stage connects the [provider HTTP mapping](PHASE_6_PROVIDER_HTTP.md) to
attempt-bound SSH access and fresh observations for all three guest allocations.
It runs the actual request/response validation through the qualified offline HTTP
fixture. It generates/checks real local keys in tests, but opens no IAP tunnel,
contacts no provider and executes no guest workload.

## Public access is part of the original request

`cloud_access.py` validates one canonical Ed25519 public key, a closed V5.2 access
descriptor and the attempt-derived user. The descriptor contains no private key.
Local generation and private/public correspondence checks reuse the existing generic
V5.1 key helper; V5.1 provider or admission behavior is not invoked or changed.
Known-host files use a V5.2 alias derived from request, node and exact instance ID,
exclusive creation, private permissions and forced bytes.

`cloud_authority.with_access()` creates a version-two request before allocation.
Its exact digest includes the public access descriptor. Rebinding access on an
already bound request rejects. Version-one control fixtures remain readable and
cannot enter the new guest observation path. A native intent is still only data;
it cannot activate the offline provider.

Guest access varies by attempt. It deliberately does not change the shared
source/sequence/configuration/layout/policy identity, so all five whole members
can use distinct keys under the same frozen cohort. The ledger still rejects reused
attempt IDs. This is not permission to change a prepared request's key or splice
results across requests.

Instance creation now uses the bound public key in instance metadata, with project
keys blocked, OS Login disabled and guest attributes enabled. Validation checks the
exact metadata; no later unbound `setMetadata` action is added. This follows the
[instance SSH key metadata contract](https://docs.cloud.google.com/compute/docs/metadata/predefined-metadata-keys)
and [project-key blocking mechanism](https://docs.cloud.google.com/compute/docs/connect/restrict-ssh-keys).

## Bracket host-key discovery with complete resource observations

`cloud_identity.observe()` requires the complete original allocation claim, an
ACTIVE unexpired retained lease and its pending ledger reservation. Renewal may
change expiry/generation, but cannot change the stable allocation claim. A missing,
cleaning, expired or replaced owner rejects before accepting a guest observation.

For each node the adapter reads exact retained numeric IDs for the instance, boot
disk and data disk. It checks the complete provider ownership/configuration fields,
RUNNING/READY states, an RFC1918 IPv4 address and both sides of the two disk
attachments. The disks' users must identify exactly the intended instance.

It then requests only `hostkeys/` through the
[guest attributes endpoint](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances/getGuestAttributes),
validates the Ed25519 key, and repeats the complete three-resource sample plus
lease/charge checks under the original bounded observation deadline. Identity,
address, attachment or lease changes are fatal. Guest attributes can supply SSH
host keys when OS Login is disabled, as described in the
[guest attributes guide](https://docs.cloud.google.com/compute/docs/metadata/manage-guest-attributes).

An absent attributes response or missing key is `HostKeyPending` only after the
second complete resource sample succeeds. A permission error, malformed/duplicate
key, foreign namespace, malformed attribute row or vanished/replaced instance is
not a readiness retry. The attribute response, individual key/value fields and
canonical Ed25519 encoding are bounded before accepting a key. This module does not
retry an original command or extend its deadline.

The observation binds source/checkout, attempt, request/configuration/access and
stable resource claim hashes, exact instance/disk IDs, private address, node,
public host key and known-host bytes hash. It explicitly says `guestObserved=false`
and `paidCloud=false`; provider facts are not evidence of actual guest boot/user,
mounted data, loaded JARs or workload execution.

## Three-node result and remaining boundary

`observe_group()` executes three complete observations under the caller's original
deadline. It requires distinct instance IDs, private addresses and host public
keys, and derives the existing closed `owned-private-hosts` topology using the
configured replication port. These sequential samples are not an atomic snapshot
of three VMs. Fresh checks still precede actual receiver preparation and histories.

The measurement unit gate includes `test_cloud_identity`. Coverage includes local
key generation/pinning, per-attempt keys across all five ledger members, metadata
binding, renewal, both-sided attachments, replacements, expiry/fencing during key
lookup, missing versus invalid host keys, original deadlines and duplicate hosts.
Results and exact executed source hashes are retained in
`target/v52-cloud-identity/`. No earlier engine history is rebound to this source.

Final validation: **639 V5.2 Python tests pass in 229.369 seconds**, including
**26 new access/provider-identity tests**. The earlier combined control/HTTP/identity
run passed all 100 cases before the final host-key rejection regression was added.
All **30 CI classification tests pass in 43.169 seconds**. Documentation contract,
changed links/fences, Python AST, shell syntax and whitespace checks pass. The full
suite uses the actual local UID; installer permissions/ownership guards are unchanged.

The new foreign/malformed host-key regression first failed because those rows were
misclassified as pending, then passed after the strict entry check. Its before/after
logs and original implementation remain retained. A separate intermediate test log
retains one diagnostic mismatch: the earlier key-length guard now rejects before
the decoder; the final assertion still requires fatal Ed25519 rejection rather than
pending readiness. No Maven or full engine-history/cloud workload was rerun, and
printed synthetic unit fixture PASS records are not cloud qualification.

Still required: dedicated native credentials/admission, owned IAP transport and
credential epochs, actual guest boot/user and mounted data identity, installed
helper delivery, complete owned members and independent five-member aggregation,
then protected exact-master/full-CI and operator cloud entry. This stage does not
change V5.1 defaults, the 33 whole histories, source/sequence rules, or soft time
and cost policies.
