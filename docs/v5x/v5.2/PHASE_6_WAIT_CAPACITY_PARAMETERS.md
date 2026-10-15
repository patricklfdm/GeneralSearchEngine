# V5.2 Phase 6O read-wait and capacity parameters

**Status:** closed configuration and local integration validation passed.
M02/M03 scheduling, relation/saturation proof and the complete machine execution
freeze remain open. No formal measurement has run.

## Separate fixed fixture configurations

`measurement-options.json` is permitted only for candidate minimum-read M02/M03
preparation. Both Python and the independently compiled Java consumer validate its
exact fields and numeric choices. The consumer rejects foreign modes, unknown
fields, non-integers, symlinks and oversized configuration files. Startup evidence
reports the configuration actually read by that JVM; copied bindings retain the
declared parameters. Setup, runtime bounds and explicit read options use it.

| Family | Pending operations P | Minimum wait | Operation deadline |
| --- | ---: | ---: | ---: |
| M01/default short integration | 64 | 5,000 ms | 9,600 ms |
| M02 | 64 | 0 / 1,000 / 5,000 ms | 9,600 ms |
| M03 | 4 / 65 | 60,000 ms | 120,000 ms |

M01 does not accept a configuration file; its existing numbers remain fixed. The
short gate also rejects a changed file or startup observation. The complete M01
member/set binding requires these same defaults. Existing short evidence without
the new observation remains replayable against its original binding.

M03 needs behind reads to remain owned while the controller observes saturation,
the excess rejection and reserved writer progress. Its 60-second wait follows
the earlier resource fixture; a 120-second operation deadline prevents the normal
9.6-second integration operation limit from silently truncating that declared wait.
These are pre-execution fixture choices, not a production default or a response to
a measured failure. They must be included in the complete machine freeze before
M03 runs. All other runtime bounds and the frozen P/R counts remain unchanged.

## Admission follows the declared profile

The shared lifecycle and cut validators now take the declared minimum wait and
pending bound explicitly, retaining their original M01 defaults. Idle admission
and resource-window counters use the declared P, while the read limit remains
`min(64, P-1)`.

`PROGRESS_NOT_REACHED` is an admissible recorded rejection only when the caller
explicitly enables the zero-wait profile, the mode is candidate minimum, and the
original observed invocation is `AT_LEAST_INDEX` with zero wait and outcome
`REJECTED`. It cannot expose a callback or carry an answer/token. Positive waits,
missing invocations and ordinary M01 qualification still reject that classification.
The later M02 validator must additionally prove the actual below-bound publication;
this lifecycle admission alone is not relation/correctness proof.

## Validation

Deterministic tests cover all closed choices, changed M01 parameters, bool/float and
unknown fields, zero-wait outcome admission and resource windows at P=4/P=65.
Actual Java preparation/configuration probes and the unchanged five-mode short gate
passed: seven Java configurations, five malformed-input rejections and 24 proxy
API calls cover every allowed wait plus strong/stale/setup behavior. Complete
`run.RWVcQf` passes all five real short modes (55 reads, 15 updates), original and
relocated physical/query/resource replay, 200 negatives, and the 4388-file large
package with 24 negatives at each of three locations. All 170 V5.2 Python tests
pass. One unchanged pre-configuration minimum history also preserves its entire
validation result. CI inventory, documentation contract, changed local links,
shell syntax and whitespace pass; no fresh reactor or hosted result is claimed.

The initial malformed-fraction probe was correctly rejected by Java's JSON parser,
but the temporary script expected a later configuration error message. Both that
failed assertion and the corrected exact-reason checks remain retained; no product
rule was weakened. Logs and failed development checks remain at
`target/v52-read-measurement-options`. Continue with fault schedules and machine
freeze under the [local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
