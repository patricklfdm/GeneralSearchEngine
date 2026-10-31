"""Original-first native carried-slot replay, independent of Java result claims.

A three-voter prior round stops at ACCEPT, PROOF, CERTIFICATE or application.
The native network selects two original owners, finishes the exact old entry,
then publishes a fresh barrier. This is not autonomous election or joint closure.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
import uuid
from . import native_dispatch_evidence as d
from . import distinct_minority_evidence as old
from . import inherited_future_evidence as install
from . import native_source_retirement_evidence as retirement

b, c, e, f, need = d.b, d.c, d.e, d.f, d.need
s, future = d.s, d.future
PHASES = {'ACCEPT': (), 'PROOF': ('PROOF',), 'CERTIFICATE': ('PROOF', 'CERTIFICATE'), 'APPLIED': ('PROOF', 'CERTIFICATE')}


def prelude(root, phase):
    group = s.initialize(b.original(root, 3, False))
    group = {n: dict(files, **{future.FILE: future.frame(future.initial(files), {})}) for n, files in group.items()}
    prepared, chosen, installed = s.campaign(root, group, 2, 'round-1-prepared', selected_prefix=d.slot.prefix)
    for label, state in [('prepared', prepared), ('selected', chosen), ('installed', installed)]:
        b.match(root, 'round-1-'+label, state)
    group = b.settled(installed); b.match(root, 'round-1-settled', group)
    _, local, packet = c.current(group['node-1']); cap = packet['capsule']
    selected = f.decode(local['selected.gsr'], 'records', 'SELECTED')
    entry = f.encode('records', 'ENTRY', dict(root=cap['root'], authority=selected['view'], index=1,
        previous=cap['cut']['entry'], origin=selected['ballot'], kind='BARRIER', payload=e.digest(b'')))
    need(b.t.plans.read(root/'entry-1.gsr', 8192) == entry and b.t.plans.read(root/'payload-1.bin', e.MIB) == b'', 'carried original entry/payload')
    accept = f.encode('records', 'ACCEPT', dict(root=cap['root'], authority=selected['view'], ballot=selected['ballot'], index=1, entry=e.digest(entry)))
    def witnesses(raw, kind):
        return [dict(voter=n, incarnation=future.identity(files)['storage'], receipt=e.digest(f.canonical(dict(root=cap['root'], voter=n,
            incarnation=future.identity(files)['storage'], phase=kind, record=e.digest(raw))))) for n, files in sorted(group.items())]
    proof = f.encode('records', 'PROOF', dict(f.decode(accept, 'records', 'ACCEPT'), accepts=witnesses(accept, 'ACCEPT')))
    cert = f.encode('records', 'CERTIFICATE', dict(f.decode(proof, 'records', 'PROOF'), proofs=witnesses(proof, 'PROOF')))
    originals = [('ACCEPT', b''), ('PROOF', proof), ('CERTIFICATE', proof+cert)]
    after = dict(group)
    for kind, extra in originals:
        if kind != 'ACCEPT' and kind not in PHASES[phase]: break
        after = {}
        for n, files in group.items():
            _, own, _ = c.current(files)
            vote = e.container([files['selector.gsr'], own['promise.gsr'], own['selected.gsr'], entry, accept], b'')+extra
            vote = vote[:8]+struct.pack('>I', len(vote))+vote[12:]
            after[n] = dict(files, **{'pending.accept': vote})
        b.match(root, 'slot-1-'+{'ACCEPT':'accepted', 'PROOF':'proved', 'CERTIFICATE':'certified'}[kind], after)
    if phase == 'APPLIED':
        catalog = copy.deepcopy(f.decode(packet['objects'][cap['catalog']], 'records', 'CATALOG'))
        catalog['cut'] = dict(cap['cut'], index=1, entry=e.digest(entry)); catalog_raw = f.encode('records', 'CATALOG', catalog)
        statement = f.encode('records', 'CHECKPOINT', dict(root=cap['root'], scope='RANGE', start=cap['cut'], end=catalog['cut'],
            catalogBefore=cap['catalog'], catalogAfter=e.digest(catalog_raw), applicationBefore=cap['application'], applicationAfter=cap['application']))
        for n, files in after.items():
            ack = f.encode('records', 'CHECKPOINT_ACK', dict(root=cap['root'], voter=n, incarnation=future.identity(files)['storage'], cut=catalog['cut'], statement=e.digest(statement)))
            end = dict(zip(('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','application.image','ack.gsr'),
                (files['selector.gsr'], cert, catalog_raw, statement, local[cap['application']+'.image'], ack)))
            end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=cap['root'], node=n,
                files=[dict(path=k, **e.info(v)) for k, v in sorted(end.items())]))
            after[n] = dict(files, **{'applied-end':None}, **{'applied-end/'+k:v for k,v in end.items()})
    b.match(root, 'old-'+phase.lower(), after); b.match(root, 'before-network', after)
    return after, entry


def activation(root, group, phase):
    names = list(d.VOTERS); identity = future.identity(group['node-1'])
    ballot = dict(counter=3, proposer='node-1', incarnation=identity['storage'])
    prepared, sources, grants, identifiers = dict(group), {}, {}, set()
    for n in names:
        files = group[n]; _, members, _ = c.current(files)
        raw, tail = old.captured(files, PHASES[phase]); packet = s.p.decode(raw); cap = packet['capsule']
        prior = c.journal(files['grants.gsr'], cap['root'], n); observed = c.inventory(root/'installed'/n)
        rows = c.journal(observed['grants.gsr'], cap['root'], n)
        need(rows[:len(prior)] == prior and [v[0] for v in rows[len(prior):]] == ['PROMISE','BASIS','SELECTED'], 'carried original grant extension')
        identifier = rows[len(prior)][2]['basisId']
        need(str(uuid.UUID(identifier)) == identifier and identifier not in identifiers and all(v[2].get('basisId') != identifier for v in prior), 'carried fresh original grant UUID')
        identifiers.add(identifier)
        value = dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
        promise = f.encode('records', 'PROMISE', value); wrapper = s.s.wrap(promise, files[s.FILE])
        raw = c.packet_bytes(cap, dict(packet['objects'], **{e.digest(wrapper): wrapper}), packet['images']); frozen = s.p.decode(raw)
        basis = f.encode('records', 'BASIS', dict(value, voter=n, cut=cap['cut'], capsule=e.digest(frozen['capsuleBytes']), inventory=e.digest(frozen['indexBytes']), accepted=tail))
        source = 'sources/'+identifier
        changed = dict(files, **{'grants.gsr': files['grants.gsr']+promise+basis, source:None, source+'/source.gscp':raw})
        for h in packet['images']: changed[source+'/'+h+'.image'] = members[h+'.image']
        if n == 'node-1': changed['allocator.gsr'] = f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node=n, counter=3))
        prepared[n], grants[n], sources[n] = changed, (promise,basis), (basis,frozen,wrapper)
    _, installed = install.install(prepared, sources, grants, names, ballot, {}, {}, selected_prefix=d.slot.prefix)
    b.match(root, 'installed', installed)
    chosen = c.current(installed['node-1'])[1]['selected.gsr']
    need(b.t.plans.read(root/'selected.gsr', 65536) == chosen, 'carried exact installed selection')
    return installed, f.decode(chosen, 'records', 'SELECTED')


def validate(root, *, confirmed_retention=False):
    root = Path(root); phase = b.t.plans.read(root/'carried-phase.txt', 32).decode()
    need(phase in PHASES, 'carried phase')
    expected = {'initial','original-plan.gsbp','original-application.image','carried-phase.txt','carried-result.json',
        'entry-1.gsr','payload-1.bin','before-network','installed','selected.gsr','applied-1','applied-2','published-1','published-2',
        'after-close','calls.json','events.json','wire.json','failures.json','old-'+phase.lower()}
    expected |= {'round-1-'+v for v in ('prepared','selected','installed','settled')}
    expected |= {'slot-1-'+{'ACCEPT':'accepted','PROOF':'proved','CERTIFICATE':'certified'}[k] for k in ('ACCEPT', *PHASES[phase])}
    b.selection.layout(root, expected, 'carried slot inventory')
    before, entry = prelude(root, phase); group, selected = activation(root, before, phase)
    states, rounds, selected, identities = d.slots(root, group, selected, carried=entry, kinds=('BARRIER','BARRIER'), confirmed_retention=confirmed_retention)
    transfers = d.network(root, states, rounds, selected, identities, carried_first=True, confirmed_retention=confirmed_retention)
    calls = d.read(root/'calls.json')
    for kind in ('ACCEPT', *PHASES[phase]):
        rows = [v for v in calls if v['operation'] == {'ACCEPT':'accept','PROOF':'proof','CERTIFICATE':'certificate'}[kind]+'-1']
        need([v['node'] for v in rows] == sorted(before), 'carried original phased owners')
        for row in rows: s.ordered(row['events'], [kind+'_CANDIDATE_FORCED',kind+'_PARENT_FORCED',kind+'_BEFORE_RETURN'], 'carried old '+kind)
    events = d.read(root/'events.json'); stop = next(i for i,v in enumerate(events) if v['event'] == 'SLOT_BEGIN' and v['index'] == 2)
    for n in d.VOTERS:
        names = [v['event'] for v in events[:stop] if v['node'] == n]
        required = (['CERTIFICATE_ACTIVE_PARENT_FORCED','NATIVE_RETIREMENT_CERTIFICATE_RETAINED','SUPERSEDED_END_AUTHORITY_FORCED','STAGED_RETIREMENT_BEFORE_RETURN'] if phase == 'APPLIED' else [])
        s.ordered(names, required+['ACCEPT_PARENT_FORCED','FLOOR_PARENT_FORCED','PROOF_PARENT_FORCED','PUBLICATION_SELECTOR_FORCED'], 'carried cleanup/reaccept/floor '+n)
        accepted = names.index('ACCEPT_PARENT_FORCED')
        need('APPLY_ACK_DIRECTORY_FORCED' not in names[:accepted] and names.count('APPLY_ACK_DIRECTORY_FORCED') == 1, 'carried cleanup emitted application acknowledgement')
        if phase != 'APPLIED': need('NATIVE_RETIREMENT_CERTIFICATE_RETAINED' not in names, 'carried unstaged cleanup')
    need(d.read(root/'carried-result.json') == dict(status='PASS', carried=e.digest(entry), slots=2, publicReady=False), 'carried result scope')
    failures = d.read(root/'failures.json')
    need(isinstance(failures,list) and len(failures) <= 6 and all(v['node']=='node-3' and v['kind']=='FUTURE_RETENTION_INTENT'
        and v['failure']=='java.lang.IllegalArgumentException: higher ballot observed; fresh campaign required' for v in failures), 'carried unexpected network failure')
    result=dict(status='PASS', phase=phase, slots=2, voters=3, selected=2, transfers=transfers, automaticElection=False, publicReady=False, phase3Complete=False)
    if confirmed_retention:result['retentionSemantics']='original-copy-confirmation'
    return result


NEGATIVES = {
    'old-vote': 'admitted exact old-{phase}: node-1',
    'installed-original': 'admitted exact installed: node-2',
    'new-vote': 'admitted exact applied-1: node-1',
    'published': 'admitted exact published-1: node-2',
    'fresh-barrier': 'admitted exact applied-2: node-2',
    'unselected': 'admitted exact after-close: node-3',
    'missing-accept': 'selected retention force order: native dispatch slot 1 node-2',
    'early-floor': 'selected retention force order: native dispatch slot 1 node-1',
    'scope': 'carried result scope',
}


def qualify(root, *, confirmed_retention=False):
    options={'confirmed_retention':True} if confirmed_retention else {}
    root=Path(root); original=validate(root,**options); negatives=[]
    cases=dict(NEGATIVES,**d.OBSERVATION_NEGATIVES,**retirement.NEGATIVES) if confirmed_retention else NEGATIVES
    for name,reason in cases.items():
        reason=reason.format(phase=original['phase'].lower())
        with tempfile.TemporaryDirectory(prefix='v53-carried-slot-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            files={'old-vote':'old-'+original['phase'].lower()+'/node-1/pending.accept', 'installed-original':'installed/node-2/selector.gsr',
                'new-vote':'applied-1/node-1/pending.accept','published':'published-1/node-2/selector.gsr',
                'fresh-barrier':'applied-2/node-2/pending.accept','unselected':'after-close/node-3/pending.accept'}
            if name in retirement.NEGATIVES:retirement.mutate(path,name)
            elif name in d.OBSERVATION_NEGATIVES:d.mutate_observation(path,name)
            elif name in files: (path/files[name]).write_bytes(b'changed')
            elif name in ('missing-accept','early-floor'):
                rows=d.read(path/'events.json');node='node-2' if name=='missing-accept' else 'node-1'
                at=next(i for i,v in enumerate(rows) if v['node']==node and v['event']=='ACCEPT_PARENT_FORCED')
                if name=='missing-accept': rows.pop(at)
                else:
                    force=next(i for i,v in enumerate(rows) if v['node']==node and v['event']=='FLOOR_PARENT_FORCED'); rows[at],rows[force]=rows[force],rows[at]
                (path/'events.json').write_text(json.dumps(rows))
            else:
                value=d.read(path/'carried-result.json');value['publicReady']=True;(path/'carried-result.json').write_text(json.dumps(value))
            try:validate(path,**options)
            except ValueError as error:need(str(error)==reason,'carried negative wrong reason: '+name+': '+str(error))
            else:raise ValueError('carried mutation accepted: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');parser.add_argument('--confirmed-retention',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root,confirmed_retention=args.confirmed_retention),sort_keys=True))
