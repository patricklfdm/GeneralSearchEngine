# Retaining matching INTENT under a prepared learner owner

Phase 3 remains **OPEN**. This component retains a complete certified INTENT
source under the learner's existing typed owner. It supplies durable input for
subsequent voter installation; it does not create a voter journal, ballot,
selected voting generation, public runtime or deletion permission.

`MembershipLearnerProgress.retainIntent` consumes the same bounded progress
transfer that fetched the original complete source. It accepts only the live
prepared/current head and the original receiving owner/resource pool. A decoded
packet, a transport ACK or a caller-supplied voter set cannot enter this storage
transaction. The existing source verifier supplies historical provenance.

Before writing, validate:

- Exact original root, request, permanent learner identity, prepared endpoint
  ancestry and current source voter identity.
- The actual forced typed LEARNER receipt, including its image and preparation
  revision, against the retained operation descriptor. A certified later revision
  cannot admit an older local receipt.
- JOINT or COMPLETED operation state and the exact corresponding target view.
  A later unrelated membership generation cannot reopen the old operation as a
  fresh joining authority. PREPARING, READY, SEALED and CANCELLED are insufficient.
- The original INTENT certificate, entry, payload and membership checkpoint
  edge, including the sealed descriptor and prepared application image.

The existing CANCEL transaction is factored into `MembershipLearnerDisposition`.
CANCEL keeps its exact existing schema, paths and fault cut names. INTENT uses
`.gse-v53-learner-intent-<plan digest>/intent.json` and `source/`, with private
schema `gse-v53-learner-intent/1.3`; its plan additionally binds the exact typed
receipt digest. Public wire/record formats and frozen resource ceilings stay
unchanged. Each plan remains within 64 KiB and the existing metadata budget.

The transaction forces the candidate plan, atomically activates it, atomically
moves the original receiving directory, forces all retained source files and
parent directories, then returns. It retains the existing one LEARNER receiving
slot and original image reservations; it does not allocate another voting
generation. CANCEL and INTENT are mutually exclusive dispositions for this
learner owner. Their paths block old refresh/progress handles, new preparation
and successor selection even after the transaction owner has closed.

A private `Forced` capability is available only after this transaction finishes.
It revalidates its live typed owner, original inode/inventory bindings and complete
source on use. Closing either owner revokes it. Its verified capsule is data for
the future installation path, not standalone voting authority. That path must
continue to require the live capability through its own force boundary.

Cold recovery uses the original plan, receiving/source files, typed receipt and
prepared/current selection. A complete candidate plan may be resealed and its
original move completed; a missing/torn plan remains refused without writes.
Missing typed receipt, prepared marker or backup cannot be reconstructed to make
the INTENT appear admissible. Corruption, copied inodes, foreign files, a changed
receipt or another terminal disposition also refuse before recovery writes.
Closing releases reservations without deleting retained proof or application data.

`V53LearnerIntentTest` exercises real typed backups, TCP transfer, local file
forces and cold reopening. Its historical checkpoint voters are conditional
fixtures. It covers the five joining shapes at JOINT and COMPLETED, promoted
heads, stale handles, capacity and corruption, a valid later preparation revision,
and thirteen injected IOException cuts. These are component checks, not actual
SIGKILL or native joint-vote qualification. Existing cancellation assertions
guard the extracted transaction's original behavior.

The first execution retained two failures: a promoted CANCEL exceeded its
60-second receive clock during local validation, and the conditional completed
REPLACE fixture still offered the departed node-3 as a source. The fixture now
derives source voters from its actual verified view. Storage-transition tests use
an injected clock; explicit expiry before retention and during a member force
must still refuse INTENT and release the receiving slot. Their wall-clock duration
does not establish timely completion under a real deadline. The injected clock
is anchored to `System.nanoTime()` because the real TCP transport takes absolute
monotonic deadlines; the first zero-origin clock was rejected before exchange,
and that failed run is also retained. Actual transport
timeouts and production budgets remain unchanged. The extracted attachment also
reuses its just-checked immutable plan instead of recursively checking the same
store again. This removes redundant work, without claiming to solve the observed
wall-clock cost or qualifying a failover SLA.

The [component receipt](phase3-evidence/learner-intent.json) records 21 distinct
passing Java cases against identical production bytes across the final three
snapshots: nine progress cases, ten INTENT cases and two targeted CANCEL recovery
cases. Fourteen lightweight Python contract/evidence checks also pass. All failed
attempts are retained. The last isolated rerun corrects only the corruption test's
attempt to mutate a decoded immutable map; it copies that map before replacing
the receipt. It does not change the production check or rerun a measurement.
These results do not claim that the full Phase 3 gate has executed.

Remaining work includes actual voter ownership handoff and recovery, native
old-majority INTENT delivery before the joining node can participate in joint
checkpointing, joint FINAL and fresh-barrier service, and complete independent
physical/history replay. A complete published source alone must not become an
extra quorum prerequisite for the general joining protocol. The complete native
history must exercise the minimum required majorities as well as healthy peers.
Keep each source/lease/history together when moving the longer acceptance runs
to hosted measurements. See the [deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md).
