# V5.2 Phase 6Q minimum-wait and saturation evidence

**Status:** independent member and portable replay locally qualified. Formal M02/M03 runs still
require the complete machine freeze; member acceptance does not close Phase 6.

## Complete closed histories

The validator binds the exact [controller profile](PHASE_6_MINIMUM_CONTROLLERS.md),
read-parameter file, source/build/attempt, retained artifact and compiled consumer
hashes, actual JVM identity and three clean process exits. M01 shares only the
artifact/metadata identity implementation; its profile and default-parameter rules
stay unchanged.

Before reconstructing protocol authority, the checker validates the complete
offered ledger and aggregate evidence bounds. It then runs physical quorum/force,
chosen-application projection, durable publication, public consumer lifetime,
ownership and actual published-V4.4 query replay. An invalid original is never
used to claim successful negative qualification.

Every setup read/update, declared measured read, excess request and progress write
has one original identity and outcome. Hidden business calls, partial dispatch,
changed queries/targets/minima and shortened observation reject. Resource START/STOP
samples must match original controller responses and cover the whole offered
interval. CPU/allocation statistics remain process-wide observations including
observer work; sampled maxima are not exact peaks.

## Independent gates

- The lower bound preserves the setup token's domain and has the exact declared
  below/equal/above index relative to the target's physical publication.
- Baseline recovery-floor hints must match actual earlier events and independently
  decoded local/peer source packets with identical snapshots and distinct voters.
- The baseline and admitted probe counts must equal reconstructed admission events.
  All original requests must be admitted after preparation and before the gate,
  while the target remains at the declared publication cut.
- Zero-wait `PROGRESS_NOT_REACHED` requires settlement below the minimum and no
  captured view. Positive-wait failures remain in their original ledger and latency
  groups. M02 success cases require all five query families to have successful
  observations, preventing an all-failed window from passing as coverage.
- M03 requires all R original waiters to remain pending until the write invocation,
  exactly one reserved slot at both gates, the observed excess rejection, and
  successful original waiters/writer. The progress write must be the next chosen
  entry, at application sequence 5; unrelated NO_OP progress cannot substitute.

Controller and JVM durations are reported separately. Success/failure and
read/excess/write distributions never mix clock origins or discard a failed call.

## Portable replay and negative qualification

The bounded archive retains one complete history. Existing inventories are checked
before packing so changed bytes cannot be silently rebaselined. Original and
relocated replay must have identical complete results and the exact declared list
of rejected mutations, including each reason. Failed replay retains its archive,
extracted input and failure receipt. No downloaded voter is resumed.

Negative coverage includes missing offers, hidden business calls, changed response
or bound, forged query answers, premature gates/progress, fabricated admission/floor
counters, missing proof forces/generation bytes, fabricated resource samples,
premature permit release, changed waits and the missing reserved slot. These
logical mutations follow decoding and inventory verification; they supplement
archive/hash/format rejection tests rather than replace them.

## Validation boundary

Ten deterministic tests cover all eleven complete schedules, the declared metadata
negatives, query coverage, excess/failed-writer substitution, profile/configuration
agreement, early evidence-budget rejection, invalid originals, portable-result
drift and changed pre-existing inventories. The existing M01 identity/set tests
also pass. The prior eleven development histories remain on their original
controller source; replay does not relabel them as formal measurements or rerun
their workload. Logs and receipts are retained under `target/v52-minimum-evidence`.

All eleven retained histories pass complete original and relocated replay, with
320 exact negative rejections across 22 locations. The histories retain 350 reads
(318 successes, 30 zero-wait rejections and two excess-capacity rejections) and
37 successful updates; actual V4.4 query replay validates every successful query
cut. The complete replay took 216.514 seconds locally; it is validation overhead,
not workload latency or a hosted CI estimate. All 188 V5.2 Python tests, the CI
inventory, documentation contract, changed local links, shell syntax and whitespace
checks pass. This Python-only stage does not rerun the reactor or infer hosted
acceptance from the prior controller validation.

M04, the exact machine freeze, fresh formal M01–M04 histories and a complete
same-source measurement set remain open. No runtime Java, workflow topology,
production default, paid run or push is changed by this evidence stage.
