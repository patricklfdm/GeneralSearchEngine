# V5.3 frozen acceptance register

[acceptance-plan.json](acceptance-plan.json) is the machine-readable Phase 0 plan.
No entry below is marked runtime-qualified by a Python model. Existing arithmetic,
ballot, transition, recovery, activation, admission, operation, integrated and
continuity drivers are local research evidence only.

## Correctness and physical gates

| ID | Required evidence |
| --- | --- |
| S01 | All seven add/remove/replace profiles; old INTENT and joint FINAL interrupted before write, after write/force, before ACK/publication and after publication; halt and SIGKILL |
| S02 | Old/joint/new competing campaigns; PREPARE/SELECTED/ACCEPT/PROOF; duplicate, lost request/ACK and higher-ballot late response; fixed selected sources and exact chosen value |
| S03 | Add/replace learner reservation, image, receipt, INTENT; before/after force, corrupt chunk, stale revision and foreign identity; fresh processes, halt/SIGKILL |
| S04 | Old/joint/new capsule, full catalog, selector, floor and retirement; before/after force, interrupted deletion, missing owned tail; all required bytes replay independently |
| S05 | RESERVE/PREPARE/READY/SEAL/CANCEL/RETIRE; lost reply, duplicate, changed payload and restart; stable ID and irreversible boundary in deterministic and external public consumers |
| S06 | Strong/stale/minimum reads across old/joint/new cuts; before capture, after capture, response, known removal, isolated unaware node and drain; exact token/history and callback lifetime |
| S07 | Stable 3/4/5-voter round reuse; lagging predecessor, source loss, higher fence, leader restart and conflicting same-ballot value at both durable phases/publication |
| S08 | Leader/follower same-version maintenance at sizes 3/4/5; stale plan, missing survivor, restart and no quorum; no unsupported upgrade or remote-delete claim |
| S09 | Identity/results/revision/change/counter/metadata/queue/staging bounds, at/over limit and crash at limit; admitted transition completion headroom and ordinary stable DATA after membership exhaustion |
| S10 | Accepted-only, partial proof, complete proof and selected source loss; whole-group restart, rejoin, fresh disk identity and missing authority; no fallback to genesis |

The explicit axes in the machine plan are required combinations, not optional
examples. `all-seven` expands to its seven listed profiles; `old-joint-new` means
each of those profiles at all three views; `add-and-replace` selects its five
joining profiles; `stable-3-4-5` selects the three sizes. Inapplicable operations
(e.g. a new cancellation in joint state) must be tested as explicit refusal with
unchanged bytes, not silently dropped from the inventory. Modes remain separate
receipts. Phase 1 materializes that finite inventory before runtime implementation.

Every positive history records ordered invocation/completion, exact process/session/
storage identities, authority, force boundaries, original accepted/proven bytes and
read captures. Independent validators receive portable retained files and source/
build hashes, not Java object internals or a final status screenshot. Unmodified
evidence must pass before negatives count. Corruptions N01–N24 in the machine plan
each have an expected rejection family; unrelated setup failure cannot count as
successful detection. Missing/fabricated scenarios or crash labels also reject.

## Compatibility gate C01–C08

C01–C06 retain the repository's six published-consumer obligations unchanged;
their owning release inventory remains authoritative. C07 compiles/executes the new
external V5.3 membership interface and all seven profiles without private APIs.
C08 verifies unchanged token v1 bytes, legacy fixed factories, 1.1/1.2/1.3 wrong-family
refusal, and verified-backup transfer to a new root. Pin the actual released V5.2
source and nine-JAR/three-POM inventory only after publication; placeholders cannot
pass C08. No current cloud evidence may be relabelled as a published control.

## Measurements M01–M12

Each canonical repetition runs the 12 listed cells; there are three repetitions,
36 whole-cell measurement histories. M12 contains three declared saturation windows
inside each history. Preserve one source/build/plan/machine cohort; execution order
is allowed to vary, and original failures remain retained.

Every non-sweep cell starts with 10,000 documents, integer IDs 1..10,000, `category`
equal to ID mod 100 and 512-byte ASCII values padded with `x`. The PRNG and call
cycle are fixed in JSON. Search is category equality, return IDs sorted ascending,
top 20; search semantics compare to published V4.4 replay. UpdateAll changes the
primary and next ID to the same operation-labelled 512-byte value. No create/drop
index operation occurs during timed windows; indexes are prepared once before warmup.
Minimum reads use the latest successful strong token for that replica/root, beginning
with a pre-window token; they never silently downgrade or fabricate progress.

Warmup is 60 seconds / 600 calls, then 300 seconds / 3,000 open-loop calls at 10/s,
concurrency 32, queue 128. Record planned submission, actual submission, admission,
queue, force, publication, completion and read capture independently. Slow completion
does not shorten the offered schedule. Account draining and controller overhead
outside the frozen measurement window; retain outstanding outcomes after the window.

M05 requests the four size-walk changes at call indices 500/1000/1500/2000. The later
request waits for the preceding FINAL/current activation; report actual request time
and any delay, without dropping ordinary scheduled calls. M06–M08 replace one voter
at call 1000 with a fresh identity. M09 initiates ADD at 500, isolates the old leader
after proven INTENT for 10 seconds, heals, and observes automatic FINAL/recovery.
M10 removes the token-producing voter at 1000 and checks tokens on a surviving member.
M11 drains/restarts each of three voters sequentially at the same four checkpoints
(first three used), verifying rejoin before the next. M12 runs rates 5/20/100 per
second, each with 30-second warmup and 120-second measurement; saturation rejections
are classified and measured rather than hidden by retry.

M01 and M02 are the only same-topology baseline comparison. M03/M04 are size-specific
candidate observations; do not call a five-voter replication cost a version regression
against a three-voter control. Healthy cells require zero unexplained failures,
indeterminate outcomes or capacity rejections at the frozen controlled load. Fault
cells preserve all outcomes and require the history/read/physical oracles to pass;
indeterminate calls are not assumed absent or blindly reissued. Report latency and
throughput, detection/election/activation/first durable write/first strong read as
separate intervals. This plan asserts no failover SLA or fabricated speedup target.

## Cloud and execution policy

Phase 6 uses one experiment, one failure-drill and three canonical members in the
same source/sequence cohort, in any order; acceptance requires all five. Experiment
uses one M02/M05/M10 pass. Failure-drill uses the six exact `failureDrillCases` rows F01–F06: INTENT
3→4 kill, FINAL 5→4 kill, 3-voter replacement image kill, 4-voter joint selector
kill, 5-voter new-view interrupted retirement, and M09. These cover all three sizes;
they do not replace the full local S01–S10 inventory. Canonical preserves all 36 measurement histories.
Current quota/IAM/image/identity/ownership/cleanup/storage prechecks and a full price
estimate remain necessary. Actual machine/image/control hashes are frozen at the
Phase 6 admission boundary, not fabricated while V5.2 is still unpublished.

Time and monetary budgets are soft warning thresholds, following the operator's
V5.2 policy. Emit progress every 60 seconds. Integrity failures, impossible state,
finite request deadlines, bounded identical I/O retries (three total attempts),
resource exhaustion and proven nonretryable errors still fail promptly. Do not wait
for a soft budget to expire to report a known failure. Paid runs need separate user
authorization. No cloud action is authorized by this local Phase 0 document.

Whole independent profiles/cells may be sharded. A continuous window, one membership
operation/recovery history, or a lease/source/history ownership chain is indivisible.
Aggregates validate exact source/build/attempt, complete expected inventory, resource
budgets and original/negative replay after portable download. A shard passes only
its own partial scope. A rerun is a new attempt, not erasure of a failed execution.
