# Native learner cancellation: original failure and required source retention

The first actual three-voter history exposed a missing source-side retention
obligation. This is an **implementation gap**, not a timing failure. The earlier
[cancellation component](PHASE_3_LEARNER_CANCELLATION.md) still qualifies its
conditional source and local transaction only. Phase 3 remains **OPEN**.

## Original observation

The unchanged `d1a7e4b4` production runtime completed actual BARRIER, RESERVE,
PREPARE, READY and CANCEL publications. The learner had retained the original
PREPARE source at index 3. The certified CANCEL source at index 5 offered complete
original generation bytes, but its authenticated endpoints were only 0, 1, 4 and
5. The original index-3 endpoint had been pruned.

`MembershipLearnerProgress.fetch` consequently refused with
`generation did not preserve original proven parent`. No cancellation transaction
write or learner cold reopen followed. The original test failed after 273.3
seconds; the declared network history budget was 600 seconds. Its complete log,
JUnit result, source/build inputs, physical snapshots and received wire remain
retained. No rerun or timing extension was used to obtain a pass.

The independent Python reducer reproduced all five original native publications
and all **59** successful learner exchanges: 31 enrollment and 28 progress
exchanges. It matched the exact source inventories before diagnosing the missing
endpoint. Fifteen bounded `FUTURE_RETENTION_INTENT` rejections by the unselected
node-3 belong to the existing fixture contract; they are recorded separately and
are not this failure. Diagnosis returns **PARTIAL**, never cancellation acceptance.

See [the retained diagnosis receipt](phase3-evidence/learner-cancellation-native.json).

## Why preserving one convenient anchor is insufficient

`MembershipGrantJournal.applicationParents` retains selected sources, campaign
coverage, the immediate parent, governing-floor obligations, peer-retention
endpoints and frozen bases. A nonvoting learner's received endpoint is absent
from that durable set. READY hides its preceding PREPARE endpoint inside a RANGE;
the following CANCEL can then prune it.

Simply retaining every old bridge until cancellation would eventually exhaust
the six-bridge limit. Retaining only the most recent PREPARE would lose a learner
that missed a revision. The public source may also advance while PREPARING, so
the catalog's prepared image or its pre-command cut is not an exact record of
every exported post-command source. Increasing the bridge count, treating a
higher index as ancestry, inserting fixture endorsements or weakening
`verifyAncestry` is not a correction.

The next implementation must therefore track a bounded nonvoting learner source
obligation before exposing the complete original source:

- Bind the original root, complete operation request, joining storage identity
  and exact exported endpoint. Keep this separate from the set of voters.
- Persist and preserve the obligation across the actual old-view quorum and
  frozen-source selection before a later publication may prune it. A local
  transient export object is insufficient for alternative-leader recovery.
- Bound unresolved old/new endpoint uncertainty. A lost acknowledgment retains
  both possibilities; only exact forced learner-head confirmation may retire an
  old obligation. Timeouts and receipt/image equality do not prove a moved head.
- Include these obligations in publication admission and renewal, under the
  existing ancestry, source, generation, image and aggregate resource limits.
  Capacity refusal must precede accepting unfinishable work.
- Apply the same rule through PREPARE replacement, READY, CANCEL and matching
  INTENT. Missing earlier originals remain a refusal; never recreate their
  authority from current API arguments.

These are requirements for subsequent implementation, **not an implemented
ledger or a new frozen format**. Ordinary source provenance and the local A30
cancellation transaction remain unchanged in this batch.

## Deferred complete qualification

`V53LearnerCancellationQualification` is an explicit, indivisible qualification
entry. It is newly introduced outside automatic Surefire naming; no existing CI
test or gate is disabled. Its original execution used the temporary class name
`V53LearnerCancellationNetworkTest`; the retained failed snapshot preserves that
exact source. The final name and formatting change does not alter the history.
The future Phase 3 hosted aggregate must explicitly require this gate.

From an isolated Java 21 source/build:

```bash
mvn -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtest=V53LearnerCancellationQualification test
python3 -B -m scripts.v53.learner_cancellation_evidence RAW_DIRECTORY --qualify
```

The complete reader derives voter originals first, then binds admission paths,
typed backup, receipt, original file identities, complete progress transcripts,
cancellation plan, forces, resource release and cold reopen. Its twelve declared
evidence negatives run only after a successful original. The complete retention,
reopen and negative paths are **not yet qualified**: this original stopped before
retention. Small parser regressions do not substitute for that missing execution.

For this specific retained failed history only:

```bash
python3 -B -m scripts.v53.learner_cancellation_evidence FAILED_RAW_DIRECTORY --diagnose
```

The diagnostic profile requires the original FAIL result, complete physical and
wire replay, absent cancellation writes and the missing prepared endpoint. It
cannot be combined with `--qualify` or used as a successful cancellation receipt.
All five joining profiles, alternating heads, halt/SIGKILL, maximum combined
resources and autonomous continuation remain required by the
[acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).
