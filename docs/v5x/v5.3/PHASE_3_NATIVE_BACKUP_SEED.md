# Native backup seed prerequisite

The complete required-four joining fixture previously constructed only an EMPTY
bootstrap. A physical maximum-image joining experiment needs an explicit verified
backup at that same native entry, rather than fabricated images or images held by
an unrelated external receiver.

## Implemented entry

`V53NativeDispatchTest.Network` accepts a complete
`MembershipBootstrapRequest<Integer, Doc>`. The existing size-based constructors
still request EMPTY. Endpoint rebinding changes only loopback endpoints: source,
source path, group/configuration, permanent node/storage identities, target paths,
materialization configuration and admission limits remain those of the caller.
The real `planBootstrap` / `applyBootstrap` path admits the seed before retention
initialization, preparation or network actors are opened.

`V53JoiningIntentExportTest.requiredFourFromVerifiedBackup` explicitly requires a
five-voter verified backup and enters the existing complete required-four history.
It is a fixture hook, not a new accepted hosted profile. No default test, workflow,
resource limit, lifetime, transport retry or cohort membership changes.

The low-level `joining_catalog_evidence.Replay` accepts an explicit
`bootstrap_source` contract. It validates that contract against original bootstrap
bytes before reducing any history. The default is still EMPTY, and existing full
validators retain that default. A producer receipt cannot opt an old gate into
the new source contract. Unknown values and non-string truthy values are rejected
before reading originals.

## Focused validation scope

`V53NativeSeedTest` covers request preservation, a five-voter TCP bootstrap from
three documents at sequence 731, a real initial BARRIER, the unchanged EMPTY
entry, refusal of an undersized source budget before actor startup, and rejection
of EMPTY / wrong-size requests by the required-four backup hook. The backup test
checks the new history identity, unchanged application bytes and typed documents
on the actual publication voters, unchanged original backup and zero resource
leases after close.

Development logs and small original evidence are retained under
`target/v53-native-backup-seed/`; the native collector prints its original evidence
directory under the replication module's `target/v53-native-dispatch/`. These
checks do not fill a final-source cohort slot. The complete backup joining hook
and a maximum-image native history still need their own whole-history execution.

The [development evidence index](phase3-evidence/native-backup-seed-development.json)
records six Java cases, 36 focused Python checks and 19 contract checks. The
five-voter seed/BARRIER original passed in about 62 seconds; independent bootstrap,
catalog/certificate/checkpoint and typed-image replay passed over 654 files
(2,418,046 bytes). Both a false EMPTY source contract and an altered application
image were rejected, with the original inventory unchanged. The unchanged EMPTY
two-slot round also passed. The first invocation used the wrong reactor path;
its log remains retained. In the first actual test invocation, the new source
refusal assertion expected the wrong exception type. The admission correctly
rejected the budget; the exact `ReplicationException` type/message assertion was
corrected and that single case passed on recheck. This is development testing,
not a claim that the original whole invocation was green.

## Remaining combined-resource work

The [maximum transition](PHASE_3_MAXIMUM_TRANSITION_EXECUTION.md) is still a
synchronous storage probe. This seed entry does not convert it into native learner
or required-four qualification. The [complete EMPTY required-four
original](PHASE_3_REQUIRED_FOUR_ENTRY.md) remains a separate development result.

Before executing a full physical maximum, provide bounded evidence capture for
large images and all native joining/retention/lifecycle observations, propagate
the explicit source contract through a dedicated complete validator, and declare
the feasible combined pressure and refusal/continuation boundaries. Existing
in-memory wire arrays and copied snapshots must not simply have their bounds
increased. Respect the unchanged seven-application and per-owner staging limits;
independent maxima cannot be added as if observed together.

All Phase 3 closure gaps remain OPEN. No maximum-image, full backup joining,
combined-resource, final-source or workflow execution qualification is claimed by
this prerequisite.
