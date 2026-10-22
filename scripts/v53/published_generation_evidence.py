"""Independent control projection and generation-write replay for the retained component fixture.

The eight process cases use conditional history/phase observations. This validates
original bytes, catalog reduction and real file/selector ordering, not remote force,
public readiness, journal publication or power-loss durability.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_evidence as c
from . import format_fixture as f
from . import source_packet as p
from .generation_install_evidence import packet_bytes, transaction
from .journal_application_evidence import inventory
from .applied_end_evidence import read, digest
from .membership_model import need

OPEN = ['CURRENT_VALIDATED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED', 'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED']
CUTS = ('INSTALL_MANIFEST_FORCED', 'INSTALL_GENERATION_FORCED', 'INSTALL_SELECTOR_FORCED', 'INSTALL_SELECTOR_RENAMED')
COVERAGE = 'selected-coverage.json'


def plan(original):
    old = p.decode(original['generations/a/source.gscp']); cap = old['capsule']; root = cap['root']
    selected_bytes = original['generations/a/selected.gsr']; selected = f.decode(selected_bytes, 'records', 'SELECTED', root)
    promise_bytes = original['generations/a/promise.gsr']; promise = f.decode(promise_bytes, 'records', 'PROMISE', root)
    basis_bytes = original['generations/a/basis.gsr']; basis = f.decode(basis_bytes, 'records', 'BASIS', root)
    p.bind(old, basis_bytes)
    need(selected['cut'] == cap['cut'] and selected['cut']['index'] == 1 and selected['nextEntry'] is None, 'publication original fixture cut')
    need(all(selected[k] == promise[k] == basis[k] for k in ('root', 'view', 'ballot')) and promise['basisId'] == basis['basisId'], 'publication original decision')
    c.majority(cap['cut']['view'], [r['voter'] for r in selected['sources']])
    need(dict(voter='node-1', basisId=basis['basisId'], basisDigest=digest(basis_bytes)) in selected['sources'], 'publication original local basis')
    before = f.decode(old['objects'][cap['catalog']], 'records', 'CATALOG', root)
    ids = c.identities(before['identities']); nodes = sorted(set(cap['cut']['view']['old']) | set(cap['cut']['view']['new']))
    # Derive the fixture's ADD reservation from its original stable catalog and fixed new identity.
    # No candidate manifest/catalog supplies the expected result.
    added = dict(node='node-6', storage='00000000-0000-0005-0000-000000000006', host='127.0.0.1', port=19006)
    payload = f.canonical(dict(request=dict(root=root, number=before['nextOperation'], expected=c.authority(root, cap['cut']['view']),
                                           kind='ADD', target=before['identities']+[added])))
    entry = dict(root=root, authority=selected['view'], index=2, previous=cap['cut']['entry'], origin=selected['ballot'], kind='RESERVE', payload=digest(payload))
    entry_bytes = f.encode('records', 'ENTRY', entry)
    common = dict(root=root, authority=selected['view'], ballot=selected['ballot'], entry=digest(entry_bytes), index=2)
    accept_bytes = f.encode('records', 'ACCEPT', common)
    def witnesses(phase, raw):
        return [dict(voter=n, incarnation=ids[n]['storage'], receipt=digest(f.canonical(dict(root=root, voter=n, incarnation=ids[n]['storage'], phase=phase, record=digest(raw))))) for n in nodes]
    proof = dict(common, accepts=witnesses('ACCEPT', accept_bytes)); proof_bytes = f.encode('records', 'PROOF', proof)
    cert_bytes = f.encode('records', 'CERTIFICATE', dict(proof, proofs=witnesses('PROOF', proof_bytes)))
    after = c.reduce_catalog(before, cap['catalog'], 'RESERVE', json.loads(payload), digest(entry_bytes), root)
    catalog_bytes = f.encode('records', 'CATALOG', after)
    need(len(cap['items']) == 1 and cap['items'][0]['kind'] == 'RANGE', 'publication initial range fixture')
    prior = f.decode(old['objects'][cap['items'][0]['statement']], 'records', 'CHECKPOINT', root)
    statement = dict(prior, end=after['cut'], catalogAfter=digest(catalog_bytes), applicationAfter=after['application'])
    statement_bytes = f.encode('records', 'CHECKPOINT', statement)
    objects = {h: raw for h, raw in old['objects'].items() if raw == original['root.gsr'] or h == cap['initial']}
    def add(raw):
        objects[digest(raw)] = raw
        return digest(raw)
    for raw in (payload, entry_bytes, accept_bytes, proof_bytes, cert_bytes, catalog_bytes): add(raw)
    def acknowledgements(raw):
        return [add(f.encode('records', 'CHECKPOINT_ACK', dict(root=root, voter=n, incarnation=ids[n]['storage'], cut=after['cut'], statement=digest(raw)))) for n in nodes]
    item = dict(kind='RANGE', statement=add(statement_bytes), endorsements=acknowledgements(statement_bytes), certificate=None, descriptor=None)
    bridge = dict(statement, start=cap['cut'], catalogBefore=cap['catalog'], applicationBefore=cap['application'])
    bridge_bytes = f.encode('records', 'CHECKPOINT', bridge); add(bridge_bytes)
    ancestry = bridge_bytes + b''.join(objects[h] for h in acknowledgements(bridge_bytes))
    coverage = f.canonical(dict(schema='gse-v53-selected-coverage/1.3', selection=digest(selected_bytes),
                               parent={k: cap[k] for k in ('cut', 'catalog', 'application')}, certificate=digest(cert_bytes)))
    source = packet_bytes(dict(cap, cut=after['cut'], catalog=digest(catalog_bytes), application=after['application'], items=[item]), objects, old['images'])
    packet = p.decode(source)
    files = {'source.gscp': source, 'promise.gsr': promise_bytes, 'basis.gsr': basis_bytes, 'selected.gsr': selected_bytes, COVERAGE: coverage,
             'ancestry.gsr': ancestry, **{h+'.image': original['generations/a/'+h+'.image'] for h in old['images']}}
    manifest = dict(root=root, node='node-1', generation='b', **{k: packet['capsule'][k] for k in ('cut', 'catalog', 'application')},
                    capsule=digest(packet['capsuleBytes']), promise=digest(promise_bytes), basis=digest(basis_bytes), selection=digest(selected_bytes), ownedTail=None,
                    files=[dict(path=n, size=len(v), sha256=digest(v)) for n, v in sorted(files.items())])
    files['generation.gsr'] = f.encode('records', 'GENERATION', manifest)
    selector = f.encode('records', 'SELECTOR', dict(root=root, node='node-1', generation='b', digest=digest(files['generation.gsr'])))
    need(sum(len(v) for n, v in files.items() if not n.endswith('.image')) <= 32*1024*1024, 'publication metadata ceiling')
    return files, selector


def stdout(root, label):
    need(read(root/(label+'.stderr')) == b'', 'publication worker stderr')
    lines = read(root/(label+'.stdout'), 1024*1024).decode().splitlines()
    return [line if line == 'AWAITING_KILL' else json.loads(line) for line in lines]


def validate_case(root, row):
    original = inventory(root/'original'); final = inventory(root/'final')
    files, selector = plan(original); events, writes = transaction(files)
    wanted = dict(original, **{'generations/b': None, 'selector.gsr': selector})
    wanted.update({'generations/b/'+n: raw for n, raw in files.items()})
    need(final == wanted and inventory(root/'node') == wanted, 'publication final exact projection')
    need(row['manifest'] == digest(files['generation.gsr']) and row['status'] == 'PASS', 'publication receipt binding')
    position = events.index(row['cut']); renamed = position >= events.index('INSTALL_SELECTOR_RENAMED')
    crash = dict(original, **{'generations/b': None})
    crash.update({'generations/b/'+n: files[n] for n, at in writes.items() if at <= position})
    if renamed: crash['selector.gsr'] = selector
    elif position >= events.index('INSTALL_SELECTOR_WRITTEN'): crash['selector.pending.gsr'] = selector
    need(inventory(root/'crash') == crash, 'publication interrupted exact writes')
    fault = stdout(root, 'fault'); expected = [dict(event=e) for e in OPEN+events[:position+1]]
    if row['mode'] == 'kill': expected += ['AWAITING_KILL']
    need(fault == expected, 'publication crash order')
    again = 'CURRENT_VALIDATED' if renamed else 'INSTALL_SELECTOR_WRITTEN'
    need(row['recoveryCut'] == again, 'publication recovery cut')
    recovery = stdout(root, 'recovery-fault')
    expected = [dict(event=e) for e in (OPEN[:1] if renamed else OPEN+events[:events.index(again)+1])]
    need(recovery == expected, 'publication repeated recovery order')
    recovered = dict(wanted)
    if not renamed: recovered.update({'selector.gsr': original['selector.gsr'], 'selector.pending.gsr': selector})
    need(inventory(root/'recovery-crash') == recovered, 'publication repeated recovery bytes')
    done = dict(status='PASS', manifest=row['manifest'], journalPublication=False)
    need(stdout(root, 'resume') == [dict(event=e) for e in (OPEN if renamed else OPEN+events)]+[done], 'publication completed force order')


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json'))
    need(receipt['execution'] == 'private-published-generation' and receipt['observations'] == 'conditional-fixture'
         and receipt['journalPublication'] is False and receipt['powerLoss'] is False and receipt['freshJvms'] == 24, 'publication scope')
    pairs = [(mode, cut) for mode in ('halt', 'kill') for cut in CUTS]
    need([(r['mode'], r['cut']) for r in receipt['cases']] == pairs, 'publication complete matrix')
    need({p.name for p in root.iterdir()} == {'receipt.json'} | {m+'-'+c for m, c in pairs}, 'publication case inventory')
    for row in receipt['cases']: validate_case(root/(row['mode']+'-'+row['cut']), row)
    return dict(status='PASS', cases=8, freshJvms=24, projection='independent-control-reducer', journalPublication=False, observations='conditional-fixture')


def qualify(root):
    result = validate(root)  # An invalid original may never count as a successful mutation rejection.
    variants = ('changed-decision', 'changed-certificate', 'changed-coverage', 'early-selector', 'missing-force')
    rejected = []
    for variant in variants:
        with tempfile.TemporaryDirectory(prefix='v53-published-negative-') as temp:
            copy = Path(temp)/'evidence'; shutil.copytree(root, copy)
            case = copy/'halt-INSTALL_MANIFEST_FORCED'
            if variant == 'early-selector':
                (case/'crash/selector.gsr').write_bytes((case/'final/selector.gsr').read_bytes())
            elif variant == 'missing-force':
                log = case/'resume.stdout'; log.write_text(log.read_text().replace('{"event":"INSTALL_GENERATION_FORCED"}\n', ''))
            else:
                name = {'changed-decision': 'selected.gsr', 'changed-certificate': 'source.gscp', 'changed-coverage': COVERAGE}[variant]
                target = case/'final/generations/b'/name; raw = bytearray(target.read_bytes()); raw[len(raw)//2] ^= 1; target.write_bytes(raw)
            try: validate(copy)
            except (ValueError, KeyError, TypeError): rejected.append(variant)
            else: raise ValueError('accepted publication mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-published-portable-') as temp:
        copy = Path(temp)/'evidence'; shutil.copytree(root, copy); need(validate(copy) == result, 'publication portable replay')
    return dict(result, negatives=rejected, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(Path(args.root)), sort_keys=True))
