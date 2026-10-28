# V5.2 one-batch negative-quota continuation

This is the operator-authorized exception `negative-quota-20261028`, solely for
this unfinished V5.2 cloud batch. It is not a new ordinary acceptance policy.
The normal `verify-set` JSON map still requires one exact source/build/sequence.

## Frozen originals and remaining work

[quota-continuation.json](quota-continuation.json) pins ten exact successful
original invocations, requests, GitHub artifact IDs/digests, completion,
manifest and cleanup hashes. These are all nine canonical shards and
`failure-drill-m02-below` on source
`f6d7aad945b59e2c69989d4da7fd4b814080b7bf`, sequence
`c3843899543949178ab16475342368cf`.

The remaining executions, in any order, are:

- `failure-drill-m02-equal`
- `failure-drill-m02-above`
- `failure-drill-m03`
- `failure-drill-m04`
- `experiment`

They must share one clean corrected master source, one build/input package and
sequence `87900804eccc4769a000f0a7dd1e53ff`. Prepare on that merged source after
its exact-source Cloud Build and recent manual cleanup. Prepare/run commands,
explicit confirmations, environment approvals, whole-history boundaries and
resource ownership remain unchanged. Drill shards use the hosted route;
experiment and final verification use the existing self-hosted route. Never
reuse an old prepared plan on the new source or rerun a successful inherited
invocation in place of its pinned original. Failed attempts and cost entries
remain in the ledger. Existing soft time/cost budgets are unchanged.

## Explicit acceptance entry

Run the existing `V5.2 Replication Runner` with `operation=verify-set`,
`execution_host=self-hosted`, and this **explicit envelope**, replacing the
illustrative map with all fifteen real selections:

```json
{
  "continuation": "negative-quota-20261028",
  "selected": {
    "canonical-1-legacy": {
      "requestSha256": "f0b68f141e5e9ee3a89226efebe53e2c7d71eca881cffd2adedc4a83ac02afc0",
      "runId": 40264837271,
      "runAttempt": 1
    }
  }
}
```

The illustration is intentionally incomplete and will be rejected. Construct
`selected` from the ten pinned originals and the five verified new results;
never invent missing request/run IDs. The validator rejects missing members,
substituted originals, duplicate attempts, different new sequences/builds and
unknown continuation IDs before expensive replay.

The corrected checkout must contain exactly the approved support-file bytes
and otherwise reproduce the old complete tracked tree (paths, modes, object
identities). This works with Actions' shallow checkout and requires no extra
Git history/network access. The policy core is pinned separately from approved
support-file hashes, avoiding self-referential hashing. Runtime Java, tests,
POMs, measurement programs, suite, provider/configuration and workflow bytes
cannot change through this entry. Approved Python regression tests for this
exception are explicitly included in the support inventory.

All fifteen original requests retain their own real source/build/sequence.
GitHub provenance checks the original producing source and exact attempt while
separately checking that today's master is the new verification source. Original
GCS generation/hash/context checks, terminal ledger prefixes and cleanup joins
remain required. All original histories and negatives are replayed; every
member's authenticated inputs must contain the same five frozen JAR byte
hashes. Resource, boot, history and invocation reuse still rejects. No evidence
is relabelled as having run on the new source. All M01 histories remain on the
original source, so the statistical cohort reducer is unchanged.

Only the complete native join can emit `fullRemoteQualification=true`. It
explicitly carries `continuation`, both original source identities/sequences,
and all fifteen `originalBindings`; the Actions summary exposes this exception.
Partial replay, copied receipts or matching JAR hashes alone cannot qualify.

## Observed build comparison

Old Cloud Build [40260967111/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40260967111)
and quota-only corrected Cloud Build
[40645358757/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40645358757)
(source `0b8b855a87c8961b6dff8e506fda2509265e393c`) produce byte-identical
candidate core and replication JARs:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| core 5.2.0-SNAPSHOT | 860591 | `de616058e56b5c8534257a71a048ebb4a8b671b086e920e1020d8b908c6803c0` |
| replication 5.2.0-SNAPSHOT | 611559 | `6d7150e5d604fe7d321ddbb0c61ffedd2a46abde112e72efb279b8d469796b47` |

The new original artifact ZIP digest is
`5f0d423b5f1b0e48de73e893f75344a40a52dc2aae5105f07eebbc0c8dff1fdd`.
It was checked against authenticated GitHub metadata, exact source/attempt,
successful Java prerequisite steps, archive inventory and all member hashes.
The three published controls were checked from the retained original package
against the unchanged published-control manifest. Their pins are in the policy.
Build manifests themselves differ because their source/checkout identities
must differ. This comparison covers the **quota-only baseline**, not the future
merge of this verifier. That merge still needs its own exact-source build;
every final member replay enforces these same JAR pins again.

## Validation and rollback

Run `python3.11 -m unittest scripts.v52.test_cloud_quota_continuation` plus the
existing cloud acceptance, provenance, object restoration, set/member evidence
and operator suites. Synthetic tests establish validator behavior only; they do
not substitute for the five remaining paid executions or complete native replay.

Rollback is to stop using the explicit envelope and revert these support changes.
Ordinary acceptance remains strict. Never rewrite the ledger, original source,
sequence, retained objects or frozen successful invocations to manufacture a
single-source cohort. Any runtime/configuration/measurement change requires a
new complete cohort rather than extending this exception.
