"""Retained-byte replay of context-backed generation retirement.

The original context is reconstructed before deriving the complete governing
floor and deleted inventory. Process-crash and next-campaign progress are not claimed.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import journal_context_evidence as owner
from . import pending_context_evidence as e
from .round_storage_evidence import anchor


def validate(root):
    root = Path(root)
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} ==
           {'initial', 'peer', 'floor', 'retired', 'reopened', 'events.json', 'receipt.json'}, 'context retirement evidence inventory')
    snapshots = {name: owner.read_snapshot(root/name) for name in ('initial', 'peer', 'floor', 'retired', 'reopened')}
    initial, initial_dirs = snapshots['initial']; peer, _ = snapshots['peer']
    e.need(owner.ACTIVE in initial and owner.NEXT not in initial, 'context retirement complete original context')
    protected = {name: raw for name, raw in initial.items() if name != owner.ACTIVE}
    owner.original_inventory(protected, initial_dirs); owner.reconstruct_original_view(protected, initial)
    segments, _, _ = e.decode(initial[owner.ACTIVE]); original_selector = e.f.decode(segments[1], 'records', 'SELECTOR')
    old_prefix = 'generations/'+original_selector['generation']+'/'
    local_prefix, _, local_packet = e.current(initial); peer_prefix, _, peer_packet = e.current(peer)
    root_record = e.f.decode(initial['root.gsr'], 'records', 'ROOT'); registry = e.identities(root_record['initial'])
    e.need(peer['root.gsr'] == initial['root.gsr'] and e.f.decode(peer['node.gsr'], 'records', 'NODE')['identity'] == registry['node-2']
           and anchor(local_packet['capsule']) == anchor(peer_packet['capsule']), 'context retirement exact peer identity/parent')
    copies = {}; references = []
    for node, files, prefix in (('node-1', initial, local_prefix), ('node-2', peer, peer_prefix)):
        manifest_raw = files[prefix+'generation.gsr']; manifest = e.f.decode(manifest_raw, 'records', 'GENERATION')
        copies[e.digest(manifest_raw)] = {name.removeprefix(prefix): raw for name, raw in files.items() if name.startswith(prefix)}
        e.need(manifest['node'] == node, 'context retirement copy owner')
        references.append(dict(voter=node, generation=e.digest(manifest_raw), catalog=manifest['catalog'], snapshot=manifest['application']))
    e.majority(local_packet['capsule']['cut']['view'], [r['voter'] for r in references])
    floor = e.f.encode('records', 'FLOOR', dict(root=local_packet['capsule']['root'], node='node-1', cut=local_packet['capsule']['cut'], sources=references))
    expected = dict(initial, **{'floor-copies/proposal.gsr': floor, 'floor-copies/floor.gsr': floor})
    directories = initial_dirs | {'floor-copies'}
    for digest, files in copies.items():
        directories.add('floor-copies/'+digest)
        expected.update({'floor-copies/'+digest+'/'+name: raw for name, raw in files.items()})
    e.need(snapshots['floor'] == (expected, directories), 'context retirement exact governing floor copies')
    retired = {name: raw for name, raw in expected.items() if not name.startswith(old_prefix)}
    directories = directories-{old_prefix.removesuffix('/')}
    e.need(snapshots['retired'] == (retired, directories), 'context retirement exact deletion/protected originals')
    e.need(snapshots['reopened'] == snapshots['retired'], 'context retirement reopen changed authority')
    event_path = root/'events.json'
    e.need(not event_path.is_symlink() and event_path.stat().st_size <= 65536, 'context retirement event type/capacity')
    events = e.parse(event_path.read_bytes())
    e.need(type(events) is list and len(events) <= 2048 and all(type(v) is str for v in events), 'context retirement event shape')
    e.need(not any(v in owner.ACKS or v.startswith('APPLY_ACK_') or v == 'APPLY_BEFORE_RETURN' for v in events), 'context retirement old acknowledgement returned')
    order = ['FLOOR_PARENT_FORCED', 'RETIREMENT_OLD_FILES_FORCED', 'RETIREMENT_SOURCE_FORCED', 'RETIREMENT_PARENT_FORCED',
             'RETIREMENT_DELETE_VALIDATED', 'RETIREMENT_FILE_DELETED', 'RETIREMENT_DIRECTORY_DELETED',
             'RETIREMENT_AUTHORITY_CLEARED', 'RETIREMENT_CLEARED', 'RETIREMENT_BEFORE_RETURN']
    e.need(all(event in events for event in order) and [events.index(event) for event in order] == sorted(events.index(event) for event in order),
           'context retirement floor/authority/delete order')
    record = e.f.encode('records', 'RETIREMENT', dict(root=local_packet['capsule']['root'], node='node-1', floor=e.digest(floor),
            selector=e.digest(initial['selector.gsr']), files=[dict(path=name, size=len(raw), sha256=e.digest(raw)) for name, raw in sorted(initial.items()) if name.startswith(old_prefix)]))
    e.need(events.count('RETIREMENT_FILE_DELETED') == sum(name.startswith(old_prefix) for name in initial), 'context retirement complete deletion count')
    receipt_path = root/'receipt.json'
    e.need(not receipt_path.is_symlink() and receipt_path.stat().st_size <= 16384, 'context retirement receipt type/capacity')
    receipt = e.parse(receipt_path.read_bytes()); expected_receipt = dict(schema='gse-v53-context-retirement-v1', status='PASS', oldSlot=original_selector['generation'],
        peakImages=7, freshProcesses=False, nextCampaign=False, runtimeEnabled=False)
    e.need(e.f.canonical(receipt) == e.f.canonical(expected_receipt), 'context retirement receipt scope')
    return dict(status='PASS', originalFirst=True, oldSlot=original_selector['generation'], floor=e.digest(floor), retirement=e.digest(record),
        protectedContext=True, governingVoters=2, freshProcesses=False, nextCampaign=False, imageSemanticClaim=False, remoteOwnershipVerified=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    cases = {'missing-peer': 'context retirement evidence inventory', 'changed-context': 'context checksum',
        'lost-vote': 'context retirement exact deletion/protected originals', 'lost-source': 'context retirement exact deletion/protected originals',
        'changed-floor': 'context retirement exact governing floor copies', 'lost-copy': 'context retirement exact governing floor copies',
        'kept-original': 'context retirement exact deletion/protected originals', 'changed-reopen': 'context retirement reopen changed authority',
        'force-order': 'context retirement floor/authority/delete order', 'old-ack': 'context retirement old acknowledgement returned',
        'false-progress': 'context retirement receipt scope', 'linked-floor': 'owner context linked/nonregular member'}
    for name, reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-context-retirement-negative-') as temp:
            moved = Path(temp)/'evidence'; shutil.copytree(root, moved)
            if name == 'missing-peer': shutil.rmtree(moved/'peer')
            elif name == 'changed-context':
                path = moved/'initial'/owner.ACTIVE; raw = path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name == 'lost-vote': (moved/'retired/pending.accept').unlink()
            elif name == 'lost-source': next((moved/'retired/sources').rglob('source.gscp')).unlink()
            elif name == 'changed-floor': (moved/'floor/floor-copies/floor.gsr').write_bytes(b'changed')
            elif name == 'lost-copy': next((moved/'floor/floor-copies').rglob('source.gscp')).unlink()
            elif name == 'kept-original':
                prefix = 'generations/'+result['oldSlot']; shutil.copytree(moved/'initial'/prefix, moved/'retired'/prefix)
            elif name == 'changed-reopen': (moved/'reopened/pending.accept').write_bytes(b'changed')
            elif name in ('force-order', 'old-ack'):
                path = moved/'events.json'; events = e.parse(path.read_bytes())
                if name == 'force-order': events.remove('RETIREMENT_PARENT_FORCED')
                else: events.append('ACCEPT_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(events))
            elif name == 'false-progress':
                path = moved/'receipt.json'; receipt = e.parse(path.read_bytes()); receipt['nextCampaign'] = True; path.write_bytes(e.f.canonical(receipt))
            else:
                path = moved/'floor/floor-copies/floor.gsr'; path.unlink(); path.symlink_to((root/'floor/floor-copies/floor.gsr').resolve())
            try: validate(moved)
            except ValueError as error:
                e.need(str(error) == reason, 'wrong context retirement negative reason: '+name+': '+str(error)); negatives.append(dict(case=name, reason=reason))
            else: raise ValueError('accepted context retirement mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-retirement-portable-') as temp:
        moved = Path(temp)/'evidence'; shutil.copytree(root, moved); e.need(validate(moved) == result, 'context retirement portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
