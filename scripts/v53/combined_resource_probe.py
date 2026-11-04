"""Diagnose a retained failed pressure probe; never admit it as qualification.

Extra receiving lifetimes were imposed by the fixture. Their reachability in the
automatic runtime is not proved. Reconstruct the admitted prefix and installation,
then bind the partial floor and the exhausted image count to original bytes.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import continuous_transition_evidence as history
from . import floor_evidence as floor
from . import pending_accept_evidence as pending
from . import combined_receive_evidence as receiving
from . import joining_history_run as h

c,e,f,need=history.c,history.e,history.f,history.need
read=receiving.x.load
same=receiving.same


def diagnose(directory):
    root=Path(directory);before=h.inventory(root)
    need({p.name for p in root.iterdir()}=={'4-REMOVE','receipt.json'},'resource probe incomplete first profile')
    same(read(root/'receipt.json'),dict(schema='gse-v53-combined-transition-v1',status='INCOMPLETE',cases=[],network=True,
         simultaneousMaximumQualified=False,publicRuntime=False,phase3Complete=False),'resource probe original failure scope')
    member=root/'4-REMOVE';native=member/'history'
    need({p.name for p in member.iterdir()}=={'history','states','resources.json','source-promise.gsr','source-basis.gsr','result.json'},
         'resource probe exact member inventory')
    same(read(member/'result.json'),dict(profile='4-REMOVE',status='FAIL',pressureVoter='node-2',sourceCopies=1,learnerCopies=1,admittedLearner=False),
         'resource probe failed case scope')
    # Actual public bootstrap and all four admitted prelude slots, not a
    # conditionally constructed capsule. First native campaign is fully replayed.
    walk=history.a.prelude(native,'INTENT',size=4)
    installed=history.install(native,walk.group,1,history.topology(4)[0][1],current_maintenance=True)
    local_files=installed['node-1'];_,local_members,local_packet=c.current(local_files);local_cap=local_packet['capsule']
    selected=f.decode(local_members['selected.gsr'],'records','SELECTED')
    catalog=f.decode(local_packet['objects'][local_cap['catalog']],'records','CATALOG');operation=catalog['results'][-1]
    payload=f.canonical(dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}))
    entry=f.encode('records','ENTRY',dict(root=local_cap['root'],authority=selected['view'],index=5,
        previous=local_cap['cut']['entry'],origin=selected['ballot'],kind='INTENT',payload=e.digest(payload)))
    accept=f.encode('records','ACCEPT',dict(root=local_cap['root'],authority=selected['view'],ballot=selected['ballot'],index=5,entry=e.digest(entry)))
    vote=pending.container([local_files['selector.gsr'],local_members['promise.gsr'],local_members['selected.gsr'],entry,accept],payload)
    need((native/'native-entry-5.gsr').read_bytes()==entry and (native/'native-payload-5.bin').read_bytes()==payload and
         (native/'after-close/node-1/pending.accept').read_bytes()==vote,'resource probe retained original unresolved ACCEPT')
    initial=c.inventory(native/'before-network/node-2');original=installed['node-2']
    cap=c.current(initial)[2]['capsule'];grants=c.journal(initial['grants.gsr'],cap['root'],'node-2')
    promise=(member/'source-promise.gsr').read_bytes();basis_raw=(member/'source-basis.gsr').read_bytes()
    need(any(k=='PROMISE' and raw==promise for k,raw,_ in grants) and any(k=='BASIS' and raw==basis_raw for k,raw,_ in grants),
         'resource probe original source grants')
    basis=f.decode(basis_raw,'records','BASIS');prefix='sources/'+basis['basisId']+'/'
    source={name[len(prefix):]:value for name,value in initial.items() if name.startswith(prefix)}
    need(len(source)==2 and 'source.gscp' in source and sum(k.endswith('.image') for k in source)==1,'resource probe complete receiving source')
    copies={label:None for label in ('source','learner')}
    copies.update({label+'/'+name:raw for label in ('source','learner') for name,raw in source.items()})
    p=len(source['source.gscp']);image=sum(len(v) for k,v in source.items() if k.endswith('.image'))
    events=history.d.read(native/'events.json');local=[row['event'] for row in events if row['node']=='node-2']
    need([(row['node'],row['event']) for row in events if row['event'] in
          ('ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','PUBLICATION_SELECTOR_FORCED')]==[('node-1','ACCEPT_PARENT_FORCED')],
         'resource probe unresolved ACCEPT without proven publication')
    need(not any(v in local for v in ('ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','PUBLICATION_SELECTOR_FORCED')),
         'resource probe no fabricated post-refusal vote')
    failures=history.d.read(native/'failures.json');errors=[row for row in failures if row.get('node')=='node-2']
    need(len(errors)==3 and all(row.get('kind')=='ACCEPT' for row in errors) and
         len({row.get('request') for row in errors})==1 and
         [row.get('failure') for row in errors]==['java.lang.IllegalArgumentException: resource ownership/count',
             'java.lang.IllegalArgumentException: grant journal closed or failed','java.lang.IllegalArgumentException: grant journal closed or failed'],
         'resource probe original capacity failure')
    # All offered floor copies must be real installed generations. Exactly one
    # complete copy exists; no floor authority or deletion is inferred from it.
    offered={};references=[]
    for node in ('node-1','node-2','node-3'):
        prefix,files,packet=c.current(installed[node]);manifest=installed[node][prefix+'generation.gsr'];identity=e.digest(manifest)
        offered[identity]=dict(files,**{'generation.gsr':manifest})
        references.append(dict(voter=node,generation=identity,catalog=packet['capsule']['catalog'],snapshot=packet['capsule']['application']))
    cut=c.current(original)[2]['capsule']['cut'];proposal=f.encode('records','FLOOR',dict(root=cap['root'],node='node-2',cut=cut,sources=references))
    first=sorted(offered,key=lambda key:(f.decode(offered[key]['generation.gsr'],'records','GENERATION')['node']=='node-2',key))[0]
    partial=dict(original,**{'floor-copies':None,'floor-copies/proposal.gsr':proposal,'floor-copies/'+first:None})
    partial.update({'floor-copies/'+first+'/'+name:raw for name,raw in offered[first].items()})
    need(c.inventory(native/'after-close/node-2')==partial,'resource probe exact partial floor and retained authority')
    expected_events=floor.transaction(offered,proposal,handoff=True)[0]
    stop=next(i for i,v in enumerate(expected_events) if v['event']=='FLOOR_COPY_HANDED_OFF')+1
    start=local.index('FLOOR_RESERVED');actual=[v for v in local[start:] if v.startswith('FLOOR_')]
    need(actual==[v['event'] for v in expected_events[:stop]],'resource probe exact partial floor force prefix')
    points=['before-hold','held','INSTALL_BEFORE_RETURN','FLOOR_COPY_HANDED_OFF','failed']
    rows=read(member/'resources.json')
    need(type(rows) is list and [row.get('point') for row in rows]==points,'resource probe complete failure observations')
    need({q.name for q in (member/'states').iterdir()}=={f'{i:03}' for i in range(5)},'resource probe exact capture inventory')
    for i,row in enumerate(rows):
        need(set(row)=={'id','point','eventIndex','usage'} and row['id']==f'{i:03}' and type(row['eventIndex']) is int,'resource probe observation identity')
        index=row['eventIndex'];point=row['point']
        if i in (2,3):need(0<=index<len(events) and events[index]==dict(node='node-2',event=point),'resource probe original callback index')
        else:need(index==-1,'resource probe boundary index')
        state=member/'states'/row['id'];need({q.name for q in state.iterdir()}=={'authority','scratch'},'resource probe state members')
        need(c.inventory(state/'authority')==(initial if i<2 else original if i==2 else partial),'resource probe captured authority')
        need(c.inventory(state/'scratch')==({} if i==0 else copies),'resource probe exact live receiving copies')
        value=row['usage'];need(type(value) is dict and set(value)=={'metadata','staging','queued','leases','counts'} and type(value['counts']) is dict and
             all(type(value[k]) is int and value[k]>=0 for k in ('metadata','staging','queued','leases')) and
             all(type(v) is int and v>0 for v in value['counts'].values()) and value['leases']==sum(value['counts'].values()),'resource probe typed resource observation')
    usage=rows[0]['usage'];expected=dict(usage,counts=dict(usage['counts']))
    for k,v in dict(SOURCE=1,LEARNER=1,APPLICATION=2,CONTROL=2).items():expected['counts'][k]=expected['counts'].get(k,0)+v
    expected.update(metadata=usage['metadata']+2*p,staging=usage['staging']+2*(p+image),queued=usage['queued']+len(promise)+len(basis_raw)+4096,leases=usage['leases']+6)
    same(rows[1]['usage'],expected,'resource probe exact pressure increment')
    physical=sum(k.endswith('.image') for k in partial)+sum(k.endswith('.image') for k in copies)
    at_limit=rows[3]['usage']
    need(physical==7 and at_limit['counts']['APPLICATION']==7 and at_limit['counts']['SOURCE']<6 and
         at_limit['metadata']<384*e.MIB-32*e.MIB and at_limit['staging']<512*e.MIB-64*e.MIB,
         'resource probe observed image count boundary')
    need(rows[4]['usage']['counts']['APPLICATION']==7,'resource probe failed image allocation stays charged')
    need(h.inventory(root)==before,'resource probe original changed')
    return dict(status='DIAGNOSED',nativeOutcome='FAIL',completedProfiles=0,failedProfile='4-REMOVE',
        admittedPrefixAndInstallation='PASS',originalAuthorityRetained=True,forcedFloorCopies=1,
        originalUnresolvedAcceptRetained=True,unresolvedEntrySha256=e.digest(entry),
        physicalImagesAtRefusal=7,nextImageWouldBe=8,observedSourceCountAtBoundary=at_limit['counts']['SOURCE'],
        externalReceivingCopies=2,automaticRuntimeReachabilityQualified=False,phase3Complete=False,
        cause='application image count exhausted during floor copy construction',originalPreserved=True)


NEGATIVES={
    'green-receipt':'resource probe original failure scope','wrong-case':'resource probe failed case scope',
    'source-grant':'resource probe original source grants','changed-floor':'resource probe exact partial floor and retained authority',
    'invented-floor-authority':'resource probe exact partial floor and retained authority','changed-owned-authority':'resource probe exact partial floor and retained authority',
    'lost-observation':'resource probe complete failure observations','wrong-callback-index':'resource probe original callback index',
    'lost-pressure-file':'resource probe exact live receiving copies','changed-pressure-accounting':'resource probe exact pressure increment',
    'wrong-image-count':'resource probe observed image count boundary','unrelated-error':'resource probe original capacity failure',
    'lost-local-accept':'resource probe retained original unresolved ACCEPT',
    'invented-proof':'resource probe unresolved ACCEPT without proven publication',
}


def mutate(root,name):
    member=root/'4-REMOVE'
    def save(path,value):path.write_text(json.dumps(value))
    if name=='green-receipt':
        path=root/'receipt.json';v=read(path);v['status']='PASS';save(path,v)
    elif name=='wrong-case':
        path=member/'result.json';v=read(path);v['profile']='5-REMOVE';save(path,v)
    elif name=='source-grant':(member/'source-basis.gsr').write_bytes(b'not original')
    elif name=='lost-local-accept':(member/'history/after-close/node-1/pending.accept').write_bytes(pending.EMPTY)
    elif name=='invented-proof':
        path=member/'history/events.json';v=history.d.read(path);v.append(dict(node='node-1',event='PROOF_PARENT_FORCED'));save(path,v)
    elif name in ('changed-floor','invented-floor-authority','changed-owned-authority'):
        path=member/'history/after-close/node-2'
        if name=='changed-floor':path=next((path/'floor-copies').rglob('*.image'))
        elif name=='invented-floor-authority':path=path/'floor-copies/floor.gsr'
        else:path=path/'allocator.gsr'
        path.write_bytes(b'changed')
    elif name=='lost-pressure-file':next((member/'states/003/scratch/learner').glob('*.image')).unlink()
    elif name=='unrelated-error':
        path=member/'history/failures.json';v=read(path);next(row for row in v if row['node']=='node-2')['failure']='unrelated';save(path,v)
    else:
        need(name in ('lost-observation','wrong-callback-index','changed-pressure-accounting','wrong-image-count'),'resource probe declared mutation')
        path=member/'resources.json';v=read(path)
        if name=='lost-observation':v.pop(3)
        elif name=='wrong-callback-index':v[3]['eventIndex']=0
        elif name=='changed-pressure-accounting':v[1]['usage']['staging']-=1
        else:v[3]['usage']['counts']['APPLICATION']-=1;v[3]['usage']['leases']-=1
        save(path,v)


def qualify(directory):
    root=Path(directory);before=h.inventory(root);original=diagnose(root);rows=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-resource-probe-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target);mutate(target,name)
            try:diagnose(target)
            except ValueError as error:need(str(error)==reason,'resource probe unrelated negative: '+name+': '+str(error))
            else:raise ValueError('resource probe accepted mutation: '+name)
            rows.append(dict(case=name,status='REJECTED',reason=reason))
    need(before==h.inventory(root),'resource probe original changed during negatives')
    return dict(diagnosis=original,negatives=rows,originalPreserved=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else diagnose(a.directory),sort_keys=True))
