# Segmented replica capture envelope

The segmented verified-backup observer previously admitted at most 512 MiB per
replica snapshot. That was smaller than the frozen metadata allowance plus seven
maximum application images. Grant copies, retirement/publication prefixes and
ordinary physical replay now use the same explicit **832 MiB** transport envelope:

`384 MiB metadata + 7 × 64 MiB application images = 832 MiB`.

This is an evidence-reader/capture limit. It does not allocate new runtime space,
change a reservation, or establish that these peaks can coexist. It also does not
admit a file merely because its bytes fit: the independent typed physical,
authority, causal-history and resource readers still run.

## Source and ownership audit

The audit used the current source after `b7957f8352c41d9285526d5ed57ee38c53c59fe0`,
not an earlier runtime snapshot. The frozen nominal metadata categories total
324 MiB; the transport bound conservatively uses the full 384 MiB metadata cap.
The actual maximum-image native composition remains a separate acceptance task.

| Physical family | Existing owner and bound | Source checked |
| --- | --- | --- |
| Selectable generations | Two GENERATION slots, each at most 32 MiB excluding images | `MembershipCurrentGeneration`, `MembershipGenerationFiles` |
| Frozen sources and floor copies | Six shared SOURCE slots, each at most 32 MiB; each physical image copy gets its own APPLICATION owner | `MembershipBasisSources`, `MembershipFloorFiles` |
| Staged learner | One LEARNER slot, at most 32 MiB; ownership transfers retain their charge | `MembershipResources`, `MembershipLearnerSlot`, `MembershipJoinedOwner` |
| Grant journal and pending state | One 32 MiB JOURNAL allowance; append/completion admission includes pending accept/context/retention/application metadata | `MembershipGrantJournal.pendingBytes` and completion guards |
| Catalog and miscellaneous authority | Two 2 MiB categories; compact journal candidate is capped at 1 MiB; joined immutable proof/root metadata is checked against MISC | `MembershipResources`, `MembershipJournalRotation`, `MembershipJoinedOwner.targets`, `MembershipLearnerJoinedOriginal` |
| Application images | Seven APPLICATION slots, each at most 64 MiB, shared by generation/source/learner/applied-end ownership | `MembershipResources`, `MembershipCurrentGeneration`, `MembershipBasisSources`, `MembershipAppliedEndFiles` |

Source-retirement leases are released after physical deletion. Floor copies do
not release the original source charges to make room for their copies. Generation
claims do not grant additional payload bytes. The resource checks still use
completion headroom and the original per-owner staging limit.

The generic replication configuration's 8 GiB retained-log default is not added
to this replica snapshot. `MembershipReplicaConfig` requires replica and
materialization directories to be disjoint; `MembershipBallotAllocator` validates
the native replica's named files/directories, and membership records use the
bounded grant journal. Materialization, control buffers, transfer staging and
all retained observations belong to their own checks. This statement concerns
these replica observations, not a bound on the complete engine or original run.

## Entry points and unchanged boundaries

`V53CaptureFiles` derives its envelope from the production metadata and application
constants. Python's `replica_capture_limits` holds the independent frozen values.
`joining_grant_captures`, `capture_objects` and `physical_snapshot.from_model`
use those values only for an explicitly requested `VERIFIED_DURABLE_BACKUP` /
`SEGMENTED_BACKUP` pair. Caller policy is checked before opening evidence.

The segmented structural bounds are 512 members, depth eight and 64 MiB per
file. The model-selected physical reader now applies the same member-path check
as grant captures, including the file name in the eight-part path limit. A
repeated digest in different logical paths counts repeatedly toward the
832 MiB prefix limit even when the object pool stores its bytes only once.
The 128 GiB whole-original budget remains shared across every evidence family.
The small hosted backup workflow and its archive limits are unchanged; this work
does not turn it into a maximum-image execution host.

Legacy JSON capture/pool limits remain 256 MiB. Direct `physical_snapshot.Snapshot`
without an explicit policy retains its original 512 MiB / 256-member / depth-four
limits. No production Java, workflow, public limit, frozen hash or format changed.

## Validation and remaining acceptance

The [development receipt](phase3-evidence/replica-capture-envelope-development.json)
separates these results:

- Sparse synthetic files totaling exactly 832 MiB pass Java streaming inventory
  and recheck under a 32 MiB heap, and Python physical/grant metadata collection
  under a 160 MiB address-space limit. One additional byte is rejected. These
  files are not decoded application images or native maximum histories.
- Content-addressed prefix views count duplicate logical copies at the exact
  boundary. No complete snapshot is cached as payload bytes.
- Previously retained backup and EMPTY originals retain their identities and
  bytes. Old/deferred retirement and publication results agree. Twelve exact
  retirement negatives remain rejected; the prior malformed publication original
  remains rejected. EMPTY evidence is not relabeled as a backup cohort.
- The unchanged short native backup/BARRIER original passes physical, transfer,
  checkpoint, generation-window, resource and close checks with identical results.

The operator has no qualifying native Linux maximum-image host at present and
has chosen to finish development before arranging acceptance. Native-Linux,
available-memory and disk checks remain enabled. Whole-reader maximum memory,
complete default-staging histories, real simultaneous ownership/pressure evidence
and immutable final-source cohorts remain open. All five Phase 3 closure gaps
remain open; this receipt does not close them.

Rollback can restore the former 512 MiB segmented envelope and direct physical
reader selection together. Existing originals and the old JSON policy remain
intact; evidence larger than the former limit would then be rejected explicitly.
