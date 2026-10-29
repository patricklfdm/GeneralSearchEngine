# Dormant voter installation for a joining learner

Phase 3 remains **OPEN**. `MembershipLearnerVoterStage` adds durable installation
bytes for the next ownership-handoff step. It does not open a voting journal,
allocate a campaign, acknowledge a vote, change the live replica selector,
publish an application or retire the learner's originals.

Only a live `MembershipLearnerIntent.Forced` can enter. That owner has already
validated the complete received history against the actual typed receipt and
matching INTENT. Staging retains the original learner lock and INTENT ownership.
A decoded source or caller-supplied set of certificate voters is insufficient.

The fixed sibling directory contains an original private plan, expected replica
headers, local counter, adoption PROMISE, empty pending-vote file, source storage,
local generation/selector and a completion seal. The promise preserves the
certificate ballot as a historical floor and has no BASIS. The allocator names
the joining member and starts at that counter; later campaigning must allocate
strictly above the observed floor. The generation names the joining member and
uses the existing adopted-certificate format. No remote BASIS or SELECTED file
is copied into local authority. ROOT and GENESIS preserve the original initial
configuration; the joining member is never rewritten into bootstrap membership.

Before writing, charge the additional GENERATION's complete metadata plus both
64 KiB companions, and each copied image as a separate APPLICATION reservation.
The live learner generation and received source retain their existing leases.
Capacity refusal leaves no new staging directory. Closing releases reservations
and preserves all bytes. Closing the INTENT/store also closes any attached stage.

Create and force the original plan first, then directories, all payload members,
parents, and the inode-bound completion seal. Recheck the live original owner
through these boundaries and fully validate the INTENT before returning. An
existing directory requires explicit resume. A complete plan must reproduce
exactly from the original intent, receipt, destination and directory binding.
All existing payloads must be exact prefixes before any recovery writes. Missing
or torn plans remain preserved and refused. Complete seals bind all payload
inodes, lengths, hashes and child directories; copied files, unknown members and
changed authority refuse. A failed live owner cannot heal itself after a caller
restores bytes. Reopening requires a fresh original validation.

The current route requires a complete already published matching-INTENT source.
It must not become an extra quorum requirement for the general joining protocol:
native old-majority INTENT certificate/prefix delivery is still needed before a
new member can contribute to joint checkpointing at the minimum quorum.

The next ownership transaction must consume the live staged capability, bind a
joined-voter admission distinct from bootstrap, transfer the original replica
lock, and recover partial takeover from exact original files. It must release or
retire the learner generation only after durable coverage permits it, so normal
voter rotation still has its two generation slots. The stage itself grants no
such deletion or takeover permission.

`V53LearnerVoterStageTest` uses real typed preparation, local TCP, files and force
boundaries. Its source quorum history remains a conditional fixture; injected
IOException cuts are not native process-death qualification. It covers JOINT and
COMPLETED replacement, restart/reseal, interrupted payload and seal writes,
incomplete decisions, capacity refusal, original byte/inode corruption, duplicate
owners and close revocation. Full native joint histories and hosted acceptance
remain in the [deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md).

The [component receipt](phase3-evidence/learner-voter-stage.json) retains all three
executed snapshots. The first stopped at test compilation because the new test
used a nonexistent allocator method name; no test ran. After correcting the
name, six new cases passed. The final snapshot adds cross-member mutation checks,
serialized child attachment/close, a wrong-prefix rejection and loss of INTENT
during writing: seven new cases and the existing INTENT lifecycle regression all
pass (eight tests, no skips). Fourteen lightweight Python contract/evidence tests
also pass. Public byte fixtures and the frozen resource/format catalogs are
unchanged. These finite component runs do not establish native joining readiness,
process-crash safety, maximum-resource qualification or the complete Phase 3 gate.
