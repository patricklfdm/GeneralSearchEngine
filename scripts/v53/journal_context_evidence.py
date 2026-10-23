"""Physical replay of local-owner context retention and twice-interrupted recovery.

The producer injects IOException at actual file/force boundaries. This is not a
fresh-process/power-loss or source-retirement qualification. Historical bootstrap
and remote observations remain conditional; the backing source is locally owned.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import pending_context_evidence as e
from .grant_evidence import journal

CUTS = ('CONTEXT_OWNER_VALIDATED', 'CONTEXT_SOURCE_MEMBER_FORCED', 'CONTEXT_SOURCE_DIRECTORY_FORCED',
        'CONTEXT_SOURCE_PARENT_FORCED', 'CONTEXT_CANDIDATE_CREATED', 'CONTEXT_PREFIX_WRITTEN',
        'CONTEXT_CANDIDATE_WRITTEN', 'CONTEXT_CANDIDATE_FORCED', 'CONTEXT_CANDIDATE_PARENT_FORCED',
        'CONTEXT_RENAMED', 'CONTEXT_PARENT_FORCED', 'CONTEXT_OWNER_BEFORE_RETURN')
ACTIVE, NEXT = 'pending.context', 'pending.context.next'
SNAPSHOTS = ('initial', 'crash', 'recovery-crash', 'final')
ACKS = {'ACCEPT_BEFORE_RETURN', 'PROOF_BEFORE_RETURN', 'CERTIFICATE_BEFORE_RETURN', 'GRANT_BEFORE_RETURN',
        'INSTALL_BEFORE_RETURN', 'PUBLICATION_BEFORE_RETURN'}


def read_snapshot(root):
    e.need(root.is_dir() and not root.is_symlink(), 'owner context snapshot directory')
    paths = list(root.rglob('*')); e.need(len(paths) <= 512, 'owner context snapshot count')
    files = {}; directories = set(); total = 0
    for path in paths:
        e.need(not path.is_symlink() and (path.is_file() or path.is_dir()), 'owner context linked/nonregular member')
        name = path.relative_to(root).as_posix()
        if path.is_dir(): directories.add(name); continue
        size = path.stat().st_size
        e.need(0 <= size <= 64*e.MIB, 'owner context member capacity'); total += size
        e.need(total <= 512*e.MIB, 'owner context snapshot capacity')
        raw = path.read_bytes(); e.need(len(raw) == size, 'owner context changing member'); files[name] = raw
    return files, directories


def reconstruct_original_view(initial, final):
    e.need(ACTIVE in final and NEXT not in final, 'owner context final active')
    segments, metadata, binding = e.decode(final[ACTIVE]); selector = e.f.decode(segments[1], 'records', 'SELECTOR')
    basis = e.f.decode(segments[3], 'records', 'BASIS'); prefix = 'generations/'+selector['generation']+'/'
    source_prefix = 'sources/'+basis['basisId']+'/'
    e.need(prefix+'generation.gsr' in initial and source_prefix+'source.gscp' in initial, 'owner context original authority absent')
    e.need(initial['pending.accept'] == final['pending.accept'], 'owner context original vote changed')
    packet = e.p.decode(initial[source_prefix+'source.gscp'])
    original = {p.removeprefix(prefix): raw for p, raw in initial.items() if p.startswith(prefix)}
    material = {'context.gspc': final[ACTIVE], 'old-selector.gsr': segments[1], 'pending.accept': initial['pending.accept'],
                'root.gsr': initial['root.gsr'], 'backing-promise.gsr': segments[2], 'backing-basis.gsr': segments[3],
                'backing-source.gscp': initial[source_prefix+'source.gscp']}
    material.update({'original-generation/'+p: raw for p, raw in original.items() if not p.endswith('.image')})
    for digest in packet['images']:
        path = source_prefix+digest+'.image'; e.need(path in initial, 'owner context source image absent')
        material['backing-images/'+digest+'.image'] = initial[path]
    # Verify exact supplied original metadata against the retained physical directory,
    # then reuse the independent original protocol/byte replay with an analysis receipt.
    e.need(metadata == {p: raw for p, raw in original.items() if p != 'source.gscp' and not p.endswith('.image')},
           'owner context metadata differs from retained original')
    material['receipt.json'] = e.f.canonical(dict(schema='gse-v53-pending-context-codec-v1', status='PASS', execution='pure-context-codec-reconstruction',
        contextForced=False, retirementAuthorized=False, freshProcesses=False, runtimeEnabled=False, imageSemanticClaim=False, historicalBootstrap='conditional-fixture',
        contextSha256=e.digest(final[ACTIVE]), contextBytes=len(final[ACTIVE]), entry=binding['entry'], oldVoteSha256=e.digest(initial['pending.accept']),
        backingPacketSha256=e.digest(material['backing-source.gscp']), origin=20, backingBallot=21))
    with tempfile.TemporaryDirectory(prefix='v53-owner-context-view-') as temporary:
        root = Path(temporary)
        for name, raw in material.items():
            path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        e.validate(root)
    # Decode all live grant groups and the actually selected current generation.
    grants = journal(initial['grants.gsr'], binding['root'], binding['node'])
    e.need([kind for kind, _, _ in grants] == ['PROMISE', 'BASIS', 'SELECTED']*2, 'owner context original grant groups')
    e.need(segments[2] == grants[-3][1] and segments[3] == grants[-2][1], 'owner context backing missing original journal grant')
    current_prefix, current, current_packet = e.current(initial)
    selected = e.f.decode(current['selected.gsr'], 'records', 'SELECTED')
    e.need(current_prefix != prefix and selected['nextEntry'] == binding['entry']
           and all(current[kind.lower()+'.gsr'] == raw for kind, raw, _ in grants[-3:])
           and selected['cut'] == packet['capsule']['cut'] == current_packet['capsule']['cut'], 'owner context exact installed carried selection')
    e.need(set(current) == {'promise.gsr', 'basis.gsr', 'selected.gsr', 'source.gscp', 'selected-sources.gsr', 'owned-tail.gsr'}
           | {h+'.image' for h in current_packet['images']}, 'owner context installed generation inventory')
    old_vote, _ = e.votes(initial['pending.accept'], packet['capsule']['cut'])
    e.need(current['owned-tail.gsr'] == old_vote['ACCEPT'] and current_packet['objects'].get(binding['entry']) == old_vote['ENTRY'],
           'owner context exact selected tail')
    return len(packet['images'])+1


def original_inventory(files, directories):
    top = {'replica.lock', 'root.gsr', 'genesis.gsr', 'node.gsr', 'allocator.gsr', 'grants.gsr', 'pending.accept', 'selector.gsr'}
    e.need({name for name in files if '/' not in name} == top and files['replica.lock'] == b'', 'owner context initial authority inventory')
    root = e.f.decode(files['root.gsr'], 'records', 'ROOT'); root_hash = files['root.gsr'][16:48].hex()
    node = e.f.decode(files['node.gsr'], 'records', 'NODE', root_hash)
    allocator = e.f.decode(files['allocator.gsr'], 'records', 'ALLOCATOR', root_hash)
    e.need(node['identity'] == root['initial'][0] and node['identity']['node'] == allocator['node'] == 'node-1'
           and allocator['counter'] == 0 and e.digest(files['genesis.gsr']) == root['genesis'], 'owner context initial node/allocator/genesis')
    grants = journal(files['grants.gsr'], root_hash, 'node-1'); bases = {value['basisId']: raw for kind, raw, value in grants if kind == 'BASIS'}
    e.need(len(bases) == 2 and directories == {'generations', 'generations/a', 'generations/b', 'sources'}
           | {'sources/'+key for key in bases}, 'owner context initial directory inventory')
    for key, basis in bases.items():
        prefix = 'sources/'+key+'/'; e.need(prefix+'source.gscp' in files, 'owner context initial source absent')
        source = e.p.decode(files[prefix+'source.gscp']); e.p.bind(source, basis)
        members = {name.removeprefix(prefix): raw for name, raw in files.items() if name.startswith(prefix)}
        e.need(set(members) == {'source.gscp'} | {h+'.image' for h in source['images']}, 'owner context initial source inventory')
        for h, size in source['images'].items():
            e.need(e.info(members[h+'.image']) == dict(bytes=size, sha256=h), 'owner context initial source image')
        e.need(source['objects'].get(e.digest(files['root.gsr'])) == files['root.gsr'], 'owner context source ROOT')


def validate(root):
    root = Path(root); e.need(root.is_dir() and not root.is_symlink(), 'owner context root')
    e.need({p.name for p in root.iterdir()} == set(CUTS)|{'receipt.json'}, 'owner context case inventory')
    rows = []
    for cut in CUTS:
        case = root/cut; e.need(not case.is_symlink() and case.is_dir(), 'owner context case directory')
        e.need({p.name for p in case.iterdir()} == set(SNAPSHOTS)|{'events.json'}, 'owner context snapshot inventory')
        snapshots = {name: read_snapshot(case/name) for name in SNAPSHOTS}
        initial, directories = snapshots['initial']; final = snapshots['final'][0]
        e.need(ACTIVE not in initial and NEXT not in initial, 'owner context original already has context')
        original_inventory(initial, directories)
        for name, (files, dirs) in snapshots.items():
            e.need(dirs == directories and {p: raw for p, raw in files.items() if p not in (ACTIVE, NEXT)} == initial,
                   'owner context protected authority changed')
        members = reconstruct_original_view(initial, final); context = final[ACTIVE]
        prefix = ['CONTEXT_OWNER_VALIDATED']+['CONTEXT_SOURCE_MEMBER_FORCED']*members+['CONTEXT_SOURCE_DIRECTORY_FORCED', 'CONTEXT_SOURCE_PARENT_FORCED']
        candidate = ['CONTEXT_CANDIDATE_CREATED', 'CONTEXT_PREFIX_WRITTEN', 'CONTEXT_CANDIDATE_WRITTEN', 'CONTEXT_CANDIDATE_FORCED',
                     'CONTEXT_CANDIDATE_PARENT_FORCED', 'CONTEXT_RENAMED', 'CONTEXT_PARENT_FORCED', 'CONTEXT_OWNER_BEFORE_RETURN']
        active = ['CONTEXT_ACTIVE_FORCED', 'CONTEXT_ACTIVE_PARENT_FORCED', 'CONTEXT_OWNER_BEFORE_RETURN']
        complete = prefix+candidate
        stage = complete.index(cut); crash = dict(initial)
        if stage >= complete.index('CONTEXT_RENAMED'): crash[ACTIVE] = context
        elif stage >= complete.index('CONTEXT_CANDIDATE_WRITTEN'): crash[NEXT] = context
        elif cut == 'CONTEXT_PREFIX_WRITTEN': crash[NEXT] = context[:len(context)//2]
        elif cut == 'CONTEXT_CANDIDATE_CREATED': crash[NEXT] = b''
        e.need(snapshots['crash'][0] == crash, 'owner context interrupted exact prefix')
        e.need(snapshots['recovery-crash'][0] == crash, 'owner context second interruption changed bytes')
        e.need(final == dict(initial, **{ACTIVE: context}), 'owner context final inventory')
        events_path = case/'events.json'; e.need(not events_path.is_symlink() and events_path.stat().st_size <= 16384, 'owner context events capacity/type')
        events = e.parse(events_path.read_bytes()); e.exact(events, 'first recovery resume')
        for values in events.values():
            e.need(type(values) is list and len(values) <= 256 and all(type(v) is str for v in values), 'owner context events shape')
            e.need(not any(v in ACKS or v.startswith('APPLY_ACK_') for v in values), 'owner context returned old acknowledgement')
        selected = {k: [v for v in values if v.startswith('CONTEXT_')] for k, values in events.items()}
        e.need(selected['first'] == complete[:stage+1] and selected['recovery'] == prefix, 'owner context force-before-metadata order')
        resume = prefix+(active if ACTIVE in crash else candidate[1:] if NEXT in crash else candidate)
        if ACTIVE in crash or NEXT in crash: resume += prefix+active
        e.need(selected['resume'] == resume, 'owner context exact recovery force order')
        rows.append(dict(cut=cut, status='PASS', contextSha256=e.digest(context), protectedFiles=len(initial)))
    receipt_path = root/'receipt.json'; e.need(not receipt_path.is_symlink() and receipt_path.stat().st_size <= 16384, 'owner context receipt type/capacity')
    receipt = e.parse(receipt_path.read_bytes()); expected = dict(schema='gse-v53-journal-context-local-v1', status='PASS', cases=rows,
        interruptions='injected-IOException', freshProcesses=False, sourceOwnership='actual-local-force', retirementAuthorized=False,
        fullOwnerProgress=False, runtimeEnabled=False)
    e.need(receipt == expected and all(type(receipt[k]) is type(v) for k, v in expected.items()), 'owner context receipt scope')
    return dict(status='PASS', cases=12, interruptionsPerCase=2, originalFirst=True, sourceOwnership='actual-local-force',
                interruptionModel='injected-IOException', freshProcesses=False, remoteOwnershipVerified=False, imageSemanticClaim=False,
                retirementAuthorized=False, fullOwnerProgress=False, runtimeEnabled=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = {'missing-case': 'owner context case inventory', 'changed-vote': 'owner context protected authority changed',
        'missing-original': 'owner context protected authority changed', 'changed-source': 'owner context protected authority changed',
        'changed-context': 'context checksum', 'lost-prefix': 'owner context interrupted exact prefix',
        'second-crash-progress': 'owner context second interruption changed bytes', 'force-order': 'owner context force-before-metadata order',
        'old-ack': 'owner context returned old acknowledgement', 'false-process': 'owner context receipt scope',
        'linked-source': 'owner context linked/nonregular member', 'extra-all-snapshots': 'owner context initial authority inventory'}
    for name, reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-owner-context-negative-') as temporary:
            case_root = Path(temporary)/'evidence'; shutil.copytree(root, case_root)
            case = case_root/'CONTEXT_PREFIX_WRITTEN'
            if name == 'missing-case': shutil.rmtree(case)
            elif name == 'extra-all-snapshots':
                for snapshot in SNAPSHOTS: (case/snapshot/'unlisted.gsr').write_bytes(b'opaque')
            elif name == 'changed-vote': (case/'final/pending.accept').write_bytes(b'changed')
            elif name in ('missing-original', 'changed-source', 'linked-source'):
                path = next((case/'final'/('generations' if name == 'missing-original' else 'sources')).rglob('source.gscp'))
                if name == 'missing-original': path.unlink()
                elif name == 'changed-source': path.write_bytes(b'changed')
                else:
                    relative = path.relative_to(case_root); path.unlink(); path.symlink_to((root/relative).resolve())
            elif name == 'changed-context':
                path = case/'final'/ACTIVE; raw = path.read_bytes(); path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name == 'lost-prefix': (case/'crash'/NEXT).write_bytes(b'')
            elif name == 'second-crash-progress': (case/'recovery-crash'/NEXT).write_bytes((case/'final'/ACTIVE).read_bytes())
            elif name in ('force-order', 'old-ack'):
                path = case/'events.json'; events = e.parse(path.read_bytes())
                if name == 'force-order': events['first'].remove('CONTEXT_SOURCE_PARENT_FORCED')
                else: events['resume'].append('ACCEPT_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(events))
            else:
                path = case_root/'receipt.json'; receipt = e.parse(path.read_bytes()); receipt['freshProcesses'] = True; path.write_bytes(e.f.canonical(receipt))
            try: validate(case_root)
            except ValueError as error:
                e.need(str(error) == reason, 'wrong owner context negative reason: '+name+': '+str(error)); negatives.append(dict(case=name, reason=reason))
            else: raise ValueError('accepted owner context mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-owner-context-portable-') as temporary:
        moved = Path(temporary)/'evidence'; shutil.copytree(root, moved); e.need(validate(moved) == result, 'owner context portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
