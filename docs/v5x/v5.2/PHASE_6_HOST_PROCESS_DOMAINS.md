# V5.2 Phase 6AO host and process domains

Independent machines may assign the same numeric PID, and a retained restart may
reuse an earlier PID. The prior local gate required globally distinct numbers.
Replay now has an explicit host-domain input; absence retains the original local
rules. This is validation groundwork, not independent-host execution acceptance.

## Expected identity and clock boundaries

`remoteHostDomains` binds the exact source/checkout, attempt and lease digest to
three distinct resource identities, RFC1918 addresses, boot IDs, users and SSH
host-key pins. Its closed shape rejects missing or additional fields, local-mode
promotion, changed source, duplicate resource/boot/key identities and malformed
values. The retained pinned SSH routes must match these expected keys. These
hashes are supplied by a future independently admitted owner; collected JSON
does not establish provider ownership or create permission to access a host.

Each stopped JVM maps `(node, generation)` to its expected resource, boot, PID and
process start ticks. Service and JVM owners remain different. A controller may
have the same PID as a guest on another boot. A retained generation-2 process must
remain on the same resource/boot with later start ticks; missing generations,
foreign owners and reused process identities reject. UNTIMED and all M01–M04
entry points pass the same map to history/read validation.

The shared V5.1 physical inspector has an explicit `process_generations` option.
All legacy callers keep its original default. The opted-in V5.2 path distinguishes
process order by node/PID/generation, while preserving transferred basis, durable
force, ACK, proof, publication and application checks. A generation is not a new
authority source; the caller must first validate the expected host/process map.

Controller observations, guest Python events and guest JVM traces keep their own
monotonic domains. Original message IDs and response records connect them. No
controller-minus-guest or cross-host timestamp subtraction is introduced. Tests
shift each JVM and the controller independently while preserving local ordering;
a local observation-order regression still rejects.

Installed Python roots are unique within the bound resource/boot domain. Separate
hosts may use the same absolute path. The receiver boot/user must match the
expected domain, the descriptor/source bytes and runtime records must still match,
and local mode continues to reject duplicate paths. A Python source capsule does
not supply provider or SSH ownership authority.

## Validation and retained evidence

All 524 V5.2 Python tests and 59 affected V5.1 inspector/fault tests pass. The
69-test domain/voter/source subset passes independently. All four unchanged
Phase 6AN histories pass current validators at both original and relocated
locations, matching their earlier results exactly. This reuses retained published
oracle answers and does not rerun the workload or the oracle JVM. The source of
those histories remains `366990a004d6ca2d1989f539f59568d7ebd5974e`.

Synthetic tests cover equal cross-host PIDs, retained PID reuse, source/lease/map
drift, boot/user/key substitution, controller separation, missing proofs, local
trace order and unchanged local admission. The same-path test fails on the
previous validator and passes only after explicit host scoping. The prior voter
validator rejects the new independently bound PID fixture as expected.

The real retained Phase 6AN restart is also replayed with every trace PID changed
to 42 **in memory**. The original inspector rejects the lost distinction; the
generation-aware inspector reconstructs the same four processes, eight chosen
entries/publications and four successes. Collapsing generation 2, inventing
generation 3 or removing proof forces still rejects. Wire and authority bytes
remain unchanged. This diagnostic is synthetic process renumbering of real
authority, not execution on three hosts and not a new workload run.

The logs, exact source/file index and validation summary are retained under
`target/v52-remote-python/host-domains-*`. The initial sandbox test attempt is
retained: its mapped root and `/tmp` UID 65534 trips the existing installer's
ancestor-ownership check. Validation uses the actual local ownership environment;
the installer check is not weakened. No production Java, POM, workflow, frozen
window, business retry or resource limit changes in this stage.

## Next integration boundary

`remote_identity.location`, live voter admission and receiver delivery still
reject private-host execution. The new bound-host voter-message checker is only
a component validator; its receipt keeps `fullRemoteQualification=false` and
`paidCloud=false`. No synthetic result is promoted to a complete remote member.

Next, connect independently observed provider/lease/instance and pinned tunnel
ownership to topology, preparation and installed-helper routes. Carry that same
binding through bootstrap, lifecycle/export, faults and complete physical/query
replay before enabling the private-host entry. Then qualify whole owned members
and their aggregate, and connect protected exact-master full CI and fresh cloud
admission. Continuous histories, original frozen counts and one source/sequence
remain indivisible. Paid runs still require the operator's later master merge
and manual trigger.
