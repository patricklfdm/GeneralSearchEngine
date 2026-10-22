"""Original-first replay of actual journal publication/covered-retirement process evidence.

The expected generation is derived from the original forced ends and real original
votes, never the final candidate. Core image semantics are qualified separately;
this driver checks exact materialization, quorums, original-byte preservation and
force/deletion order. Historical bootstrap is conditional, not public provisioning.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import format_fixture as f
from . import source_packet as p
from .context_evidence import majority
from .generation_install_evidence import packet_bytes, transaction
from .journal_application_evidence import inventory, vote
from .applied_end_evidence import read, digest, simulate, FILES
from .published_generation_evidence import OPEN, COVERAGE
from .membership_model import need

CUTS = ('INSTALL_MANIFEST_FORCED', 'INSTALL_SELECTOR_FORCED', 'INSTALL_SELECTOR_RENAMED', 'PUBLICATION_SELECTOR_FORCED',
        'COVERED_END_FILE_DELETED', 'COVERED_END_DIRECTORY_DELETED', 'COVERED_VOTE_PREFIX_WRITTEN', 'COVERED_VOTE_RENAMED')
EMPTY = struct.pack('>4sHHI', b'GSPV', 1, 3, 12)


def original_plan(root, original):
    frames, values = vote(original['pending.accept']); root_hash = values['CERTIFICATE']['root']
    old = p.decode(original['generations/b/source.gscp']); cap = old['capsule']
    need(cap['cut'] == values['SELECTED']['cut'] and cap['cut']['index'] == 0 and cap['items'] == [], 'publication initial DATA fixture')
    need(original['selector.gsr'] == frames['SELECTOR'] and all(original['generations/b/'+n.lower()+'.gsr'] == frames[n] for n in ('PROMISE', 'SELECTED')), 'publication original decision bytes')
    majority(cap['cut']['view'], [s['voter'] for s in values['SELECTED']['sources']])
    basis_bytes = original['generations/b/basis.gsr']; basis = f.decode(basis_bytes, 'records', 'BASIS', root_hash); p.bind(old, basis_bytes)
    need(dict(voter='node-1', basisId=basis['basisId'], basisDigest=digest(basis_bytes)) in values['SELECTED']['sources'], 'publication original elected local source')
    end = {n: original['applied-end/'+n] for n in FILES}; before = f.decode(old['objects'][cap['catalog']], 'records', 'CATALOG', root_hash)
    after = f.decode(end['catalog.gsr'], 'records', 'CATALOG', root_hash); cert = values['CERTIFICATE']; entry = values['ENTRY']
    need(entry['kind'] == 'DATA' and end['certificate.gsr'] == frames['CERTIFICATE'] and after['applicationSequence'] == 42, 'publication exact original DATA end')
    expected = copy.deepcopy(before); expected.update(application=digest(end['application.image']), applicationSequence=42, lastDataIndex=1,
            cut=dict(before['cut'], index=1, entry=digest(frames['ENTRY'])))
    need(before['applicationSequence'] == 41 and expected == after and before['application'] == digest(read(root/'base.image', 64*1024*1024)), 'publication projected DATA catalog')
    statement = dict(root=root_hash, scope='RANGE', start=before['cut'], end=after['cut'], catalogBefore=cap['catalog'], catalogAfter=digest(end['catalog.gsr']),
                     applicationBefore=cap['application'], applicationAfter=after['application'])
    need(end['statement.gsr'] == f.encode('records', 'CHECKPOINT', statement), 'publication projected checkpoint')
    seen = {}; acks = []; observations = json.loads(read(root/'observations.json'))
    need(set(observations) == {'accepts', 'proofs', 'checkpoints'}, 'publication observation inventory')
    for n in ('node-1', 'node-2', 'node-3'):
        physical = original if n == 'node-1' else inventory(root/n)
        local_frames, local_values = vote(physical['pending.accept']); identity = f.decode(physical['node.gsr'], 'records', 'NODE', root_hash)['identity']; seen[n] = identity['storage']
        need(identity['node'] == n and all(local_frames[k] == frames[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE'))
             and local_frames['SELECTOR'] == physical['selector.gsr'], 'publication actual original local voter')
        local_end = {k: physical['applied-end/'+k] for k in FILES}
        need(all(local_end[k] == end[k] for k in ('application.image', 'certificate.gsr', 'catalog.gsr', 'statement.gsr'))
             and local_end['selector.gsr'] == physical['selector.gsr'], 'publication real checkpoint materialization')
        plan = dict(schema='gse-v53-applied-end/1.3', root=root_hash, node=n,
                    files=[dict(path=k, bytes=len(v), sha256=digest(v)) for k, v in sorted(local_end.items()) if k != 'plan.json'])
        need(f.canonical(plan) == local_end['plan.json'], 'publication original end inventory')
        ack = f.encode('records', 'CHECKPOINT_ACK', dict(root=root_hash, voter=n, incarnation=identity['storage'], cut=after['cut'], statement=digest(end['statement.gsr'])))
        need(ack == local_end['ack.gsr'] == read(root/('ack-'+n+'.gsr')), 'publication original physical checkpoint ACK'); acks.append(ack)
    for label, phase in (('accepts', 'ACCEPT'), ('proofs', 'PROOF')):
        need(observations[label] == [dict(voter=n, storage=s, record=digest(frames[phase]), parent=digest(f.canonical(cap['cut']))) for n, s in sorted(seen.items())], 'publication real phased observation')
        witnesses = [dict(voter=n, incarnation=s, receipt=digest(f.canonical(dict(root=root_hash, voter=n, incarnation=s, phase=phase, record=digest(frames[phase]))))) for n, s in sorted(seen.items())]
        need(cert[label] == witnesses, 'publication certificate witness provenance'); majority(cap['cut']['view'], list(seen))
    need(observations['checkpoints'] == [dict(voter=n, storage=seen[n], record=digest(a), parent=digest(f.canonical(after['cut']))) for n, a in zip(sorted(seen), acks)], 'publication real checkpoint observation')
    majority(after['cut']['view'], sorted(seen))
    objects = {h: raw for h, raw in old['objects'].items() if raw == original['root.gsr'] or h == cap['initial']}
    for raw in [end['catalog.gsr'], end['statement.gsr'], *acks, *[frames[k] for k in ('ENTRY', 'ACCEPT', 'PROOF', 'CERTIFICATE')]]: objects[digest(raw)] = raw
    # Payload is embedded after the five original frames; its exact hash is checked by vote().
    offset = 12 + sum(len(frames[k]) for k in ('SELECTOR', 'PROMISE', 'SELECTED', 'ENTRY', 'ACCEPT'))
    count = int.from_bytes(original['pending.accept'][offset:offset+4], 'big'); payload = original['pending.accept'][offset+4:offset+4+count]; objects[digest(payload)] = payload
    item = dict(kind='RANGE', statement=digest(end['statement.gsr']), endorsements=[digest(a) for a in acks], certificate=None, descriptor=None)
    source = packet_bytes(dict(cap, cut=after['cut'], catalog=digest(end['catalog.gsr']), application=after['application'], items=[item]), objects, {after['application']: len(end['application.image'])})
    packet = p.decode(source)
    coverage = f.canonical(dict(schema='gse-v53-selected-coverage/1.3', selection=digest(frames['SELECTED']),
                    parent={k: cap[k] for k in ('cut', 'catalog', 'application')}, certificate=digest(frames['CERTIFICATE'])))
    files = {'source.gscp': source, 'promise.gsr': frames['PROMISE'], 'basis.gsr': basis_bytes, 'selected.gsr': frames['SELECTED'], COVERAGE: coverage, after['application']+'.image': end['application.image']}
    manifest = dict(root=root_hash, node='node-1', generation='a', **{k: packet['capsule'][k] for k in ('cut', 'catalog', 'application')},
                    capsule=digest(packet['capsuleBytes']), promise=digest(frames['PROMISE']), basis=digest(basis_bytes), selection=digest(frames['SELECTED']), ownedTail=None,
                    files=[dict(path=n, size=len(v), sha256=digest(v)) for n, v in sorted(files.items())])
    files['generation.gsr'] = f.encode('records', 'GENERATION', manifest)
    selector = f.encode('records', 'SELECTOR', dict(root=root_hash, node='node-1', generation='a', digest=digest(files['generation.gsr'])))
    need(sum(len(v) for n, v in files.items() if not n.endswith('.image')) <= 32*1024*1024, 'publication generation metadata ceiling')
    return files, selector, end


def steps(original, files, selector):
    """Yield relevant force boundaries and exact surviving physical state; PLAN is deleted last."""
    current = dict(original)
    def event(name): return name, dict(current)
    def cleanup():
        yield event('PUBLICATION_COVERAGE_VALIDATED'); yield event('COVERED_END_VALIDATED')
        names = sorted(n for n in current if n.startswith('applied-end/') and n != 'applied-end/plan.json')
        if 'applied-end/plan.json' in current: names.append('applied-end/plan.json')
        for n in names:
            yield event('COVERED_END_BEFORE_DELETE'); del current[n]; yield event('COVERED_END_FILE_DELETED')
        if 'applied-end' in current:
            yield event('COVERED_END_BEFORE_DIRECTORY_DELETE'); del current['applied-end']; yield event('COVERED_END_DIRECTORY_DELETED')
        if 'pending.accept.next' not in current:
            current['pending.accept.next'] = b''; yield event('COVERED_VOTE_CANDIDATE_CREATED')
        offset = len(current['pending.accept.next']); need(EMPTY.startswith(current['pending.accept.next']), 'publication exact empty candidate')
        current['pending.accept.next'] = EMPTY[:offset+(len(EMPTY)-offset)//2]; yield event('COVERED_VOTE_PREFIX_WRITTEN')
        current['pending.accept.next'] = EMPTY; yield event('COVERED_VOTE_CANDIDATE_WRITTEN'); yield event('COVERED_VOTE_CANDIDATE_FORCED'); yield event('COVERED_VOTE_CANDIDATE_PARENT_FORCED')
        current['pending.accept'] = current.pop('pending.accept.next'); yield event('COVERED_VOTE_RENAMED'); yield event('COVERED_VOTE_PARENT_FORCED'); yield event('PUBLICATION_RETIRED')
    for e in OPEN: yield event(e)
    published = current['selector.gsr'] == selector
    if published and current['pending.accept'] != EMPTY: yield from cleanup()
    for e in ('ACCEPT' if published else 'CERTIFICATE')+'_ACTIVE_FORCED', ('ACCEPT' if published else 'CERTIFICATE')+'_ACTIVE_PARENT_FORCED': yield event(e)
    if not published:
        yield event('PUBLICATION_VALIDATED'); events, writes = transaction(files)
        for i, e in enumerate(events):
            if e == 'INSTALL_DIRECTORY_CREATED': current['generations/a'] = None
            for name, position in writes.items():
                if i == position: current['generations/a/'+name] = files[name]
            if e == 'INSTALL_SELECTOR_WRITTEN': current['selector.pending.gsr'] = selector
            if e == 'INSTALL_SELECTOR_RENAMED': current['selector.gsr'] = current.pop('selector.pending.gsr')
            yield event(e)
        for e in OPEN: yield event(e)
        yield event('PUBLICATION_SELECTOR_FORCED'); yield from cleanup(); yield event('PUBLICATION_BEFORE_RETURN')
    yield event('FLOOR_COPY_BEFORE_RETURN')


def validate_case(root, row):
    root = Path(root); original = inventory(root/'original'); files, selector, end = original_plan(root, original); current = original
    need(row['status'] == 'PASS' and row['manifest'] == digest(files['generation.gsr']), 'publication receipt binding')
    need(row['recoveryCut'] == ('ACCEPT_ACTIVE_FORCED' if row['cut'] == 'COVERED_VOTE_RENAMED' else
         'INSTALL_IMAGE_WRITTEN' if row['cut'] in CUTS[:2] else 'COVERED_VOTE_CANDIDATE_FORCED'), 'publication repeated recovery cut')
    for label, stop, snapshot, mode in (('fault', row['cut'], 'crash', row['mode']), ('recovery-fault', row['recoveryCut'], 'recovery-crash', 'halt'), ('resume', None, 'final', None)):
        need(read(root/(label+'.stderr')) == b'', 'publication worker stderr')
        rows = [json.loads(raw) for raw in read(root/(label+'.stdout'), 2*1024*1024).splitlines()]
        expected = []; resulting = current
        for e, state in steps(current, files, selector):
            expected.append(e); resulting = state
            if e == stop: break
        need(stop is None or expected[-1] == stop, 'publication missing crash cut')
        names = [r.get('event', '') for r in rows]
        actual = [e for e in names if e.startswith(('INSTALL_', 'PUBLICATION_', 'COVERED_', 'CURRENT_')) or e in
                  ('ACCEPT_ACTIVE_FORCED', 'ACCEPT_ACTIVE_PARENT_FORCED', 'CERTIFICATE_ACTIVE_FORCED', 'CERTIFICATE_ACTIVE_PARENT_FORCED', 'FLOOR_COPY_BEFORE_RETURN')]
        need(actual == expected, 'publication exact force/deletion order: '+label)
        if current['selector.gsr'] != selector and 'PUBLICATION_VALIDATED' in expected:
            _, _, applied = simulate(end, end, True)
            need([r for r in rows if r.get('event', '').startswith('APPLY_')] == applied, 'publication repeat applied-end forcing')
            need(names.index('CERTIFICATE_ACTIVE_PARENT_FORCED') < names.index('APPLICATION_AUTHORITY_VALIDATED') < names.index('REPLAY_BEFORE_RETURN')
                 < names.index('APPLY_END_FORCED') < names.index('APPLY_BEFORE_RETURN') < names.index('PUBLICATION_VALIDATED'), 'publication force before selector')
        else: need(not any(e.startswith(('APPLY_', 'REPLAY_')) for e in names), 'covered cleanup must not replay application')
        if mode is None:
            need(rows[-1] == dict(status='PASS', manifest=row['manifest'], selectedIndex=1, journalPublication=True) and sum('status' in r for r in rows) == 1, 'publication exact returned receipt')
        else:
            need(not any('status' in r for r in rows), 'publication success before recovery')
            need(rows[-1] == (dict(event='AWAITING_KILL', cut=stop) if mode == 'kill' else dict(event=stop)), 'publication exact halt/kill cut')
        need(inventory(root/snapshot) == resulting, 'publication exact surviving bytes: '+label)
        need(sum(n.endswith('.image') for n in resulting) <= 7, 'publication physical image count')
        current = resulting
    need(inventory(root/'node-1') == current and current['pending.accept'] == EMPTY and 'applied-end' not in current, 'publication final owned state')


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json'))
    need(receipt['execution'] == 'private-journal-publication' and receipt['expectedCases'] == 16 and receipt['freshJvms'] == 48
         and receipt['phasedObservations'] == 'actual-local-owners' and receipt['checkpointObservations'] == 'actual-forced-ends'
         and receipt['bootstrap'] == 'private-fixture' and receipt['selectorPublication'] is True and receipt['powerLoss'] is False, 'publication qualification scope')
    pairs = [(mode, cut) for mode in ('halt', 'kill') for cut in CUTS]
    need([(r['mode'], r['cut']) for r in receipt['cases']] == pairs and {p.name for p in root.iterdir()} == {'receipt.json'} | {m+'-'+c for m, c in pairs}, 'publication complete matrix')
    for row in receipt['cases']: validate_case(root/(row['mode']+'-'+row['cut']), row)
    return dict(status='PASS', cases=16, freshJvms=48, selectorPublication=True, originalObservations='actual-local-votes-and-ends')


def qualify(root):
    root = Path(root); result = validate(root)
    row = json.loads(read(root/'receipt.json'))['cases'][0]; source = root/(row['mode']+'-'+row['cut']); rejected = []
    for variant in ('missing-vote', 'false-observation', 'altered-original-end', 'changed-coverage', 'early-selector', 'early-vote-clear', 'missing-force', 'unrelated-file-deleted'):
        with tempfile.TemporaryDirectory(prefix='v53-publication-negative-') as temp:
            case = Path(temp)/'case'; shutil.copytree(source, case)
            if variant == 'missing-vote': (case/'node-2/pending.accept').unlink()
            elif variant == 'false-observation': (case/'observations.json').write_bytes(b'{}')
            elif variant == 'altered-original-end': (case/'original/applied-end/application.image').write_bytes(b'wrong')
            elif variant == 'changed-coverage': (case/'final/generations/a'/COVERAGE).write_bytes(b'{}')
            elif variant == 'early-selector': (case/'crash/selector.gsr').write_bytes(read(case/'final/selector.gsr'))
            elif variant == 'early-vote-clear': (case/'crash/pending.accept').write_bytes(EMPTY)
            elif variant == 'unrelated-file-deleted': (case/'final/generations/b/selected.gsr').unlink()
            else:
                log = case/'resume.stdout'; log.write_bytes(read(log, 2*1024*1024).replace(f.canonical(dict(event='INSTALL_GENERATION_FORCED'))+b'\n', b''))
            try: validate_case(case, row)
            except (ValueError, KeyError, OSError, TypeError): rejected.append(variant)
            else: raise ValueError('accepted publication mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-publication-portable-') as temp:
        dest = Path(temp)/'evidence'; shutil.copytree(root, dest); need(validate(dest) == result, 'publication portable replay')
    return dict(result, negatives=rejected, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
