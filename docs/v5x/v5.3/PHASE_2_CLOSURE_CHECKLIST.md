# Phase 2 closure obligations

Status: **OPEN**. The operator authorized continuous local development through
Phase 2 closure, with a local commit after each validated batch. No push or V5.2
cloud operation is authorized by that instruction. This checklist expands the
[entry plan](PHASE_2_ENTRY_PLAN.md); it does not reduce its scope.

| Obligation | Current evidence / outstanding acceptance |
| --- | --- |
| Exclusive 1.3 root/node owner and separately forced ballot allocation | Local component gates pass; complete-store open/provisioning integration still required |
| Forced root-wide PROMISE and immutable original BASIS/source | Local metadata, source and current-generation capture gates pass; adoption and lifetime integration still required |
| One durable selected set per ballot | [2C1 gate](PHASE_2_DURABLE_SELECTION.md) passes; selected materialization/ACK remains pending |
| Selected-source generation installation | PENDING: retain exact original references/parent/tail, reserve shared resources, force complete generation and selector under the same writer; recover interruptions without same-ballot reselection |
| Adoption and configuration-aware prefix recovery | PENDING: certificate-derived promise floor, ancestry across old/joint/new cuts, no old-ballot vote/READY after adoption; retain removal authority and reject missing/ambiguous state |
| ACCEPT/PROOF/certificate and complete catalog/application persistence | PENDING: exact phased records and real ownership observations, duplicate/conflict/fencing checks, original carried entries, stable next-slot progression and immutable application bytes |
| Checkpoint, governing-quorum floor and retirement | PENDING: actual exact floor copies under the cut's next authority, forced retirement inventory before deletion, retain above-floor owned tails and resume interrupted deletion without selecting stale authority |
| Bounded storage and rotation | PENDING: actual peak bytes/counts/staging and completion headroom; two generations/six sources/one learner/global shared limits, safe 32 MiB journal rotation, no accumulating unbounded abandoned campaigns or bypassing exhausted capacity |
| Offline initialization and reopen | PENDING: complete EMPTY/verified-backup paths for supported identities, distinct root/history, exact disjoint target bindings, no silent legacy conversion/repair/genesis fallback; missing/corrupt/torn/stale authority and recovery interrupted again |
| Independent physical qualification and closure audit | PENDING: fresh JVMs and halt/SIGKILL across storage paths and old/joint/new authorities; source/build-bound raw bytes, original-first negatives, portable replay, real local ownership replacing fixture assertions where storage claims it; map every Phase 2 requirement to direct evidence |

The frozen physical S/N inventory is not satisfied by these component counts.
Closure must map the storage obligations in S02/S04/S07/S09/S10 and relevant N
families to actual storage evidence, retaining their prescribed profiles and
boundaries. Phase 3–5 still own distributed campaigns/transitions, learners,
public operations/reads/maintenance and combined runtime qualification. Any such
unexecuted rows remain PLANNED; they must not be relabelled by a Phase 2 unit test.

Final audit must also verify unchanged 1.1/1.2 production behavior and frozen byte
inventories, local source/build provenance, resource accounting on failure/reopen,
the disabled public runtime, and the explicit limitations of process crashes.
Unified protected acceptance and actual released V5.2 integration remain later
gates under the [local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
