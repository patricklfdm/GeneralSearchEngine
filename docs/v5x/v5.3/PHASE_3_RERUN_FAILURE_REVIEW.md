# Phase 3 rerun review: defd80d2

Status: **OPEN**. These are attempt-1 results at
`defd80d258845a4965fb1a51d9073f5cd8c8a409`, inspected on 2026-11-12.
They are separate from the [5217a556 expansion](PHASE_3_EXPANSION_FAILURE_REVIEW.md).
Local repairs cannot change an original run's conclusion or qualify a different
source/attempt. No Phase 3 completion is claimed.

## Complete observed runs

The API snapshot includes all pages of jobs and artifacts for all nine runs
(416 jobs), including failed/cancelled jobs and downstream failures.

| Family | Run | Result |
| --- | --- | --- |
| Joining reply loss | [43123624778](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123624778) | PASS, eight jobs. |
| Round histories | [43123647228](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123647228) | PASS, sixteen jobs. |
| Joining processes | [43123587436](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123587436) | All 120 original groups passed. Replay: 80 groups passed, 35 cancelled, five failed. Aggregate failed. |
| Joint-floor processes | [43123675932](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123675932) | 31 originals passed; one wrapper initialization failed. All 31 available replays failed the same reply-shape check. |
| Node renames | [43123631252](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123631252) | Four original failures; no complete qualifying replay. |
| Learner histories | [43123639693](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123639693) | Alternating-slot original deadline; retained cancellation original and replay passed. |
| Carried DATA | [43123653230](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123653230) | Ten original/replay pairs passed; data-proof exchange deadline, data-applied wrapper initialization failure. |
| Carried transition | [43123661360](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123661360) | All sixteen originals passed; fourteen replays passed. Basic INTENT/FINAL legacy transcripts lack caller-terminal association. |
| Automatic | [43123668648](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43123668648) | Reply-revocation passed. Competition original passed, replay rejected a losing local-only grant; restart original hit an exchange deadline. |

Joining's 35 cancelled replay jobs explicitly report GitHub's six-hour job
limit. Group 009 failed with a cancellation annotation but no equally specific
timeout annotation; its precise cause remains unproven. The other four failed
groups retain actual validator errors: 044, 094 and 105 reject a current-generation
interval; 073 rejects an abandoned offer boundary. Partial successes inside a
failed/cancelled group do not make that group green.

## Current repair batch

* Joint-floor accepts the producer's existing connection format by independently
  matching socket identities and complete observations. Parent `NETWORK_*`
  callbacks and scoped child callbacks use the shared normalizer. Withheld,
  undelivered, mixed-format and failed attempts still reject. Metadata is not
  stripped to simulate legacy evidence.
* A current-prefix request can arrive before a synchronized same-cut install
  completes. The reader now distinguishes that initial receipt from the first
  offer. Only a complete physical predecessor edge with unchanged permanent
  identity/root/cut can admit the **new** generation's exact bytes. Old-generation
  chunks cannot cross revocation; owner restart or missing selector evidence
  cannot supply an edge. Packet-only maintenance lookup does not become a
  learner retention permit.
  STATUS discovery uses the same proven install boundary and remains a hint:
  it does not grant readiness or retained-copy credit.
* Revoked first offers use the same independently derived alias/content catalogue
  as completed transfers, including packet-only offers. They retain content
  kind/hash, zero received bytes and zero committed objects. The process summary
  requires exactly one authenticated offer for every excluded offer-only session;
  neither missing content nor an unrelated failed transfer is silently excluded.
* Hosted Joining verification uses the existing three-process pool for independent
  authority mutations. Complete original validation still precedes all mutations;
  each worker has its own copied evidence. The three original histories per group
  remain sequential and indivisible. All 150 slots per history, 360 histories,
  physical/transaction checks and final exact-attempt aggregation remain required.
  This reduces serial CPU work; the next hosted execution must establish actual
  job duration. It is not a promise that every environment meets six hours.
* Maven wrapper initialization retains bounded stdout/stderr and exit/timeout
  details before a producer directory exists. Only explicitly recognized transient
  failures of a **completed** `mvnw -version` bootstrap retry, at most three
  attempts with two/four-second pauses. Timeout, checksum, authorization,
  certificate, configuration and unknown errors stop immediately. No reactor or
  native history retries are introduced; URL credentials/query strings are redacted.
* Basic carried INTENT/FINAL now record complete per-connection transport
  observations. The reader requires that format and retains all existing
  negatives, with connection-specific rejection reasons. Terminal mutations
  target the exact socket; an excess-attempt mutation uses distinct connection
  identifiers so it reaches the attempt bound rather than a duplicate-observer
  guard. Four additional metadata mutations per original raise this subset
  from 3,914 to 3,922 exact negatives. The fourteen process adapters are unchanged.
* Competition now has an explicit third original-derived branch: one local
  grant, no remote grant or SELECTED, three unanswered PREPAREs to one peer,
  then one delivered higher-ballot rejection from the other. Original lifecycle
  anchors, durable higher promise, bytes, sequence, full response coverage and
  complete physical/export replay are mandatory. Unanswered requests give no
  vote or installation credit. Seven loss/physical mutations plus twenty export
  and twelve lifecycle mutations qualify this branch. Other shapes still reject.
* Automatic restart already permits an original without a third, unused-source
  pull. Its negative driver now derives that fact from complete original replay,
  explicitly records `current/unused-offer-bytes` as not applicable only when
  there was no such transfer, and preserves the other 72 negatives. An original
  with the transfer still requires all 73. Missing or malformed derived counts,
  omitted applicability records and invalid original evidence reject; absence
  does not count as a successful mutation rejection.

The unchanged competition artifact `13903210615` passes that complete chain and
all 39 exact negatives. Two new local INTENT/FINAL native originals passed once
in 451.8 seconds total and both pass the complete original physical/network/
export/ledger/retirement/prefix chain. Their original bytes and failure-oriented
negative diagnostics are retained under `target/v53-run-ready-repair/`.
Old missing connection observations are not reconstructed.
The final mutation diagnostics cover all 157 network cases for each new original;
they do not replace the hosted complete-suite receipt.

Production Java, history/request deadlines, frozen capacity limits, native
measurement attempts, workflow job counts and the removed matrix parallel caps
are unchanged. There is no paid-cloud execution in this repair batch.

## Separate latest master nightly

[43278888197](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/43278888197)
is a scheduled master run at `1216bc9e87fd6cc0ce96c44903864a882950035e`,
not one of the V5.3 reruns above. Three jobs failed:

* V5.2 installed runtime retains a concrete `FileNotFoundError` for
  `/usr/sbin/chroot`. The shared qualification helper now locates `chroot`
  only in fixed system bin/sbin directories, before changing fixture ownership
  or mounting anything. It never searches the operator's inherited PATH.
* V5.1 provider adapters failed while establishing the root-helper clock.
  It uses that same helper, so the path issue is a plausible shared cause;
  its retained error does not independently identify the missing executable.
  Local root installation and lifecycle qualification passed after the change.
* Owned canonical repetition 1 failed during healthy candidate workload:
  node 2's UPDATE, ordinal 82/cycle 8 in `instrumented-a`, returned
  `INDETERMINATE / QUORUM_UNAVAILABLE` (`timedOut=false`). Repetitions 2 and 3
  passing do not establish a scheduling cause. This failure remains open.

The chroot correction affects local qualification infrastructure, not guest
production code. Eight V5.2 isolated-root storage cases and eleven V5.1 root
receiver cases plus three controller lifecycle cases passed locally. Their
metadata, accounts and block devices are modeled; no real cloud device was written.

## Retained evidence and validation boundary

The ignored directory `target/v53-rerun-review-defd80d2/` retains paginated API
responses, job annotations, 87 small failure/diagnostic artifacts, selected
original bundles, archive/manifest hash checks, before/after local replay logs,
and test logs. `raw-index.json` locates unpacked originals. Original archives
and failed receipts have not been overwritten. Diagnostic downloads include
ephemeral URL metadata and should not be committed wholesale.

The corrected joint-floor reader replays unchanged artifact `13903692583`
through physical, network/export, maintenance, peer, learner, future and ballot
checks. This is one original replay, not its entire negative catalogue or the
32-member hosted qualification. Original Joining replays and selected parallel
negatives are recorded separately in the local validation summary. Synthetic
regression checks do not replace native observations.

All four Joining originals that produced validator errors in groups 044, 073,
094 and 105 now complete the physical/export/control/maintenance/ledger replay
using their unchanged retained bytes. These diagnostic readers deliberately
return `PARTIAL`: process-death qualification and the entire negative catalogue
are still required. The hashed receipt index is
`target/v53-rerun-review-defd80d2/validation-summary.json`.

The final complete V5.3 Python suite passed 4,698 tests in 219.755 seconds;
the two system-tool discovery tests also passed. Fixture updates
also align existing unselected-capture, size-4/5 voter and transport-observation
tests with their actual producer contracts. Six selected authority mutations
passed with three workers against an unchanged original; that selected subset
does not qualify the complete 150-slot negative catalogue.

Five local native test methods passed: basic carried INTENT/FINAL, automatic
higher-ballot restart, and carried DATA PROOF/APPLIED. The last three passed
their complete original replay and respectively 72, 32 and 33 exact negative
cases; automatic restart explicitly reports one inapplicable unused-source
mutation. Native history and exchange deadlines were not changed. This supports
another diagnostic execution, not a claim that the earlier deadline mechanisms
were fixed or that hosted timing will match local timing.

The source coverage inventory and documentation contract pass; the latter
checks 3,248 local links. Logs, original identities and hashed receipts for this
additional validation are retained at
`target/v53-run-ready-repair/validation-summary.json`.

## Still open; do not blanket-rerun

Node-renames' duplicate `applied-3` snapshot needs occurrence/activation-aware
capture **and** independent replay, not overwrite or ignore-on-exists. Its other
deadline failures and the learner deadline still need native diagnosis. The
carried-DATA proof and automatic restart probes passed locally, but neither a
runtime root cause nor GitHub scheduling has been established for their earlier
deadlines.

The carried-DATA, automatic restart and alternating learner entry points retain
transport timing/failure diagnostics on their next original execution. This
adds observations only, not retries or relaxed native/request budgets. Local
successful probes cannot establish the root cause of previous deadline failures.

Node renames and the alternating learner are held from this repair dispatch.
The duplicate snapshot needs an occurrence-aware capture **and** the independent
carried-BARRIER recovery model; changing a filename alone would merely move the
failure into replay. A six-revision learner deadline cannot be excused by a
passing short component. These are still open, not omitted from final admission.

This dispatch is limited to Joining processes, joint-floor processes, carried
transition histories, carried DATA histories and automatic histories. Each is a
fresh source-bound execution; passing reply-loss and round-history runs are not
needlessly repeated in this diagnostic batch.

Keep this batch's verified fixes separate from those remaining investigations.
Fresh source-bound hosted qualification is still necessary after capture changes;
diagnostic replay of old evidence does not merge sources or erase failures.
