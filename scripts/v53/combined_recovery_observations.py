"""Inspect cold majority continuation after the separately replayed failed probe.

This reader checks original continuity, voting/publication records and selected
current generations. It does NOT reduce every new selection, retirement or wire
transfer from bootstrap, and therefore does not admit a Phase 3 history.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
from . import combined_resource_probe as probe
from . import admitted_cross_view_evidence as cross

h,c,e,f,need=probe.h,probe.c,probe.e,probe.f,probe.need
read=probe.history.d.read
COHORTS=(('node-1','node-3','node-4'),('node-1','node-3','node-4'),('node-1','node-3'))
NODES=('node-1','node-2','node-3','node-4')


def application_boundary(before,after,node,kind):
    if node in set(after['old'])|set(after['new']):return 'APPLY_ACK_DIRECTORY_FORCED'
    need(kind=='FINAL' and before['operation'] is not None and node in before['old'] and node not in before['new'] and
         after['operation'] is None and after['old']==after['new']==before['new'] and after['generation']==before['generation']+1,
         'cold continuation exact departing FINAL')
    return 'APPLY_NONVOTING_DIRECTORY_FORCED'


def inspect(directory):
    root=Path(directory);before=h.inventory(root)
    need({p.name for p in root.iterdir()}=={'pressure','recovery','lineage.json','receipt.json'},'cold continuation exact inventory')
    receipt=dict(schema='gse-v53-combined-recovery-v1',status='PASS',profile='4-REMOVE',pressureOutcome='FAIL',sameDirectories=True,
                 partialFloorRecoveryQualified=False,automaticRuntimeReachabilityQualified=False,phase3Complete=False)
    need(read(root/'receipt.json')==receipt,'cold continuation bounded scope')
    diagnosis=probe.diagnose(root/'pressure');old=root/'pressure/4-REMOVE/history';native=root/'recovery'
    expected={'before-network','after-close','calls.json','events.json','wire.json','failures.json','result.json'}
    expected|={f'{name}-{i}{suffix}' for i in range(1,4) for name,suffix in [('installed',''),('selected','.gsr')]}
    expected|={f'{name}-{i}{suffix}' for i in range(5,8) for name,suffix in [('applied',''),('published',''),('native-entry','.gsr'),('native-payload','.bin')]}
    need({p.name for p in native.iterdir()}==expected,'cold continuation exact recovery inventory')
    need(read(native/'calls.json')==[],'cold continuation no second bootstrap/prelude')
    initial={n:c.inventory(old/'after-close'/n) for n in NODES}
    probe.history.b.match(native,'before-network',initial)
    entry=(old/'native-entry-5.gsr').read_bytes();payload=(old/'native-payload-5.bin').read_bytes()
    lineage=read(root/'lineage.json');root_id=c.current(initial['node-1'])[2]['capsule']['root']
    need(type(lineage) is dict and set(lineage)=={'root','directories','retainedEntry','retainedPayload'} and
         lineage['root']==root_id and lineage['retainedEntry']==e.digest(entry) and lineage['retainedPayload']==e.digest(payload),
         'cold continuation original lineage')
    paths=lineage['directories']
    need(type(paths) is list and len(paths)==4 and all(type(row) is dict and set(row)=={'node','replica','application'} for row in paths) and
         [row['node'] for row in paths]==list(NODES) and all(type(row[k]) is str and Path(row[k]).is_absolute() for row in paths for k in ('replica','application')) and
         len({row[k] for row in paths for k in ('replica','application')})==8,'cold continuation directory observations')
    need((native/'native-entry-5.gsr').read_bytes()==entry and (native/'native-payload-5.bin').read_bytes()==payload,
         'cold continuation inherited original command')
    stages=['before-network',*[f'installed-{i}' for i in range(1,4)],*[f'{s}-{i}' for i in range(5,8) for s in ('applied','published')],'after-close']
    for stage in stages:
        need({p.name for p in (native/stage).iterdir()}==set(NODES),'cold continuation complete original owners')
        need(c.inventory(native/stage/'node-2')==initial['node-2'],'cold continuation unfinished floor owner unchanged')
    events=read(native/'events.json');rounds=[row for row in events if row['event'].startswith('ROUND_')]
    need([row['event'] for row in rounds]==['ROUND_'+name for name in ['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE']*3+['BEFORE_READY']],
         'cold continuation exact round lifecycle')
    identities={n:probe.history.d.future.identity(files) for n,files in initial.items()}
    parent=c.current(initial['node-1'])[2]['capsule'];last_ack=None
    for ordinal,(kind,voters) in enumerate(zip(('INTENT','FINAL','BARRIER'),COHORTS),1):
        index=ordinal+4;selected_raw=(native/f'selected-{ordinal}.gsr').read_bytes();selected=f.decode(selected_raw,'records','SELECTED')
        need([s['voter'] for s in selected['sources']]==list(voters) and selected['root']==root_id and
             selected['ballot']==dict(counter=ordinal+3,proposer='node-1',incarnation=identities['node-1']['storage']) and
             selected['nextEntry']==(e.digest(entry) if ordinal==1 else None),'cold continuation selected surviving majority')
        installed={n:c.inventory(native/f'installed-{ordinal}'/n) for n in NODES}
        _,members,packet=c.current(installed['node-1']);cap=packet['capsule']
        need(c.anchor(cap)==c.anchor(parent),'cold continuation installed published parent')
        before_catalog=f.decode(packet['objects'][cap['catalog']],'records','CATALOG')
        op=before_catalog['results'][-1]
        command=dict(sealed={k:op[k] for k in ('request','prepared','receipt')}) if kind=='INTENT' else dict(binding=op['binding']) if kind=='FINAL' else None
        body=f.canonical(command) if command is not None else b''
        raw=(native/f'native-entry-{index}.gsr').read_bytes();value=f.decode(raw,'records','ENTRY')
        need((native/f'native-payload-{index}.bin').read_bytes()==body and value==dict(root=root_id,authority=selected['view'],index=index,
             previous=cap['cut']['entry'],origin=f.decode(entry,'records','ENTRY')['origin'] if ordinal==1 else selected['ballot'],kind=kind,payload=e.digest(body)),
             'cold continuation exact subsequent command')
        cross.context.majority(cap['cut']['view'],list(voters))
        after=cross.context.reduce_catalog(before_catalog,cap['catalog'],kind,command,e.digest(raw),root_id)
        cross.context.majority(after['cut']['view'],[n for n in voters if n in set(after['cut']['view']['old'])|set(after['cut']['view']['new'])])
        catalog=f.encode('records','CATALOG',after)
        accept=f.encode('records','ACCEPT',dict(root=root_id,authority=selected['view'],ballot=selected['ballot'],index=index,entry=e.digest(raw)))
        def witnesses(record,phase):return [dict(voter=n,incarnation=identities[n]['storage'],receipt=e.digest(f.canonical(
            dict(root=root_id,voter=n,incarnation=identities[n]['storage'],phase=phase,record=e.digest(record))))) for n in voters]
        proof=f.encode('records','PROOF',dict(f.decode(accept,'records','ACCEPT'),accepts=witnesses(accept,'ACCEPT')))
        certificate=f.encode('records','CERTIFICATE',dict(f.decode(proof,'records','PROOF'),proofs=witnesses(proof,'PROOF')))
        applied={n:c.inventory(native/f'applied-{index}'/n) for n in NODES}
        published={n:c.inventory(native/f'published-{index}'/n) for n in NODES}
        for node in voters:
            _,installed_members,_=c.current(installed[node]);_,local,_=c.current(applied[node]);prefix,pub,published_packet=c.current(published[node])
            need(installed_members['selected.gsr']==local['selected.gsr']==pub['selected.gsr']==selected_raw,'cold continuation installed selection binding')
            frames,_=c.pending(applied[node]['pending.accept'],('PROOF','CERTIFICATE'))
            need(frames['ENTRY']==raw and frames['PAYLOAD']==body and frames['ACCEPT']==accept and frames['PROOF']==proof and frames['CERTIFICATE']==certificate and
                 applied[node]['applied-end/certificate.gsr']==certificate and applied[node]['applied-end/catalog.gsr']==catalog and
                 applied[node]['applied-end/application.image']==members[cap['application']+'.image'] and published_packet['capsule']['cut']==after['cut'] and
                 published_packet['objects'][published_packet['capsule']['catalog']]==catalog and published[node]['pending.accept']==c.EMPTY,
                 'cold continuation exact observed vote and publication')
            if application_boundary(cap['cut']['view'],after['cut']['view'],node,kind)=='APPLY_NONVOTING_DIRECTORY_FORCED':
                need(not any(k.startswith('applied-end/') and k.endswith('ack.gsr') for k in applied[node]),
                     'cold continuation departed owner has no successor checkpoint ACK')
        probe.history.publication(native,SimpleNamespace(slot=index,voters=voters,group=published,applied=applied),ordinal)
        for offset,record in enumerate((selected_raw,raw)):
            row=rounds[(ordinal-1)*3+offset]
            need(set(row)=={'node','event','record','bytes'} and row['node']=='node-1' and
                 row['record']==e.digest(record) and base64.b64decode(row['bytes'],validate=True)==record,'cold continuation original round record')
        row=rounds[(ordinal-1)*3+2];last_ack=base64.b64decode(row['bytes'],validate=True);ack=f.decode(last_ack,'wire','PUBLISH_ACK')
        prefix,_,published_packet=c.current(published['node-1'])
        need(row['node']=='node-1' and row['record']==e.digest(last_ack) and ack['root']==root_id and ack['view']==selected['view'] and ack['ballot']==selected['ballot'] and
             ack['sender']==ack['recipient']==identities['node-1'] and ack['payload']==dict(certificate=e.digest(certificate),selection=e.digest(selected_raw),
             published=c.anchor(published_packet['capsule']),generation=e.digest(published['node-1'][prefix+'generation.gsr'])),
             'cold continuation original completion acknowledgement')
        starts=[i for i,v in enumerate(events) if v['event']=='SLOT_BEGIN' and v['index']==index]
        finish=events.index(row)
        need(len(starts)==1 and starts[0]<finish,'cold continuation complete slot observation')
        for node in voters:
            trace=[v['event'] for v in events[starts[0]:finish+1] if v['node']==node]
            probe.history.d.s.ordered(trace,['ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED',
                application_boundary(cap['cut']['view'],after['cut']['view'],node,kind),'PUBLICATION_SELECTOR_FORCED','PUBLICATION_ACK_BEFORE_RETURN'],
                'cold continuation durable slot '+node)
        parent=published_packet['capsule']
    need(rounds[-1]['node']=='node-1' and rounds[-1]['record']==e.digest(last_ack) and base64.b64decode(rounds[-1]['bytes'],validate=True)==last_ack,
         'cold continuation readiness after original barrier')
    probe.history.b.match(native,'after-close',published)
    errors=read(native/'failures.json')
    need(any(row.get('node')=='node-2' and row.get('kind')=='PREPARE' and row.get('failure')==
             'java.lang.IllegalArgumentException: native maintenance requires recovered storage' for row in errors),'cold continuation partial floor refusal')
    need(read(native/'result.json')==dict(status='PASS',activations=3,internalReady=True,publicReady=False),'cold continuation original result')
    need(h.inventory(root)==before,'cold continuation original changed')
    return dict(status='OBSERVED',pressureDiagnosis=diagnosis['status'],publishedSlots=[5,6,7],originalCommandPreserved=True,
        partialFloorOwnerUnchanged=True,partialFloorRecovered=False,survivingCohorts=[list(v) for v in COHORTS],
        completePhysicalReplayQualified=False,fullNetworkQualified=False,phase3Complete=False,originalPreserved=True)


NEGATIVES={
    'scope':'cold continuation bounded scope','lineage':'cold continuation original lineage',
    'lost-command':'cold continuation inherited original command','changed-floor':'cold continuation unfinished floor owner unchanged',
    'lost-round':'cold continuation exact round lifecycle','lost-refusal':'cold continuation partial floor refusal',
    'wrong-ready':'cold continuation readiness after original barrier','unrelated-result':'cold continuation original result',
    'wrong-voters':'cold continuation selected surviving majority',
    'lost-certificate':'cold continuation exact observed vote and publication',
    'changed-catalog':'cold continuation exact observed vote and publication',
    'lost-accept-force':'selected retention force order: cold continuation durable slot node-1',
    'invented-departed-ack':'cold continuation departed owner has no successor checkpoint ACK',
}

def mutate(root,name):
    if name=='lost-command':(root/'recovery/native-entry-5.gsr').write_bytes(b'changed');return
    if name=='changed-floor':(root/'recovery/after-close/node-2/floor-copies/proposal.gsr').write_bytes(b'changed');return
    if name=='lost-certificate':(root/'recovery/applied-5/node-3/applied-end/certificate.gsr').write_bytes(b'changed');return
    if name=='changed-catalog':(root/'recovery/applied-6/node-1/applied-end/catalog.gsr').write_bytes(b'changed');return
    if name=='invented-departed-ack':(root/'recovery/applied-6/node-4/applied-end/ack.gsr').write_bytes(b'invented');return
    if name=='wrong-voters':
        path=root/'recovery/selected-1.gsr';v=f.decode(path.read_bytes(),'records','SELECTED');v['sources'][1]['voter']='node-2'
        path.write_bytes(f.encode('records','SELECTED',v));return
    need(name in NEGATIVES,'cold continuation declared mutation')
    path=root/('receipt.json' if name=='scope' else 'lineage.json' if name=='lineage' else 'recovery/failures.json' if name=='lost-refusal' else
               'recovery/result.json' if name=='unrelated-result' else 'recovery/events.json')
    value=read(path)
    if name=='scope':value['partialFloorRecoveryQualified']=True
    elif name=='lineage':value['retainedEntry']='0'*64
    elif name=='lost-refusal':value=[]
    elif name=='unrelated-result':value['publicReady']=True
    elif name=='lost-round':value=[row for row in value if row['event']!='ROUND_BEFORE_READY']
    elif name=='lost-accept-force':value=[row for row in value if not (row['node']=='node-1' and row['event']=='ACCEPT_PARENT_FORCED')]
    else:next(row for row in value if row['event']=='ROUND_BEFORE_READY')['record']='0'*64
    h.save(path,value)


def qualify(directory):
    root=Path(directory);before=h.inventory(root);original=inspect(root);rows=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-cold-observation-negative-') as temp:
            copy=Path(temp)/'raw';shutil.copytree(root,copy);mutate(copy,name)
            try:inspect(copy)
            except ValueError as error:need(str(error)==reason,'cold continuation unrelated rejection: '+name+': '+str(error))
            else:raise ValueError('cold continuation accepted mutation: '+name)
            rows.append(dict(case=name,status='REJECTED',reason=reason))
    need(h.inventory(root)==before,'cold continuation original changed during negatives')
    return dict(observation=original,negatives=rows,originalPreserved=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else inspect(args.directory),sort_keys=True))
