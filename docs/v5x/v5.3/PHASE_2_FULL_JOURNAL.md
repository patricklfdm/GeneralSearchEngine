# Full shared-journal boundary and interrupted compaction

Status: local qualification **PASS**. Phase 2 remains **OPEN**.

The complete admitted owner shares its 32 MiB JOURNAL reservation with pending
vote/context and application recovery metadata. With an empty pending vote, the
current reserved completion allowance is 2,275,352 bytes. Therefore the largest
journal admitted by this profile is **31,279,080 bytes**, not a 32 MiB journal
plus unaccounted completion work. The frozen resource limits are unchanged.

Three voters are provisioned through the public offline bootstrap operation and
produce actual original grant/source/selection files. The tested voter retains
those originals while a declared fixture appends complete abandoned PROMISE
frames to the exact byte boundary. This history is preconstructed; the batch does
not claim that each frame came from an executed campaign or disk force.

The actual owner opens that full journal, compacts once before the new PROMISE,
preserves its current/source grant and highest abandoned promise, then captures
a new original source. A fresh worker replays that new grant without rewriting
it. Separate valid-frame fixtures exceed the usable shared boundary by one byte
and the physical file limit by one byte. Both opens refuse with unchanged files
and released reservations, for their distinct capacity errors.

All six compaction boundaries run under halt and SIGKILL. Each case interrupts
recovery a second time before successful completion: twelve cases, 36 workers,
plus two clean/duplicate workers and six live lock probes. The final journal is
3,490 bytes. Original source/generation/bootstrap files remain exact throughout;
no source deletion, higher ballot reset or fabricated acknowledgement makes room.

The independent reader derives public bootstrap and the initial actual campaign,
reconstructs every fixture byte, and checks exact physical snapshots, retained
original frames, fresh source contents, force/death order, duplicate replay, exit
codes and ownership locks. It validates the original before running mutations.
One Java matrix test and 17 focused Python tests pass. Normal, optimized and
relocated replay agree, including eleven exact evidence rejections. The fixture
contains 89,876 declared abandoned PROMISE frames. All 707 production classes and
both production JARs are unchanged from the preceding corrected runtime.
The [source/build index](phase2-evidence/full-journal.json) retains all attempts.
The first Java attempt used the wrong exception class for the physical file
limit; the producer now asserts each exact class and message. A reader invocation
before the producer finished refused the incomplete evidence; that failure is
also retained and is not a successful negative qualification.

This qualifies the full shared-journal boundary on a small application. It does
not qualify maximum-sized images/capsules, all membership lifetime limits,
complete cross-view storage, power loss or the disabled public runtime. Those
remain separate obligations in the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
