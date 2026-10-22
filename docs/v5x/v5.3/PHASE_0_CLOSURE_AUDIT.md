# V5.3 Phase 0 local closure audit

**Result: LOCALLY CLOSED, 2026-10-21. Phase 1 not started.**
This closes the operator-authorized design/model goal, not production/protected
acceptance. Local branch `feat/v53-cluster-operations`; no push, PR, tag or cloud
dispatch. V5.2 production and its separate active cloud work remain unchanged.

## Source and retained evidence

- Base inspected: `73f3bd5c21c97eee564397ab11af7b66bc1b13a3` (unpublished V5.2
  development predecessor). Latest code/contract batch at measurement:
  `4676673`; all exact script hashes are retained in [closure index](phase0-closure.json).
- The audit ran against a dirty worktree because the format catalog status and its
  fixture binding were being frozen locally. It is not relabelled as clean-master
  or hosted evidence. All script bytes stayed unchanged during the complete run;
  final closure edits only update documentation/status and add receipts.
- Evidence: `target/v53-phase0-closure/run-20261022T025111Z/`; total audit elapsed
  **251.182 seconds**, approximately **3.5 MiB** retained at completion. UTC date is
  October 22; the operator's America/Los_Angeles date is October 21.
- Original logs, portable compressed histories, command runner and summary remain
  under that unique target directory/parent. Nine final machine receipts are copied
  into `phase0-evidence/`; the closure index records receipt/log/source hashes.
  Earlier attempts and per-batch receipts were preserved.
  Individual model receipts deliberately retain `phase0Accepted=false`: one model
  cannot close the contract by itself. The combined decision audit records local
  design closure separately, with production/protected acceptance still false.

## Actual local validation

| Gate | Result on final script bytes |
| --- | --- |
| Entire `scripts/v53` unit suite | 198 tests, no failures/errors, 38.840 seconds test-runner time |
| Contract/links/fixtures | All required deliverables, schemas/IDs, 45 framed fixtures, nine control payloads, unchanged read-token fixture and complete acceptance inventory pass |
| Membership arithmetic | 41 configurations, 510 transitions, 53,760 certificate and 82,770 intersection checks |
| Durable ballot matrix | 2,884 cases / 21 contexts, retained examples replayed |
| Transition matrix | 196 cases plus 13-slot membership walk; 15 portable histories replayed |
| Checkpoint/floor recovery | 42 inputs, 1,080 crash observations; 42 portable histories replayed |
| Global promise/activation | 420 cases, 1,008 campaigns; 60 portable histories replayed |
| Authority/learner | 220 cases, 660 capsules; 55 portable histories replayed |
| Operation lifecycle | 308 cases, 2,436 controls/data applications; all 308 portable histories replayed |
| Integrated protocol/catalog | 126 cases, 1,141 campaigns; 21 portable histories replayed |
| Stable round/catalog extension | 49 portable histories, 252 publications, 70 incremental cut capsules |

These counts describe different bounded research domains. They must not be summed
as physical cluster tests or claimed to explore every asynchronous schedule.
Original evidence passes before negative mutations; negative cases and deliberately
unsafe variants remain tested in the unit suites. Source/root/force/identity/capacity
and parser failures use explicit exceptions, including optimized-Python checks.

## Decision audit

| Row | Final decision and concrete local detection |
| --- | --- |
| D01 | Root vs configuration and replacement identity are distinct; arithmetic/context tests, identity reservation conflicts, wrong-root fixture and unchanged token layout detect substitution |
| D02 | Forced predecessor controls old/joint/new authority; direct-switch counterexample, both-majority and accepted-tail integration detect single-side or speculative authority |
| D03 | Global promise/immutable basis/selected quorum/fresh activation and stable round reuse fixed; force/fence/crash/callback/source-substitution tests detect unsafe reuse |
| D04 | Exact forced learner image/readiness/INTENT gating fixed; independent observers reject pre-admitted voters, missing image/receipt and future endorsements |
| D05 | Stable client number, revision, certified SEAL/CANCEL and retired watermark fixed; selected SEAL beats stale CANCEL; duplicate/revision/retirement/counter tests pass |
| D06 | Full metadata plus explicit membership descriptors, new range endorsements, floor/selector/owned-tail retirement fixed; lost/modified proofs, hidden boundaries and missing state reject |
| D07 | Capture/removal semantics and operator-serialized maintenance fixed; read-role matrix and fresh survivor/cut/nonce negatives pass; no instantaneous remote revocation or distributed maintenance lock claimed |
| D08 | Concrete additive signatures and explicit 1.3 family frozen; 24/21 kind inventory, 45 byte fixtures, nine control payloads/token fixture and corruption/context/parser tests pass |
| D09 | Logical lifetime and physical byte reservation ceilings fixed; bounded metadata formula, counters, capacities, cancelled identity retention and 10,000 DATA reducer steps pass |
| D10 | S/N/C/M inventory, five-member same-source cohort, exact six cloud drill cases, failure retention and soft experiment budgets fixed; plan integrity rejects incomplete or relaxed cohorts/windows |

The final code review also found and covered two non-obvious requirements: a removed
5→4 proposer must remain in its own selected joint quorum, and a leader restart must
invalidate an already pending publication callback even if its disk promise remains.
The final document review explicitly retains all seven current compatibility
consumers, maps stale operation/history refusals, and requires verified discovery
before a stale-configuration node begins a new campaign.

No unresolved Phase 0 semantic decision is deferred as an implementation detail.
Implementation composition is still pending: heterogeneous prefix discovery,
same-round catalog commands, compacted selected sources, real application bytes,
authenticated transport identities and actual filesystem ordering. The protocol
defines their required behavior and Phase 1–5 gates must qualify it.

## Scope and exclusions

The cumulative branch diff from the recorded V5.2 base has paths only under
`docs/v5x/v5.3/` and `scripts/v53/`. The audit checks exact scope and current source
hashes, changed local links and whitespace. No production Java, tests from earlier
versions, POM, workflow, frozen predecessor pin or cloud resource was modified.

Not executed: Maven/full GSE CI, Java compatibility compilation for the new APIs,
real multi-JVM storage/wire faults, paid cloud, publication or protected review.
The actual published V5.2 control cannot be pinned before release. Those are later
gates in [Phase 1 entry](PHASE_1_ENTRY_PLAN.md), not evidence manufactured by this audit.
The final local commit records the closure; development stops here under the current
goal. A future counterexample reopens its owning contract decision.

## Reproduction

From this source, run the unit discovery command in [README](README.md), then each
listed research CLI into a new output directory, plus:

```bash
python3 -m scripts.v53.contract_check
python3 -m scripts.v53.continuity_research --output <new-directory>
```

All original commands and hashes are retained in the audit parent script and
machine receipts. Do not overwrite historical output or use a newer source to
relabel these results. Model execution needs no network, sudo, Maven or cloud.
