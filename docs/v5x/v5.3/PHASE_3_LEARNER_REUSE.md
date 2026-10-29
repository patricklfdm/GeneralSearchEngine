# Phase 3 — reuse the retired learner slot

The slot manager now owns one selected image and at most one pending image under
its existing exclusive lock. Source files, typed handles, retained leases and
stored-copy verification bind the individual image. This avoids adding a new
successor owner or another authority directory for each refresh.

After the original A25 vacancy is forced, the selected B typed owner may acquire
one further original source through the same resource pool. Its pending A plan
binds the current B head, the original vacancy, its own inode and the next native
source's original inventory. It reuses the retired seed's `source/` and typed
paths. The immutable seed plan, selected marker, old head and initial retirement
records remain intact. The new plan lives in the existing slots root.

B remains current throughout acquisition, installation and pending A typed decode.
A cannot supply a current-head capability, select itself, make a voting receipt or
start a third acquisition. Reopening independently checks both source capsules
before recovery forces. The exact original vacancy prevents phantom old-seed
charges; the new pending A still consumes its own generation and image leases.
Old retirement traversal is bypassed only after the bound reuse plan and original
vacancy validate, so it cannot delete newly installed A files.

The retained complete candidate can finish without another download. A partial
plan, copied plan inode, changed source, changed vacancy or unknown slot/source member is
preserved and refused. Acquisition guards end after installation; a closed
download cannot invalidate the retained owner. The manager also handles the
current typed guard's structural re-entry without recursively calling that same
guard indefinitely.

The exact disk and accounting contract is [A26](PHASE_3_CONTRACT_AMENDMENTS.md#a26--reuse-of-the-cleared-a-paths-under-one-slot-owner).
Its conservative metadata envelope is **1852 KiB** within the unchanged 2 MiB
MISC lease; the limits remain two GENERATION and seven APPLICATION resources.
Identical image bytes at separate physical locations still consume separate
leases. Existing B plan/head/vacancy formats are unchanged.

## Qualification boundary

[Component evidence](phase3-evidence/learner-reuse.json) records the exact sources,
reports and retained failures. The focused histories use conditional voting
fixtures, real original transfers, core semantic decoding and exception cuts.
The TCP case closes the download before using pending A and cold-reopens both
images, preserving all original bytes. This is not native consensus,
halt/SIGKILL, maximum-resource or complete repeated-cycle qualification.

This batch installs the first reused A (sequence 2). Selecting A, retiring B,
reusing B again, cancellation, matching local INTENT and autonomous READY remain
OPEN. `promoteSlot` explicitly refuses this pending reused image until the
replacement-head protocol is implemented. Long complete histories remain in the
[deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md); Phase 3 is not closed.

The local combined execution completed nine methods: eight passed and one failed
at the added malformed-inventory assertion. The mutation had rebound the A plan
but omitted the installed marker's plan hash, so the implementation correctly
rejected it at the earlier metadata check. After correcting that test fixture,
the single affected method passed, including the intended inventory-shape
refusal. Production sources and all 876 compiled production files were identical
between those two executions. This establishes nine passing component methods
across source-matched executions, not a claim that the original combined command
was green. Its failed report and the earlier superseded execution remain retained.
