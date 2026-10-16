# V5.2 Phase 6AM installed Python runtime over SSH

The [bounded Python package](PHASE_6_REMOTE_PYTHON.md) now has an explicit trusted
launch path. Every new isolated receiver gets the same source-bound capsule in a
separate private directory over pinned SSH. The original controller retains its
Git/checkout checks. Receivers and detached child workers verify the externally
supplied descriptor pin, complete installed inventory, current Java identity and
explicit receiver binding before work. A manifest found on disk grants no launch
authority, and an installed directory nested under a repository cannot silently
use that ancestor's Git identity.

## Transport and startup

The Python payload is larger than the existing 1 MiB V5.1 control envelope. A
separate bounded stream sends at most the capsule request limit in 64 KiB pieces,
with one original absolute deadline and one terminal response of at most 8 KiB.
The old envelope limit and ordinary business send limits stay unchanged. A lost
installation response can reconnect only to verify the original installation;
it cannot submit installation again. Partial destinations remain consumed.

Trusted bootstrap runs with `python -I -S`. It validates the installation before
any payload import, enables no bytecode writes and admits only the fixed delivery,
voter, relay and partition entry functions. Retained restart still belongs to the
original voter owner and does not gain an arbitrary-command entry. Detached
bootstrap and voter children receive the same explicit pin and isolated root.
Loaded repository modules must belong to that exact source inventory.

## Retained evidence

The complete Python payload and descriptor join the portable evidence. Each node
has a distinct installation receipt and parent-directory identity. Bootstrap and
voter records bind the executed entry, installed root, source, isolation flags
and original process PID to the existing process/boot/launch chain. Original and
relocated replay recheck these records and every Python payload member against
the external binding. Missing whole-node runtime records cannot count as an empty
success. Only a declared retained restart may have a second control generation.

Nine mutations at both retained locations reject missing payloads/records,
altered Python bytes/source, substituted process identity, fallback paths, enabled
site packages and the wrong bootstrap entry. The existing lifecycle, delivery,
physical/query/read and history negative checks remain in place.

## Ordinary smoke coverage correction

The first complete installed-helper history (`run.dTIsjk`) executes all original
calls and stops all owners, but its physical replay rejects the legacy six-frame
basis threshold. Its unchanged retained authority has three successful updates,
five publications and four DATA observations for the one complete selected pair.
This is the same ordinary-election boundary already corrected for M01–M03.
The smoke entry now explicitly requires `selected-quorums`; the historical V5.1
fault matrix retains its extra-traffic coverage requirement. Selection reconstruction,
chunk continuity/digests, proof quorums, publication and all public calls still
validate. A regression fails before the correction and passes afterward.

## Local qualification

```bash
scripts/verify-v52-phase6-remote-python.sh --skip-build
```

This gate performs one complete declared minimum-policy untimed smoke history.
It installs all three Python receivers over real loopback SSH, discards one
installation reply, and retains the existing lost-upload/bootstrap/voter-launch
and original-update-response cases. Reconnection queries the original work;
no business operation, JVM or bootstrap is replayed. Minute heartbeats cover
preparation, original workload and independent replay. The original services,
JVMs, SSH channels, private daemon and sockets must all terminate cleanly.

Thirteen launch/transport tests and eight retained-evidence tests join the
thirteen existing package tests and the three smoke-evidence tests in this explicit gate and the lightweight CI test
list. The complete source-bound local gate passes in 159.016 seconds, with 11
original reads, three updates, 48 ordinary evidence negatives, 18 Python-source
negatives, 14 delivery negatives and 14 lifecycle negatives. All three services,
JVMs and channels stop; one lost installation reply queries the original result.
The capsule has 162 files, 1,616,096 expanded bytes and 2,161,770 encoded bytes.
All 498 V5.2 Python tests pass.

To preserve the concurrent formal gate's immutable worktree, this validation runs
in a separate local source snapshot (`abad8d13d4f825c5bf062e7f6afdfa7d0cd24779`,
checkout `fca233d1a53b1ead2dbe20c68fb531caa6bac7d63dff924c136686f87ab92fa8`).
Its complete code hash index and receipt summary remain at
`target/v52-remote-python/installed-runtime-executed-files.json` and
`target/v52-remote-python/installed-runtime-validation-summary.json`.
The immutable run is under the sibling `qualification-checkout` evidence tree,
`target/v52-remote-python/run.96nHVl/evidence/receipt.json`.
The snapshot is not an upstream commit or protected CI result. Applying its exact
code back to the development worktree does not rewrite the recorded source.

The original failed `run.dTIsjk` remains intact. Replaying that same unchanged
history after the smoke-coverage correction passes both locations and all 24
negatives per location. Removing either transferred selected basis still rejects
with `selection lacks transferred basis`; no business workload was rerun for this
separate retained-evidence diagnostic.

`sharedPythonCheckout=false` describes the helper deployment for this gate.
`independentHosts=false`, `qualifiedMeasurement=false`, `fullRemoteQualification=false`
and `paidCloud=false` remain explicit. The three receivers still share one Linux
host and its clock domain. Complete formal/fault histories over installed helpers,
independent-host causal validation, owned members and provider admission remain
before cloud entry. This stage starts no hosted workflow or paid experiment.
