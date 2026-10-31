"""Derive predecessor retirement and native ownership from original placement.

This gate compares the immutable handoff and surviving original files. The later
retention initialization, new grant/source and allocator advance remain separate
physical transitions; their presence in the native snapshot is not acceptance.
"""
import argparse
import copy
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile

from . import joining_placement_evidence as placement

s, f, disk, need, sha = placement.s, placement.f, placement.disk, placement.need, placement.sha
KIB, MIB = 1024, 1024 * 1024
# Persisted 1.3 companion envelopes and resource reservations, not elapsed-time
# budgets. These agree with the original runtime whose input bytes are replayed.
COMPANIONS = (256 + 2 * 64 + 64 + 256 + 64 + 64) * KIB
PENDING_JOURNAL = 2 * (64 * KIB + 8 * MIB // 3) + 2048 + 32 * KIB
MUTABLE_ORIGINALS = frozenset(('allocator.gsr', 'grants.gsr'))


def metadata(files):
    return sum(len(raw) for name, raw in files.items() if raw is not None and not name.endswith('.image'))


def deletions(original, receipt):
    """Only the fixed projection of derived custody roots may authorize removal."""
    typed = [family for family in placement.CUSTODY_ROOTS if original.get(family, {}).get('learner.gsr') == receipt]
    need(len(typed) == 1, 'joining retirement unique typed original')
    removed = []
    for family in placement.CUSTODY_ROOTS:
        if family not in original: continue
        files = original[family]; keep = {'.'}
        for name, raw in files.items():
            if name.endswith('.lock') and raw == b'': keep.add(name)
            if family == 'replica' and name != 'learner' and not name.startswith('learner/') and name != 'learner-admission.gslp':
                keep.add(name)
            if family == typed[0] and name in ('preparation.json', 'learner.gsr'): keep.add(name)
        for name in tuple(keep): keep.update(str(parent) for parent in PurePosixPath(name).parents)
        removed.extend(dict(root=family, name=name) for name in files.keys()-keep)
    removed.sort(key=lambda row: (row['root'], -len(PurePosixPath(row['name']).parts), row['name']))
    need(removed and original['replica'].get('replica.lock') == b'', 'joining retirement original lock')
    return removed


def reservations(owner):
    """Reconstruct the actual original seed, two received cuts and dormant voter.

    Equal image bytes in different owned files incur distinct reservations. The
    original typed backup retains its full completion reservation, not its small
    observed file size. No reservation is read from retirement.json itself.
    """
    sources = owner.history.sources
    rows = [dict(unit=unit, bytes=metadata(sources[index])) for unit, index in
            (('GENERATION', 4), ('SOURCE', 8), ('LEARNER', 9))]
    rows += [dict(unit='GENERATION', bytes=metadata(owner.installed)+2*64*KIB+COMPANIONS),
             dict(unit='JOURNAL', bytes=PENDING_JOURNAL), dict(unit='MISC', bytes=2*MIB),
             dict(unit='APPLICATION', bytes=64*MIB)]
    for files in (*[sources[index] for index in (4, 8, 9)], owner.installed):
        rows += [dict(unit='APPLICATION', bytes=len(raw)) for name, raw in files.items()
                 if raw is not None and name.endswith('.image')]
    return sorted(rows, key=lambda row: (row['unit'], row['bytes']))


def native_storage(installed, surviving):
    rows = [dict(unit='JOURNAL', owner='membership-grants', bytes=32*MIB),
            dict(unit='MISC', owner='current-authority', bytes=2*MIB)]
    generation = {name.removeprefix('generations/a/'): raw for name, raw in installed.items()
                  if name.startswith('generations/a/') and raw is not None}
    rows.append(dict(unit='GENERATION', owner='a', bytes=metadata(generation)))
    rows += [dict(unit='APPLICATION', owner='generation-a:'+name, bytes=len(raw))
             for name, raw in generation.items() if name.endswith('.image')]
    misc = COMPANIONS + sum(len(raw) for family, files in surviving.items() if family in placement.CUSTODY_ROOTS and family != 'replica'
                            for raw in files.values() if raw is not None)
    misc += sum(len(raw) for name, raw in installed.items() if '/' not in name and name != 'grants.gsr' and raw is not None)
    need(misc <= 2*MIB, 'joining retirement native immutable capacity')
    return sorted(rows, key=lambda row: (row['unit'], row['owner']))


class Retirement:
    def __init__(self, root, owner):
        self.owner = owner
        self.snap = placement.snapshot.read(Path(root)/'joining-originals-native')
        self.ids = {family: {v['name']: v['identity'] for v in row.get('files', [])}
                    for family, row in self.snap.identities.items()}
        need({name for name, row in self.snap.identities.items() if row['present']} == placement.PRESENT | {'retirement', 'nativeOwner'},
             'joining retirement present roots')
        for family, row in self.snap.identities.items():
            need(row['path'] == owner.binding(family), 'joining retirement original path changed')
        self.removed = deletions(owner.expected, owner.receipt)
        self.expected = copy.deepcopy(owner.expected)
        for row in self.removed: del self.expected[row['root']][row['name']]
        self.expected.update(retirement={'.': None}, nativeOwner={'.': None})

    def key(self, family, name='.'):
        need(name in self.ids[family], 'joining retirement original identity missing')
        return self.ids[family][name]['key']

    def fingerprint(self, family, name, raw):
        return dict(key=self.key(family, name), size=len(raw), sha256=sha(raw))

    def records(self):
        owner = self.owner
        decision = f.canonical(dict(schema='gse-v53-joined-retirement/1.3', plan=owner.plan, root=owner.replay.root,
            identity=owner.joining, path=owner.binding('retirement'), directoryKey=self.key('retirement'),
            recordKey=self.key('retirement', 'retirement.json'),
            joined=self.fingerprint('placement', 'joined.json', owner.expected['placement']['joined.json']),
            deletions=self.removed, reservations=reservations(owner)))
        done = f.canonical(dict(schema='gse-v53-joined-retired/1.3', plan=sha(decision),
            planKey=self.key('retirement', 'retirement.json'), recordKey=self.key('retirement', 'retired.json'), deleted=len(self.removed)))
        self.expected['retirement'].update({'retirement.json': decision, 'retired.json': done})
        native = f.canonical(dict(schema='gse-v53-native-joining/1.3', plan=owner.plan, root=owner.replay.root,
            identity=owner.joining, path=owner.binding('nativeOwner'), directoryKey=self.key('nativeOwner'),
            recordKey=self.key('nativeOwner', 'native.json'),
            retirement=self.fingerprint('retirement', 'retirement.json', decision),
            retired=self.fingerprint('retirement', 'retired.json', done), storage=native_storage(owner.installed, self.expected)))
        self.expected['nativeOwner']['native.json'] = native

    def compare(self):
        # This later snapshot includes initialization and an own grant. Only the
        # predecessor projection is derived here; never import later bytes into
        # the initial native owner or assert a full replica inventory match.
        for row in self.removed:
            need(row['name'] not in self.ids[row['root']], 'joining retirement predecessor still present')
        compared = keys = 0
        for family, files in self.expected.items():
            if family != 'replica':
                actual = {name: None if 'directory' in identity else self.snap.member(family, name)
                          for name, identity in self.ids[family].items()}
                need(actual == files, 'joining retirement exact family: '+family)
            for name, raw in files.items():
                if family in self.owner.expected:
                    if family == 'replica' and name == 'allocator.gsr': continue  # Atomic allocator replacement is later.
                    need(self.key(family, name) == self.owner.key(family, name), 'joining retirement surviving original inode')
                    keys += 1
                if family == 'replica' and name in MUTABLE_ORIGINALS: continue
                if raw is not None:
                    need(self.snap.member(family, name) == raw, 'joining retirement surviving original bytes')
                    compared += 1
        return compared, keys

    def run(self):
        self.records(); compared, keys = self.compare()
        return dict(status='PASS', scope='native-'+self.owner.replay.kind+'-original-retirement-and-owner', deletedOriginalMembers=len(self.removed),
            predecessorReservations=len(reservations(self.owner)), nativeReservations=len(native_storage(self.owner.installed, self.expected)),
            exactSidecarFamilies=len(self.expected)-1, comparedFiles=compared, preservedOriginalKeys=keys,
            oldOwnerSnapshots=self.owner.history.comparisons, joiningRetirementPhysicalQualified=True,
            nativeOwnerHandoffPhysicalQualified=True, nativeInitializationQualified=False,
            completePhysicalQualified=False, forceAndNetworkQualified=False, processDeathQualified=False, phase3Complete=False)


def validate(root, *, size=3, kind='ADD'):
    root = Path(root); original = s.collection.inventory(root)
    placement.transition.publication.validate(root, size=size, kind=kind)
    replay = s.Replay(root, size=size, kind=kind)
    for index in range(1, 12): replay.step(index)
    replay.publication_receipts = placement.transition.publication.CheckpointReceipts(root, replay)
    history = placement.History(root, replay); history.run()
    owner = placement.Placement(root, history); owner.run()
    result = Retirement(root, owner).run()
    need(s.collection.inventory(root) == original, 'joining original changed during retirement replay')
    return result


NEGATIVES = {
    'deletion-omitted': 'joining retirement exact family: retirement',
    'deletion-reordered': 'joining retirement exact family: retirement',
    'deletion-live-generation': 'joining retirement exact family: retirement',
    'reservation-shrink-typed': 'joining retirement exact family: retirement',
    'reservation-alias-images': 'joining retirement exact family: retirement',
    'reservation-shrink-journal': 'joining retirement exact family: retirement',
    'reservation-shrink-stage': 'joining retirement exact family: retirement',
    'reservation-after-deletion': 'joining retirement exact family: retirement',
    'joined-fingerprint': 'joining retirement exact family: retirement',
    'retired-count': 'joining retirement exact family: retirement',
    'retired-record-key': 'joining retirement exact family: retirement',
    'native-retirement-fingerprint': 'joining retirement exact family: nativeOwner',
    'native-journal-charge': 'joining retirement exact family: nativeOwner',
    'native-image-owner': 'joining retirement exact family: nativeOwner',
    'native-generation-charge': 'joining retirement exact family: nativeOwner',
    'native-record-key': 'joining retirement exact family: nativeOwner',
    'predecessor-payload-survives': 'joining retirement predecessor still present',
    'live-typed-proof-missing': 'joining retirement exact family: initialTyped',
    'empty-lock-replaced': 'joining retirement surviving original inode',
    'generation-inode-replaced': 'joining retirement surviving original inode',
    'absent-root-path-changed': 'joining retirement original path changed',
    'unowned-sidecar-file': 'joining retirement exact family: nativeOwner',
}


def mutate(root, name):
    """Change disposable snapshots and refresh hashes, preserving the prior gate."""
    need(name in NEGATIVES, 'unknown joining retirement mutation')
    path = Path(root)/'joining-originals-native'
    rows = s.catalog.parse((path/'inventory.json').read_bytes())
    by_root = {v['name']: v for v in rows}
    def edit(family, file, action):
        p = path/family/file; value = s.catalog.parse(p.read_bytes()); action(value); p.write_bytes(f.canonical(value))
    def retirement(action): edit('retirement', 'retirement.json', action)
    def native(action): edit('nativeOwner', 'native.json', action)
    def charge(value, unit, amount): next(row for row in value['reservations'] if row['unit'] == unit)['bytes'] = amount
    extra = None
    if name == 'deletion-omitted': retirement(lambda v: v['deletions'].pop())
    elif name == 'deletion-reordered': retirement(lambda v: v['deletions'].reverse())
    elif name == 'deletion-live-generation': retirement(lambda v: v['deletions'].append(dict(root='replica', name='generations/a')))
    elif name == 'reservation-shrink-typed': retirement(lambda v: v['reservations'][4].update(bytes=837))
    elif name == 'reservation-alias-images': retirement(lambda v: v['reservations'].pop(0))
    elif name == 'reservation-shrink-journal': retirement(lambda v: charge(v, 'JOURNAL', 1))
    elif name == 'reservation-shrink-stage': retirement(lambda v: v['reservations'][6].update(bytes=1))
    elif name == 'reservation-after-deletion': retirement(lambda v: charge(v, 'SOURCE', 1))
    elif name == 'joined-fingerprint': retirement(lambda v: v['joined'].update(key='copied-key'))
    elif name == 'retired-count': edit('retirement', 'retired.json', lambda v: v.update(deleted=v['deleted']-1))
    elif name == 'retired-record-key': edit('retirement', 'retired.json', lambda v: v.update(recordKey='copied-key'))
    elif name == 'native-retirement-fingerprint': native(lambda v: v['retirement'].update(sha256='0'*64))
    elif name == 'native-journal-charge': native(lambda v: next(r for r in v['storage'] if r['unit'] == 'JOURNAL').update(bytes=1))
    elif name == 'native-image-owner': native(lambda v: next(r for r in v['storage'] if r['unit'] == 'APPLICATION').update(owner='foreign'))
    elif name == 'native-generation-charge': native(lambda v: next(r for r in v['storage'] if r['unit'] == 'GENERATION').update(bytes=1))
    elif name == 'native-record-key': native(lambda v: v.update(recordKey='copied-key'))
    elif name == 'predecessor-payload-survives':
        extra = ('pendingIntent', 'joining-ack.gsr')
        (path/extra[0]/extra[1]).write_bytes((Path(root)/'joining-originals-placed'/extra[0]/extra[1]).read_bytes())
    elif name == 'live-typed-proof-missing': (path/'initialTyped/learner.gsr').unlink()
    elif name in ('empty-lock-replaced', 'generation-inode-replaced'):
        family, member = ('operation', 'operation.lock') if name == 'empty-lock-replaced' else ('replica', 'generations/a')
        next(v for v in by_root[family]['files'] if v['name'] == member)['identity']['key'] = 'replacement-original-inode'
    elif name == 'absent-root-path-changed': by_root['materialization']['path']['path'] += '-different'
    elif name == 'unowned-sidecar-file':
        extra = ('nativeOwner', 'orphan.bin'); (path/extra[0]/extra[1]).write_bytes(b'unowned')
    # Keep downstream hashes internally consistent. A rejection must arise from
    # independent derivation, not merely a stale pointer to the mutated record.
    if name.startswith(('deletion-', 'reservation-')) or name == 'joined-fingerprint':
        edit('retirement', 'retired.json', lambda v: v.update(plan=sha((path/'retirement/retirement.json').read_bytes())))
    if name.startswith(('deletion-', 'reservation-', 'retired-')) or name == 'joined-fingerprint':
        def rebound(value):
            for field, file in (('retirement', 'retirement.json'), ('retired', 'retired.json')):
                raw = (path/'retirement'/file).read_bytes()
                value[field].update(size=len(raw), sha256=sha(raw))
        native(rebound)
    for row in rows:
        if not row['present']: continue
        files = []
        for member in row['files']:
            p = path/row['name']/member['name']
            if not p.exists(): continue
            if p.is_file(): member['identity'].update(size=p.stat().st_size, sha256=sha(p.read_bytes()))
            files.append(member)
        if extra and extra[0] == row['name']:
            raw = (path/extra[0]/extra[1]).read_bytes()
            files.append(dict(name=extra[1], identity=dict(key='negative-original-extra', size=len(raw), sha256=sha(raw))))
        row['files'] = sorted(files, key=lambda v: v['name'])
    (path/'inventory.json').write_bytes(f.canonical(rows))


def qualify(root):
    root = Path(root); original = validate(root); results = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-retirement-negative-') as temp:
            copied = Path(temp)/'raw'; shutil.copytree(root, copied); mutate(copied, name)
            placement.validate(copied)
            try: validate(copied)
            except ValueError as error: need(str(error) == reason, 'joining unrelated retirement negative: '+name+': '+str(error))
            else: raise ValueError('joining retirement mutation accepted: '+name)
        results.append(dict(case=name, status='REJECTED', reason=reason, placementGate='PASS'))
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
