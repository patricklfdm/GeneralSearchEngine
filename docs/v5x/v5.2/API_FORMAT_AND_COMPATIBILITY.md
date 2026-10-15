# V5.2 API, token format and compatibility

**Status:** design candidate, revision 0.1. These are proposed declarations;
no Java/API/version/format implementation is delivered in Phase 0.
See [contract](PHASE_0_CONTRACT.md) and [lifecycle](READ_AUTHORITY_AND_LIFECYCLE.md).

## Exact additive inventory

All six new top-level types are in
`io.github.patricklfdm.generalsearch.replication`, in the existing optional artifact.
Ordinary record constructors/accessors/equality and enum compiler methods are
implicit. No convenience factories, extra public constructors, setters or public
implementation classes are included. Standard imports are `List`, `Optional`,
`UUID`, `CompletableFuture`, `Function` and the existing core query/result types
shown in `SearchEngine.java`. K/T match the owning automatic handle.

```java
public enum ReplicaReadPolicy {
    LEADER_STRONG, STALE_ALLOWED, AT_LEAST_INDEX
}

public record ReplicaReadToken(
        int version,
        ReplicationGroupId groupId,
        UUID historyId,
        String manifestDigest,
        long index) {
    public byte[] encode();
    public static ReplicaReadToken decode(byte[] encoded);
}

public record ReplicaReadOptions(
        ReplicaReadPolicy policy,
        Optional<ReplicaReadToken> minimum,
        int waitTimeoutMillis) { }

public record ReplicaReadResult<R>(
        R value,
        ReplicaReadPolicy policy,
        ReplicaReadToken progress,
        long applicationSequence) { }

public interface ReplicaReadView<K, T> {
    T get(K id);
    List<T> search(Query<T> query);
    List<SearchHit<T>> searchTopK(RankedSearchRequest<T> request);
    SearchResult<T> search(SearchRequest<T> request);
    HighlightedSearchResult<T> search(HighlightedSearchRequest<T> request);
    Optional<SearchExplanation<T>> explain(SearchRequest<T> request, K id);
    long currentSequence();
}

public final class ReplicaReadException extends RuntimeException {
    public enum Reason {
        INVALID_TOKEN, UNSUPPORTED_TOKEN_VERSION, INCOMPATIBLE_HISTORY,
        PROGRESS_NOT_REACHED, VIEW_NOT_ACTIVE
    }
    public ReplicaReadException(Reason reason, String message);
    public ReplicaReadException(Reason reason, String message, Throwable cause);
    public Reason reason();
}
```

Add exactly one **default** method to `AutomaticReplicatedSearchEngine<K,T>`:

```java
default <R> CompletableFuture<ReplicaReadResult<R>> read(
        ReplicaReadOptions options,
        Function<ReplicaReadView<K, T>, R> reader);
```

The default implementation validates non-null arguments and returns a failed Future
with `UnsupportedOperationException`; it never simulates the capability through
old strong methods. Existing third-party implementers need no new abstract method.
The GSE implementation overrides this only in the later public enablement phase.
Phase 1's GSE handles also reject before resources/side effects. `read` does not
exist in the published V5.1 interface; new callers need aligned V5.2 artifacts.

`ReplicaReadView` deliberately does not extend `SearchEngine`, `AutoCloseable` or
`DurableSearchEngine`. It has no mutation, maintenance, paging, metrics or lifecycle
methods and cannot expose the underlying engine. Schema/field construction and
diagnostics use the existing owning handle's metadata/status APIs. Old methods,
records, reason enums, constructors, constants and return types remain unchanged.

## Validation and call contract

| Input / method | Required behavior |
| --- | --- |
| Token constructor | Non-null identity/digest; version exactly 1; digest exactly 64 lowercase hex characters; nonnegative signed-long index. Do not narrow to current runtime's int position. Bad shape uses INVALID_TOKEN; other version uses UNSUPPORTED_TOKEN_VERSION |
| Options constructor | Non-null policy/Optional; AT_LEAST_INDEX requires a token and wait in [0,60000] ms. Other policies require empty minimum and wait=0. Null uses NullPointerException; invalid combinations/ranges use IllegalArgumentException |
| Result constructor | Non-null policy/progress, sequence >=0; value may be null (`get` miss or caller callback). A caller-constructed result is not runtime evidence |
| Exception constructors | Non-null reason/message; cause may be null |
| `read` invocation | Returns promptly with a Future; does not run the callback inline. Null options/reader throws NullPointerException synchronously. Other admission/lifecycle failures complete the Future exceptionally |
| View methods | Invoke existing core semantics against one captured cut; original query/document/index errors survive. `currentSequence` equals result.applicationSequence |
| View lifetime | Only the invoking callback thread may use it while active. Every use after return or on another thread fails VIEW_NOT_ACTIVE before engine access; returning/capturing the wrapper does not extend its life |
| Callback failure | Preserve the callback throwable via exceptional completion, invalidate view/release once; do not retry callback or return a success token |
| Cancellation | Standard Future cancellation; before capture suppress invocation, after capture do not interrupt/close the live engine. Keep actual-work accounting until callback releases |

Typed tokens are immutable and may be transferred by callers; the runtime checks
them against verified authority even if constructed directly rather than decoded.
No token index alone authorizes any change. Requests with a compatible but impossible
large lower bound follow normal wait/reject behavior, with no allocation proportional
to that index. Requested positive wait is capped by the current operation timeout;
there is no new global timeout or modification to leadership timers.

After non-null/option validation, admission checks same-handle reentrancy, closing,
local startup/fatal/readable state, identity compatibility and then capacity. Capture
rechecks these conditions plus deadline and progress under the authority boundary.
For simultaneous later faults, report the condition observed at that boundary;
do not promise a universal ordering between unsynchronized events. Deterministic
tests freeze each isolated fault and its expected classification.

## Failure mapping

| Condition | Public error |
| --- | --- |
| Malformed token bytes/components | ReplicaReadException / INVALID_TOKEN |
| Structurally well-formed token with unsupported version | ReplicaReadException / UNSUPPORTED_TOKEN_VERSION |
| Group/history/manifest differs | ReplicaReadException / INCOMPATIBLE_HISTORY; reject without progress wait |
| Zero-wait minimum exceeds captured local position | ReplicaReadException / PROGRESS_NOT_REACHED |
| Positive progress wait or ordinary admission/capture deadline exhausted | AutomaticReplicationException / DEADLINE_EXCEEDED / NOT_APPLICABLE |
| Not started, campaigning or recovering | AutomaticReplicationException / NOT_READY / NOT_APPLICABLE |
| Strong read on follower / without quorum / fenced | Existing NOT_LEADER / QUORUM_UNAVAILABLE / STALE_EPOCH with NOT_APPLICABLE |
| Capacity, close, reentrant call, fatal storage/integrity | Existing appropriate AutomaticReplicationException reason with NOT_APPLICABLE |
| Escaped/cross-thread view method | ReplicaReadException / VIEW_NOT_ACTIVE |
| Unsupported implementation | UnsupportedOperationException in returned Future |
| Cancellation | CancellationException; no mutation retry inference |
| Core query/business or caller callback error | Original throwable; no token success or policy fallback |

The new exception has no mutation outcome field because none of its operations
submits an application mutation. Explicit strong reads still append a NO_OP and
consume inherited authority bounds; failure/cancellation does not undo it. Token
or read errors never make an earlier indeterminate write safe to replay.

## Token bytes, version 1

Token serialization is a **client value format**, not a replication frame or a
backup/storage authority. `encode` returns a fresh 112-byte array; `decode` accepts
exactly 112 bytes, copies it and validates without filesystem/network access.
No input-controlled length allocation, compression, JSON, trailing fields or
implicit Base64 parser is part of this API. An application may transport these
bytes using its own encoding, with its own bounded input validation.

All integer fields are big-endian. UUIDs are the existing 128-bit UUID value in
most-significant then least-significant 64-bit order. The following offsets are
half-open and exhaustive:

| Bytes | Content |
| --- | --- |
| [0,4) | ASCII `GSRT` (`47 53 52 54` hex) |
| [4,5) | Unsigned version byte, 1 |
| [5,8) | Three reserved zero bytes |
| [8,24) | GroupId UUID |
| [24,40) | Application history UUID from verified manifest |
| [40,72) | Manifest digest as 32 binary bytes |
| [72,80) | Signed 64-bit nonnegative replication index |
| [80,112) | SHA-256 of ASCII `gse-replica-read-token/1` followed by one zero byte, followed by bytes [0,80) |

`manifestDigest` is precisely the verified GSER 1.2 manifest's embedded record
digest (bytes [16,48) of that manifest frame), rendered in lowercase hex. It is
**not** SHA-256 of the entire manifest file; the existing frame checksum covers
its first 16 header bytes and body. This choice matches existing authority binding.

Decode precedence: null -> NullPointerException; wrong length/magic -> INVALID_TOKEN;
unsupported version -> UNSUPPORTED_TOKEN_VERSION; nonzero reserved bits, negative
index or checksum failure -> INVALID_TOKEN. Version dispatch happens before a
version-specific checksum rule. Exact identity comparison with a live replica
belongs to read admission, not decoding. No guessed UUID/history rewriting.
Unknown version is never converted to version 1.

The digest/checksum does not authenticate the caller: it can be recomputed. Tokens
express lower-bound constraints under the existing trusted-peer/client scope, not
certified provenance. Application-level read-your-writes claims require the actual
runtime issuance and happens-before chain; qualification records that chain.
Phase 1 produces independent Java/Python byte fixtures for this exact layout, plus
recomputed-checksum negatives. It may not alter this layout silently.

## Paging, queries and retained objects

All seven view methods observe the single cut; queries may reuse the handle's
canonical fields. Existing ranking, highlight, explanation, missing-document and
immutable-document requirements apply. Full query results retain caller-owned
document references according to the existing API; releasing the wrapper does not
invalidate already returned ordinary values. The library cannot bound memory that
the application chooses to retain or capture in a callback.

`SearchPageRequest` has no overload on the new view. Page operations on the original
automatic handle retain fresh-leader admission and current-snapshot cursor rules;
configured handles retain their own behavior. Calling the owning engine's page
method from inside its active explicit view is reentrant and rejects, not an escape
route. No page token is reinterpreted as a progress token or vice versa. Public
consumer compile-negative fixtures check the absent method; runtime tests check
old cursor continuity/invalidation and attempted nested access.

## Compatibility and migration

| Axis | Selection |
| --- | --- |
| Maven/core/processor | Same three artifacts and dependency direction; Phase 1 will align active coordinates to 5.2.0-SNAPSHOT after authorization |
| Published API | Old descriptors and semantics unchanged; old compiled consumers run against new JARs. Third-party automatic implementation fixture verifies default rejection |
| Automatic authority | GSER/GSRP 1.2 and existing manifest/genesis/entry/proof/snapshot bytes unchanged; no persistent reader state or extra message kind |
| Configured authority | Existing 1.1 factory, reads, replacement and consumers unchanged; no cast/adapter to explicit automatic reads |
| Deployment | Homogeneous qualified V5.2 build only. Same-protocol handshake cannot detect every mixed binary and does not qualify rolling upgrade |
| V5.1-to-V5.2 migration | Quiesce/resolve old work, fresh verified canonical backup, stop old group, new GroupId/three absent targets, strong-compare then cut over |
| Restart and disk loss | Retained V5.2 directory restart required; lost disk still needs reviewed new-group transfer. No in-place cross-minor/downgrade guarantee in this contract |
| Token retention | No automatic expiry or disk registry; new-group transfer invalidates old tokens even if application sequence is preserved |

Keep old volumes/backup until verification. Reopening the old group after new
writes is not rollback. A reverse transfer requires its own resolved backup/new
group procedure. Protocol sameness avoids unnecessary consensus changes but does
not invent upgrade evidence. Existing release inventories/hashes are immutable;
new release fixtures and consumers get new exact identities in their owning phases.
