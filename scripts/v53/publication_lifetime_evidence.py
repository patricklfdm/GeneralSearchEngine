"""Bounded final-state audit across repeated fresh ballots, not force/peak reconstruction."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import format_fixture as f
from . import source_packet as p
from . import selected_sources_evidence as sources
from .ancestry_pruning_evidence import frames
from .grant_evidence import journal
from .context_evidence import majority
from .journal_application_evidence import inventory
from .journal_publication_evidence import EMPTY
from .applied_end_evidence import read, digest
from .membership_model import need


def state(path, row, previous):
    physical = inventory(path); raw_files = {k: v for k, v in physical.items() if v is not None}
    indexed = [dict(path=k, sha256=digest(v)) for k, v in sorted(raw_files.items())]
    need(row['files'] == len(indexed) and row['inventorySha256'] == digest(f.canonical(indexed)), 'lifetime snapshot index')
    cycle, node = row['cycle'], row['node']; root = physical['root.gsr'][16:48].hex()
    root_value = f.decode(physical['root.gsr'], 'records', 'ROOT'); genesis = f.decode(physical['genesis.gsr'], 'records', 'GENESIS')
    need(digest(physical['genesis.gsr']) == root_value['genesis'] and all(genesis[k] == root_value[k] for k in ('groupId', 'historyId', 'baseSequence', 'schema', 'indexes')), 'lifetime original root/genesis')
    identity = f.decode(physical['node.gsr'], 'records', 'NODE', root)['identity']; need(identity['node'] == node, 'lifetime node identity')
    need(identity in root_value['initial'], 'lifetime original local identity')
    sel = f.decode(physical['selector.gsr'], 'records', 'SELECTOR', root); prefix = 'generations/'+sel['generation']+'/'
    raw = physical[prefix+'generation.gsr']; manifest = f.decode(raw, 'records', 'GENERATION', root)
    need(sel['generation'] == manifest['generation'] == 'a' and sel['node'] == manifest['node'] == node
         and sel['digest'] == digest(raw) == row['manifest'], 'lifetime current manifest')
    members = {k.removeprefix(prefix): v for k, v in raw_files.items() if k.startswith(prefix) and k != prefix+'generation.gsr'}
    need(manifest['files'] == [dict(path=k, size=len(v), sha256=digest(v)) for k, v in sorted(members.items())], 'lifetime complete generation inventory')
    packet = p.decode(members['source.gscp']); cap = packet['capsule']
    need(manifest['capsule'] == digest(packet['capsuleBytes']) and all(manifest[k] == cap[k] for k in ('root', 'cut', 'catalog', 'application'))
         and cap['cut']['index'] == row['cut'] == cycle+1 and manifest['ownedTail'] is None, 'lifetime published position')
    grants = journal(physical['grants.gsr'], root, node)
    need([k for k, _, _ in grants] == ['PROMISE', 'BASIS', 'SELECTED'] and len(physical['grants.gsr']) == row['journalBytes'], 'lifetime bounded original journal')
    for kind, raw, value in grants:
        name = kind.lower()+'.gsr'
        need(members[name] == raw and manifest[{'PROMISE': 'promise', 'BASIS': 'basis', 'SELECTED': 'selection'}[kind]] == digest(raw)
             and value['ballot']['counter'] == 20+cycle, 'lifetime exact current grant')
    basis, selected = grants[1][2], grants[2][2]; retained = sources.retained(physical, prefix)
    need(sources.cuts(retained[sources.FILE], selected) == [basis['cut']]*3 and basis['cut']['index'] == cycle, 'lifetime fresh selected sources')
    source_prefix = 'sources/'+basis['basisId']+'/'
    source = p.decode(physical[source_prefix+'source.gscp']); p.bind(source, members['basis.gsr']); frozen = source['capsule']
    allowed = {'allocator.gsr', 'genesis.gsr', 'grants.gsr', 'node.gsr', 'pending.accept', 'replica.lock', 'root.gsr', 'selector.gsr', prefix+'generation.gsr', source_prefix+'source.gscp'}
    allowed |= {prefix+k for k in members} | {source_prefix+h+'.image' for h in source['images']}
    directories = {k for k, v in physical.items() if v is None}
    need(set(raw_files) == allowed and directories == {'generations', 'generations/a', 'sources', source_prefix[:-1]}, 'lifetime only current generation and one source')
    need(physical['pending.accept'] == EMPTY and physical['replica.lock'] == b'' and sum(k.endswith('.image') for k in raw_files) == 2, 'lifetime settled physical images/vote')
    for pref, data in ((prefix, packet), (source_prefix, source)):
        need(data['objects'].get(digest(physical['root.gsr'])) == physical['root.gsr'] and data['objects'].get(digest(physical['genesis.gsr'])) == physical['genesis.gsr'], 'lifetime original packet root')
        for h, size in data['images'].items():
            image = physical[pref+h+'.image']; need(len(image) == size and digest(image) == h, 'lifetime original image binding')
    catalog = f.decode(packet['objects'][cap['catalog']], 'records', 'CATALOG', root)
    before = f.decode(source['objects'][frozen['catalog']], 'records', 'CATALOG', root)
    need(catalog['applicationSequence'] == 42 and catalog['lastDataIndex'] == 1, 'lifetime application sequence')
    coverage = json.loads(members['selected-coverage.json']); certificate = f.decode(packet['objects'][coverage['certificate']], 'records', 'CERTIFICATE', root)
    expected = dict(schema='gse-v53-selected-coverage/1.3', selection=digest(members['selected.gsr']), parent={k: frozen[k] for k in ('cut', 'catalog', 'application')}, certificate=coverage['certificate'])
    need(coverage == expected and f.canonical(coverage) == members['selected-coverage.json'] and certificate['ballot'] == selected['ballot']
         and certificate['index'] == cycle+1 and certificate['entry'] == cap['cut']['entry'], 'lifetime original selected coverage')
    entry = f.decode(packet['objects'][certificate['entry']], 'records', 'ENTRY', root)
    need(entry['previous'] == frozen['cut']['entry'] and entry['index'] == cycle+1 and entry['origin'] == selected['ballot'], 'lifetime certified successor')
    if previous is not None:
        need(physical[source_prefix+'source.gscp'] == previous['packet'] and frozen['cut'] == previous['cut'], 'lifetime actual previous publication captured')
        projection = copy.deepcopy(before); projection['cut'] = cap['cut']
        need(entry['kind'] == 'BARRIER' and packet['objects'][entry['payload']] == b'' and projection == catalog
             and cap['application'] == frozen['application'], 'lifetime BARRIER projection')
        need(all(physical[k] == previous['immutable'][k] for k in previous['immutable']), 'lifetime immutable history/identity')
        ancestry = frames(members['ancestry.gsr']); need(len(ancestry) == 4, 'lifetime one ancestor group')
        statement = dict(root=root, scope='RANGE', start=frozen['cut'], end=cap['cut'], catalogBefore=frozen['catalog'], catalogAfter=cap['catalog'],
                         applicationBefore=frozen['application'], applicationAfter=cap['application'])
        need(ancestry[0] == f.encode('records', 'CHECKPOINT', statement), 'lifetime exact retained parent')
        ids = {v['node']: v['storage'] for v in catalog['identities']}
        for n, ack in zip(('node-1', 'node-2', 'node-3'), ancestry[1:]):
            need(f.decode(ack, 'records', 'CHECKPOINT_ACK', root) == dict(root=root, voter=n, incarnation=ids[n], cut=cap['cut'], statement=digest(ancestry[0])), 'lifetime parent ACK binding')
        majority(cap['cut']['view'], ['node-1', 'node-2', 'node-3'])
    else: need(entry['kind'] == 'DATA' and 'ancestry.gsr' not in members and before['applicationSequence'] == 41, 'lifetime initial publication')
    need(sum(len(v) for k, v in members.items() if not k.endswith('.image')) <= 32*1024*1024 and len(physical['grants.gsr']) <= 32*1024*1024, 'lifetime physical metadata bound')
    return dict(packet=members['source.gscp'], cut=cap['cut'], originals=retained[sources.FILE], basis=members['basis.gsr'],
                immutable={k: physical[k] for k in ('root.gsr', 'genesis.gsr', 'node.gsr', 'allocator.gsr')})


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json'))
    need(receipt['execution'] == 'private-repeated-publication-maintenance' and receipt['expectedRounds'] == 13
         and receipt['sameBallotContinuation'] is False and receipt['freshProcesses'] is False and receipt['historicalBootstrap'] == 'conditional-fixture', 'lifetime scope')
    need([(r['cycle'], r['node']) for r in receipt['rows']] == [(i, 'node-'+str(n)) for i in range(13) for n in (1, 2, 3)], 'lifetime complete round/node inventory')
    need({p.name for p in (root/'snapshots').iterdir()} == {'round-'+str(i) for i in range(13)}, 'lifetime exact rounds')
    previous = {}
    for cycle in range(13):
        directory = root/'snapshots'/('round-'+str(cycle)); need({p.name for p in directory.iterdir()} == {'node-1', 'node-2', 'node-3'}, 'lifetime complete voters')
        group = {}
        for row in receipt['rows'][cycle*3:cycle*3+3]: group[row['node']] = state(directory/row['node'], row, previous.get(row['node']))
        originals = b''.join(group[n]['basis'] for n in sorted(group))
        need(all(v['originals'] == originals and v['packet'] == group['node-1']['packet'] for v in group.values()), 'lifetime common original selection and publication')
        previous = group
    for node in previous: need(inventory(root/node) == inventory(root/'snapshots/round-12'/node), 'lifetime final owner snapshot')
    need(0 < receipt['peakImages'] <= 7 and 0 < receipt['peakMetadata'] <= 384*1024*1024 and 0 < receipt['peakStaging'] <= 512*1024*1024, 'lifetime reported reservation bounds')
    return dict(status='PASS', rounds=13, nodeSnapshots=39, freshBallotSuccessors=12, settledImagesPerNode=2, settledSourcesPerNode=1,
                reservationPeaks='producer-observed-not-independently-reconstructed', fullCrashQualification=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    for variant in ('missing-round', 'retained-obsolete-source', 'missing-original-basis', 'altered-generation', 'early-cleared-history', 'false-scope'):
        with tempfile.TemporaryDirectory(prefix='v53-lifetime-negative-') as tmp:
            case = Path(tmp)/'evidence'; shutil.copytree(root, case)
            path = case/'snapshots/round-12/node-1'
            if variant == 'missing-round': shutil.rmtree(case/'snapshots/round-7')
            elif variant == 'retained-obsolete-source': (path/'sources/extra').mkdir()
            elif variant == 'missing-original-basis': (path/'generations/a/basis.gsr').unlink()
            elif variant == 'altered-generation': (path/'generations/a/ancestry.gsr').write_bytes(b'')
            elif variant == 'early-cleared-history': (path/'grants.gsr').write_bytes(b'')
            else:
                r = json.loads(read(case/'receipt.json')); r['sameBallotContinuation'] = True; (case/'receipt.json').write_bytes(f.canonical(r))
            try: validate(case)
            except (ValueError, OSError, KeyError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted lifetime mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-lifetime-portable-') as tmp:
        case = Path(tmp)/'evidence'; shutil.copytree(root, case); need(validate(case) == result, 'lifetime portable audit')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args(); print(json.dumps(qualify(args.root), sort_keys=True))
