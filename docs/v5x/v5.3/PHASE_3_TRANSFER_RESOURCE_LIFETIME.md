# Phase 3 — observed native reply resource lifetimes

Phase 3 remains **OPEN**. The existing 48-case
[reply revocation matrix](PHASE_3_TRANSFER_REPLY_LIFETIME.md) now captures and
independently checks storage/control accounting at actual TCP and handler
boundaries. This adds no experiment histories or hosted execution groups.

## Original observations and independent derivation

The Java producer records `transport-resources.json` in each original case.
Each row belongs to one exact request/reply and its client or server boundary.
The capture reads the resource owner's usage without changing runtime admission,
fault clocks, deadlines, retries or protocol behavior. The complete matrix
receipt is now `gse-v53-transfer-reply-lifetime-v2`; old v1 evidence lacks these
observations and cannot supply this scope. Historical receipts remain retained.

[`transfer_reply_resources.py`](../../../scripts/v53/transfer_reply_resources.py)
runs after the existing original bootstrap, source, force, frame and revocation
replay. It derives the storage baseline from the actual current generation and
original PROMISE-source files, including both separate application copies and
the existing journal/miscellaneous reservations. A reported baseline is compared
to that derivation; it is not used as the expected value.

The reader reconstructs the following CONTROL reservations from original record
and wire lengths:

| Observed boundary | Required live charges above original storage |
| --- | --- |
| Client before request write | The encoded outgoing request |
| Server after request read | The received request and existing service/session/cache state |
| Service before returning a materialized reply | The received request, service registry, trace marker, original record export, source session and retained reply |
| Server before response write | The same state plus the independent outgoing reply buffer |
| Client after response read | Both outgoing request and received reply |

Once the final commit is materialized, the export/session/reply leases have
closed and one completion marker owns the cached decoded reply. An identical
cached retry must not recreate the export or charge it again. After revocation,
both retry probes still reserve their real TCP frames but cannot revive the
service. Owner-close also removes the storage baseline; service-close, expiry
and higher-ballot revocation keep the live owner's original storage charged.

Every observed metadata/staging/queued total, lease count and category count must
match. The returned queue maximum is the **maximum of these observed boundaries**,
not a claim about all allocations or the whole runtime peak. The model uses the
declared reservation contract, not a measurement of JVM heap consumption.

## Admission and negative checks

The original 30 negatives remain. Fourteen additional mutations reject missing
or foreign observations, incorrect request/reply charges, an invented storage
baseline, premature storage release, duplicate completed-export charges, boolean
counts and resources retained after owner-close. Each mutation must produce its
exact declared reason after an unchanged original passes; unrelated original
failure cannot count as a successful rejection.

The existing automatic-history local and hosted aggregate now require resource
results for all 48 cases, exact boundary counts and the complete 44-negative
reply vector. Depending on the already supported competition shape, the complete
three-group vector has 156 or 221 negatives. Source/build/reader/run/attempt
binding and the existing whole-history grouping remain unchanged. This is an
extension of the existing adapter, not a new hosted feature or a weaker fallback.

The [development receipt](phase3-evidence/transfer-resource-lifetime.json) records
the native execution, original inventory, reader qualification and local checks.
The initial sandbox-denied socket attempt is retained separately and supplies no
successful native cases. No paid cloud or hosted workflow is dispatched.

Reproduce from a recorded source/build:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtest=V53TransferReplyLifetimeTest test
python3 -B -m scripts.v53.transfer_reply_lifetime "$ORIGINAL" --qualify
```

This covers native PROMISE export boundaries at stable sizes 3/4/5. Other export
kinds, acquisition/publication overlap during full membership transitions,
simultaneous physical maxima, and final-source phase admission remain open.
The twelve hosted subsets and 544 planned histories are unchanged. Rollback
reverts the producer/reader/aggregate version together; v1 must not be described
as passing the new resource scope.
