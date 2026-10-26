"""Derive original published histories, every complete peer generation and its floor.

Network copies retain historical proof, never manufacture new voting observations.
The frozen six-profile matrix does not establish autonomous membership recovery.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import bootstrap_publication_evidence as b
from . import promised_source_evidence as t
from . import floor_evidence as floor
from . import floor_release_evidence as release
from . import retirement_evidence as retirement
from .transport_evidence import load
c=b.c;e=b.e
PROFILES=tuple((size,backup) for size in (3,4,5) for backup in (False,True))
def profile(size,backup):return f"size-{size}-"+('backup' if backup else 'empty')

def original_calls(root,names):
    expected=[]
    def many(label):expected.extend((n,label) for n in names)
    def campaign_order(round):
        expected.append(('node-1',f'allocate-{round}'))
        for label in ('prepare','select','install'):many(f'{label}-{round}')
        many(f'round-{round}-settled-copy');many(f'round-{round}-settled-maintain')
    def publication_order(slot):
        expected.append(('node-1',f'entry-{slot}'))
        for label in ('accept','proof','certificate','apply','publish'):many(f'{label}-{slot}')
        many(f'slot-{slot}-settled-copy');many(f'slot-{slot}-settled-maintain');many(f'inspect-{slot}')
    campaign_order(1);publication_order(1);publication_order(2)
    actual=e.parse(b.t.plans.read(root/'calls.json',8*e.MIB))
    e.need(type(actual) is list and len(actual)==len(expected),'admitted complete owner calls')
    for row,(node,operation) in zip(actual,expected):
        e.exact(row,'node operation events');ev=row['events']
        e.need(row['node']==node and row['operation']==operation and type(ev) is list and 0<len(ev)<=4096 and all(type(v) is str for v in ev),'admitted exact owner call order')
        phase=operation.split('-')[0]
        required={'allocate':['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'],
                  'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],
                  'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],
                  'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN'],
                  'accept':['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN'],
                  'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
                  'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
                  'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'],
                  'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN']}.get(phase)
        if required:e.need([v for v in ev if v in set(required)]==required,'admitted force before response: '+phase)



def sessions(rows):
    e.need(type(rows) is list and 0<len(rows)<=32768,'generation bounded transcript')
    traces=[]
    for row in rows:
        e.need(type(row) is dict and set(row)=={'request','response'},'generation transcript row')
        trace=t.t.wire(row['request'])[1]['trace']
        if not traces or traces[-1][0]!=trace:
            e.need(all(trace!=previous for previous,_ in traces),'generation repeated session')
            traces.append((trace,[]))
        traces[-1][1].append(row)
    e.need(len(traces)==2,'generation complete sessions')
    return traces


def attempts(rows):
    """Sequential source transfers permit at most three identical original attempts."""
    logical=[];counts=[]
    for row in rows:
        sequence=t.t.wire(row['request'])[1]['sequence']
        if sequence==len(logical) and logical:
            e.need(row==logical[-1],'generation changed retry');counts[-1]+=1
            e.need(counts[-1]<=3,'generation retry limit')
        else:
            e.need(sequence==len(logical)+1,'generation request sequence')
            logical.append(row);counts.append(1)
    return logical


def peer_transcripts(path,peers):
    rows=e.parse(b.t.plans.read(path,8*e.MIB))
    e.need(type(rows) is list and len(rows)==len(peers),'generation contacted peers')
    result={}
    for row in rows:
        e.need(type(row) is dict and set(row)=={'node','exchanges'} and type(row['node']) is str
               and row['node'] in peers and row['node'] not in result,'generation contacted peers')
        result[row['node']]=row['exchanges']
    e.need(set(result)==set(peers),'generation contacted peers')
    return result


def case(directory,size,backup):
    root=Path(directory);raw=root/'history';names=[f'node-{n}' for n in range(1,size+1)]
    peers=names[1:size//2+1]
    b.selection.layout(root,{'history','copied','floor.gsr','wire.json','events.json'},'generation case')
    required={'original-plan.gsbp','original-application.image','initial','calls.json','observations.json','network-floor','network-floor-released'}
    required|={f'round-1-{stage}' for stage in ('prepared','selected','installed','settled')}
    required|={f'slot-{slot}-{stage}' for slot in (1,2) for stage in ('accepted','proved','certified','applied','published','settled')}
    required|={f'typed-{slot}-{node}' for slot in (1,2) for node in names}
    required|={f'{kind}-{slot}.{ext}' for slot in (1,2) for kind,ext in (('entry','gsr'),('payload','bin'))}
    b.selection.layout(raw,required,'generation original history')
    group=b.campaign(raw,b.original(raw,size,backup),1);observations=[];first=None
    for slot in (1,2):
        group,first=b.publication(raw,group,slot,first,observations)
        for node,files in group.items():
            _,members,packet=c.current(files)
            b.typed_image(raw/f'typed-{slot}-{node}',members[packet['capsule']['application']+'.image'])
    actual=load(raw/'observations.json')
    e.need(type(actual) is list and sorted(map(e.f.canonical,actual))==sorted(map(e.f.canonical,observations)),'generation original observations')
    original_calls(raw,names)
    copies={node:{name.removeprefix(c.current(group[node])[0]):data for name,data in group[node].items() if name.startswith(c.current(group[node])[0])} for node in ['node-1',*peers]}
    b.selection.layout(root/'copied',set(peers),'generation copied peers')
    wires=peer_transcripts(root/'wire.json',peers)
    _,local,local_packet=c.current(group['node-1']);ballot=e.f.decode(local['selected.gsr'],'records','SELECTED')['ballot']
    cap=local_packet['capsule'];r=cap['root'];view=e.authority(r,cap['cut']['view'])
    identities={n:e.f.decode(group[n]['node.gsr'],'records','NODE')['identity'] for n in ['node-1',*peers]}
    exchanges=0;unique=set()
    for node in peers:
        e.need(c.inventory(root/'copied'/node)==copies[node],'generation exact original members')
        _,members,packet=c.current(group[node]);remote_cap=packet['capsule']
        traces=sessions(wires[node]);e.need(all(trace not in unique for trace,_ in traces),'generation reused peer session');unique.update(trace for trace,_ in traces)
        expected=[(e.digest(e.f.canonical(remote_cap['cut'])),members['source.gscp'],'CAPSULE')]+[(h,members[h+'.image'],'APPLICATION') for h in sorted(packet['images'])]
        t.transcript(attempts(traces[0][1]),expected,r,view,ballot,identities['node-1'],identities[node],'generation prefix',chunk_bytes=4*e.MIB)
        manifest=copies[node]['generation.gsr'];reference=e.digest(e.f.canonical(dict(root=r,cut=remote_cap['cut'],scope='retained-current-generation')))
        expected=[(reference,manifest,'RECORD')]
        if 'ancestry.gsr' in members:expected.append((e.digest(members['ancestry.gsr']),members['ancestry.gsr'],'RECORD'))
        for name,data in sorted(members.items()):
            if name not in ('generation.gsr','source.gscp','ancestry.gsr') and not name.endswith('.image'):expected.append((e.digest(data),data,'RECORD'))
        t.transcript(attempts(traces[1][1]),expected,r,view,ballot,identities['node-1'],identities[node],'generation original members',chunk_bytes=4*e.MIB)
        exchanges+=len(wires[node])
    references=[dict(voter=node,generation=e.digest(members['generation.gsr']),catalog=cap['catalog'],snapshot=cap['application']) for node,members in sorted(copies.items())]
    e.need(all(len(set(copies)&set(cap['cut']['view'][side]))>len(cap['cut']['view'][side])//2 for side in ('old','new')),'generation actual floor majority')
    record=e.f.encode('records','FLOOR',dict(root=r,node='node-1',cut=cap['cut'],sources=references))
    e.need(record==b.t.plans.read(root/'floor.gsr',16384),'generation exact quorum floor')
    events,files,_,directories=floor.transaction({e.digest(v['generation.gsr']):v for v in copies.values()},record)
    expected=dict(group);expected['node-1']=dict(group['node-1'],**{name:None for name in directories},**files)
    b.match(raw,'network-floor',expected);b.match(raw,'network-floor-released',group)
    relinquish=e.f.encode('records','RETIREMENT',dict(root=r,node='node-1',floor=e.digest(record),selector=e.digest(group['node-1']['selector.gsr']),files=[dict(path=name,size=len(data),sha256=e.digest(data)) for name,data in sorted(expected['node-1'].items()) if name.startswith('floor-copies/') and data is not None]))
    state={name:({'directory':True} if data is None else retirement.entry(data)) for name,data in expected['node-1'].items()}
    release_events=[name for name,_ in release.transaction(state,relinquish)]
    e.need(load(root/'events.json')==['FLOOR_COPY_BEFORE_RETURN']+[v['event'] for v in events]+release_events,'generation exact force and release order')
    return dict(case=profile(size,backup),status='PASS',voters=size,backup=backup,copies=len(copies),exchanges=exchanges)


def validate(directory):
    root=Path(directory);b.selection.layout(root,{'receipt.json'}|{profile(s,k) for s,k in PROFILES},'generation matrix')
    cases=[case(root/profile(size,backup),size,backup) for size,backup in PROFILES]
    expected=dict(schema='gse-v53-generation-copy-v1',status='PASS',cases=cases,publicRuntime=False,publicBootstrap=True,historicalObservationsSupplied=False)
    e.need(load(root/'receipt.json')==expected,'generation matrix scope')
    return dict(status='PASS',profiles=6,floorCopies=sum(row['copies'] for row in cases),sourceExchanges=sum(row['exchanges'] for row in cases),historicalObservationsSupplied=False,publicRuntime=False)


NEGATIVES=(
    ('extra-file','generation case'),
    ('missing-observation','generation original observations'),
    ('missing-force','admitted force before response: prepare'),
    ('missing-peer','generation copied peers'),
    ('missing-copy-member','generation exact original members'),
    ('copy-coverage','generation exact original members'),
    ('copy-image','generation exact original members'),
    ('copy-extra','generation exact original members'),
    ('missing-transcript','generation contacted peers'),
    ('session-reuse','generation complete sessions'),
    ('wrong-source','generation original members correlation'),
    ('wrong-reference','generation original members original offer'),
    ('changed-data','generation original members exact data'),
    ('missing-commit','generation original members incomplete transcript'),
    ('excess-retries','generation retry limit'),
    ('changed-retry','generation changed retry'),
    ('floor-minority','generation exact quorum floor'),
    ('floor-copy','admitted exact network-floor: node-1'),
    ('floor-force','generation exact force and release order'),
    ('early-release','generation exact force and release order'),
    ('changed-remote','admitted exact network-floor-released: node-2'),
)


def mutate(root,name):
    def save(path,value):path.write_bytes(e.f.canonical(value))
    if name=='extra-file':(root/'foreign.bin').write_bytes(b'foreign')
    elif name=='missing-observation':
        path=root/'history/observations.json';value=load(path);value.pop();save(path,value)
    elif name=='missing-force':
        path=root/'history/calls.json';value=load(path);row=next(v for v in value if v['operation']=='prepare-1');row['events'].remove('BASIS_FORCED');save(path,value)
    elif name=='missing-peer':shutil.rmtree(root/'copied/node-2')
    elif name=='missing-copy-member':(root/'copied/node-2/promise.gsr').unlink()
    elif name=='copy-coverage':(root/'copied/node-2/selected-coverage.json').write_bytes(b'{}')
    elif name=='copy-image':next((root/'copied/node-2').glob('*.image')).write_bytes(b'changed')
    elif name=='copy-extra':(root/'copied/node-2/foreign.gsr').write_bytes(b'extra')
    elif name=='missing-transcript':save(root/'wire.json',[])
    elif name=='floor-minority':
        path=root/'floor.gsr';value=e.f.decode(path.read_bytes(),'records','FLOOR');value['sources']=value['sources'][:2];path.write_bytes(e.f.encode('records','FLOOR',value))
    elif name=='floor-copy':
        next((root/'history/network-floor/node-1/floor-copies').glob('*/promise.gsr')).write_bytes(b'changed')
    elif name in ('floor-force','early-release'):
        path=root/'events.json';value=load(path)
        if name=='floor-force':value.remove('FLOOR_AUTHORITY_FORCED')
        else:
            i=value.index('FLOOR_RELEASE_RELINQUISHED');value.insert(value.index('FLOOR_AUTHORITY_FORCED'),value.pop(i))
        save(path,value)
    elif name=='changed-remote':(root/'history/network-floor-released/node-2/grants.gsr').write_bytes(b'changed')
    else:
        path=root/'wire.json';value=e.parse(b.t.plans.read(path,8*e.MIB));rows=next(v['exchanges'] for v in value if v['node']=='node-2');traces=sessions(rows);start=len(traces[0][1]);index=start;side='request'
        if name=='missing-commit':rows.pop()
        elif name=='excess-retries':rows[start:start]=[dict(rows[start]) for _ in range(3)]
        elif name=='changed-retry':
            duplicate=dict(rows[start]);kind,frame=t.t.wire(duplicate['response']);frame['payload']['digest']='f'*64
            duplicate['response']=base64.b64encode(e.f.encode('wire',kind,frame)).decode();rows.insert(start+1,duplicate)
        elif name=='session-reuse':
            for row in rows[start:]:
                for key in ('request','response'):
                    kind,frame=t.t.wire(row[key]);frame['trace']=traces[0][0];row[key]=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
        else:
            if name=='wrong-source':side='response'
            if name=='changed-data':side='response';index=start+1
            kind,frame=t.t.wire(rows[index][side])
            if name=='wrong-source':frame['sender']=frame['recipient']
            elif name=='wrong-reference':frame['payload']['digest']='a'*64
            elif name=='changed-data':frame['payload'].update(bytes=base64.b64encode(b'changed').decode(),digest=e.digest(b'changed'))
            else:raise ValueError('unknown generation mutation: '+name)
            rows[index][side]=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
        save(path,value)


def qualify(directory):
    root=Path(directory);original=validate(root);negatives=[]
    for name,reason in NEGATIVES:
        with tempfile.TemporaryDirectory(prefix='v53-generation-negative-') as tmp:
            # Two copies are well-formed FLOOR bytes but not a four-voter majority.
            # A singleton would fail fixture construction before testing evidence.
            size=4 if name=='floor-minority' else 3
            copy=Path(tmp)/'case';shutil.copytree(root/profile(size,False),copy);mutate(copy,name)
            try:case(copy,size,False)
            except ValueError as error:e.need(reason in str(error),'generation unrelated negative: '+name+': '+str(error))
            else:raise ValueError('generation accepted mutation: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory),sort_keys=True))
