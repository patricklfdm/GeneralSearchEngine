# Phase 3 — profile-bound network and durable acknowledgements

`scripts.v53.joining_profile_network_evidence` composes original physical
continuation with the attempted-transport and durable-ACK reader for all five
explicit ADD/REPLACE profiles. It accepts a complete indivisible history, never
a set of fragments from different executions. Its overall result is **PARTIAL**.

The reader first derives bootstrap, placement, custody retirement,
initialization, selected FINAL/BARRIER continuation, supported final adoption
and retaining cold snapshots. Only then does it check the original network.
The joining identity comes from the profile (`node-4`, `node-5` or `node-6`);
that identity determines the required owner scope and installed snapshot path.
It is not supplied by a receipt label. Permanent identities and both governing
majorities retain their preceding independent checks.

The shared network gate consumes actual sends, received requests, responses,
deliveries and qualified terminal failures. It binds complete transfer sessions,
captured grants, delivered PROMISEs, selected installation forces, INSTALL_ACKs,
slot phases and future-retention/publication ordering. Failed controls remain
separate from ACK rows and contribute their own attempt counts. Missing
terminal observations still fail; this reader cannot repair an old trace.

The two qualification flags describe the observed transcript and its bound
durable acknowledgements only. They do not prove that every control export was
authorized at its precise use time, that all maintenance/peer-ledger writes have
been derived, or that process-death recovery is qualified. The corresponding
flags and `phase3Complete` remain false. Same-view final recovery remains rejected
until its unequal-source preparation, maintenance and installation are fully
derived; an adoption-only history cannot substitute for it.

## Execution and replay

```bash
python3 -u -B -m scripts.v53.joining_profile_run /new/output/3-REPLACE \
  --profile 3-REPLACE --complete
python3 -B -m scripts.v53.joining_profile_network_evidence /original/raw \
  --profile 3-REPLACE --qualify
```

The producer creates a fresh source copy, retains source/build/toolchain
manifests, reports progress each minute, and performs no native retry. Its
semantic receipt does not replace physical/network replay. For later deferred
parallel execution, use the first producer's immutable `--source-from` for every
other whole profile. Do not divide a profile's lease, source or history across
jobs. The two REMOVE profiles require their separate implementation and gates;
they are not accepted as joining profiles.

Negative qualification runs the untouched full precondition first. Disposable
mutations change only `events.json` and `wire.json`; every other member and all
directories must remain unchanged before reusing the storage derivation. The
network reader must then reject each mutation for its exact designated reason.
Twenty-two common negatives cover causal pairing, original grants, selected
installation and transfer integrity. Six additional terminal mutations run only
when the original actually contains a paired caller/receiver failure. They are
not synthesized for a healthy transcript. The original inventory is rechecked
after all mutations, and each completed negative reports progress.

## Callback preservation

The first new 3-REPLACE execution completed FINAL and retaining cold recovery,
but failed the independent network gate: five outgoing control failures had
received-request observations and no receiver terminal. The continuation
endpoint's diagnostic lambda forwarded `Events.at` and silently used the
default no-op `Events.failed`. Its diagnostic error strings cannot replace
the missing original callback observations. That history remains rejected.

The collector now composes both methods when adding diagnostics, preserving
the collector-before-diagnostics order. The learner head and pending-checkpoint
listeners also forward `failed` through their existing lifecycle wrappers.
Their before-response lifetime checks remain in place. These changes preserve
observations; they do not manufacture replies, change voting or publication,
extend deadlines, or retry a history. Dedicated real TCP tests require the
rejected original request and its receiver classification to reach the observer.

Corrected-source evidence must come from a fresh complete execution. Both the
failed original and the corrected history retain their separate source/build
manifests; replay cannot stitch them together. A relocated copy of the failed
original must still fail for the same missing receiver terminal.

## Evidence and remaining acceptance

The [batch receipt](phase3-evidence/joining-profile-network.json) records actual
executions, immutable producer inputs, independent reader hashes, original-first
rejections and portable replay. Conditional tests cover all five profile
identities; they do not claim five native executions. The larger-profile identity
regressions fail with the previous hardcoded installer and pass with the
profile-bound implementation.

The corrected complete 3-REPLACE execution took 682.607 seconds and passed its
nine semantic evidence negatives. It retained five caller and five receiver
terminal observations, compared with five caller and zero receiver observations
in the failed original. Eighteen focused Java tests cover collector composition,
actual transport failures, both learner listeners and their existing lifetime
checks; 430 joining Python tests include sixteen profile-network tests. The new
checkpoint test initially captured its storage baseline before listener startup
forced the legitimate original ACK. That test baseline was corrected and the
affected test rerun; the initial failing report remains retained.
The corrected original also passes all 28 exact network evidence rejections
(22 common and six terminal mutations). The six short TCP scenarios separately
pass thirteen negative mutations. The retained older 3-ADD source-loss history
continues to pass the profile-bound original reader without a native rerun.
The compressed archive retains both complete originals, their source/build
manifests, the independent reader, short TCP originals and test diagnostics.
All 22,799 archived file hashes match after extraction to a different directory.
With Python assertions disabled, the corrected original still passes and the
failed original still rejects for its missing receiver terminal.

Complete current-source profile/cohort qualification, same-view recovery,
control-export authority, maintenance/peer composition, whole-history fault and
process cuts, REMOVE profiles and frozen acceptance mapping remain open.
No workflow dispatch, push or paid cloud experiment is part of this batch.
