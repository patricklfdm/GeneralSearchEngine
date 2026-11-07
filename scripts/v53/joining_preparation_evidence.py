"""Original-first joint preparation and continuation with every captured grant.

Unlike the archived conditional reader, this requires the complete intermediate
sources from one new execution. Copied directories are comparison targets only.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_continuation_evidence as continuation
from . import joining_grant_captures as captures
from . import joining_source_retirement as retirements

c = continuation
init, s, f, disk, need, sha = c.init, c.s, c.f, c.disk, c.need, c.sha


class Captures:
    def __init__(self, root, events, *, voters=('node-1', 'node-2'), old_owner_lifetimes=None,
                 bootstrap_source='EMPTY', wire_layout='JSON'):
        self.root = Path(root)
        self.source_args = captures.policy.options(bootstrap_source, wire_layout)
        rows = captures.collect(root, events, **self.source_args)
        self.counter = captures.require_intermediate(root, rows, voters=voters, old_owner_lifetimes=old_owner_lifetimes, **self.source_args)
        self.by_ballot = {(v['node'], f.canonical(v['ballot'])):v for v in rows}
        need(len(self.by_ballot) == len(rows), 'joining preparation duplicate observed grant')
        self.used = set(); self.comparisons = 0; self.derived = {}

    def original(self, node, ballot):
        key = node, f.canonical(ballot)
        need(key in self.by_ballot, 'joining preparation original capture missing')
        path = self.root/self.by_ballot[key]['capture']/'replica'
        if self.source_args.get('wire_layout') == captures.policy.SEGMENTED:
            return captures.inventory(path, **self.source_args)[0]
        return disk.inventory(path)

    def match(self, node, files):
        root = f.decode(files['node.gsr'], 'records', 'NODE')['root']
        journal = disk.journal(files['grants.gsr'], root, node)
        need(len(journal) >= 2 and [v[0] for v in journal[-2:]] == ['PROMISE','BASIS'], 'joining preparation derived complete grant')
        key = node, f.canonical(journal[-1][2]['ballot'])
        need(key not in self.used, 'joining preparation duplicate derivation')
        actual = self.original(node, journal[-1][2]['ballot'])
        expected = {k:v for k,v in files.items() if k != '.'}
        need(actual == expected, 'joining preparation exact captured inventory: '+node+': '+str(journal[-1][2]['ballot']['counter']))
        self.used.add(key); self.comparisons += 1; self.derived[key] = copy.deepcopy(expected)

    def complete(self):
        need(self.used == self.by_ballot.keys(), 'joining preparation underived captured grant')

    def retirement_order(self, events, final, *, owners=c.VOTERS):
        self.complete(); segments = 0
        for node in owners:
            keys = sorted((k for k in self.by_ballot if k[0] == node), key=lambda k:self.by_ballot[k]['capturedEvent'])
            for i, key in enumerate(keys):
                before = self.derived[key]; start = self.by_ballot[key]['capturedEvent']
                if i+1 < len(keys):
                    following = keys[i+1]; after = self.derived[following]; end = self.by_ballot[following]['capturedEvent']
                else: after = final[node]; end = len(events)
                deleted = source_deletions(before, after)
                local = [v['event'] for v in events[start+1:end] if v.get('node') == node]
                retirement_order(local, deleted); segments += len(deleted)
        return segments


def source_deletions(before, after):
    def sources(files): return {n.split('/')[1] for n in files if n.startswith('sources/') and n.endswith('/source.gscp')}
    return sorted(sum(raw is not None and name.startswith('sources/'+identifier+'/') for name,raw in before.items())
                  for identifier in sources(before)-sources(after))


def retirement_order(local, deleted_file_counts):
    """Check local journal-before-delete callbacks, not identity-linked force proof."""
    prefix = ['SOURCE_RETIREMENT_'+v for v in ('CREATED','WRITTEN','FORCED','PARENT_FORCED')]
    prefix += ['JOURNAL_ROTATION_'+v for v in ('CREATED','WRITTEN','FORCED','RENAMED','PARENT_FORCED')]
    prefix += ['SOURCE_RETIREMENT_JOURNAL_PRUNED']
    suffix = ['SOURCE_RETIREMENT_'+v for v in ('DIRECTORY_DELETED','CLEARED','BEFORE_RETURN')]
    rows = [v for v in local if v != retirements.EVENT and v.startswith(('SOURCE_RETIREMENT_', 'JOURNAL_ROTATION_'))]
    position = 0; observed = []
    while position < len(rows):
        need(rows[position:position+len(prefix)] == prefix, 'joining preparation original source retirement order')
        position += len(prefix); count = 0
        while position < len(rows) and rows[position] == 'SOURCE_RETIREMENT_FILE_DELETED': position += 1; count += 1
        need(count > 0 and rows[position:position+len(suffix)] == suffix, 'joining preparation original source retirement order')
        position += len(suffix); observed.append(count)
    need(sorted(observed) == sorted(deleted_file_counts), 'joining preparation original source retirement count')


class History(init.placement.History):
    def __init__(self, root, replay, originals):
        self.originals = originals
        super().__init__(root, replay)

    def prepared(self, node, files): self.originals.match(node, files)


class Initialization(init.Initialization):
    def __init__(self, root, handoff, originals):
        self.captures = originals
        super().__init__(root, handoff)

    def prepared(self, node, files): self.captures.match(node, files)


class Continuation(c.Continuation):
    def __init__(self, root, initialization, originals):
        self.captures = originals
        super().__init__(root, initialization)

    def prepared(self, node, files): self.captures.match(node, files)

    def preparation(self):
        boundary = c.preparation_boundary(self.root, self.group)
        ballot = init.next_ballot(self.group['node-1'])
        need(ballot['counter'] == self.captures.counter, 'joining preparation original next ballot')
        for node in ('node-1','node-2'):
            original = self.captures.original(node, ballot)
            self.group[node], source = init.prepare(self.group[node], ballot, original['grants.gsr'], self.identifiers)
            self.prepared(node, self.group[node])
            if node == boundary['oldPeer']:
                need(sha(source[0]) == boundary['observedBasisSha256'], 'joining preparation response original basis')
            else:
                rows = disk.journal(self.group[node]['grants.gsr'], self.replay.root, node)
                need(sha(rows[-2][1]) == boundary['observedProposerPromiseSha256'], 'joining preparation transferred original promise')
        # Serving each new grant performs the governing-copy maintenance. Only
        # superseded sources with exact coverage may be retired. The newest
        # unselected preparation is still pinned until the next fresh grant.
        for node in ('node-1','node-2'): self.group[node] = self.maintenance(self.group, node)
        return boundary

    def run(self):
        boundary = self.preparation()
        counter = boundary['ballot']['counter']
        self.campaign(9, counter+1); self.slot(10)
        for node in c.VOTERS: self.group[node] = self.maintenance(self.group, node)
        self.campaign(10, counter+2); self.slot(11)
        self.match('after-close'); self.joining_snapshot('joining-originals-stable-cold')
        c.cold_order(json.loads((self.root/'events.json').read_bytes()))
        retirement_segments = self.captures.retirement_order(json.loads((self.root/'events.json').read_bytes()), self.group)
        return dict(status='PASS', scope='native-ADD-original-joint-preparation-and-continuation',
                    capturedGrantComparisons=self.captures.comparisons, ownerSnapshotComparisons=self.comparisons,
                    selectedInstallations=2, publications=2, finalCut=11, coldSnapshots=2,
                    sourceRetirementLocalOrderSegments=retirement_segments,
                    intermediatePreparationPhysicalQualified=True, unconditionalContinuationQualified=True,
                    completePhysicalQualified=False, forceAndNetworkQualified=False,
                    processDeathQualified=False, phase3Complete=False)


def validate(root):
    root = Path(root); original = s.collection.inventory(root)
    events = s.collection.read_json(root, 'events.json', s.collection.EVENT_BYTES)
    if (root/retirements.DIRECTORY).exists() or any(row.get('event') == retirements.EVENT for row in events):
        retirements.validate(root,events)
    observed = Captures(root, events)
    c.t.publication.validate(root)
    replay = s.Replay(root)
    for index in range(1,12): replay.step(index)
    history = History(root, replay, observed); history.run()
    owner = init.placement.Placement(root, history); owner.run()
    handoff = init.retirement.Retirement(root, owner); handoff.run()
    initialization = Initialization(root, handoff, observed); initialization.run()
    result = Continuation(root, initialization, observed).run()
    need(s.collection.inventory(root) == original, 'joining original changed during preparation replay')
    result['precedingOwnerSnapshotComparisons'] = history.comparisons+3
    return result


NEGATIVES = {
    'bootstrap-extra-allocation': 'joining preparation exact captured inventory: node-1: 2',
    'intermediate-extra-file': 'joining preparation exact captured inventory: node-2: 7',
    'intermediate-prior-source-lost': 'joining initialization exact prepared grant suffix',
    'intermediate-frozen-ledger': 'joining initialization exact frozen grant bytes',
    'native-grant-extra-file': 'joining preparation exact captured inventory: node-4: 6',
    'activation-obsolete-source-restored': 'joining preparation exact captured inventory: node-1: 8',
    'retirement-force-lost': 'joining preparation original source retirement order',
    'retirement-delete-extra': 'joining preparation original source retirement count',
    'duplicate-complete-grant': 'joining preparation duplicate observed grant',
    'joint-source-image-changed': c.NEGATIVES['joint-source-image-changed'][2],
    'standalone-grant-changed': c.NEGATIVES['standalone-grant-changed'][2],
    'cold-peer-revision': c.NEGATIVES['cold-peer-revision'][2],
}


def mutate(root, name):
    if name in c.NEGATIVES:
        c.mutate(root, name); return
    events = json.loads((root/'events.json').read_bytes())
    def locate(node, counter):
        for event in events:
            if event.get('event') != captures.EVENT or event['node'] != node: continue
            path = root/event['capture']; _, metadata = captures.json_file(path/'capture.json')
            if metadata['ballot']['counter'] == counter: return event, path, metadata
        raise ValueError('negative original grant absent')
    if name.startswith('retirement-'):
        event, _, _ = locate('node-1', 7); start = events.index(event)
        kind = 'SOURCE_RETIREMENT_FORCED' if name == 'retirement-force-lost' else 'SOURCE_RETIREMENT_FILE_DELETED'
        at = next(i for i in range(start+1,len(events)) if events[i].get('node') == 'node-1' and events[i]['event'] == kind)
        if name == 'retirement-force-lost': events.pop(at)
        else: events.insert(at,dict(events[at]))
    elif name == 'duplicate-complete-grant':
        first = [v for v in events if v.get('event') == captures.EVENT][-1]
        destination = 'grant-captures/capture-'+str(sum(v.get('event') == captures.EVENT for v in events)+1).zfill(4)
        shutil.copytree(root/first['capture'],root/destination)
        events += [dict(node=first['node'],scope=first['scope'],event='GRANT_BEFORE_RETURN'),dict(first,capture=destination)]
    else:
        node, counter = ('node-1',2) if name == 'bootstrap-extra-allocation' else ('node-4',6) if name == 'native-grant-extra-file' else ('node-1',8) if name == 'activation-obsolete-source-restored' else ('node-2',7)
        event, path, metadata = locate(node,counter); replica = path/'replica'
        if name == 'bootstrap-extra-allocation':
            allocator = replica/'allocator.gsr'; value = f.decode(allocator.read_bytes(),'records','ALLOCATOR'); value['counter'] += 1
            allocator.write_bytes(f.encode('records','ALLOCATOR',value))
        elif name.endswith('extra-file'): (replica/'unexpected.bin').write_bytes(b'not derived')
        elif name == 'intermediate-prior-source-lost':
            rows = disk.journal((replica/'grants.gsr').read_bytes(), metadata_root(replica),node)
            identifier = next(v['basisId'] for kind,_,v in rows if kind == 'BASIS' and v['ballot']['counter'] == 6)
            shutil.rmtree(replica/'sources'/identifier)
            (replica/'grants.gsr').write_bytes(b''.join(raw for kind,raw,v in rows if v['ballot']['counter'] != 6))
        elif name == 'activation-obsolete-source-restored':
            _, old_path, _ = locate(node,7); old = old_path/'replica'
            original = disk.journal((old/'grants.gsr').read_bytes(),metadata_root(old),node)
            prior = [row for row in original if row[2]['ballot']['counter'] == 6]
            identifier = prior[-1][2]['basisId']; shutil.copytree(old/'sources'/identifier,replica/'sources'/identifier)
            rows = disk.journal((replica/'grants.gsr').read_bytes(),metadata_root(replica),node)
            at = next(i for i,row in enumerate(rows) if row[2]['ballot']['counter'] > 6)
            (replica/'grants.gsr').write_bytes(b''.join(row[1] for row in rows[:at]+prior+rows[at:]))
        elif name == 'intermediate-frozen-ledger':
            journal = replica/'grants.gsr'; rows = disk.journal(journal.read_bytes(),metadata_root(replica),node)
            basis = dict(rows[-1][2]); promise = rows[-2][1]
            ledger = replica/c.PEERS; before = ledger.read_bytes(); state = c.peers.decode(before)
            state.update(revision=state['revision']+1,previous=sha(before)); after = c.peers.frame(state); ledger.write_bytes(after)
            source = replica/'sources'/basis['basisId']/'source.gscp'; packet = disk.p.decode(source.read_bytes())
            wrapper, _ = init.retention.source(packet,basis,0x47535250,65536)
            objects = dict(packet['objects']); objects.pop(sha(wrapper))
            replacement = init.retention.peer_source.wrap(promise,after); objects[sha(replacement)] = replacement
            encoded = disk.packet_bytes(packet['capsule'],objects,packet['images']); source.write_bytes(encoded); packet = disk.p.decode(encoded)
            basis.update(capsule=sha(packet['capsuleBytes']),inventory=sha(packet['indexBytes']))
            value = f.encode('records','BASIS',basis); journal.write_bytes(b''.join(row[1] for row in rows[:-1])+value)
            metadata.update(basisSha256=sha(value),packetSha256=sha(encoded));event['basis'] = sha(value)
        else: raise ValueError('unknown preparation mutation')
        _, inventory, _ = captures.inventory(replica)
        metadata['files'] = [dict(name=k,identity=inventory[k]) for k in sorted(inventory)]
        encoded = f.canonical(metadata); (path/'capture.json').write_bytes(encoded); event['sha256'] = sha(encoded)
    (root/'events.json').write_bytes(f.canonical(events))


def metadata_root(replica):return f.decode((replica/'node.gsr').read_bytes(),'records','NODE')['root']


def qualify(root, progress=None):
    root = Path(root); original = validate(root); outcomes = []
    if progress: progress(dict(stage='original',status='PASS'))
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-preparation-negative-') as temp:
            target = Path(temp)/'raw'; shutil.copytree(root,target); mutate(target,name)
            events = s.collection.read_json(target,'events.json',s.collection.EVENT_BYTES)
            captures.validate(target,events,whole_history=True)
            init.validate(target)
            try: validate(target)
            except ValueError as error:
                need(str(error) == reason,'unrelated joining preparation negative: '+name+': '+str(error))
            else: raise ValueError('joining preparation mutation accepted: '+name)
        outcomes.append(dict(case=name,status='REJECTED',reason=reason,captureCollection='PASS',initializationGate='PASS'))
        if progress: progress(outcomes[-1])
    return dict(original=original,negatives=outcomes)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify',action='store_true'); args=parser.parse_args()
    report=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(args.root,report) if args.qualify else validate(args.root), sort_keys=True))
