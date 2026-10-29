# V5.2 one-run experiment retention recovery

The operator authorized this exception on 2026-10-29, conditional on complete
collection and verification. It applies only to `experiment`, original GitHub
run `40809895634`, attempt `1`, source
`0cbcfbcb3bec76f4f751e9cf720e0df2adfcce27`, sequence
`87900804eccc4769a000f0a7dd1e53ff`, request
`994a402f4b8f255cfa8fa76118dee08c37f63937f9130049e7499f109ed7b7b6`.

All five original histories completed. The original retention GET exhausted its
30-second read deadline after 34 of 55 chunks had been uploaded. The job,
completion object and ledger correctly remain failed. Exact-ID cleanup passed
for all thirteen resources and the lease was released. This exception waives
that one unsuccessful retention closure; it does not manufacture an original
successful job, completion, seal or ledger entry.

## Evidence and scope

The original GCS manifest (SHA-256
`894f601fa42c2b67abccf1bbe784de75e614bf26f187a0f8a47b58cd404b6309`)
already committed all thirty original files, 131,426,342 bytes. The self-hosted
completion hook preserved those files. Export and independent collection checked
every file and all 55 part hashes against that original manifest. An unmodified
local replay of original authority, artifacts and all five histories passed
(55 reads, 15 updates); the historical Java binding remains unchanged. That
diagnostic replay used the workstation Java 21 and is not protected final
qualification with the pinned Runner toolchain.

The recovery copies only missing chunks 34–54 using create-only generation
preconditions and validates exact bytes on read-back. Original chunks,
manifest, completion, cleanup, ledger and invocation records are never replaced.
The recovered chunks are supplemental uploads after the failed execution; their
contents were bound by the original manifest before the failure. No VM,
workload, measurement or business operation is retried.

[experiment-retention-recovery.json](experiment-retention-recovery.json) freezes
all fifteen selections: the existing nine canonical shards and five failure
drills remain successful original invocations; only this experiment has the
explicit failed-retention exception. Both original sources/builds/sequences
remain visible. The five JAR pins, configurations and whole-history boundaries
are unchanged. The existing narrow support-file tree guard also binds every
byte of this verifier; unrelated runtime/workflow/POM changes cannot enter.

## Explicit protected acceptance

Use the existing Runner's `verify-set` operation and `self-hosted` host, with an
explicit envelope containing **all fifteen exact pinned selections**:

```json
{"recovery":"experiment-retention-40809895634","selected":{}}
```

The empty illustration rejects. Ordinary selection and quota-continuation
requests retain their successful-original requirements. Only the recovery
envelope permits the fixed FAIL completion and missing success seal, and only
after authenticating the exact failed run/attempt, its full step record and
immutable diagnostic artifact. It also checks original GCS generations,
manifest/content hashes, original reservation and FAIL terminal ledger history,
and every exact resource absence. It then independently replays all fifteen
members, all physical/read oracles and required negatives. Any missing file,
changed byte, different attempt/failure, failed replay, reused history/resource,
changed original selection or unsupported source rejects.

The final result explicitly reports the recovery policy, original FAIL states
and supplemental chunk ordinals. Only a complete protected set replay may emit
`fullRemoteQualification=true`. Local collection/replay and this exception's
unit tests do not close Phase 6 on their own.

Rollback: stop selecting the recovery envelope and revert its support changes.
Keep all original and supplemental evidence and failed ledger entries intact.
