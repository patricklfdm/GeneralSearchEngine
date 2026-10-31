# Original joining discovery and maintenance floor replay

`scripts.v53.joining_maintenance_evidence` extends the original `9136083f`
healthy native `3-ADD` history. It first requires the complete
[control replay](PHASE_3_JOINING_CONTROL_REPLAY.md), including the earlier
independent physical, network and export readers. No new workload, source grant,
recording, floor or execution is created to repair an earlier history.

## Discovery is a hint

All 55 original `STATUS_PROBE`/`STATUS` exchanges bind the permanent sender and
proposer storage identities, exact nonce, original responder's current cut and
`ready=false`. Correlation can name an earlier view or a learner's original
ballot. It does not change the responder's current configuration or grant a
PROMISE, installation, READY, read barrier or permission to delete anything.
The joining responder must still belong to its original live endpoint owner.

## Complete original floor copies

The history contains 40 floor lifetimes and 96 complete original generation
copies. Their routes stay explicit:

| Route | Floors | Remote copies | Required observation |
| --- | ---: | ---: | --- |
| Native network maintenance | 38 | 52 | Delivered STATUS, original packet and complete generation metadata transfers |
| Direct calls in the existing joining fixture | 2 | 4 | Original still-open old and joining owners' copy-return callbacks |

The network reader requires delivery of the original hint before the packet
request, and complete packet delivery before generation acquisition. All final
transfer commits must reach the receiving owner before it reserves the floor;
a server-side commit alone is insufficient. Each remote copy retains its actual
identity, manifest and every member from the preceding byte/authority replay.
Packet-only acquisition borrows actual local image bytes, checked by length and
digest; equality of a terminal application identifier cannot supply absent data.

Each floor includes its exact local current generation, complete copies at the
same root and endpoint, and the original governing majority. During JOINT this
also requires the actual newly added owner's copy. The two direct fixture floors
remain direct observations, not synthetic network exchanges. Their joining copy
must come from the live initial owner after native placement. They do not prove
automatic discovery or transport for those two calls.

## Force, handoff and release

The reader derives the entire floor write/force sequence and release counts from
those complete members. Every manifest, image and metadata member must be forced
before its copy directory. Network receiving ownership is handed off only after
that durable copy exists. All copies and the floor authority must be forced
before the floor returns.

Generation retirement must force its authority and parent before deletion, and
finish while the same floor remains owned. Source-retirement callbacks and the
already qualified transient captures must also remain inside that floor lifetime.
The original capture label `network-owner` is normalized only for that explicit
capture event; unrelated endpoint scopes are rejected.

Release requires its own forced authority and parent before relinquishing the
floor. It then deletes exactly the complete copied files and directories before
clearing the proposal, release authority and final directory. No floor event may
remain outside the validated intervals. A repeated floor must reacquire its own
network observations; an earlier successful STATUS cannot silently be reused.

## Qualification and remaining work

The [receipt](phase3-evidence/joining-maintenance-replay.json) records the original
result, negative results, tests and portable archive. Fourteen negative variants
preserve every physical file and directory and must still pass network, export
and control replay. They alter status cut/nonce/readiness, delay discovery or
final-copy delivery, remove a force or deletion, move handoff/authority/release,
move retirement outside its floor, omit a direct joining copy, or add an unbound
floor event. Only the exact expected rejection counts; invalid originals,
unrelated failures and accepted mutations fail qualification.

This is the observed healthy maintenance force/acquisition boundary. The earlier
physical reader still supplies the derivation of complete generations and
captured source-retirement bytes; callbacks do not invent missing transient
records. Broader peer-observation/retention composition, expired or cancelled
operations, process halt/SIGKILL/restart, all seven profiles and the frozen
acceptance mapping remain required. Whole Phase 3 flags remain false. Production
Java, POM, workflows, frozen formats, toolchains and workload parameters are
unchanged.

```bash
python3 -B -m scripts.v53.joining_maintenance_evidence <collection-v3-raw> --qualify
```
