# V5.1 Phase 6C3C20 — owned experiment fault cells

**Status:** accepted through PR #251, master
`49845530b0dd42db5b721219e92d36d8ced005a2`, exact-master CI
`36551903980` attempt 1. Its native-UID qualification passed.

## Scope

Execute leader-loss and no-quorum through the existing owned Runner, one modeled
reservation/lease/topology, three authenticated SSH package installations and six
persistent guest services. Each cell has a fresh deterministic group identity and
an EMPTY two-field public bootstrap on every receiver. Each guest keeps only its
assigned authority live. Prepared sibling outputs remain unstarted diagnostics;
no filesystem-bound seals or replica authority are copied between guests.
The existing rich healthy service configuration is unchanged. Fault configurations
add one closed `faultCell` field; only these two automatic cells are admitted.

The [frozen experiment](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md) has four cells:
healthy (all three modes), leader-loss, maintenance and no-quorum. This gate
qualifies the two specified fault cells separately from the accepted healthy gate.
The subsequent [C21 candidate](PHASE_6_OWNED_EXPERIMENT.md) adds maintenance and
the four-cell assembly; corrected-source protected qualification remains open. Neither this
receipt nor the earlier healthy receipt claims a complete experiment, full remote
qualification, real block devices, native IAP or paid admission.

## Original commands and budgets

All prepare/start/call/kill/restart/isolate/heal/stop/collect requests pass through
the existing persistent command store. A lost submission reply queries the same
command ID and cannot replay a mutation. Original public intent IDs are consumed
before dispatch; an uncertain intent cannot be resubmitted under another command.
Only the frozen read/status/two-document ADD_ALL vocabulary is accepted. No
request provides arbitrary programs, paths, network rules or durations.

Each cell keeps the original 120-second wall-clock limit, including startup,
control, injection, public calls, retained restart and close. Progress and rejoin
keep the nested sixty-second ceilings. There are three seed bulks, one seed read,
at most four fresh progress pairs and four final reads within the 24-call cap.
Every attempted branch and conservative outcome remains in the original history.
Storage/integrity/unknown failures cannot count as transient availability.

Leader-loss SIGKILLs the voter identified by the successful seed read, confirms its
exit, archives its exact stopped authority, observes surviving-majority progress,
then reopens that same authority as generation two and observes durable rejoin.
An uncertain or failed stop is not resubmitted. The remaining voters are closed
within the cell budget even after another operation fails.

No-quorum installs the closed all-direction drop rules on all three guests. The
controller starts its independent fifteen-second release timer only after all
original installation replies are observed. Read/write refusal must complete
inside that common interval. Each guest also has a seventeen-second emergency
release; triggering it fails qualification. Original guest timestamps must show
15–17 seconds of actual isolation, all three traces must contain real drops,
and no guest clock is ordered against another guest's clock. Control/SSH delays
remain charged; delayed installation or release cannot silently extend a passing
fault. Healing is attempted independently of a blocked public call.

## Independent portable evidence

Retain the original package manifest, command store, controller observation
intervals, every JVM generation/exit/exchange, full force/wire/resource traces,
crash archive and final stopped authority in bounded binary parts. Replay all
six downloads in fresh scratch directories. Recheck original receipt equality,
source/build/group/topology, loaded JAR hashes, frozen settings, local process
lifetimes, complete public-call coverage and combined evidence budgets.

The existing two-field history checker and physical vote/proof/publication/read
checker run independently of the controller's status. Inspections use the actual
retained bytes and each receiver's original sealed path. Process identity is
(node, PID); separate guests may legitimately allocate the same numeric PID.
Evidence-negative cases remove the crash/isolation witness, rejoin/refusal,
progress deadline, final read contents, proof force and read invocation. The
unmodified evidence must pass before any rejection can count.

## Qualification

The required guest services/faults lane (foundation/runtime in accepted PR #251) runs:

```bash
python3 -m scripts.v51.guest_owned_qualification target/v51-owned-faults \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)" \
  --faults --allow-sudo-namespace
```

It uses native-UID independent mount views and actual loopback SSH, discards every
original workload submission reply, and checks unique submission IDs, three
package installations, six service exits, exact-ID cleanup and one retained budget
reservation. `--fault-local` instead exercises actual SSH/JVMs in separate local
paths without namespace privileges; that diagnostic makes no independent-mount
claim. Unit fixtures do not substitute for hosted native-UID qualification.

The 1440-second outer CI backstop does not alter internal stage/cell limits.
The always-uploaded artifact is `v51-owned-faults-${sha}`. Existing healthy and
local twelve-fault gates remain required. Production Java, POMs, paid workflows
and frozen measurement parameters are unchanged. Cloud execution remains an
operator action after separate exact-request authorization.
