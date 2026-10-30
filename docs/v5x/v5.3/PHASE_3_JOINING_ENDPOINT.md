# Joining endpoint ownership and voting handoff

The following describes the endpoint-handoff increment. The subsequent
[owned initialization](PHASE_3_JOINING_INITIALIZATION.md) now makes promotion
private and provides the managed `initialize(hint)` entry; its final-source
validation is recorded separately.

Phase 3 remains **OPEN**. `MembershipJoiningEndpoint` replaces the test-only
joining listener with an explicit production lifecycle component. It does not
implement the complete autonomous coordinator or expose public READY.

A fresh endpoint requires the actual unused native joined owner and its original
resource pool. It serves only STATUS and bounded current-prefix/generation reads
for exact old identities at the original JOINT cut. STATUS remains not-ready.
PREPARE and other voting requests, arbitrary record aliases and altered identities
are rejected before observing a ballot. The original preparation guard, cut and
deadline are checked before and after reads. Existing transfer limits and exact
retry handling remain unchanged; expiry does not renew an initialization. The
owning runtime must still close/poll this explicit scope when idle or expired.

Acquisition and initialization remain separate existing operations. `activate()`
first requires the original forced completion marker and all three recovered,
validated retention ledgers. An early call leaves the read-only service intact.
It then stops new dispatch, closes the read-only transfer service, waits for
entered calls to exit and opens the ordinary typed activation endpoint. An old
handler cannot return through the dispatcher after switching. A read-only reply
already returned to the transport may finish writing; it carries no voting
permission and is not claimed to have been revoked at the socket send boundary.

The dispatcher reserves 4096 bytes of existing CONTROL capacity. A close, drain
or factory failure prevents serving; failed cleanup keeps references and charges
for a subsequent explicit close. Close racing with factory creation closes the
returned child instead of publishing it. Cleanup waits use the existing request
timeout, without changing the acquisition deadline or frozen bounds. ACTIVE uses
the ordinary endpoint's per-campaign deadlines; becoming ACTIVE is not an
application-readiness assertion and cannot bypass PREPARE, selection, proof,
publication or fresh BARRIER.

Cold `resume()` requires the actual retaining joined owner and its original
completed initialization. Missing, partial or conditional history cannot start a
voting endpoint or fall back to empty ledgers. Each dispatched active request
also checks that the original completed initialization and recovered ledgers
remain available; the ordinary endpoint performs current-view protocol checks.

The native test
`V53JoiningIntentExportTest#actualJoiningVoterAcquiresRetentionOverTcpThenCompletesFinalAndBarrier`
now uses this fresh read-only service while preparing the old majority, performs
the original network acquisition and durable initialization, and promotes the
service. After original cold reopen it uses the same production resume entry for
actual new-voter FINAL and fresh BARRIER participation. This complete history is
compiled but **not executed in this batch**. It must remain one original history,
not independently run setup/initialization/continuation shards.

Final-source focused validation passed **41 tests in 142.180 seconds**, with no
failures or skips: six lifecycle tests, four read/admission tests, five network
acquisition tests, eight old-majority preparation tests, two durable initialization
file tests and sixteen existing transfer-service regressions. The first run's
malformed PREPARE test fixture and the second run's integration-test local-name
compilation error are both retained; neither is presented as a passing run.

Validation results and source/archive hashes are in
`phase3-evidence/joining-endpoint.json`. The focused tests distinguish conditional
read/protocol fixtures from lifecycle-only dispatch tests. They do not establish
native promotion, process-death recovery, an availability SLA or complete Phase 3
acceptance. Native whole histories, all add/replace profiles, maximum combined
resource use, physical replay, process-death and autonomous inter-owner scheduling
remain in [deferred acceptance](PHASE_3_DEFERRED_ACCEPTANCE.md).

No public API, wire/storage format, resource/timing bound, workflow, POM or V5.2
experiment changes are included. No hosted or paid cloud run is triggered.
