# Original-source joining ledger replay

Phase 3 remains **OPEN**. This layer reconstructs the joining initialization
bytes independently of the Java test's reported seed/plan/PASS fields. It does
not establish complete capsule ancestry, force/network provenance, process-death
recovery, FINAL/BARRIER completion, or public readiness.

`scripts.v53.joining_retention_evidence` first reads the strict portable native
joining snapshot. The installed generation and its actual capsule supply the
new identity, root and cut. Each retained old source must occur in its actual
old owner's grant journal and original `sources/<basisId>/source.gscp`. A copied
standalone source or a claimed endpoint alone cannot pass this binding.

The independent decoder checks the exact old majority, distinct ordered owners,
same original ballot, settled tails, full packet/BASIS inventories, included
peer/learner wrappers and their matching capture promises. The default mode
conservatively unions every retained endpoint, including pending learner renewals.
It does not interpret peer confirmations. Different same-index endpoints, a
future endpoint, wrong permanent identities and excess endpoint counts reject.

From those inputs, derive the canonical seed and all three revision-zero ledgers
for the original joining identity. Reconstruct the initialization decision and
completion frames, including their recorded original inode keys and native-owner
binding; compare every byte to the actual files. Current initial ledgers must
still match exactly. A later used-owner snapshot is deliberately not accepted as
an initialization snapshot. Recorded paths are data, never opened as live paths.

The reader deliberately returns **PARTIAL**, including separate false fields for
capsule ancestry, force/network and whole-history qualification. The original
source snapshots still need the complete protocol history oracle: the inventory
and source binding checked here do not turn stored claims into consensus proof.

## Validation

- 42 focused Python tests pass, including all five conditional ADD/REPLACE
  profiles, source/ballot/identity rejection, conservative union and strict copied
  inventories. Conditional fixtures are never native-history evidence.
- Replayed the initialized/cold-reopened substage of the retained failed native
  run `joiningearlyhistory-4f644ca2`. Its two original old sources reconstruct
  exactly the actual seed, peer/future/learner ledgers and both transaction files.
  That execution still failed later at the coordinator scratch-parent defect.
- All 13 exact evidence negatives reject. Mutated copied files have their copied
  inventory hashes updated where appropriate, so these cases exercise semantic
  checks rather than merely stopping at a checksum. Validate the unmodified
  original before any mutation; an invalid original cannot count as successful
  negative qualification.
- No Java, workflow, POM, wire/resource limits or cloud behavior changes in this
  increment. The corrected coordinator whole history remains independently
  tracked in [native qualification](PHASE_3_NATIVE_JOINING_QUALIFICATION.md).

Portable source/data hashes and command results are recorded in
[the receipt](phase3-evidence/joining-ledger-replay.json). The corresponding
archive retains the reader dependencies and original failed-history raw bytes;
each archive member is hash checked after packing.

```bash
python3 -B -m scripts.v53.joining_retention_evidence /path/to/native/raw --qualify
```

This command qualifies only the stated ledger derivation layer. Complete
initialization authority, full native/process histories, all actual profiles and
alternative majorities remain in the [acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).

## Explicit confirmed-peer mode

Current native originals can carry complete-copy confirmations and pending
renewals. Use `--confirmed-peers` for those originals; a failed default replay
never silently changes interpretation. All original packet/BASIS, journal,
owner, promise and source-cut bindings still apply.

Before dropping any peer endpoint, the reader checks every source's possible
endpoints and renewal obligations against its exact current generation's capsule
endpoints or retained ancestry. It checks bridge framing, both endpoints,
permanent ACK identities, exact statement bindings and the governing majority.
It validates all supplied bridges, including ones no longer needed after merge.
These checks establish endpoint bindings; they are not independent reconstruction
of the complete capsule history or proof that an ACK was actually forced.

The merger rejects original conflicts across peers and sources before discharge.
It selects the highest confirmed endpoint for each permanent peer, breaking
equal-endpoint ties by the SHA-256 of the exact encoded generation. Only strictly
older peer endpoints are discharged. Later unresolved targets remain, the final
two-endpoint limit remains, and learner renewals are always merged conservatively.
The initial ledgers and transaction files are still compared byte for byte.

```bash
python3 -B -m scripts.v53.joining_retention_evidence /path/to/native/raw \
  --confirmed-peers --qualify
```

Confirmed-mode negative qualification requires an original confirmation and adds
missing/changed confirmation checks to the original 13 mutations. Each mutation
must reject at its exact expected check, after the unmodified original validates.
The result remains **PARTIAL**: `capsuleAncestryQualified`,
`forceAndNetworkQualified`, `nativeHistoryQualified` and `phase3Complete` remain
false. Passing this layer does not convert a failed later continuation into a
successful complete history.

The full early-start native probe of `825513a4` reached actual JOINT publication
and original joining-prefix receipt, then rejected a third renewal in the test
coordinator's pre-seed maintenance. That coordinator still called strict
`retainPeerObservation` directly after forcing the complete floor. It now uses
`retainMaintenancePeerObservation`, matching production maintenance: full debt
remains in the original ledger until the actual joining-source merge. The strict
operation, its rejection checks, production Java and all resource/time limits
are unchanged. This failed original remains retained independently of the
corrected execution.

The next retained execution passed that maintenance boundary and the two
maintenance regression methods, then stopped at the fixture's remaining literal
learner expectation `[3,5]`. Its actual PREPARE/SEAL endpoints were `[4,8]` because
the real pre-command selections also publish BARRIERs. The assertion now requires
the endpoints of those already completed PREPARE and SEAL operations, preserving
the exact two obligations rather than deleting an expected endpoint. Both failed
executions remain failed; neither is replaced by the later run's result.

The corrected-index execution completed actual remote initialization, FINAL at
cut 10, the fresh stable BARRIER at cut 11 and retaining stable cold reopen.
However, closing the fixture then failed while encoding `events.json`: the whole
trace exceeded the single-message 65,536-token budget. The test remains **FAIL**.
Its `wire.json` and joining snapshots/results survive; `events.json`, `calls.json`
and `after-close` do not. Missing observations are not reconstructed or combined
with a later execution to manufacture a complete pass.

`V53EvidenceArray` now encodes each test observation using the unchanged protocol
encoder, then assembles the canonical array under the existing aggregate byte
limit. Network wire/events/failures and native call histories use this helper.
No production parser, per-record token/depth check or file byte limit changes.
Seven serialization regressions pass, including a 20,000-row trace reproducing
the old token error, byte-limit boundaries and identical small-history bytes.
The two native maintenance regressions and 77 related Python tests also pass.

On that failed execution's unchanged initialized substage, confirmed-mode replay
derives the exact three ledgers and both transaction files; all 15 negatives
reject at their specified checks. Default legacy mode explicitly rejects its
confirmation-bearing plans. The earlier legacy original still passes its 13
negative checks. The complete corrected-writer history and full independent
physical/force/network replay remain required. Retained source hashes, execution
outcomes, portable replay and archive identities are in
[the qualification receipt](phase3-evidence/joining-confirmations.json).
