# Certified operations and learner admission

**Status:** integrated research candidate for D02–D05. No production enablement.
Parent `ee38852`; Phase 0 remains open while steady-state policy, bounded compacted
metadata, exact formats and the final contract/acceptance register are completed.

## What is now connected

`integrated_model.Group` wraps the existing global-promise activation adapter.
It uses actual research PREPARE, frozen bases, immutable selected sources,
installation ACKs, ACCEPT/PROOF forces, certificates and local prefix publication.
Each replica also has its own committed operation catalog, advanced only after
that replica has forced the corresponding certified prefix. A status sample or
another replica's catalog does not authorize a vote.

The transition entry catalog adds `CONTROL`, a stable-authority entry whose
payload commits the full canonical command digest. Complete descriptor bytes
remain required for validation. CONTROL may contain RESERVE, PREPARE, READY,
SEAL, CANCEL or RETIRE. It cannot disguise INTENT/FINAL, DATA or BARRIER, which
have their own transition/application semantics. Ordinary control records consume
log positions without advancing application sequence. An activation BARRIER also
advances the catalog position, preserving exact preparation/index binding.

Before accepting/proving a selected command, each voter validates it against its
own applied catalog. This checks the active request, revision, forced readiness,
exact sealed binding, cancellation boundary and resource rules. Recovery may select
a different command from the caller's proposal; the selected command is applied.
A requested CANCEL cannot overwrite a chosen SEAL just because SEAL's client ACK
was lost. Duplicate/new requests are interpreted against the recovered catalog.

## Learner image, catalog and voting order

1. Old voters certify RESERVE and PREPARE. The joining identity is still absent
   from all voting quorums; its request/descriptor is durably reserved.
2. Force an abstract learner image bound to that request, preparation revision,
   data index/digest, source cut and durable identity. This is an atomic model
   image event; the earlier admission model separately exercises staged image and
   receipt forces. Actual application byte validation remains a storage gate.
3. Verify and install the source authority/catalog on the learner, including the
   certificate-derived global promise floor. Force the bound readiness receipt
   only after the installed catalog agrees with the image.
4. Old voters certify READY and SEAL. DATA progress before SEAL requires another
   PREPARE revision and image receipt under the same client request. After SEAL,
   new DATA cannot interleave before FINAL.
5. Old voters certify INTENT. The learner is eligible only after it forces that
   exact INTENT and applies the matching catalog, with the retained image receipt.
   A PREPARE/vote before that boundary fails even if transfer completed earlier.
6. FINAL uses both old/new majorities. New-stable activation requires a fresh
   current-ballot barrier. A removed proposer cannot start that new-stable round.

Replica crashes preserve forced images/catalogs/promises, lose volatile pending
work and READY, and recover accepted-only or proven-but-unpublished controls through
fresh ballots. This model does not confuse process restart with a new disk identity.
There is no same-identity disk-loss replacement or endpoint recycling.

## Joint quorum containing a removed proposer

The proposer must contribute its own frozen basis. In a 5→4 removal, every globally
minimal joint quorum can consist of three surviving members and omit the removed
proposer. Filtering those quorums for proposer inclusion incorrectly finds none.

The correct construction is: form each valid old/new quorum, **include the proposer**,
then minimize under that inclusion constraint. For the removed proposer in 5→4,
four selected sources are valid: itself plus three surviving voters. All four must
complete selected installation; both ACCEPT and PROOF still satisfy both majorities.
Do not drop the local basis requirement or switch the selected set mid-ballot.

The first integrated test exposed this issue in the schedule helper. It is fixed
and has a dedicated regression. The 3–5 voter/peak-six identity resource contract
must size the selected set for this case rather than assume its globally minimal size.

## Independent checks and matrix

`integrated_oracle` first checks the complete global-promise and transition traces,
then independently joins them to command descriptors, per-node catalog application,
image/receipt forces and learner eligibility. It uses the separate operation
reference reducer, never live Group state. It checks control type confusion,
catalog apply before prefix force, a future/missing receipt and unknown descriptors.
Earlier protocol oracles still check durable voting quorums and selected recovery.

The declared matrix is seven add/remove/replace size profiles × SEAL/INTENT/FINAL
× six cuts = **126 cases**. Cuts are prepared, one ACCEPT, all selected ACCEPTs,
one PROOF, complete certificate before publication, and forced local prefix before
catalog/publication. Every case restarts all six model processes and uses fresh
recovery plus explicit source synchronization to complete FINAL and new activation.

Twenty-one representative histories retain the publication cut for every
profile/target and replay after gzip/JSON serialization. All 126 complete traces
contribute to the trace digest. The checker verifies actual force/certificate/cut
observations against their labels. Partial matrices are INCOMPLETE, not PASS.
Targeted tests additionally select a new learner as proposer after INTENT, recover
SEAL against a competing CANCEL request, preserve one client request across DATA
progress/repreparation, fence a pending control force and reject missing evidence.

```bash
python3 -m unittest scripts.v53.test_integrated_model
python3 -m scripts.v53.integrated_research \
  --output "target/v53-integrated-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

See [source-bound receipt](integrated-research.json). These schedules deliberately
use a fresh recovery ballot per command to expose recovery selection. They do not
choose or benchmark the steady-state client round policy. They also retain the
full finite prefix, so they do not qualify compacted-source operation metadata,
autonomous failure detection, real disk/wire behavior, public Java or cloud results.
Those distinctions remain explicit in the [closure worklist](PHASE_0_CLOSURE_PLAN.md).
