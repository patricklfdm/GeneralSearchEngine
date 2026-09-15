# V5.0 API, artifact and compatibility policy

- **Status:** Accepted Phase 0 policy
- **Published predecessor:** `4.4.0`

## Compatibility direction

The [public-admission API amendment](PUBLIC_ADMISSION_API.md) is a review candidate
for explicit additive declarations and the unpublished V5 protocol constant change.
The [associated contract](PUBLIC_ADMISSION_CONTRACT.md) proposes separate replicated
`1.1` bytes. Neither inventory nor format fixture is changed by that documentation PR;
the accepted Phase 1 declarations remain the current implementation baseline.

V5 is a new major line, but replication is additive and opt-in. Existing
`SearchEngine`, `DurableSearchEngine`, `general-search-engine` and
`general-search-engine-processor` behavior remains the V4.4 oracle. V5.0 does not
silently make `build()`, `buildDurable()` or a V4 directory replicated.

Phase 1 must compile clean published-style V3, V4 and V5 consumers. Japicmp/API
inventory gates continue for the existing artifacts even though semantic-versioning
would permit a break. Any unavoidable break requires a separate explicit contract;
none is authorized by Phase 0.

## Artifact boundary

The replication capability is frozen as optional artifact:

```text
io.github.patricklfdm:general-search-engine-replication:5.0.0
```

It depends on the same-version core artifact. Core does not depend on replication or
its transport. The processor remains optional and independent. Changing this artifact
boundary or identity requires reopening Phase 0 review.

## Runtime/API capabilities to declare in Phase 1

The declaration-only fixture must represent:

- replicated engine/node lifecycle;
- immutable group/member/endpoint/storage/bounds configuration;
- group bootstrap plan/apply and independent inspection;
- configured-leader activation and role-aware admission;
- immutable replication status/metrics and classified exceptions; and
- asynchronous mutation/checkpoint/backup/close outcomes.

Production networking and storage are not enabled in Phase 1.

The Phase 1 candidate freezes both the top-level type inventory and the full declared
public/protected signature inventory: generic parents/interfaces, constructors,
methods, fields and constant values, ordered record components, enum values and
public nested types. Tests compare checked-in fixtures without regenerating them.
Inherited core declarations remain covered by the published-artifact compatibility
gate. Fixture regeneration is an explicit review step.

## Existing operation mapping

| Existing operation | V5.0 rule |
| --- | --- |
| add/update/remove | One replicated application entry |
| addAll/updateAll/removeAll | One atomic replicated bulk entry |
| createIndex/dropIndex | One replicated application entry |
| search/get/ranked/page/highlight/explain | Configured leader only, through AppliedIndex |
| currentSequence | ApplicationSequence, never LogIndex |
| checkpoint | Local committed-state maintenance; no application sequence |
| backup | Leader committed application cut; not replica authority |
| close | Stop admission, resolve accepted work, stop transport, force metadata, release ownership |

Follower application calls fail before enqueue with a stable role/unavailable
classification. No method silently forwards to the leader in V5.0.

## Backup, bootstrap and transfer separation

A V4-format application backup remains portable application state and may seed a new
group through offline bootstrap. It cannot join, repair or replace a member of an
existing group. Replica catch-up uses a group-bound replicated snapshot with log and
commit identities. This prevents application portability from becoming accidental
cluster authority.

## Unsupported compatibility claims

V5.0 supports no mixed V4/V5 cluster, rolling protocol upgrade, downgrade, live
in-place conversion, V5-to-V4 replica open or V4 tool mutation of replicated storage.
Independent header inspection may identify an unsupported replicated family without
opening or altering it.
