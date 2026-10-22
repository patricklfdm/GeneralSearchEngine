# Phase 2C5a — original pending ACCEPT and fresh source capture

Status: local component qualification PASS. The public runtime remains disabled and Phase 2 remains open.

## Actual local ownership

`openVoting` coordinates the existing exclusive root owner, exact current selector,
original PROMISE/SELECTED, immutable ENTRY/origin/payload, and a real locally forced
ACCEPT. The first entry must be the selected carried entry; when no entry was
carried, it must be a new eligible next-slot entry with this ballot's origin.
Full configuration/control validation runs before writing. An exact duplicate
returns the same local observation; conflicting bytes or a higher observed ballot
cannot return the earlier request's success.

A mandatory provisioned `pending.accept` container stores original records and
payload. A complete `pending.accept.next` candidate is forced, its parent is forced,
then it atomically replaces the active file and the parent is forced again. Only
then can a local Owned observation return. A complete candidate left by process
death is validated against the original journal and unchanged current selection
before completion. A partial candidate requires a fully validated request matching its retained
prefix and immutable entry/payload binding to supply its missing suffix. It blocks other authority mutations; it is
never an empty vote, inferred ACK, alternative entry or silently deleted staging.
The existing active file must remain present and valid throughout recovery.

The bounded container is private framing: `GSPV`, version 1.3, total length, original
SELECTOR/PROMISE/SELECTED/ENTRY/ACCEPT frames, payload length and bytes. It adds no
frozen record/wire kind and defines no new application operation encoding. Its
12-byte empty form is provisioned by the private fixture only. Production EMPTY /
verified-backup bootstrap remains a separate required task.

## Capture, budgets and retention

PREPARE composes the actual pending ENTRY, payload and ACCEPT with all immutable
current objects. It preserves terminal application/catalog/cut, derives the new
inventory/capsule digest and captures the highest actual owned ACCEPT at the next
slot. Older BASIS/source packets remain unchanged. Capture recovery binds both
the original selected generation and pending file; half-intent, source and BASIS
recovery must reconstruct that exact combined source.

Active and candidate files share the existing **32 MiB JOURNAL** reservation with
`grants.gsr`. Admission accounts for the old active bytes, complete new candidate,
and the next maximum PROMISE/BASIS response. It also builds/checks the complete
future **32 MiB source packet before forcing ACCEPT**. An 8 MiB DATA payload does
not go into the 2 MiB MISC reservation or an uncounted extra journal.

The pending vote's original source cannot retire. Existing compaction already
preserves that source's complete original journal group. Same-parent higher-ballot
selection/install/reaccept retains the immutable ENTRY/origin/payload. This batch
refuses advancing-generation or cross-view adoption while a pending vote exists;
covered-tail retirement and proof/publication integration must remove that private
development restriction before complete-store/public acceptance.

## Retained qualification

All **42 cases / 270 fresh JVMs**, **12 exact evidence negatives** and portable
replay passed in **148.382 seconds**. The process matrix covers 3/4/5-node
stable clean profiles with/without an original carried entry, halt/SIGKILL at nine
ACCEPT boundaries, and repeated death at seven candidate-recovery plus two
active-reseal boundaries. Every successful case then captures the actual vote
through a fresh original PREPARE and reopens it in another process.

The reactor passed **246 Java tests**. The final **13-test pending suite** includes
two subsequently added tests for six interrupted fresh-capture boundaries and
3/4/5-node joint FINAL/new-stable DATA acceptance, for **248 distinct Java tests**
across those commands. Other tests cover same-parent higher-ballot reaccept after
real selected installation/floor retirement, duplicate/conflict/observation fencing,
missing/corrupt originals, same-byte inode replacement, maximum 8 MiB payload,
shared journal exhaustion and source-packet exhaustion before force. The **25
focused Python/build tests** passed normally and under `-O`.

The first focused development run exposed the composed-source/current-context
identity mismatch; it was corrected while retaining the original current-context
observation guard. Another focused run had one incorrect expected capacity error
text; the unchanged production refusal occurred before writes. Both original
logs remain retained. Neither failed run is counted as acceptance.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.pending_accept_qualification target/v53-pending-accept-new
```

[Source/build/evidence index](phase2-evidence/pending-accept.json).
Raw process logs, snapshots and development failures remain under
`target/v53-pending-accept/`.

## Remaining work

PROOF/certificate persistence, full application/sequence/catalog publication,
covered-tail and partial-request cancellation under a new durable fence, stable
round progression and INTENT termination, maximal SOURCE/APPLICATION completion
headroom, complete bootstrap/reopen, distributed protocol and physical S/N closure
remain required. Historical remote quorum observations are fixture inputs. Local
force/reopen and halt/SIGKILL evidence does not assert remote network ACKs, service
readiness or power-loss durability. No separate V5.2 Runner, workflow or cloud change.
