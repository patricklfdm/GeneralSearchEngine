# Phase 3 hosted review: 373da301

This reviews the five completed attempt-1 runs at
`373da3018243f6e01f0e1b5e812b83684d845c19`. A failed aggregate does not mean every
original failed. Successful jobs at this source are not receipts for a corrected
source or a completed Phase 3 cohort.

| Cohort / run | Original jobs passed | Replay jobs passed | Primary failures |
| --- | ---: | ---: | --- |
| [Joining processes 43350565983](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43350565983) | 119 / 120 groups | 118 / 120 groups | group-060 Maven wrapper download; group-062 negative moved a transfer across a reused socket interval |
| [Joint-floor 43350566525](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43350566525) | 32 / 32 | 0 / 32 | 30 negative reason mismatches; two premature retirement comparisons |
| [Carried transition 43350566407](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43350566407) | 16 / 16 | 14 / 16 | INTENT failed-control mutation; FINAL peer-event mutation expectation |
| [Carried DATA 43350565916](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43350565916) | 10 / 12 | 10 / 12 | APPLIED publication exchange deadline; APPLIED cleanup-kill second-process readiness deadline |
| [Automatic 43350565615](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43350565615) | 2 / 3 | 1 / 3 | competition discovery-only schedule; higher-ballot restart DATA publication exchange deadline |

Joining groups contain three whole histories each. Missing originals correctly
fail their dependent replay and aggregate; these are not additional independent
runtime failures. This review retained all pages of 376 jobs, all five attempts,
680 artifact listings and the failed job logs. Selected downloaded ZIPs and
extracted original files were checked against their recorded hashes.

## Corrections

- Wrapper initialization requests verbose non-debug output so wget's actual
  HTTP/network cause survives. Only recognized transient failures may use the
  existing three attempts. A bare `Failed to fetch`, authentication error,
  checksum failure or unknown failure still stops. The group-060 log alone does
  not prove a transient network cause.
- A negative relocating a retired source's exchanges now chooses a gap outside
  other invocations of their unchanged socket routes. Original invocation IDs,
  bytes and remaining event order are preserved. The complete original must
  pass before the copied mutation can earn rejection credit.
- Unselected-peer maintenance is compared once, after original network replies
  select independently derived before/after-install copies. The former
  speculative call could consume durable retirement prefixes using the wrong
  copy set. Interrupted maintenance still cannot authorize deletion.
- One joint-floor original additionally queued a STATUS in its reopened owner
  while a same-cut installation completed. The hint may describe the new
  generation only inside that same declared cold-owner lifetime, with exact
  identity, root and cut. This does not permit an old data export to survive
  close/reopen; content transfers retain the existing predecessor checks.
- The child-request and unbound peer-reseal negatives now require the exact
  first strict rejection (`connection boundary without start` and
  `REMOVE peer event shape`). No arbitrary exception counts as rejection.
- Failed-control mutations select an actually unanswered operation instead of
  corrupting an earlier timed-out operation's later successful reply. PREPARE,
  SELECTED and FUTURE_RETENTION_INTENT mutate their existing authority field;
  none may acquire an extra wire field.
- Competition replay explicitly admits the observed discovery-only shape:
  original START/ROUND_BEGIN, delivered bootstrap STATUS prefix, no local
  reservation/grant, then an independently replayed higher remote grant and
  close/drain. Full physical, publication, network and export validation still
  precedes branch selection. Six copied-claim negatives supplement the 20
  applicable export and 12 lifecycle negatives. They are not native faults.

The coverage catalogue hash changes with the corrected negative vectors and
the new explicit branch. The acceptance plan, original workloads, Required
workflows, runtime Java, timing limits and retry counts are unchanged.

## Verification and remaining work

Local replay uses unchanged downloaded originals. The retained INTENT original
passes all 157 network negatives, FINAL passes all 41 retention negatives, and
competition passes the complete discovery-only chain and 38 negatives.
The previously failing Joining group-062 history passes its complete original
authority chain and the specific retired-source negative. Both special
joint-floor originals pass complete physical/network/floor/ledger replay. A third
joint-floor original passes that chain and the corrected child-request negative.

The three native deadline failures remain a separate investigation. Two retained
traces show PUBLISH retry exhaustion while reverse transfers were still making
progress; the third stops waiting for the restarted process to become ready.
Neither a deadline message nor a successful retry establishes GitHub scheduling
as the cause. Failed original runs remain failed and cannot qualify by replay.

All three unchanged native fixtures passed targeted local diagnostics with two
active JVM processors: DATA APPLIED (with JFR), higher-ballot restart, and
cleanup-kill including the second process. These local OpenJDK runs are diagnostic,
not the pinned hosted cohort, and do not establish a latency guarantee or repair
the hosted failures. A fresh hosted execution must still produce a successful
original before replay; preserve the failed attempts for comparison.

The Python suite ran 4,708 tests: 4,707 passed and one old three-branch catalogue
assertion failed. After adding the fourth explicit branch to that assertion,
the final 151-test affected suite passed. The selector audit, changed-document
links and whitespace checks passed. The initial sandboxed native attempt failed
to bind a loopback socket; the approved local TCP diagnostics above followed it.

Local API records, original ZIPs, hash inventory, replay outputs, test logs and
diagnostic recordings are retained under
`target/v53-action-review-373da301/`. Signed artifact download references there
are temporary local transport data and must not be published. Corrected-source
hosted qualification and the existing maximum-host/coverage obligations remain
open; this review does not close Phase 3.
