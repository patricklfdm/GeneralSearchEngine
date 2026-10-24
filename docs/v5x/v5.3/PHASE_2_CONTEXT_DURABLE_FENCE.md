# Retained context under a later durable promise

Phase 2 remains **OPEN**. This batch separates three storage identities that the
context reader previously treated as the same: the original vote's backing grant,
the installed selection, and the newest durable promise. It is recovery groundwork;
starting/capturing/rebinding a new campaign while context remains is still disabled.

## Recovery behavior

A context records its exact backing PROMISE/BASIS, which may remain the original
ballot-21 pair after a later ballot-22 promise exists. The owner now looks those
frames up by their recorded identity and requires byte equality with the retained
journal. It reads and reseals that exact physical source. It separately verifies
that the installed selection exists, the latest promise is in the current view,
its proposer matches an eligible durable identity, and latest promise ≥ backing
ballot ≥ installed ballot. The original ENTRY, ballot-20 vote, historical selector and original generation/floor binding retain
all prior checks.

Reopen/reseal and predecessor-source cleanup can preserve a higher durable
promise without substituting its absent BASIS for the old backing. Conversely,
`acceptRetainedCurrent` explicitly requires the latest PROMISE/BASIS/SELECTED to
be the installed authority before any conversion. A newer incomplete grant cannot
turn the old installed vote into an acknowledgement. General PREPARE and arbitrary
context turnover remain blocked by the existing transaction gate.

The retained-source reader is shared with the original latest-grant accessor;
that accessor still requires a complete latest BASIS. No wire, disk record,
resource limit, public runtime or legacy-family behavior is intentionally changed.

## Qualification boundary

The new regression first failed against the prior implementation with
`retained context installed authority changed`. It supplies and explicitly forces
a valid higher PROMISE frame as a **fixture boundary** after actual earlier context
and source operations. This is not evidence that the runtime executed a new
campaign. Tests cover three retained states: original generation present, original
generation retired, and predecessor source retired. Reopen/reseal preserves every
byte, exact old certificate and the higher promise; new acceptance/grant attempts
refuse. Other tests interrupt recovery twice, finish predecessor-source cleanup
without an old ACK, and reject missing/corrupt context/backing authority unchanged.
A separate red/green regression rejects a higher frame with an unknown proposer, wrong incarnation or
foreign view; successful cases use a different valid proposer from the backing.

The independent validator first checks the earlier original context/source
history, derives the appended higher frame and exact unchanged inventories, checks
that its BASIS/source was not fabricated, and verifies reseals without a new ACK.
Fourteen exact-reason mutations and relocated/optimized replay qualify these three
retained states. Cleanup and corruption assertions are additional Java tests; the
independent byte replay does not claim a complete newer campaign or independently
replay their unretained temporary directories.

The focused regression build also exercises the prior context codec/transfer,
owner retention, source reclamation, successor acceptance, three-owner publication
and all 86 repeated-death completion cases. Source/build/raw hashes and results
are recorded in the [evidence index](phase2-evidence/context-durable-fence.json).

## Still open

Protected capture must reserve and reconstruct original plus current images,
force the exact new source and rebind the same original context, and recover every
interruption before a new grant can return. Subsequent selected installation must
compare original generation identities, not only reusable `a`/`b` slot names.
Bounded retirement of old backing/floor copies, maximal completion headroom and
complete old/joint/new lifetime remain separate required work. The general context
transaction gate must not be removed to bypass these obligations.
