# Phase 3 — one internal owner across membership transitions

Status: locally qualified internal transition owner; see the
[source-bound receipt](phase3-evidence/native-departure-round.json). This extends the
[stable round lifetime](PHASE_3_ROUND_LIFECYCLE.md) and
[explicit continuous sender](PHASE_3_CONTINUOUS_TRANSITION.md); it does not close
Phase 3, enable public membership or supply a complete process-fault matrix.

## Operation ownership

`MembershipRoundDriver` now inspects its actual verified operation catalog after
activation and exact carried-entry completion. SEALED requires the original
INTENT descriptor; JOINT requires the original FINAL binding. The caller cannot
substitute either payload through the ordinary stable submit interface.

After an authority-changing publication, the child has already drained its work
and checked the exact original publication acknowledgement. The parent checks
the actual new cut, original selection and observed ballot solely to finish that
completed work. The old endpoint scope still cannot serve the new configuration.
It revokes readiness, closes the old activation and performs fresh activation
before the next control. Only a fresh new-stable BARRIER permits internal READY.
Submitting SEAL revokes previous readiness and drives the same completion path;
its return value remains the original SEAL acknowledgement.

At most two authority handoffs belong to one serialized operation. Each
activation retains the existing bounded campaign-attempt count; all campaigns,
carried recovery and slots inherit the same original parent start and deadline.
An indeterminate DATA operation is never automatically replayed. Resource limits,
default timeouts and public factories are unchanged. The companion
[departing publication](PHASE_3_DEPARTING_PUBLICATION.md) integration changes only
the unpublished APPLY_ACK acknowledgement field as specified by A11.

## Retained observations

The original implementation's test returned internal readiness at SEALED after
one BARRIER, leaving the operation unfinished. Its failed assertion and raw
history remain retained. The first integrated trial completed INTENT and joint
activation but expired during FINAL: the test declared a 600-second parent while
reusing 180-second endpoint fixtures. The endpoint correctly enforced the smaller
original deadline. This test now declares 600 seconds for both parent and endpoint;
the existing default-profile tests remain unchanged. It is not a default latency
or availability guarantee.

The aligned single-owner REMOVE test passes: one `start()` completes three
activations, INTENT at index 5, FINAL at 6 and BARRIER at 7 on the same four live
stores. Additional tests for joint startup, SEAL submission, carried controls and
authority-boundary fencing/close/deadline are under execution. Existing stable
round regression and final portable qualification are still required before this
batch can be called locally qualified.

The ten-case guard execution finished with nine passes and one error: after its
initial BARRIER and submitted SEAL published, the INTENT acceptance exchange in
the SEAL-submission case ended with nested EOF/I/O failure. All six authority
fences, joint startup and both carried-control cases passed. The failed raw
history is retained; its cause is not established by the outer I/O message.
One diagnostic execution records request times and full nested failures with
unchanged production Java and timeout/retry settings. A later pass alone would
not establish a causal correction or erase the original failure.

The instrumented execution reproduced the same failure. A focused resource
regression also demonstrated that a completed single-record transfer retained
four CONTROL reservations. The correction under test collapses a fully consumed
export into one bounded exact-final-reply marker, releasing its original export,
session and cached response reservations. Partial sources stay live; failed or
changed traces cannot reopen. CONTROL count/byte limits, request attempts and
deadlines are unchanged. The subsequent unchanged-runtime JSONL diagnostic measured node 1 at 256/256
CONTROL reservations during repeated subsecond CHUNK failures. The earlier
whole-array counter writer exceeded its own JSON token limit; that failed
instrumentation and all runtime failures are retained. Corrected-source pressure,
transition integration and portable qualification are still required before closure.

The compacted service passes forty source/record/service regressions, including
the eighty-transfer workload that exhausted the original implementation. Its v2
three-profile physical replay and fifteen negatives also pass. The full SEAL
execution then advances past the resource failure (maximum observed CONTROL
count 121 on node 1) but fails at INTENT publication: the native publication
endpoint collected new applied-end endorsements without retaining required,
already authenticated ancestry from the earlier stable slots. The original
physical history and diagnostic failure are preserved separately. This is a
different proven-parent failure, not evidence that increasing a deadline would
repair the operation.

The correction obtains the exact required retained bridges through the live
publication owner. Bridges inside an enlarged RANGE still require renewal;
membership edges preserve the original historical ACKs without converting them
into new observations. Sixteen checkpoint/ancestry tests pass, including missing,
changed, unauthenticated and unneeded-bridge cases. Complete native integration
and corrected-source regression remain in progress; this batch is not yet closed.

The next original integration attempt passed the earlier publication boundary
but failed at a receiver's next SELECTED installation: its own retained grant
required an authenticated stable ancestor absent from the supplied selection
ancestry. Installation now preserves only required, exact locally authenticated
bridges, revalidates their endpoints in the selected prefix and leaves the original
selection and source bytes unchanged. Twenty focused tests pass on the first
corrected snapshot; complete network qualification is still pending.

The separate removed-proposer diagnostic confirms a different gap. An old-only
joint proposer forces the FINAL certificate, then tries to produce a new-view
checkpoint ACK during local application. The next-authority identity check
correctly rejects it. Removing that check or treating the failure as removal
success would be wrong. Nonvoting FINAL completion, governing retention and durable
removal adoption remain open for both a departing proposer and selected follower.

The next SEAL attempt passed SELECTED installation and exposed one further
projection boundary: native pending-certificate materialization discarded the
already authenticated supplemental ancestry before the next application. That
same-prefix projection now retains its original historical keys while requiring
separate native authority for any new certificate. Forty-nine focused tests pass,
covering installation, checkpoint renewal, publication and storage recovery. The
first new negative fixture inadvertently included observations from future steps;
its failed execution is retained, and the corrected fixture restricts the owner
to observations present in its original packet. Complete native transition
qualification remains separate from these component results.

## Independent qualification

The original physical reducer is shared with the explicit sender without changing
any original file or event. Its exact inventory differs only in the declared
result filename. It independently derives selections, votes, certificates,
application images, peer/future ledgers, source retirement and publication order.
The new reader then binds each owner activation, slot and completion to those
original bytes. It permits one readiness boundary after the final stable barrier.

Ten mutations target missing reactivation, early readiness, substituted selection,
old-ballot or forged completion, changed entry, changed scope/profile, and physical
publication corruption. A failed unmodified history cannot count as successful
negative qualification. The declared time budget is profile metadata; deadline
behavior is tested separately through the runtime clock and fencing guards.

## Remaining obligations

Learner ADD/REPLACE, every frozen configuration profile, complete carried/restart
combinations, fresh-process interruption of this
whole owner, autonomous election/discovery/adoption, maximum combined headroom and
the complete [Phase 3 checklist](PHASE_3_ENTRY_PLAN.md) remain required. Earlier
storage process tests are not relabelled as whole-operation process evidence.
Protected CI, predecessor integration, Phase 4–6 and paid cloud remain separate.

The corrected-source submitted-SEAL regression now completes all five native
slots (BARRIER 4, SEAL 5, INTENT 6, FINAL 7, fresh BARRIER 8) and all three
activations. Its Java assertions pass in 597 seconds including fixture
preparation. Original network/files/diagnostics remain retained. This is a
distinct profile from the existing sealed-start physical reducer (slots 5–7);
independent original-first replay for the submitted-SEAL profile is still pending.
The passing Java execution does not close removed-owner completion or Phase 3.

The subsequent [departing publication qualification](PHASE_3_DEPARTING_PUBLICATION.md)
now proves native removed-proposer/follower completion and internal service
refusal for two explicit four-to-three histories. The submitted-SEAL reader also
replays the retained five-slot history and twelve exact negative mutations. It
derives required hidden endpoints from the original still-owned source packets,
renews RANGE endorsements, preserves membership-edge ancestry and checks both
internal readiness boundaries. That source is the earlier `originalproof` build;
the final-source round regression is still under execution. Earlier diagnostic
observations above retain their original scope and are not erased by later passes.

The final-source `departureguards-86be472e` execution has now completed its
sealed-start REMOVE history at
`run-15b1501a-dc8d-40ee-ab28-fb2ce6dfe0f8`. Its closed original files pass the
independent round/physical reader and all ten exact mutations. A relocated copy
also passes with Python assertions disabled, with identical results. The receipt
is `target/v53-native-departure/current-round-replay/controlled/summary.json`.
These are two replays of one newly executed history, not two workloads. The whole
Java gate and its final-source submitted-SEAL profile remain pending; this partial
qualification does not close or authorize committing the combined batch.

## Final current-source qualification

The `departureguards-86be472e` execution passes all eleven transition tests,
while its stable-round class has ten passes and the one default-profile timeout
described below. The separate `finalstablefixed-3f63493f` execution passes all
eleven stable-round tests under the declared profiles. The submitted-SEAL
case completes in 578.708 seconds including preparation; the sealed-start case
in 413.652 seconds. These observations do not define a latency SLA. All six
authority-boundary guards, both carried transitions and joint startup pass.
Both current-source histories also pass independent original-first and relocated
optimized replay, with ten sealed-start and twelve submitted-SEAL exact negative
variants. The companion native departing-owner gate supplies the other two
histories and 22 negatives. All 47 Java tests share the same 474 production inputs.
The final 1,136-file source inventory retains the test-fixture distinction: the
original stable carried-ordering test exhausted three default 5-second PUBLISH
waits, while the receiver finished publication after sender shutdown. It never
entered readiness. That failed raw/JUnit/timing trace remains archived. The final
semantic profile declares a 30-second caller timeout while preserving the
180-second original lifetime, production defaults and retry count. A pass in
that profile is not a correction or guarantee of default-profile latency.
Earlier pending paragraphs above are the retained chronology, not the final status.
The stable/carried round originals also pass their independent physical/lifecycle
readers and 50 exact negative variants, with matching relocated optimized replay.
Whole Phase 3, native process faults, learners and public service remain open.
