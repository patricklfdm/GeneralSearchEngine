# Independent replay of three native automatic owners

Phase 3 remains **OPEN**. This batch independently replays the retained successful
`V53CompetingNodeQualification` execution from the
[recovery-heartbeat batch](PHASE_3_RECOVERY_HEARTBEAT.md). That producer's unchanged
receipt remains `PARTIAL`; its assertions and diagnostics supply no vote, floor,
publication or readiness authority. No workload is rerun and no Java, POM,
workflow, default bound or timing policy changes.

## Whole-history reconstruction

The reader admits the original three-node bootstrap, then derives the campaign's
proposer and selected majority from original SELECTED bytes. The fresh source
identifiers are observations; the expected PROMISE/BASIS, retained wrappers,
selection, installed generations and all later files are reconstructed from
original inputs. Role names are not relabelled and a winner is not chosen by the
reader. Unsupported additional campaigns or grants fail rather than being ignored.

The two slots are the original fresh BARRIER and the sole DATA operation adding
document 100 with value `competing-node-100`. Intermediate ACCEPT/PROOF,
certificate, application, retention and publication states are derived in memory,
not supplied as fabricated evidence snapshots. The actual final directories of all
three owners must match exactly. The original application image is checked for
its typed contents. The unselected owner cannot gain writes or voting authority
from status or heartbeat responses.

The original ROUND/SLOT hooks must match those derived entries, certificates,
majorities and publication acknowledgements. READY follows the fresh BARRIER;
the client observations must be exactly one start completion and one DATA
completion. The trace's monotonic timestamps order observations, not a measured
failover SLA.

## Network and ownership checks

Every raw send binds its complete bytes to its permanent sender, recipient,
root, view and digest. Each received request consumes a preceding send, each
response consumes a received request, and each delivery consumes a preceding
response. Byte-identical retries retain the existing three-attempt bound; a
duplicate or future response cannot invent delivery.

Complete source transcripts are matched to the independently derived original
bytes. Actual source/receipt delivery must precede the dependent grant, selected
installation, governing floor, PROOF, certified application or publication.
Retention is recorded by the real majority before **every** publication send.
Original force-order checks remain distinct from the peer's returned ACK.

Heartbeats are checked against the installed ballot and each owner's actual
published cut at the original event boundary. A sample's request stays immutable,
and each completed sample needs delivered contact with the governing majority
before continuation. Contact creates no durable grant, copied floor, read lease
or READY. This history has ten completed samples and one final sample interrupted
during close after client completion. The final sample cannot supply earlier
contact or authorization. Unanswered retention intents to the unselected owner
are tied to their exact slot and cannot satisfy recording quorum.

After close, archived scratch may contain only its original owner marker and
empty scope lock. Marker root, identity, role and recorded original-path binding
must agree, and the retained drain inventory must match every file. The zero-lease
claim is checked for consistency with the producer receipt; it is not a fresh
live-process resource measurement or process-death qualification.

## Evidence

The [source-bound receipt](phase3-evidence/competing-replay.json) retains the reader
hashes, original producer inputs, qualification outputs and verified portable
archive. The complete original passes before any mutation is attempted:

- Three native owners; one fresh campaign; one selected majority; one BARRIER
  and one client DATA operation. Final physical state and complete wire replay
  pass. The result is scoped to this single-campaign history.
- All **231 sends**, **223 response pairs** and **39 complete source transfers**
  are accounted for. There are twenty heartbeat replies and two distinct unused
  retention intents, each with three finite unanswered attempts.
- **32 evidence mutations** reject for their exact intended reasons, covering
  physical files, client/readiness hooks, original vote transfers, force order,
  send/receive conservation, heartbeat delivery, publication-before-quorum,
  leftover scratch and fabricated diagnostics. An invalid original or an
  unrelated rejection cannot count as a successful negative.
- The unchanged history also passes after archive extraction into a different
  directory; optimized Python (`-O`) reproduces all 32 exact negative results.
  The verified archive contains 2,910 files in 5,994,935 bytes.
- **30 focused Python tests** pass, including ten new reader/transport guards.
  No Java or long workload acceptance is repeated for this Python-only batch.

Replay an unpacked retained history with:

```bash
python3 -B -m scripts.v53.competing_node_evidence "$RAW" --qualify
```

This upgrades the independent physical/network evidence for the retained run;
it does not rewrite its producer receipt or erase previous failed executions.
The [observation-replay batch](PHASE_3_OBSERVATION_REPLAY.md) continues to qualify
its separate explicit-round component histories and historical reader mode.

## Remaining closure and rollback

One clean three-owner history does not establish general convergence, a latency
distribution, all stable sizes, all seven membership profiles, process-death
recovery or public service. The native joining/joint continuation gate, cold
receiving-scratch recovery, maximal combined resource headroom, fault matrices
and the full original Phase 3 requirement mapping remain open. Earlier component
gates retain their original source-bound scope.

Rollback removes these independent reader, network and negative-driver modules
and their tests together. Runtime behavior and persisted formats are unaffected.
Preserve the archived originals, reader-development outputs and source
manifests when updating the reader further.
