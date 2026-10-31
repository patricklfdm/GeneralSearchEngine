# Original joining export lifetimes and record capabilities

`scripts.v53.joining_export_evidence` extends the
[network reader](PHASE_3_JOINING_NETWORK_REPLAY.md) on the same uninterrupted
`9136083f` native `3-ADD` execution. It first requires the complete independent
physical and network replay. Checked original snapshots supply exact bytes;
an object appearing anywhere in the history does not authorize its export at
an arbitrary later point. No native execution or measurement is repeated.

## What this reader binds

The transfer decoder exposes contents only after the exact original commit.
An opening rejection, partial download or exact retry does not create another
completed content observation. The original session context and four causal
network boundaries remain mandatory.

The reader derives 41 current-generation intervals from the exact selector
changes and completed installation/publication returns. The initial joining
owner additionally requires its original directory force. Each checked session
must remain inside one owner's interval through its last server commit response.
Current packet, ancestry and generation aliases are derived independently from
the verified cut and scope. Permanent identities and proposer storage identity
must match the current catalog. Generation metadata, packet and images are
compared against the particular original snapshot, not a union of historical
objects. A metadata-only client sequence does not independently establish that
all packet and image contents were transferred; that composition remains part of
the prerequisite physical replay.

Nineteen frozen-source intervals start at the completed writer-held capture and
end at the exact source's retirement transaction. A source session requires its
original BASIS, PROMISE, packet alias, view and ballot. Images may be omitted only
when the recipient's verified current generation already contains their exact
bytes throughout the session. The source's recorded identity determines its
retirement boundary.

There are also 382 record-capability intervals. Forced journal records, completed
accept/proof/certificate records, vote receipts, payloads and applied checkpoint
ACKs retain their respective original owners, bytes and boundaries. A new local
PROMISE ends live vote/payload/application capabilities even before a selector
replacement. Historical generic records remain distinct from live vote receipts.
An unused checkpoint ACK inside a packet cannot become authenticated evidence:
it must be referenced by the verified capsule or ancestry, or by the original
live application capability.

A completed publication may expose its own exact local checkpoint through the
original request view after the view changes. This exception requires the
original ballot, authenticated retained bytes and an uninterrupted publication
capability ending at the next local PROMISE or generation replacement. It does
not permit old grants, vote receipts or payloads under that earlier view.

Two joining ACK transfers occur before node 4 has a native current generation.
They instead require the original pending-intent ACK force, parent force and
completed return, the original old voter/view/ballot and the pending listener.
The pending export interval ends when retention handoff starts. These transfers
do not manufacture ordinary voter authority for the joining node.

## Observed coverage and explicit gaps

| Content family | Sessions | Committed contents |
| --- | ---: | ---: |
| Current generation / prefix | 104 | 368 |
| Frozen source | 20 | 60 |
| Journal records | 18 | 18 |
| Learner current content | 6 | 27 |
| Native applied checkpoint | 27 | 27 |
| Native vote receipt | 90 | 90 |
| Pending joining checkpoint | 2 | 2 |
| Pending payload | 7 | 7 |
| Pending record | 52 | 52 |
| Completed local checkpoint through prior view | 4 | 4 |
| Published record | 23 | 23 |
| **Bound by this reader** | **353** | **678** |
| Joining control exports still unqualified | 8 | 8 |

The network reader counts 363 attempted sessions: 361 contain committed content,
and two are rejected-only attempts. The 353 bound plus eight unqualified sessions
refer to those 361 content-bearing sessions; rejected attempts are not coverage.

The six learner content sessions have their original aliases, request context,
current bytes and generation lifetimes checked. Their temporal retention/quorum
authorization is **not** established by those content checks. The eight remaining
sessions contain the learner root and joining intent, preparation, retention and
completion control exports. Their exact original references and event positions
are enumerated in the result for subsequent control/retention composition.

The result is deliberately `PARTIAL`. `allExportFamiliesQualified`,
`learnerRetentionAuthorizationQualified`, `completePhysicalQualified`,
`forceAndNetworkQualified`, `processDeathQualified` and `phase3Complete` remain
false. Export expiry/cancellation under faults, the remaining maintenance/control
boundaries, process cuts, all seven profiles and the frozen acceptance mapping
still require their own qualification. This healthy history does not establish
those cases or an elapsed-time guarantee.

## Validation and provenance

The [batch receipt](phase3-evidence/joining-export-replay.json) records the original
source/build, reader inputs, original-first replay, 12 negative results and
portable archive. Negatives change only the observed transcript: every physical
file and directory must remain unchanged, and the existing network gate must
still pass before the new authority reader rejects the declared error. A bad
unmodified original, broken transport, accepted mutation or unrelated error fails
qualification rather than counting as a successful rejection.

Negatives cover changed generation/source aliases and bytes, wrong source ballot,
post-retirement source access, changed vote-receipt alias/voter, pre-force receipt
access, wrong request view, a foreign completed-checkpoint voter and pending ACK
access after handoff. Unit regressions also guard fresh-promise revocation, the
narrow prior-view exception, authenticated checkpoint references, force/parent
ordering and completed-content collection.

Early reader diagnostics remain retained. They identified learner-specific
aliases, empty ancestry, the pre-native pending listener and the completed
publication's prior-view checkpoint exception. These were gaps in the new reader,
not newly observed runtime failures. The first full negative qualification passed;
the final qualification additionally checks proposer storage identity and
fresh-PROMISE revocation. The portable replay uses the frozen reader source and
must reproduce the exact same `PARTIAL` coverage result after extraction.

Production Java, POMs, workflows, frozen formats, bounds and toolchain are unchanged.

```bash
python3 -B -m scripts.v53.joining_export_evidence <collection-v3-raw> --qualify
```
