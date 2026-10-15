# V5.2 local development sequence

The operator authorized multiple locally verified commits without intermediate
pushes or review pauses. Phase 1 is local commit `d8412a8`. Continue through the
pre-cloud implementation on the existing branch; do not push, create a PR, merge,
publish or dispatch cloud work. Each coherent local stage receives its own commit
and validation record. Keep failed runs and distinguish local checks from hosted
acceptance.

This instruction supersedes the earlier requirement to obtain protected CI
between local phases and the earlier operator-owned **commit** boundary. Push,
PR, merge and paid triggers remain operator-owned. Before cloud entry, stop for
the operator to push and merge the accumulated work. The final exact-source
protected full CI and fresh cloud admission are still required before cloud runs.

## Remaining implementation order

1. Phase 2: atomic application publication capture, callback lifetime, bounded
   waiter scheduling, cancellation/deadlines and deterministic race tests. Keep
   the public read default disabled until Phase 3.
2. Phase 3: connect all three policies to the public handle, existing admission
   permits and strong NO_OP barrier. Exercise the seven methods externally.
3. Phase 4: complete the declared lifecycle, fault, resource, compatibility and
   independent evidence matrix. Synthetic Phase 1 evidence is not physical proof.
4. Phase 5: combined recovery/partition and slow-callback resource hardening.
5. Phase 6 pre-cloud: frozen local measurements, portable no-GCP replay and a
   concrete cloud plan/admission review. Stop before any paid execution.

Actual implementation and validation are recorded in phase documents. This order
does not authorize different token bytes, weaker read semantics, new authority
formats, reduced CI checks or unrecorded changes to frozen workload parameters.
