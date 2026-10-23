"""Original-first actual parent-ACK/publication replay. Historical bootstrap is conditional.

Derive the new DATA catalog and both statements from the retained original parent
and peer ends, then simulate exact writes/deletions. This is not a semantic image
oracle, network authentication or power-loss test.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import format_fixture as f
from . import source_packet as p
from .applied_end_evidence import read, digest
from .context_evidence import majority
from .generation_install_evidence import packet_bytes
from .journal_application_evidence import inventory, vote
from .journal_publication_evidence import steps, EMPTY
from .published_generation_evidence import OPEN, COVERAGE
from .membership_model import need
from .selected_sources_evidence import retained as selected_originals

CUTS = ('APPLY_PARENT_STATEMENT_PREFIX_WRITTEN', 'APPLY_PARENT_ACK_PREFIX_WRITTEN', 'APPLY_PARENT_ACK_FORCED',
        'PUBLICATION_SELECTOR_FORCED', 'COVERED_END_FILE_DELETED', 'COVERED_VOTE_PREFIX_WRITTEN')
FILES = ('plan.json', 'selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'parent-statement.gsr', 'application.image', 'ack.gsr', 'parent-ack.gsr')


def original_plan(root, original, renewal=False, *, pruning=False):
    need(not (renewal and pruning), 'exclusive parent profile')
    at = 8 if pruning else 4 if renewal else 2
    frames, values = vote(original['pending.accept']); old = p.decode(original['generations/b/source.gscp']); cap = old['capsule']; root_hash = cap['root']
    need(cap['cut'] == values['SELECTED']['cut'] and cap['cut']['index'] == at and len(cap['items']) == 1 and cap['items'][0]['kind'] == 'RANGE', 'parent original compacted fixture')
    need(original['selector.gsr'] == frames['SELECTOR'] and all(original['generations/b/'+k.lower()+'.gsr'] == frames[k] for k in ('PROMISE', 'SELECTED')), 'parent original decision')
    basis_bytes = original['generations/b/basis.gsr']; basis = f.decode(basis_bytes, 'records', 'BASIS', root_hash)
    p.bind(p.decode(original['sources/'+basis['basisId']+'/source.gscp']) if renewal else old, basis_bytes)
    need(dict(voter='node-1', basisId=basis['basisId'], basisDigest=digest(basis_bytes)) in values['SELECTED']['sources'], 'parent original local source')
    majority(cap['cut']['view'], [s['voter'] for s in values['SELECTED']['sources']])
    before = f.decode(old['objects'][cap['catalog']], 'records', 'CATALOG', root_hash)
    peer = inventory(root/'node-2'); image = peer['applied-end/application.image']; entry = values['ENTRY']; cert = values['CERTIFICATE']
    need(entry['kind'] == ('BARRIER' if pruning else 'DATA') and entry['index'] == at+1 and entry['previous'] == cap['cut']['entry'] and before['applicationSequence'] == 41
         and cap['application'] == digest(read(root/'base.image', 64*1024*1024)), 'parent original application base')
    after = copy.deepcopy(before); after.update(cut=dict(before['cut'], index=at+1, entry=digest(frames['ENTRY'])))
    if pruning: need(image == read(root/'base.image', 64*1024*1024), 'pruning BARRIER preserves application')
    else: after.update(application=digest(image), applicationSequence=42, lastDataIndex=at+1)
    catalog = f.encode('records', 'CATALOG', after)
    prior = f.decode(old['objects'][cap['items'][0]['statement']], 'records', 'CHECKPOINT', root_hash)
    need(prior['end'] == cap['cut'] and prior['catalogAfter'] == cap['catalog'] and prior['applicationAfter'] == cap['application'], 'parent original range end')
    statement = dict(prior, end=after['cut'], catalogAfter=digest(catalog), applicationAfter=after['application']); statement_bytes = f.encode('records', 'CHECKPOINT', statement)
    parent = dict(statement, start=cap['cut'], catalogBefore=cap['catalog'], applicationBefore=cap['application']); parent_bytes = f.encode('records', 'CHECKPOINT', parent)
    need(prior['start']['index'] == 0 and parent['start']['view'] == parent['end']['view'] and parent['start']['view']['operation'] is None
         and parent_bytes == read(root/('bridge-4-statement.gsr' if renewal else 'parent-statement.gsr')), 'parent derived same-era statement')
    observations = json.loads(read(root/'observations.json')); need(set(observations) == ({'accepts', 'proofs', 'checkpoints', 'bridges', 'historical'} if renewal else {'accepts', 'proofs', 'checkpoints', 'parents'} | ({'historical'} if pruning else set())), 'parent observation inventory')
    if pruning:
        from .ancestry_pruning_evidence import original_sources
        original_sources(root, original, cap, before, observations)
    lowers = []; extra_statements = []; extra_acks = [[], []] if renewal else []
    if renewal:
        ids_before = {v['node']: v['storage'] for v in before['identities'] if v['node'] in cap['cut']['view']['old']}; old_bytes = b''
        for number, physical in ((1, original), (2, peer)):
            basis_raw = physical['generations/b/basis.gsr']; frozen = f.decode(basis_raw, 'records', 'BASIS', root_hash)
            packet = p.decode(physical['sources/'+frozen['basisId']+'/source.gscp']); p.bind(packet, basis_raw); cut = packet['capsule']
            need(cut['cut']['index'] == number and frozen['voter'] == 'node-'+str(number) and frozen['ballot'] == values['SELECTED']['ballot']
                 and dict(voter=frozen['voter'], basisId=frozen['basisId'], basisDigest=digest(basis_raw)) in values['SELECTED']['sources'], 'ancestor actual original source binding')
            for h, size in packet['images'].items():
                raw = physical['sources/'+frozen['basisId']+'/'+h+'.image']; need(len(raw) == size and digest(raw) == h, 'ancestor original source image')
            lower = {k: cut[k] for k in ('cut', 'catalog', 'application')}; lowers.append(lower)
            old_statement = dict(prior, start=lower['cut'], catalogBefore=lower['catalog'], applicationBefore=lower['application'])
            raw = f.encode('records', 'CHECKPOINT', old_statement); old_bytes += raw
            for n, storage in sorted(ids_before.items()):
                ack = f.encode('records', 'CHECKPOINT_ACK', dict(root=root_hash, voter=n, incarnation=storage, cut=cap['cut'], statement=digest(raw)))
                need(dict(voter=n, storage=storage, record=digest(ack), parent=digest(f.canonical(cap['cut']))) in observations['historical'], 'ancestor historical endorsement binding'); old_bytes += ack
            renewed = f.encode('records', 'CHECKPOINT', dict(statement, start=lower['cut'], catalogBefore=lower['catalog'], applicationBefore=lower['application']))
            need(renewed == read(root/('bridge-'+str(number)+'-statement.gsr')), 'ancestor exact renewal'); extra_statements.append(renewed)
        need(original['generations/b/ancestry.gsr'] == old_bytes, 'ancestor original complete bridge inventory')
    ids = {}; acks = []; parents = []; local_end = None
    for n in ('node-1', 'node-2', 'node-3'):
        physical = original if n == 'node-1' else inventory(root/n); local_frames, _ = vote(physical['pending.accept'])
        identity = f.decode(physical['node.gsr'], 'records', 'NODE', root_hash)['identity']; ids[n] = identity['storage']
        need(identity['node'] == n and all(local_frames[k] == frames[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE'))
             and local_frames['SELECTOR'] == physical['selector.gsr'], 'parent actual original voter')
        def ack(raw): return f.encode('records', 'CHECKPOINT_ACK', dict(root=root_hash, voter=n, incarnation=identity['storage'], cut=after['cut'], statement=digest(raw)))
        main_ack, parent_ack = ack(statement_bytes), ack(parent_bytes)
        end = {'selector.gsr': physical['selector.gsr'], 'certificate.gsr': frames['CERTIFICATE'], 'catalog.gsr': catalog, 'statement.gsr': statement_bytes,
               'parent-statement.gsr': parent_bytes, 'application.image': image, 'ack.gsr': main_ack, 'parent-ack.gsr': parent_ack}
        for i, raw in enumerate(extra_statements):
            end['ancestor-'+str(i)+'-statement.gsr'] = raw; end['ancestor-'+str(i)+'-ack.gsr'] = ack(raw)
        end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=root_hash, node=n,
                files=[dict(path=k, bytes=len(v), sha256=digest(v)) for k, v in sorted(end.items())]))
        if n == 'node-1':
            need(not any(k == 'applied-end' or k.startswith('applied-end/') for k in physical), 'parent original local end absent'); local_end = end
        else:
            need({k.removeprefix('applied-end/'): v for k, v in physical.items() if k.startswith('applied-end/')} == end, 'parent real peer materialization')
            need(main_ack == read(root/('ack-'+n+'.gsr')) and parent_ack == read(root/(('bridge-4-' if renewal else 'parent-')+n+'.gsr')), 'parent real retained ACKs')
            acks.append(main_ack); parents.append(parent_ack)
            for i, raw in enumerate(extra_statements):
                extra_acks[i].append(ack(raw)); need(ack(raw) == read(root/('bridge-'+str(i+1)+'-'+n+'.gsr')), 'ancestor actual renewed ACK')
    for label, phase in (('accepts', 'ACCEPT'), ('proofs', 'PROOF')):
        need(observations[label] == [dict(voter=n, storage=s, record=digest(frames[phase]), parent=digest(f.canonical(cap['cut']))) for n, s in sorted(ids.items())], 'parent original phase observations')
        witnesses = [dict(voter=n, incarnation=s, receipt=digest(f.canonical(dict(root=root_hash, voter=n, incarnation=s, phase=phase, record=digest(frames[phase]))))) for n, s in sorted(ids.items())]
        need(cert[label] == witnesses, 'parent original phase witnesses'); majority(cap['cut']['view'], sorted(ids))
    for label, records in ((('checkpoints', acks),) if renewal else (('checkpoints', acks), ('parents', parents))):
        need(observations[label] == [dict(voter=n, storage=ids[n], record=digest(a), parent=digest(f.canonical(after['cut']))) for n, a in zip(('node-2', 'node-3'), records)], 'parent physical end observations: '+label)
        majority(after['cut']['view'], ['node-2', 'node-3'])
    if renewal:
        expected_observations = [dict(voter=n, storage=ids[n], record=digest(a), parent=digest(f.canonical(after['cut']))) for group in [*extra_acks, parents] for n, a in zip(('node-2', 'node-3'), group)]
        need(observations['bridges'] == sorted(expected_observations, key=lambda v: (v['record'], v['voter'])), 'ancestor actual renewal observations')
    objects = {h: raw for h, raw in old['objects'].items() if raw == original['root.gsr'] or h == cap['initial']}
    for raw in [catalog, statement_bytes, parent_bytes, *extra_statements, *[a for group in extra_acks for a in group], *acks, *parents, *[frames[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE')]]: objects[digest(raw)] = raw
    offset = 12 + sum(len(frames[k]) for k in ('SELECTOR', 'PROMISE', 'SELECTED', 'ENTRY', 'ACCEPT'))
    count = int.from_bytes(original['pending.accept'][offset:offset+4], 'big'); payload = original['pending.accept'][offset+4:offset+4+count]; objects[digest(payload)] = payload
    item = dict(kind='RANGE', statement=digest(statement_bytes), endorsements=[digest(a) for a in acks], certificate=None, descriptor=None)
    source = packet_bytes(dict(cap, cut=after['cut'], catalog=digest(catalog), application=after['application'], items=[item]), objects, {after['application']: len(image)})
    packet = p.decode(source)
    coverage_value = dict(schema='gse-v53-selected-coverage/1.3', selection=digest(frames['SELECTED']), parent={k: cap[k] for k in ('cut', 'catalog', 'application')}, certificate=digest(frames['CERTIFICATE']))
    if renewal: coverage_value['ancestors'] = lowers
    coverage = f.canonical(coverage_value)
    packed_ancestry = b''.join(raw+b''.join(group) for raw, group in zip(extra_statements, extra_acks)) + parent_bytes+b''.join(parents)
    files = {'source.gscp': source, 'promise.gsr': frames['PROMISE'], 'basis.gsr': basis_bytes, 'selected.gsr': frames['SELECTED'], COVERAGE: coverage,
             'ancestry.gsr': packed_ancestry, after['application']+'.image': image}
    files.update(selected_originals(original, 'generations/b/'))
    manifest = dict(root=root_hash, node='node-1', generation='a', **{k: packet['capsule'][k] for k in ('cut', 'catalog', 'application')},
                    capsule=digest(packet['capsuleBytes']), promise=digest(frames['PROMISE']), basis=digest(basis_bytes), selection=digest(frames['SELECTED']), ownedTail=None,
                    files=[dict(path=n, size=len(v), sha256=digest(v)) for n, v in sorted(files.items())])
    files['generation.gsr'] = f.encode('records', 'GENERATION', manifest)
    selector = f.encode('records', 'SELECTOR', dict(root=root_hash, node='node-1', generation='a', digest=digest(files['generation.gsr'])))
    need(sum(len(v) for k, v in files.items() if not k.endswith('.image')) <= 32*1024*1024 and len(files['ancestry.gsr']) <= (3 if renewal else 1)*16*1024, 'parent bounded publication')
    return files, selector, local_end


def application(expected, original, exists, stop):
    current = dict(original); events = []
    def event(name): events.append(dict(event=name)); return name == stop
    if event('APPLY_VALIDATED'): return current, exists, events
    if not exists:
        exists = True
        if event('APPLY_DIRECTORY_CREATED'): return current, exists, events
    count = sum('ancestor-'+str(i)+'-statement.gsr' in expected for i in range(5))
    names = FILES[:6] + tuple('ancestor-'+str(i)+'-statement.gsr' for i in range(count)) + FILES[6:] + tuple('ancestor-'+str(i)+'-ack.gsr' for i in range(count))
    need(set(names) == set(expected), 'ancestor bounded end inventory')
    for name in names:
        label = {'plan.json': 'APPLY_PLAN', 'application.image': 'APPLY_IMAGE', 'ack.gsr': 'APPLY_ACK',
                 'parent-statement.gsr': 'APPLY_PARENT_STATEMENT', 'parent-ack.gsr': 'APPLY_PARENT_ACK'}.get(name, 'APPLY_METADATA')
        if name.startswith('ancestor-'):
            parts = name.split('-'); label = 'APPLY_ANCESTOR_'+parts[1]+('_ACK' if parts[2] == 'ack.gsr' else '_STATEMENT')
        if name == 'ack.gsr' and event('APPLY_END_FORCED'): return current, exists, events
        if name not in current:
            current[name] = b''
            if event(label+'_CREATED'): return current, exists, events
        need(expected[name].startswith(current[name]), 'parent exact resumable prefix')
        offset = len(current[name]); current[name] = expected[name][:offset+(len(expected[name])-offset)//2]
        if event(label+'_PREFIX_WRITTEN'): return current, exists, events
        current[name] = expected[name]
        if event(label+'_WRITTEN'): return current, exists, events
        if event(label+'_FORCED'): return current, exists, events
    if event('APPLY_ACK_DIRECTORY_FORCED'): return current, exists, events
    event('APPLY_BEFORE_RETURN'); return current, exists, events


def validate_case(root, row, renewal=False):
    root = Path(root); current = inventory(root/'original'); files, selector, end = original_plan(root, current, renewal)
    recovery = (('APPLY_ANCESTOR_1_ACK_PREFIX_WRITTEN' if renewal else 'APPLY_PARENT_ACK_PREFIX_WRITTEN') if row['cut'].startswith('APPLY_') else 'COVERED_VOTE_CANDIDATE_FORCED')
    replay_case(root, row, current, files, selector, end, 5 if renewal else 3, recovery)


def replay_case(root, row, current, files, selector, end, selected_index, recovery_cut, publication_steps=steps):
    """Replay exact physical effects; callers supply independently projected original inputs."""
    need(row['status'] == 'PASS' and row['manifest'] == digest(files['generation.gsr']) and row['recoveryCut'] == recovery_cut, 'parent repeated recovery identity')
    for label, stop, snapshot, mode in (('fault', row['cut'], 'crash', row['mode']), ('recovery-fault', row['recoveryCut'], 'recovery-crash', 'halt'), ('resume', None, 'final', None)):
        need(read(root/(label+'.stderr')) == b'', 'parent worker stderr'); rows = [json.loads(line) for line in read(root/(label+'.stdout'), 2*1024*1024).splitlines()]
        names = [r.get('event', '') for r in rows]; applied_stop = stop is not None and stop.startswith('APPLY_')
        if current['selector.gsr'] != selector:
            staged = {n.removeprefix('applied-end/'): v for n, v in current.items() if n.startswith('applied-end/')}
            staged, exists, events = application(end, staged, 'applied-end' in current, stop if applied_stop else None)
            need([r for r in rows if r.get('event', '').startswith('APPLY_')] == events, 'parent exact application force order: '+label)
            need(names.index('CERTIFICATE_ACTIVE_PARENT_FORCED') < names.index('APPLICATION_AUTHORITY_VALIDATED') < names.index('REPLAY_BEFORE_RETURN') < names.index('APPLY_VALIDATED'), 'parent certified replay before end')
            if not applied_stop: need(names.index('APPLY_BEFORE_RETURN') < names.index('PUBLICATION_VALIDATED'), 'parent force before publication')
            current = {n: v for n, v in current.items() if n != 'applied-end' and not n.startswith('applied-end/')}
            if exists: current['applied-end'] = None
            current.update({'applied-end/'+n: v for n, v in staged.items()})
        else: need(not any(e.startswith(('APPLY_', 'REPLAY_')) for e in names), 'parent covered cleanup cannot reapply')
        if applied_stop:
            expected = OPEN + ['CERTIFICATE_ACTIVE_FORCED', 'CERTIFICATE_ACTIVE_PARENT_FORCED']; resulting = current
        else:
            expected = []; resulting = current
            for event, state in publication_steps(current, files, selector):
                expected.append(event); resulting = state
                if event == stop: break
            need(stop is None or expected[-1] == stop, 'parent publication crash point')
        actual = [e for e in names if e.startswith(('INSTALL_', 'PUBLICATION_', 'COVERED_', 'CURRENT_', 'SELECTED_SOURCES_')) or e in
                  ('ACCEPT_ACTIVE_FORCED', 'ACCEPT_ACTIVE_PARENT_FORCED', 'CERTIFICATE_ACTIVE_FORCED', 'CERTIFICATE_ACTIVE_PARENT_FORCED', 'FLOOR_COPY_BEFORE_RETURN')]
        need(actual == expected, 'parent exact publication/deletion order: '+label)
        if mode is None:
            need(rows[-1] == dict(status='PASS', manifest=row['manifest'], selectedIndex=selected_index, journalPublication=True) and sum('status' in r for r in rows) == 1, 'parent final receipt')
        else:
            need(not any('status' in r for r in rows) and rows[-1] == (dict(event='AWAITING_KILL', cut=stop) if mode == 'kill' else dict(event=stop)), 'parent premature success or wrong cut')
        need(inventory(root/snapshot) == resulting, 'parent exact surviving bytes: '+label)
        need(sum(n.endswith('.image') for n in resulting) <= 7, 'parent image count'); current = resulting
    need(inventory(root/'node-1') == current and current['pending.accept'] == EMPTY and 'applied-end' not in current, 'parent final owned state')


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json'))
    need(receipt['execution'] == 'private-parent-checkpoint-publication' and receipt['expectedCases'] == 12 and receipt['freshJvms'] == 36
         and receipt['phasedObservations'] == 'actual-local-owners' and receipt['checkpointObservations'] == 'actual-forced-ends'
         and receipt['bootstrap'] == 'private-fixture' and receipt['selectorPublication'] is True and receipt['powerLoss'] is False, 'parent scope')
    pairs = [(m, c) for m in ('halt', 'kill') for c in CUTS]
    need([(r['mode'], r['cut']) for r in receipt['cases']] == pairs and {p.name for p in root.iterdir()} == {'receipt.json'} | {m+'-'+c for m, c in pairs}, 'parent complete matrix')
    for row in receipt['cases']: validate_case(root/(row['mode']+'-'+row['cut']), row)
    return dict(status='PASS', cases=12, freshJvms=36, originalObservations='actual-local-votes-and-parent-ends', selectorPublication=True)


def qualify(root):
    root = Path(root); result = validate(root); row = json.loads(read(root/'receipt.json'))['cases'][0]; source = root/(row['mode']+'-'+row['cut']); negatives = []
    for variant in ('missing-peer-ack', 'false-observation', 'wrong-parent', 'main-ack-as-parent', 'early-ack', 'missing-force', 'changed-ancestry', 'unrelated-delete'):
        with tempfile.TemporaryDirectory(prefix='v53-parent-negative-') as temp:
            case = Path(temp)/'case'; shutil.copytree(source, case)
            if variant == 'missing-peer-ack': (case/'node-2/applied-end/parent-ack.gsr').unlink()
            elif variant == 'false-observation': (case/'observations.json').write_bytes(b'{}')
            elif variant == 'wrong-parent': (case/'parent-statement.gsr').write_bytes(read(case/'node-2/applied-end/statement.gsr'))
            elif variant == 'main-ack-as-parent': (case/'parent-node-2.gsr').write_bytes(read(case/'ack-node-2.gsr'))
            elif variant == 'early-ack': (case/'crash/applied-end/parent-ack.gsr').write_bytes(read(case/'parent-node-2.gsr'))
            elif variant == 'changed-ancestry': (case/'final/generations/a/ancestry.gsr').write_bytes(b'')
            elif variant == 'unrelated-delete': (case/'final/generations/b/selected.gsr').unlink()
            else:
                log = case/'resume.stdout'; log.write_bytes(read(log, 2*1024*1024).replace(f.canonical(dict(event='APPLY_PARENT_ACK_FORCED'))+b'\n', b''))
            try: validate_case(case, row)
            except (ValueError, KeyError, OSError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted parent mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-parent-portable-') as temp:
        dest = Path(temp)/'evidence'; shutil.copytree(root, dest); need(validate(dest) == result, 'parent portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args(); print(json.dumps(qualify(args.root), sort_keys=True))
