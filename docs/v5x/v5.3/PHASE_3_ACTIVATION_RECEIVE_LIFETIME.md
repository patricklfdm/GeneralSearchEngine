# Native activation receive lifetime

Phase 3 and combined-resource qualification remain **OPEN**. This batch checks
the permitted lifetime behind the [retained pressure diagnosis](PHASE_3_COMBINED_RESOURCE_PROBE.md).
It does not make the diagnostic's externally held copies into native owners.

## Controller boundaries

`MembershipActivationDriver.run` selects complete original sources, waits for
the remote installation acknowledgements and installs locally last. Its round
then stops/drains peer tasks and closes their source pulls before returning the
selection. A failed drain retains the active round for external cleanup. The
result is cleared and the endpoint abandoned if cleanup fails.

`MembershipRoundDriver` calls this activation synchronously. Its `INSTALLED`
callback and subsequent slot therefore follow the receiving cleanup. It closes
the preceding activation before the next campaign. Stable readiness follows the
new configuration's published BARRIER, not merely local installation.

| Owner | Permitted overlap | End of receiving custody |
| --- | --- | --- |
| Activating voter | Selected incoming capsules, original local source, installed generations and their images | Selected pulls drain before activation returns; failed cleanup cannot return success |
| Maintenance voter | Original incoming copy and its replacement floor copy | Original copy drains only after the replacement and its parents are forced; the existing physical/floor readers bind this interval |
| Actual joining learner | Its received metadata/image and subsequent generation/source claims | The existing handoff reader follows atomic custody transfer on that learner; an old voter's artificially allocated LEARNER lease is not this role |

This table defines boundaries, not a global mutex or a proof that unrelated
endpoint work never overlaps. The 324 MiB metadata expression remains a
conservative reservation envelope. Independent maxima cannot be added to claim
one physically reachable owner state. The seven-image limit is unchanged.

## Regressions

[`V53ActivationReceiveLifetimeTest`](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53ActivationReceiveLifetimeTest.java)
uses the existing real bootstrap, journals, source pull/receive and resource pool.
For stable sizes 3, 4 and 5 it binds each selected capsule offer's transfer ID,
digest and byte length to the live SOURCE charge and actual `source.gscp` file at
the local installation cut. GENERATION, APPLICATION and receiving CONTROL charges
must coexist there; no LEARNER charge is manufactured. Successful return must
remove the receiving files and their charges while retaining installed authority.
These focused activation cases use asynchronous in-process endpoint delivery.

The cleanup fault adds an unexpected file to one receiving directory at that
same installation cut. Installation has already occurred, but `run` must fail
and `selection` must be unavailable. Repeated external close must retain both
the foreign file and original packet charge. Removing only the injected file
allows production cleanup to finish. The test compares the installed journal's
entire file inventory before and after cleanup; it never rolls back authority.

A separate real loopback TCP four-voter REMOVE history runs one native round
through all three activations, INTENT, FINAL and the stable BARRIER. All three
`INSTALLED` boundaries, all three slot starts and `BEFORE_READY` require the
parent's actual activation scratch to contain no retained receiving packets.
The existing complete physical/lifecycle reader independently replays its raw
history. This is a small EMPTY bootstrap, not a maximum-image or required-four
replacement execution.

## Acceptance boundary

These are controller lifecycle regressions and one scoped native continuation.
No production resource limit, runtime logic, frozen cohort, workflow or existing
failed original changes. Maximum byte pressure, the full required-four/learner
combination, final-source cohorts and the Phase 3 closing audit still require
their own complete originals. Large-host acceptance remains deferred until the
operator arranges a suitable environment.

The [development index](phase3-evidence/native-receive-lifetime-development.json)
records five new tests, three related existing regressions, 19 contract tests,
and the standard `4-REMOVE` physical/lifecycle replay. Deliberately skipping
successful activation cleanup makes all three stable-size tests fail at their
drain check; temporary mutant bytecode was restored exactly. The initial
assertion correction and historical-replay mismatch remain recorded alongside
the passing results.

Local commands, logs, raw-history paths and hashes are also retained in
`target/v53-native-receive-lifetime/validation-summary.json`. Replay the final
original with the explicit current-maintenance profile:

```bash
python3 -m scripts.v53.transition_round_evidence <original-directory> --profile 4-REMOVE
```
