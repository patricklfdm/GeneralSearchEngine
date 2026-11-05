# Original persistent BASIS resource lifetimes

The required-four native resource entry now binds persistent BASIS packet and
image reservations to original grant captures, source-retirement prefixes and
cold-owner files. Physical/network/export/maintenance and continuous-ledger
admission precede this layer. The original BASIS ID names the SOURCE reservation;
each APPLICATION reservation uses that ID plus its exact original image digest.
Packet bytes and the complete image inventory supply the required extents.

All reservations must be acquired within the original capture invocation and
before `SOURCE_BEFORE_CREATE`. Each packet/image lease is immutable and remains
continuous until its owner's last applicable boundary. Releasing and reacquiring
the same byte count between callbacks is an extra lifetime and is rejected.
Missing source charges, a different category, another image digest or an extra
temporary source image cannot substitute for original ownership. The underlying
resource-transition replay independently verifies every delta, count, bound and
zero-usage terminal state.

For retired sources, the recorded retirement must identify the exact original
packet and images. The preceding physical reader separately derives the durable
retirement authority and all exact deletion prefixes. Capacity stays charged
through the capture following `SOURCE_RETIREMENT_DIRECTORY_DELETED`, which follows
the source-parent force, and releases by `SOURCE_RETIREMENT_CLEARED`. A deletion
callback by itself does not authorize retirement.

## Reopen and generation changes

A joining source can survive closing one owner and opening another on the same
root. The reader accepts only the independently admitted joining lifecycle scopes
and compares the complete retained source inventory with the original cold files.
The old lease must cover the last event before the next opening and close by that
opening. The next reservation must occur after `CURRENT_DIRECTORY_FORCED` and
by `JOINING_RETENTION_SEED_RECOVERY_FORCED`. Its bytes must be the same originals.
The final stable cold owner additionally needs its explicit open/close returns.

`CURRENT_VALIDATED` alone is not an owner restart: it also appears when a live
owner loads a newly published generation. Only the first original opening of a
lifecycle scope introduces another reservation interval. Every ordinary generation
reload must preserve the existing source lease. The first diagnostic rejected
these same-owner generation events as unexpected reopens; that prototype failure
is retained, and a regression now distinguishes them from actual owner changes.

## Qualification and scope

Seventeen conditional tests cover original packet/image derivation, immutable
charges, legitimate reopens, generation reloads, unchanged cold originals,
retirement bindings, complete checkpoints and original-first validation. Seventeen
coherent negative mutations exercise wrong sizes/category/identity, early/late
reservation and release, hidden reopens, lifetime gaps and unbound temporary
images. Negative replay changes only copied resource journals/checkpoints; original
files, events and expectations remain fixed, and every rejection needs its exact
specified reason.

The retained required-four original at Java source `f0b60e1d` is reused. The focused
diagnostic derives 26 BASIS sources, 22 retirements, 29 owner intervals and 58
packet/image leases, including three reopens and 284 boundary checks. Complete
physical/network/export/maintenance and four-ledger replay pass, followed by all
seventeen exact native negative rejections. Complete replay and negatives took
442.9 seconds. All 181 related Python/contract tests pass. The original
inventory and 1128 Java/resource input hashes remain unchanged. Reports and source
hashes are retained in the [development index](phase3-evidence/basis-resource-binding.json).
No Java or workload measurement is repeated for this Python-only addition.

Six final packet/image leases on three old owners have no explicit final close
callback in this original. The reader requires continuous charging through each
owner's last event and eventual accounting release, but does not claim the exact
physical shutdown order in that unobserved interval. Direct receiving-file force
captures, post-handoff learner custody, other control/storage owners, simultaneous
physical maxima, completion at capacity and final-source qualification remain
separate obligations. The newly bound persistent source scope does not turn the
whole-runtime resource result into PASS.

```bash
python3 -m unittest scripts.v53.test_basis_resource_evidence
python3 -m scripts.v53.basis_resource_negatives "$ORIGINAL"
```

Phase 3 remains OPEN; twelve hosted subsets / 544 planned histories remain
unchanged. Production code, formats, limits, workflows, POMs and paid-cloud
behavior are unchanged. Rollback removes this reader, negative driver, tests and
its required-four entry call together, preserving all original evidence.
