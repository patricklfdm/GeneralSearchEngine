# Phase 3 — native carried-slot continuation

The [local receipt](phase3-evidence/carried-slots.json) records this component's completed local qualification. The original TCP regression reached a new installed
selection with an old certified/applied entry, then failed because the outgoing
slot tried to establish a floor before transferring the old vote. The original
failure remains in `target/v53-carried-slots`.

The installed voting scope now identifies the first selected carried slot from
its actual selection and published parent. Typed acceptance first matches the
exact carried entry and payload against that installed packet. Only then may the
existing original-proof retirement remove old derived application work. Original
ACCEPT/PROOF/certificate bytes stay owned until the new ACCEPT is forced.
Changed requests cannot authorize that cleanup; a higher ballot still prevents
new voting even if the exact old derived cleanup finishes.

Both outgoing and incoming native paths defer generation maintenance for that
first carried slot. The proposer forces its new ACCEPT, obtains every selected
owner's actual new ACCEPT, then establishes its governing floor before PROOF.
Each receiver establishes its own original-copy floor after its new ACCEPT and
before handling PROOF. The existing certificate/application/future-quorum and
publication path then completes the unchanged logical entry. The following
current-ballot BARRIER uses the usual maintenance-first stable-slot path.

This does not weaken floor or retirement guards, regenerate a missing original,
count a control ACK as a vote observation, or reset a deadline. Unstaged ACCEPT
and PROOF histories take the same acceptance path without inventing an old
certificate. No storage/wire schema or production timeout/resource bound changes.

Local validation covers three-voter native histories at the old ACCEPT, PROOF,
CERTIFICATE and APPLIED boundaries, malformed replacement and higher-ballot
refusals. Original-first replay derives bootstrap, both selections, immutable
sources, exact votes, old derived state, both published slots and actual network
transfers; a new barrier cannot be substituted for the carried entry. All four carried histories and the final-source ordinary dispatcher history pass
portable optimized replay with 61 exact negative mutations. Sixteen Java tests
and 680 Python tests pass. Earlier failure and successful diagnostic evidence
remain separately source-bound; no process-crash qualification is inferred from
these live TCP histories.

This is whole-slot continuation under an explicitly started native campaign,
not an autonomous election loop or public READY. Larger combined headroom,
carried INTENT/FINAL across authority changes, learner ADD/REPLACE, complete
process/network fault coverage and the full Phase 3 checklist remain open.
