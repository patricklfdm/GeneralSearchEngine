# Original joining peer ledger composition

`scripts.v53.joining_peer_evidence` follows the peer retention ledger continuously
through the existing `9136083f` healthy native `3-ADD` execution. It requires the
complete [maintenance replay](PHASE_3_JOINING_MAINTENANCE_REPLAY.md) first,
including the preceding physical, network, export and control readers. It creates
no new native execution, source grant, floor or replacement observation.

## Continuous derivation

The reader initializes the three old voters from the original bootstrap packet
and permanent identities. The joining voter's initial ledger comes from its exact
retained seed and original old-voter sources. Each subsequent state uses the
previous derived bytes, rather than restarting from a reported final ledger.

| Cause | Durable writes | Original authority |
| --- | ---: | --- |
| Maintenance observation and view reconciliation | 54 | Complete copies owned by the already forced governing floor |
| Selected-source merge | 12 | Exact local predecessor, selected recovery intent and frozen source ledgers |
| Publication future-target promotion | 24 | Original applied target, publication proof and retained future ledger |
| Total | 90 | One continuous original history |

Maintenance uses the actual copy observation order. It preserves unresolved
endpoints, original confirmation bytes and renewal obligations. A deferred
observation at the existing renewal bound does not create a revision or consume a
write. Adding the joining identity requires its actual complete copy under the
governing floor. Final-view reconciliation preserves all retained identities.
The two direct fixture floors remain direct observations; this reader does not
relabel them as network acquisition.

Selection binds the original before-ledger bytes to the selected generation's
recovery intent and merges the selected sources' frozen plans. Publication uses
the preceding applied snapshot and original proof to derive promotion. A no-op
preserves the exact bytes. Every change advances revision by exactly one, retains
root and permanent owner, and names the preceding complete record's hash.

The continuous states must match 97 retained observations: bootstrap and joining
initialization, installed generations, before/after publication, all 19 frozen
grant ledgers, eight open-time reseals and cold-close snapshots. The final revisions are 40, 40, 0 and 10
for nodes 1–4 respectively. These counts describe this producer's fixed history;
they are not general limits or a claim about other profiles.

## Durable lifetime composition

Each change consumes exactly one original seven-event write sequence: before
write, prefix written, written, file forced, candidate parent forced, renamed and
final parent forced. The owner and scope must remain unchanged throughout. Every
sequence must belong to exactly one derived change:

- Maintenance writes finish after the floor becomes durable and before retirement
  starts, or before release starts when no generation is retired.
- Selected merges finish after installation's parent force and before the selected
  completion callback. No-op installations have no completion or write.
- Publication promotions finish after publication retirement and before the
  future-retention promotion callback.

Incomplete, duplicate, out-of-lifetime and unbound writes are rejected. Every
selected completion must belong to an actual selected merge. Original source and
owner lifetimes remain prerequisites from the preceding readers.

The eight original opens also reseal the existing active peer file and its parent.
Both forces must follow current-generation validation and learner recovery, and
precede future-retention recovery in the same original owner scope. Resealing
preserves the continuously derived bytes and revision. Missing, reordered and
unbound reseals are rejected. All peer-retention callbacks must be accounted for
by these reseals or the 90 write chains; other retention paths are unsupported in
this fixed healthy-history reader.

The intermediate ledger bytes are independently derived and checked against the
retained snapshots; individual write callbacks do not contain captured candidate
bytes. This composition therefore does not establish crash-prefix recovery for
each intermediate transaction. That requires the separate process-cut evidence.

## Qualification

The [receipt](phase3-evidence/joining-peer-replay.json) retains the original result,
negative results, test logs, producer bindings and portable archive reference.
Twenty negative variants modify only the event trace, preserving every physical
file, directory and wire byte. Each must still pass network, export, control and
maintenance replay before failing this reader for its exact declared reason.

Variants remove forces or entire writes, reorder rename, change ownership, leave
an incomplete final write, add duplicate or unbound writes/completions, move
maintenance outside its floor interval, move selected writes before installation
or their completion before force, and move publication writes across promotion or
retirement. Invalid originals, unrelated failures and accepted mutations fail the
qualification driver itself.
The additional reseal variants remove the parent force, reverse the two forces,
move them after future recovery, or introduce a foreign owner.

This qualifies the healthy peer-ledger composition boundary. Faulted, expired and
cancelled operations, process halt/SIGKILL/restart, all seven profiles and the
frozen acceptance mapping remain required. Whole Phase 3 flags stay false.
Production Java, POM, workflows, frozen formats, toolchains and workload parameters
are unchanged.

```bash
python3 -B -m scripts.v53.joining_peer_evidence <collection-v3-raw> --qualify
```
