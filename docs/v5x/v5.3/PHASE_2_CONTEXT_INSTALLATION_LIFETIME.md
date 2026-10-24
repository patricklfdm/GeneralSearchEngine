# Repeated selected installation and obsolete source reclamation

Phase 2 remains **OPEN**. This extends [context-backed installation](PHASE_2_CONTEXT_INSTALLATION.md)
through repeated slot reuse without accumulating obsolete source images.

## Authority boundary

With original vote 20, governing floor 21 and installed generation 23, source 22
may be obsolete even though its ballot is older than the current installation.
The earlier intermediate-backing check required a ballot newer than the installed
decision and therefore refused this safe reclamation. The first retained failing
execution reproduces that refusal after successful installation of generation 23.

The corrected context-specific check uses the fully verified local governing-floor
copy as its lower ballot bound and the latest backing as its upper bound. It also
pins the current installed BASIS explicitly. The exact original pending vote,
backing, parent, ENTRY and payload remain required; a source must carry the same
original ACCEPT, plus any original proof and certificate. The normal source
retirement plan still verifies current/floor references, ancestry, complete source
inventory and preservation of above-floor bytes and unresolved ownership.

After journal compaction, interrupted deletion uses the exact saved original
decision. It does not infer authority from a partially deleted directory. The
decision remains bound to the current selector, governing floor and newer durable
promise. This change neither relaxes resource limits nor permits deleting a floor,
current installation or latest backing.

## Local qualification

The [evidence index](phase2-evidence/context-installation-lifetime.json) retains
source/build inputs, failure and success logs, producer classes, JAR hashes, raw
inventories and independent normal/optimized/relocated replay results.

Three actual local owners capture, select and install ballots 22–27, retaining
original vote 20 and floor 21. Each owner retires the prior generation and then
the obsolete source, while attempted deletion of pinned sources leaves bytes
unchanged. Both generation slots are reused. The last exact successor ACCEPT
releases the obsolete context and floor and reserves completion space.

The frozen seven-image reservation limit is checked at storage callbacks and
reopen. After maintenance, five physical images plus one future publication
reservation remain; after successor acceptance, completion is admitted within
seven reservations. These are reservation counts, not a claim that each test
image occupies its maximum allowed size.

Source deletion at installed ballot 23 is interrupted at all 14 existing source
retirement boundaries and interrupted again during context re-sealing. Reopening
preserves the old vote and completes only authorized deletion. External JVM lock
probes verify exclusion while the owner is live. Independent replay derives the
actual captured sources, immutable selected sets, generation/selector bytes,
retirement states, force order and original successor; deliberately altered
evidence must fail for its specified reason after the original passes.

## Remaining obligations

The new source cuts use injected IOException; they do not establish process-death
or power-loss behavior for the repeated-installation path. Historical bootstrap is
still conditional, images are small, and this path requires the same original
ACCEPT digest. Mixed higher-ballot acceptances, full typed publication after this
new lifetime, full-capacity journal/image/staging headroom, admitted bootstrap to
complete lifetime, and coordinated old/joint/new profiles remain separate Phase 2
obligations. Public online membership remains disabled.
