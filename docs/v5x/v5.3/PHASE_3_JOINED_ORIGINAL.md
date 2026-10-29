# Original installed joining-history validation

Phase 3 remains **OPEN**. `MembershipLearnerJoinedOriginal` validates the complete
original installed generation independently of the predecessor learner payloads.
The [joined-admission writer](PHASE_3_JOINED_ADMISSION.md) runs this check before
returning its forced capability. A separate cold entry acquires the existing
replica lock without creating files and returns only inspection diagnostics.

## Surviving proof and original bytes

Reconstruct the installed inventory from the complete original custody decision
and fixed placement moves. Require the original placement plan and complete
completion marker, including their inode bindings. Preserve the original ROOT,
NODE and root lock; each installed path, directory identity, file identity,
extent and digest must equal the original projected inventory. Unknown,
missing, replaced or altered installed members refuse.
Before hashing, bound the inventory to 64 members, the fixed native paths and
directories, each existing per-file maximum, 32 MiB generation metadata, 2 MiB
native miscellaneous metadata and seven images. Declared extents do not grant
additional quota or allow an unbounded scan.
The old replica's `learner/` payload and `learner-admission.gslp` are excluded
from that native inventory, only when named by the original custody decision.
Their presence, absence or contents are not a retirement qualification. Every
other root member and every native generation member remains exact.

Require a complete canonical joined record with its original inode, exact
schema, reviewed plan, root/local identity, replica/materialization paths,
captured configuration and custody/completion fingerprints. Preserve the small
original selected typed plan and LEARNER receipt, including their directory and
file identities from the custody decision. Match configuration, materialization
binding and preparation-source digest to that actual typed plan, not solely the
joined record's self-reported values. A missing or partial proof is not repaired.
The cold reader does not reopen the typed engine, old backup, receiving source
or INTENT source. Retiring payloads must preserve those small proof originals.

Walk the complete installed capsule under a private, short-lived original-copy
token, with the actual root lock and complete original inventory checked before
and after the walk. The token has a private constructor in the sealed set of
storage readers. It accepts no caller observation set or generic verifier and
expires at the end of that read. Historical checkpoint/certificate structure,
images and ancestry are verified; this creates no fresh voter observation.

Check the original LEARNER receipt against the matching INTENT edge, exact
sealed request and certified target view. Check the recorded INTENT ENTRY and
CERTIFICATE bytes against that actual edge. Require the sole original `a`
installation, no selected grant/BASIS/owned tail, the certificate-derived local
PROMISE, matching durable journal bytes, exact allocator floor and empty pending
ACCEPT. The installed source, generation and cut must match the joined proof.
This entry describes the initial joined installation; later mutable journal
history will require its own native owner and recovery rules.

## Scope and accounting

Live validation uses the already charged placement custody and does not add,
transfer or release a reservation. Cold inspection is a bounded read-only
diagnostic, not a retained runtime owner or capacity-admission result. It returns
digests, cut index and inventory size; it exposes no capsule capability, root
descriptor, allocator or journal. It writes, forces, deletes and repairs nothing.

The persisted joined proof records the prior successful typed preparation;
this original-history inspection does not reopen a typed engine or rerun the
application codec. Native runtime materialization must still perform its own
typed checks before service. Physical proof inspection does not establish
whether a predecessor's absence was authorized. Only the remaining forced
retirement inventory can authorize and recover those deletions, including their
resource accounting and directory-force boundaries.

## Executed and pending qualification

The [component receipt](phase3-evidence/joined-original.json) retains actual
snapshot hashes, raw executions and test results. Focused tests check live and
cold equivalence; actual kernel exclusion using independent JVM probes; absent
predecessor payloads without recreation; ordinary recovery's refusal of those
missing predecessors; missing/torn/copied proofs; changed semantic bindings;
installed inode substitution; and corruption at the last read boundary.

The absent-predecessor test moves receiving/INTENT sources, the typed backup and
the replica's old learner payload under test control, retaining the original
typed plan/receipt and the three joined decisions. It is not an
execution of production retirement, nor proof that those absences are legal.
Historical quorum fixtures remain conditional. Whole native histories,
halt/SIGKILL cuts, all joining profiles and original-first independent replay
remain in [deferred acceptance](PHASE_3_DEFERRED_ACCEPTANCE.md). Covered retirement,
descriptor/reservation adoption, joined retention, minimum-quorum INTENT and
FINAL/fresh-barrier integration remain required before Phase 3 closure.
