# Native joining slot forces and delivered acknowledgements

The [complete original joining history](PHASE_3_JOINING_CATALOG_REPLAY.md) now
has an additional independent reader, `scripts.v53.joining_phase_evidence`.
It starts by validating the complete semantic chain, then uses the same original
files and global event order. Producer PASS fields do not provide authority.
The [batch receipt](phase3-evidence/joining-phases.json) binds the producer,
reader, tests and retained replay inputs separately.

## Qualified boundary

The reader covers all eleven slots, including the manual SEAL/INTENT and the
joining node's actual joint FINAL and new-view BARRIER:

- Derive each node's participation from the original ACCEPT/PROOF certificate.
  Require the complete ordered successful vote, certificate, application and
  publication callbacks for each of the 24 owned slot transactions. The new
  voter's callbacks must come from its continuation owner lifetime.
- Require four application metadata file forces and the original applied end's
  parent/ancestor statement and ACK forces. Publication also needs the new
  generation, selector and directory forces before the published selector.
- Bind every retained response to exactly one original response callback, using
  permanent endpoint/storage identity, root and correlation fields. A delivery
  consumes one earlier actual response; duplicate or invented deliveries fail.
  All 2,211 retained responses are accounted for; 2,208 have a matching delivery.
  Undelivered responses are not usable acknowledgements.
- Match all 71 ACCEPT, PROOF, APPLY, future-retention and PUBLISH responses to
  original record/receipt bytes. Every required remote acknowledgement follows
  the corresponding force/return and arrives before the dependent local stage.
  Identical attempts stay bounded; an unrelated acknowledgement cannot substitute.
- Reconstruct future-retention proof bytes for all 13 publication targets from
  actual applied ends, original selected records and phased certificates. Check
  the resulting revision/hash acknowledgements, the file/parent force sequence,
  and the exact empty ledger after publication. Every observed PUBLISH send must
  follow the actual recording forces and delivered acknowledgements for all
  targets in that slot.

Seventeen original-first mutations remove required file/directory forces, move
an ACK or publication before its dependency, duplicate a delivery, drop an
original wire row/event, change the new-node lifetime, alter a future ACK or
alter the resulting ledger. Each mutation must fail for its declared reason;
an unrelated earlier failure is not a successful negative result.

```bash
python3 -B -m scripts.v53.joining_phase_evidence <original-raw-directory> --qualify
```

## Remaining original-observation requirement

The executed `df22c398` producer recorded original old-node responses and received
results, plus every PUBLISH send. It did **not** retain all other old-node request
attempts and arrivals. This reader cannot reconstruct those missing observations
from responses. Complete activation/source-transfer causality, all send attempts,
ownership/generation reclamation and process interruption remain open.

The current test-only fixture enables `NETWORK_SEND` (including original bytes)
and `NETWORK_REQUEST` for the early-start whole-history case before its first
campaign. Existing fixture families keep their trace vocabulary. The new callback
does not add responses or change transport, consensus, retries or deadlines.
Focused Java tests cover unanswered and repeated attempts separately from arrivals.

That changed fixture still needs a fresh, single-filesystem complete execution,
which may run in deferred hosted acceptance. Keep the existing passing original
and its source binding; do not append synthetic events or combine attempts.
Neither this scoped PASS nor the observation change sets
`completePhysicalQualified`, `forceAndNetworkQualified`, `processDeathQualified`
or `phase3Complete`. All seven profiles and the frozen Phase 3 mappings remain
required.
