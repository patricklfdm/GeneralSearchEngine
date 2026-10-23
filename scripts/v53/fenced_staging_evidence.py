"""Original-first physical replay of cleanup under a higher volatile observation.

Local callback ordering and retained bytes are checked. This does not establish
fresh-process durability, remote ownership or independent core image semantics.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import journal_context_evidence as owner
from . import pending_context_evidence as e
from .round_storage_evidence import anchor

CUTS = ('before', 'STAGED_RETIREMENT_AUTHORITY_VALIDATED', 'SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN',
        'SUPERSEDED_END_AUTHORITY_FORCED', 'SUPERSEDED_END_FILE_DELETED',
        'SUPERSEDED_END_RETIREMENT_DELETED', 'STAGED_RETIREMENT_BEFORE_RETURN')


def protected(files):
    return {name: raw for name, raw in files.items() if not name.startswith(('applied-end/', 'application-replay/'))}


def original(files, directories):
    frozen = protected(files)
    owner.original_inventory(frozen, directories-{'applied-end'})
    prefix, selected_files, selected_packet = e.current(frozen)
    frames, values = e.votes(frozen['pending.accept'], selected_packet['capsule']['cut'])
    old_prefix, old_files, packet = e.current(dict(frozen, **{'selector.gsr': frames['SELECTOR']}))
    e.need(old_prefix != prefix, 'fenced staging distinct original generation')
    root = e.f.decode(frozen['root.gsr'], 'records', 'ROOT'); registry = e.identities(root['initial'])
    view = {'original-generation/'+name.removeprefix(old_prefix): raw for name, raw in frozen.items()
            if name.startswith(old_prefix) and not name.endswith('.image')}
    view.update({'backing-images/'+h+'.image': old_files[h+'.image'] for h in packet['images']})
    members, selected = e.original_generation(view, frames['SELECTOR'], packet, root, registry)
    e.need(frames['PROMISE'] == members['promise.gsr'] and frames['SELECTED'] == members['selected.gsr'], 'fenced staging original vote authority')
    grants = owner.journal(frozen['grants.gsr'], packet['capsule']['root'], 'node-1')
    e.need(all(members[kind.lower()+'.gsr'] == raw for kind, raw, _ in grants[:3])
           and all(selected_files[kind.lower()+'.gsr'] == raw for kind, raw, _ in grants[3:]), 'fenced staging exact original grant groups')
    current = e.f.decode(selected_files['selected.gsr'], 'records', 'SELECTED')
    basis = grants[-2][2]; source_prefix = 'sources/'+basis['basisId']+'/'
    backing = e.p.decode(frozen[source_prefix+'source.gscp'])
    e.need(current['ballot']['counter'] == 21 and current['cut'] == packet['capsule']['cut']
           and current['nextEntry'] == e.digest(frames['ENTRY']) and basis['accepted'] == e.digest(frames['ACCEPT'])
           and selected_files['owned-tail.gsr'] == frames['ACCEPT'], 'fenced staging installed carried authority')
    e.need(anchor(backing['capsule']) == anchor(packet['capsule']) == anchor(selected_packet['capsule']), 'fenced staging same parent')
    e.need(e.cuts(selected_files['selected-sources.gsr'], current) == [current['cut']]*3, 'fenced staging complete selected sources')
    for kind in ('ENTRY', 'PAYLOAD', 'ACCEPT', 'PROOF', 'CERTIFICATE'):
        e.need(backing['objects'].get(e.digest(frames[kind])) == frames[kind], 'fenced staging exact retained certified source')
    for kind in ('ENTRY', 'PAYLOAD'):
        e.need(selected_packet['objects'].get(e.digest(frames[kind])) == frames[kind], 'fenced staging selected exact carried data')
    e.certificate_links(backing, frames['CERTIFICATE'], packet['capsule']['cut'], registry)
    # Reconstruct the exact derived end using the original parent/certificate and
    # recorded image. Java alone executes the typed core image semantic check.
    cap = packet['capsule']; end = {name.removeprefix('applied-end/'): raw for name, raw in files.items() if name.startswith('applied-end/')}
    e.need('application.image' in end, 'fenced staging original derived image absent')
    after = e.f.decode(packet['objects'][cap['catalog']], 'records', 'CATALOG')
    after.update(cut=dict(cap['cut'], index=2, entry=e.digest(frames['ENTRY'])), application=e.digest(end['application.image']), applicationSequence=43, lastDataIndex=2)
    catalog = e.f.encode('records', 'CATALOG', after)
    start = e.f.decode(packet['objects'][cap['items'][0]['statement']], 'records', 'CHECKPOINT')
    statement = dict(start, end=after['cut'], catalogAfter=e.digest(catalog), applicationAfter=after['application'])
    statement_raw = e.f.encode('records', 'CHECKPOINT', statement)
    parent_raw = e.f.encode('records', 'CHECKPOINT', dict(statement, start=cap['cut'], catalogBefore=cap['catalog'], applicationBefore=cap['application']))
    def ack(raw):
        return e.f.encode('records', 'CHECKPOINT_ACK', dict(root=cap['root'], voter='node-1', incarnation=registry['node-1']['storage'], cut=after['cut'], statement=e.digest(raw)))
    expected = dict(zip(('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr', 'parent-statement.gsr', 'parent-ack.gsr'),
                       (frames['SELECTOR'], frames['CERTIFICATE'], catalog, statement_raw, end['application.image'], ack(statement_raw), parent_raw, ack(parent_raw))))
    expected['plan.json'] = e.f.canonical(dict(schema='gse-v53-applied-end/1.3', root=cap['root'], node='node-1',
        files=[dict(path=name, bytes=len(raw), sha256=e.digest(raw)) for name, raw in sorted(expected.items())]))
    e.need(end == expected, 'fenced staging exact original derived end')
    return frozen


def validate(root):
    root = Path(root)
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} == set(CUTS)|{'receipt.json'}, 'fenced staging case inventory')
    rows = []
    for point in CUTS:
        path = root/point
        e.need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()} == {'initial', 'final', 'events.json'}, 'fenced staging snapshot inventory')
        initial, directories = owner.read_snapshot(path/'initial'); final, final_dirs = owner.read_snapshot(path/'final')
        expected = original(initial, directories)
        e.need(final == expected and final_dirs == directories-{'applied-end'}, 'fenced staging protected originals changed')
        events_path = path/'events.json'
        e.need(not events_path.is_symlink() and events_path.stat().st_size <= 65536, 'fenced staging event type/capacity')
        events = e.parse(events_path.read_bytes())
        e.need(type(events) is list and len(events) <= 512 and all(type(v) is str for v in events), 'fenced staging event shape')
        e.need(not any(v in owner.ACKS or v.startswith('APPLY_ACK_') or v == 'APPLY_BEFORE_RETURN' for v in events), 'fenced staging old acknowledgement returned')
        selected = [v for v in events if v.startswith(('STAGED_', 'SUPERSEDED_', 'TEST_'))]
        observed = 'TEST_OBSERVED_24'
        e.need(selected.count(observed) >= 1 and (selected[0] == observed if point == 'before'
               else all(i > 0 and selected[i-1] == point for i, v in enumerate(selected) if v == observed)), 'fenced staging observation boundary')
        normal = [v for v in selected if v != observed]
        head = ['STAGED_RETIREMENT_AUTHORITY_VALIDATED', 'SUPERSEDED_END_VALIDATED', 'SUPERSEDED_END_RETIREMENT_CREATED',
                'SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN', 'SUPERSEDED_END_RETIREMENT_WRITTEN', 'SUPERSEDED_END_RETIREMENT_FORCED',
                'SUPERSEDED_END_RETIREMENT_PARENT_FORCED', 'SUPERSEDED_END_RETIREMENT_RENAMED', 'SUPERSEDED_END_AUTHORITY_FORCED']
        members = sum(name.startswith('applied-end/') for name in initial)
        tail = ['SUPERSEDED_END_BEFORE_DELETE', 'SUPERSEDED_END_FILE_DELETED']*members + [
            'SUPERSEDED_END_BEFORE_RETIREMENT_DELETE', 'SUPERSEDED_END_RETIREMENT_DELETED',
            'SUPERSEDED_END_BEFORE_DIRECTORY_DELETE', 'SUPERSEDED_END_DIRECTORY_DELETED', 'STAGED_RETIREMENT_BEFORE_RETURN']
        e.need(normal == head+tail, 'fenced staging exact force/delete order')
        rows.append(dict(cut=point, status='PASS', observed=24, oldWritesRejected=True))
    receipt_path = root/'receipt.json'
    e.need(not receipt_path.is_symlink() and receipt_path.stat().st_size <= 16384, 'fenced staging receipt type/capacity')
    receipt = e.parse(receipt_path.read_bytes()); expected = dict(schema='gse-v53-fenced-staging-v1', status='PASS', cases=rows,
        freshProcesses=False, oldAckReturned=False, transferredLifetime=False)
    e.need(e.f.canonical(receipt) == e.f.canonical(expected), 'fenced staging receipt scope')
    return dict(status='PASS', cases=7, originalFirst=True, freshProcesses=False, remoteOwnershipVerified=False,
                imageSemanticClaim=False, transferredLifetime=False, oldAcknowledgement=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    cases = {'missing-case': 'fenced staging case inventory', 'changed-vote': 'fenced staging protected originals changed',
        'lost-original': 'fenced staging protected originals changed', 'retained-staging': 'fenced staging protected originals changed',
        'changed-end': 'fenced staging exact original derived end', 'force-order': 'fenced staging exact force/delete order',
        'old-ack': 'fenced staging old acknowledgement returned', 'missing-observation': 'fenced staging observation boundary',
        'false-process': 'fenced staging receipt scope', 'linked-authority': 'owner context linked/nonregular member',
        'extra-authority': 'owner context initial authority inventory'}
    for name, reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-fenced-staging-negative-') as temp:
            moved = Path(temp)/'evidence'; shutil.copytree(root, moved); path = moved/'before'
            if name == 'missing-case': shutil.rmtree(path)
            elif name == 'changed-vote': (path/'final/pending.accept').write_bytes(b'changed')
            elif name == 'lost-original': next((path/'final/generations').rglob('source.gscp')).unlink()
            elif name == 'retained-staging': shutil.copytree(path/'initial/applied-end', path/'final/applied-end')
            elif name == 'changed-end': (path/'initial/applied-end/ack.gsr').write_bytes(b'changed')
            elif name in ('force-order', 'old-ack', 'missing-observation'):
                event_path = path/'events.json'; events = e.parse(event_path.read_bytes())
                if name == 'force-order': events.remove('SUPERSEDED_END_AUTHORITY_FORCED')
                elif name == 'old-ack': events.append('APPLY_ACK_FORCED')
                else: events.remove('TEST_OBSERVED_24')
                event_path.write_bytes(e.f.canonical(events))
            elif name == 'false-process':
                receipt_path = moved/'receipt.json'; receipt = e.parse(receipt_path.read_bytes()); receipt['freshProcesses'] = True; receipt_path.write_bytes(e.f.canonical(receipt))
            elif name == 'linked-authority':
                member = path/'final/grants.gsr'; member.unlink(); member.symlink_to((root/'before/final/grants.gsr').resolve())
            else:
                for stage in ('initial', 'final'): (path/stage/'extra.gsr').write_bytes(b'opaque')
            try: validate(moved)
            except ValueError as error:
                e.need(str(error) == reason, 'wrong fenced staging negative reason: '+name+': '+str(error)); negatives.append(dict(case=name, reason=reason))
            else: raise ValueError('accepted fenced staging mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-fenced-staging-portable-') as temp:
        moved = Path(temp)/'evidence'; shutil.copytree(root, moved); e.need(validate(moved) == result, 'fenced staging portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
