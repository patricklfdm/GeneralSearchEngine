# V5.2 Phase 6P minimum-wait and saturation controllers

**Status:** all eleven controller configurations observed in fresh local
three-JVM development histories. These are integration checks before the complete
machine freeze, not formal M02/M03 measurement acceptance. Independent scenario
admission, complete negative qualification and M04 remain required.

## Exact requests and progress gates

The controller uses the [closed read parameters](PHASE_6_WAIT_CAPACITY_PARAMETERS.md)
and [frozen document/query program](PHASE_6_MEASUREMENT_PROGRAM.md). Three confirmed
updates precede one setup strong read. All three voters must publish that cut and
observe its recovery floor before measured requests are offered. The original
leader and target stay fixed; unexpected publication progress rejects the fixture.

M02 runs each below/equal/above minimum at 0, 1,000 and 5,000 ms, with 30 original
requests to the highest-ordinal initial follower. The minimum preserves the setup
token's group/history/manifest and sets its index relative to the actual target's
published index. It is a constructed lower bound, not an issued commit certificate.

The gate observes all 30 **admission events**, not 30 simultaneously owned reads.
Completed or expired requests still count and retain their original outcomes.
Below/equal cases and above/zero-wait issue no progress mutation. Above/positive-wait
offers exactly one update after all admissions plus 250 ms. The delay is not a
deadline reset; it does not guarantee that every original deadline will survive.

M03 targets the initial leader. P=4/P=65 keeps R=3/R=64 above-bound requests
owned, waiting and alarmed, with no captured/settling read and exactly one remaining
admission slot. One excess read must return `CAPACITY_EXCEEDED`. The unchanged
pending set is observed again before one update uses the reserved writer slot.
Every original waiter and that write must complete successfully. Nothing resubmits
an uncertain write or replaces a failed read.

## Observation and failure retention

The observer adds cumulative admission and recovery-floor hints after recording
the corresponding complete trace events. These hints only guide live execution;
the independent validator must reconstruct events and verify physical authority.
They are not an atomic global state cut or a substitute for raw evidence.

All requests retain original futures, identities and controller timestamps. A
dispatch failure preserves its failed row and the undispatched suffix. A common
drain observes original responses. Configuration/startup, public-call, gate or
close failures remain failures; the controller returns only `OBSERVED` on success.
Every started worker is stopped; an original execution error is retained separately
from secondary cleanup errors. The M01 controller shares this process ownership
helper without changing its offered program.

Activation/floor/gate observation bounds are 40/80/10 seconds. Polling at 100 ms
keeps their combined controller traffic below the existing 4,096-command per-JVM
ceiling. Publication preparation retains its existing 40-second bound. Common
drain is 35 seconds for M02 and 75 for M03. No business retry is introduced.

## Validation and remaining work

Eight deterministic tests cover all eleven schedules, exact targets/counts/token
domains, zero-wait rejection, saturation/reserved capacity, early settlement,
partial dispatch, missing floor, role/progress changes and uncertain writes.
The existing seven M01 controller tests still pass, including cleanup failure
preservation. All 178 V5.2 Python tests pass.

The eleven real development histories retain 350 reads including setup/excess
calls and 37 updates. All expected successful reads and writes completed; 30
zero-wait requests rejected with `PROGRESS_NOT_REACHED` and two excess reads with
`CAPACITY_EXCEEDED`. Shared physical, publication, lifecycle, cut and sampled
resource validation passes. All eleven original/relocated pairs preserve identical
results and actual V4.4 query answers (22 complete component replays). They bind
source `e5c732435e97c92bf092a50413136cc400d6a337`, checkout
`d45ff392b50a6b8abe04bf40a41b70e6168209bcfd9863051e72c51abf760d3b`,
and one identical candidate JAR/class set. Their development timing is not a formal
measurement or CI performance estimate.

The unchanged five-mode gate `run.af0Foj` passes 55 reads, 15 updates and 200
original/relocated evidence negatives. Its 4,384-file large package passes 24
negatives at each of three replay locations. CI inventory, documentation/link,
shell and whitespace checks pass. Complete scenario-specific acceptance is still
open. Evidence and validation records are under `target/v52-minimum-controller`.

The first new unit-test assertion incorrectly assumed query descriptors contain
an ordinal. It was corrected to compare exact frozen query descriptors; the
original failed test output is retained. No production Java, POM, runtime default,
workload count or paid-cloud behavior changes. Continue under the
[local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md), without pushing.

A temporary replay command also matched summary JSON files in a directory glob;
its `NotADirectoryError` is retained. Restricting that glob to directories completed
the unchanged evidence replay; no workload was rerun for this command correction.
