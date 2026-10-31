# Phase 3 — joining profile FINAL and cold recovery

The five joining execution profiles now share the original end-to-end producer:
`3-ADD`, `4-ADD`, `3-REPLACE`, `4-REPLACE`, and `5-REPLACE`. The new complete entry
extends the [prefix gate](PHASE_3_JOINING_PROFILES.md) through original head
confirmation, placement, retention initialization, FINAL, a fresh stable BARRIER
and retaining cold reopen. REMOVE remains a separate family. Implementation and
local scoped results do not close Phase 3 or qualify all seven profiles.

## Actual selected owners

Head confirmations, foreign-owner refusal probes, governing floor copies and
old retention preparation use the original live majority of the selected
profile. Every new-side identity and retained filename comes from that profile.
The old `1 - voter`, two-owner loops and fixed node-4 identities cannot govern
four/five-member or replacement executions.

Continuation verifies the actual SELECTED sources against both majorities and
the available permanent identities. It checks each selected owner's original
selection and retains its original grant bytes before slot publication. It does
not require the joining voter in an already sufficient overlapping majority.
The new stable barrier checks the actual target configuration and selected ends;
every offline old voter remains offline with its initial cut.

After the original old proposer finishes and drains its round, a joining voter
that was not selected may still be behind. It uses `MembershipPrefixRecovery`
over its original TCP transport to acquire a newer certified authority. If it
already has the new authority at FINAL but lacks the same-view BARRIER, ordinary
`MembershipActivationDriver` selection and installation acquire that end. No
extra workload slot or synthetic checkpoint supplies this recovery. Neither
recovery path grants public READY. The actual original joining directory is
then closed, reopened retaining all three ledgers, observed and closed again.

The pre/post recovery snapshots and original network/force observations remain
available to the subsequent physical/network readers. This batch's semantic
reader does not promote those unqualified observations into a complete physical
or causal proof.

## Preserving local ancestry during newer-prefix adoption

The first complete 3-REPLACE execution reached FINAL at index 10 and the new
stable BARRIER at 11 using the valid old-only majority node-1/node-2. The joining
node-4 remained at JOINT index 9. Its TCP acquisition of index 11 then failed with
`generation did not preserve original proven parent`. This is a recovered-path
implementation defect, not evidence of a timeout: the incoming prefix retained
anchors 0/8/9/10/11, while the local owner also needed its authenticated original
bridges 4→8, 6→8 and 7→8. Remote ancestry alone could not preserve those parents.
The complete failed source, raw history and JUnit result remain retained.

`MembershipGenerationPlan.adoption` now verifies all explicit incoming ancestry
first, then inherits only missing required parents from the current owner's
verified ancestry. `MembershipCapsule.inheritingAncestry` checks that the exact
original upper endpoints still occur in the incoming prefix. It changes neither
the incoming packet nor the original bridge bytes and supplies no fresh owned
vote. All original parent checks, membership-certificate fencing, journal/slot
installation checks, and the six-bridge/96 KiB limits remain enforced.

Three conditional original-history regressions at sizes 3/4/5 fail at the same
adoption boundary on the original implementation. They exercise actual journal
adoption, floor retention, inactive retirement, idempotence and cold reopen.
Additional negatives reject unverified, missing, changed, duplicate, excessive,
foreign-root and obsolete-endpoint proofs, including invalid explicit remote
proofs when valid local proof also exists. These fixtures establish the narrow
regression; they are not a substitute for the complete native profile cohort.

The related retirement regression also exposed an obsolete test expectation on
the unchanged parent commit: selected installation already retains the original
ACCEPT/ENTRY/payload bytes after a longer proven prefix covers that slot, so
retirement may succeed without an unresolved `owned-tail.gsr` file. The test now
checks all three exact originals in both carried and covered cases. Three
separate malformed-generation cases remove each original in turn and require
retirement planning to reject it without changing the old owner. No retirement
implementation or deletion authority is relaxed.

## Execution and portable semantic replay

```bash
# One indivisible history. A separate output is mandatory for every execution.
python3 -B -u -m scripts.v53.joining_profile_run target/joining-complete-3-replace \
  --profile 3-REPLACE --complete --maven /opt/maven/bin/mvn

# Reuse only the immutable source inputs, never generated disks or history.
python3 -B -u -m scripts.v53.joining_profile_run target/joining-complete-4-add \
  --profile 4-ADD --complete --source-from target/joining-complete-3-replace \
  --maven /opt/maven/bin/mvn

python3 -B -m scripts.v53.joining_completion_evidence /path/to/original/raw \
  --profile 3-REPLACE --qualify
```

Omitting `--complete` still invokes only the JOINT prefix. Each mode checks its
exact single JUnit method; prefix success cannot satisfy complete execution.
The driver uses the reader from the same immutable source, retains failures and
minute progress, and never retries a native measurement. Successful receipts
remain `PARTIAL`; `semanticFinalAndColdQualified` is distinct from complete
physical, network, process, profile-matrix and Phase 3 qualification.

The independent semantic reader derives the full catalog and every original
ACCEPT/PROOF, applied end, checkpoint and selected source from bootstrap. The
FINAL target membership comes from the explicit reader profile, not producer
labels. Closed old owners cannot regress below their original observed
publication; any later end must be in the same independently derived history.
The cold joining owner must retain its original root/permanent identity and
exact final derived capsule. Offline owners remain byte-for-byte unchanged.
The original round must still finish its new-view BARRIER before readiness.

Nine original-first mutations cover missing slots/publications, changed joining
ACK or applied catalog, changed offline state, missing final readiness, wrong
FINAL binding, duplicate votes and missing original cold files. Each must fail
for its exact reason. An unnecessary joining vote is not removed as a universal
negative: old-only majorities are valid for the overlapping profiles. Separate
majority rejection remains tested for every profile.

## Qualification status and remaining work

See the source/build-bound [batch receipt](phase3-evidence/joining-profile-completion.json)
for actual local executions, tests and retained failed attempts. The [profile-aware physical follow-up](PHASE_3_JOINING_PROFILE_PHYSICAL.md) now
replays the retained 3-REPLACE history through three scoped gates. Its fresh 4-ADD
execution reached the final cold reopen but failed on the old wire-evidence
envelope; it remains unqualified. The complete corrected-source five-profile
hosted cohort is still pending. Old source evidence is
retained and replayed without relabeling it as a new native execution.

The corrected complete local 3-REPLACE history passes all eleven original slots,
including the actual unselected joiner's newer-prefix adoption and retaining
cold reopen. Its independent semantic replay rejects all nine declared mutations.
The focused class receipts contain 72 Java cases; 343 joining Python tests pass.
Original and relocated evidence are checked separately. This result qualifies
one native execution and its semantic history, not the remaining four complete
profiles or the complete physical/network/process gates.

Before full acceptance, generalize and run the complete physical/force/network
readers for each profile, including unselected joining recovery and any extra
same-view installation. Run complete process/fault compositions, both REMOVE
profiles, and the unchanged frozen S/N mapping. Independent whole histories can
run in parallel on hosted runners, but each history's source, lease and original
disks remain indivisible. No workflow, paid cloud run or push is introduced here.
