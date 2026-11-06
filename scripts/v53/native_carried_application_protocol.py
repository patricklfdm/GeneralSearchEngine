"""Original callbacks and TCP replies around carried INTENT/FINAL application death.

Require independent physical reconstruction first. Complete callbacks do not
claim transient byte capture, export lifetime, or final-source qualification.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_application_evidence as application
from . import native_carried_transition_forces as forces
from . import native_carried_transition_network as network
from . import native_retirement_evidence as retirement

p=application.p;c,d,e,f,need=p.c,p.d,p.e,p.f,p.need
RETIREMENT=('STAGED_','SUPERSEDED_','NATIVE_RETIREMENT_')
TRACKED=forces.TRACKED+RETIREMENT
def cold(rows,before,**kwargs):
    for node in before:
        end=next(i for i,v in enumerate(rows) if v.get('node')==node and v['event']=='NODE_OPEN')
        no_retirement([v for v in rows[:end] if v.get('node')==node])
    return forces.cold(rows,before,**kwargs)


def maintenance(group,node,**kwargs):
    if 'applied-end' in group[node]:return [],dict(generations=0,sources=0,borrowed=0)
    return forces.maintenance(group,node,pin_current=pin_current(group,node),**kwargs)


def pin_current(group,node):
    files=group[node];prefix,members,_=c.current(files)
    inactive=any(k.startswith('generations/') and k!=prefix[:-1] and not k.startswith(prefix) for k in files)
    sources={k.split('/')[1] for k in files if k.startswith('sources/') and k.endswith('/source.gscp')}
    voters=p.floors.floor_voters(group,node) if p.needs_maintenance(files) else ()
    return inactive and 'selected.gsr' in members and 2+len(voters)+len(sources)>7


def no_retirement(rows):
    need(not any(v['event'].startswith(RETIREMENT) for v in rows),'application protocol unexpected retirement')


def campaign(rows,before,installed,**kwargs):
    no_retirement(rows)
    return forces.campaign(rows,before,installed,maintainer=maintenance,**kwargs)


def replay_order(events,initial,applied):
    expected=[point for _,point,_ in forces.replay_files.transaction(initial,applied)]
    forces.exact(events,('REPLAY_',),expected,'application protocol exact control replay')


def retired(rows,before):
    """Only a completely validated owner prefix can be removed from fresh-slot replay."""
    result=copy.deepcopy(before);consumed=set()
    for node,files in before.items():
        if 'applied-end' not in files:continue
        owned=[(i,v) for i,v in enumerate(rows) if v.get('node')==node]
        end=next((i for i,v in owned if v['event']=='STAGED_RETIREMENT_BEFORE_RETURN'),None)
        need(end is not None,'application protocol missing retirement completion')
        # Socket observations may interleave with synchronous storage work.
        # Validate/remove only this owner's storage callbacks; transport keeps
        # every original observation and its unchanged global index.
        storage=[(i,v) for i,v in owned if i<=end and v['event'].startswith(TRACKED)]
        prefix=[v['event'] for _,v in storage]
        frames,_=p.data.pending(files)
        result[node]=application.retire(files,frames['ENTRY'],frames['PAYLOAD'])
        final,cleanup=retirement.staging.cleanup(files,retirement.authority(files))
        need(final==result[node],'application protocol exact retirement projection')
        replay=[point for _,point,_ in forces.replay_files.retirement(files)]
        expected=['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED',
                  'NATIVE_RETIREMENT_CERTIFICATE_RETAINED',cleanup[0],*replay,*cleanup[1:]]
        retirement.order(prefix,cleanup,True)
        need(prefix==expected,'application protocol exact retirement before new vote')
        consumed.update(i for i,_ in storage)
    remaining=[v for i,v in enumerate(rows) if i not in consumed]
    no_retirement(remaining)
    return remaining,result


def interrupted(rows,before,after):
    no_retirement(rows)
    selected=f.decode(c.current(before['node-1'])[1]['selected.gsr'],'records','SELECTED')
    voters=[v['voter'] for v in selected['sources']];accepting=copy.deepcopy(before);stats=[]
    frames,_=p.data.pending(after['node-1'])
    for node in voters:accepting[node]['pending.accept']=p.vote(before[node],frames['ENTRY'],frames['PAYLOAD'])
    for node in before:
        events=forces.names(rows,node)
        forces.exact(events,forces.GRANTS,[],'application protocol interrupted campaign overlap')
        expected,detail=maintenance(accepting,node) if node in voters else ([],{})
        forces.maintenance_order(rows,node,expected);stats.append(detail)
        forces.ledger_order(rows,node,before[node][d.s.FILE],after[node][d.s.FILE])
        if node not in voters:
            forces.exact(events,TRACKED,[],'application protocol untouched interrupted owner');continue
        forces.vote_order(events,'ACCEPT',ack=node!='node-1');forces.vote_order(events,'PROOF',ack=node!='node-1')
        critical=['ACCEPT_PARENT_FORCED']
        if expected:critical+=['FLOOR_BEFORE_RETURN','FLOOR_RELEASE_BEFORE_RETURN']
        critical+=['PROOF_VALIDATED','PROOF_PARENT_FORCED']
        forces.native.ordered(events,critical,'application protocol interrupted durable votes')
        forces.exact(events,('INSTALL_','PUBLICATION_','COVERED_','FUTURE_RETENTION_',
                           'APPLICATION_ACK_BEFORE_RETURN'),[],'application protocol crash cannot publish or ACK')
        if node!='node-1':
            forces.exact(events,('CERTIFICATE_','APPLY_','REPLAY_','NATIVE_CERTIFICATE_RETAINED',
                               'APPLICATION_AUTHORITY_VALIDATED'),[],'application protocol peer application not dispatched');continue
        forces.vote_order(events,'CERTIFICATE')
        forces.exact(events,('CERTIFICATE_ACTIVE_',),['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED'],
                     'application protocol interrupted certificate force')
        end={k.removeprefix('applied-end/'):v for k,v in after[node].items() if k.startswith('applied-end/')}
        _,_,writes=forces.applied.simulate(end,{},False,stop=application.CUT)
        forces.exact(events,('APPLY_',),[v['event'] for v in writes],'application protocol exact interrupted end')
        forces.exact(events,('NATIVE_CERTIFICATE_RETAINED','APPLICATION_AUTHORITY_VALIDATED'),
                     ['NATIVE_CERTIFICATE_RETAINED','APPLICATION_AUTHORITY_VALIDATED'],'application protocol interrupted native authority')
        initial=retirement.staging.without_staging(after[node]);replay_order(events,initial,after[node])
        forces.native.ordered(events,['PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_ACTIVE_FORCED',
            'CERTIFICATE_ACTIVE_PARENT_FORCED','NATIVE_CERTIFICATE_RETAINED','APPLICATION_AUTHORITY_VALIDATED',
            'REPLAY_RESERVED','REPLAY_BEFORE_RETURN','APPLY_VALIDATED',application.CUT],
            'application protocol interrupted application order')
    return stats


def slot(rows,before,applied_group,published,*,first,point=None,**collectors):
    # These adapters qualify callback order only. Transient collectors must not
    # accidentally acquire apparent coverage through the application adapter.
    need(all(v is None for v in collectors.values()),'application protocol transient collectors unsupported')
    if point is not None:
        need(point==application.CUT and first,'application protocol exact interrupted cut')
        return interrupted(rows,before,published)
    rows,before=retired(rows,before)
    stats=forces.slot(rows,before,applied_group,published,first=first,maintainer=maintenance)
    selected=f.decode(c.current(before['node-1'])[1]['selected.gsr'],'records','SELECTED')
    for source in selected['sources']:
        node=source['voter'];files=applied_group[node]
        replay_order(forces.names(rows,node),retirement.staging.without_staging(files),files)
    return stats


def interrupted_network(root,history,events,rows):
    stage=next(v for v in history.ranges if v['kind']=='interrupted')
    before=forces.group(root,stage['before']);selected=f.decode(c.current(before['node-1'])[1]['selected.gsr'],'records','SELECTED')
    frames,_=p.data.pending(c.inventory(root/'at-cut/node-1'))
    need(p.process.read(root/'process/result.json')['cut']==application.CUT,'application protocol original network cut')
    own=[v for v in rows if stage['start']<v['offered']<stage['stop'] and
         v['kind'] not in ('CHUNK','TRANSFER_COMMIT','STATUS_PROBE','HEARTBEAT')]
    used=set()
    for phase,key,boundary in (('ACCEPT','acceptance','PROOF_VALIDATED'),('PROOF','proof','CERTIFICATE_VALIDATED')):
        stops=[i for i,v in enumerate(events) if stage['start']<i<stage['stop'] and v==dict(node='node-1',event=boundary)]
        need(len(stops)==1,'application protocol original interrupted local boundary');stop=stops[0]
        for source in selected['sources']:
            node=source['voter']
            if node=='node-1':continue
            forced=[i for i,v in enumerate(events) if stage['start']<i<stop and v==dict(node=node,event=phase+'_BEFORE_RETURN')]
            need(len(forced)==1,'application protocol original interrupted '+phase)
            receipt=f.canonical(dict(root=selected['root'],voter=node,incarnation=d.future.identity(before[node])['storage'],
                                    phase=phase,record=e.digest(frames[phase])))
            held=network.network.phase.control(own,phase,node,{key:e.digest(frames[phase])},
                dict(entry=e.digest(frames['ENTRY']),receipt=e.digest(receipt)),selected,forced[0],stop)
            used.update(v['offered'] for v in held)
    need(used=={v['offered'] for v in own},'application protocol unbound interrupted control')
    return len(used)


def replay(root,kind):
    callbacks=forces.replay(root,kind,application.CUT,handlers=sys.modules[__name__])
    wire=network.replay(root,kind,interrupted_replay=interrupted_network,slot_projection=slot_projection)
    return dict(callbacks=callbacks,network=wire,status='PARTIAL',phase3Complete=False)


def slot_projection(root,history,events):
    result=list(events)
    for stage in history.ranges:
        if stage['kind']!='slot':continue
        before=forces.group(root,stage['before']);stop=stage['stop']
        starts=[at for at in range(stage['start']+1,stop) if events[at]['event']=='ROUND_SLOT_BEGIN']
        need(len(starts)==1,'application protocol original slot start');start=starts[0]+1
        remaining,_=retired(events[start:stop],before);retained={id(v) for v in remaining}
        for at in range(start,stop):
            if id(events[at]) not in retained:result[at]=dict(event='VALIDATED_OLD_APPLICATION_RETIREMENT')
    return result


def validate(root):
    root=Path(root);before=p.process.collection.inventory(root);original=application.validate(root)
    result=replay(root,original['physical']['kind'])
    need(p.process.collection.inventory(root)==before,'application protocol original changed')
    return dict(original=original,protocol=result,status='PARTIAL',phase3Complete=False)


OMISSIONS={
    'retired-certificate-force':(2,'CERTIFICATE_ACTIVE_FORCED','native retirement original certificate force'),
    'retired-authority-force':(2,'SUPERSEDED_END_AUTHORITY_FORCED','native retirement exact force/delete order'),
    'retired-replay-force':(2,'REPLAY_CLAIM_FORCED','application protocol exact retirement before new vote'),
    'pin-original-force':(2,'FLOOR_LOCAL_ORIGINAL_FORCED','transition forces exact maintenance callbacks'),
    'pin-selector-force':(2,'FLOOR_LOCAL_SELECTOR_FORCED','transition forces exact maintenance callbacks'),
    'pin-release':(2,'FLOOR_RELEASE_LOCAL_CLEARED','transition forces exact maintenance callbacks'),
    'interrupted-certificate-force':(1,'CERTIFICATE_ACTIVE_FORCED','application protocol interrupted certificate force'),
    'interrupted-ack-force':(1,'APPLY_ACK_FORCED','application protocol exact interrupted end'),
}
NEGATIVES={name:reason for name,(_,_,reason) in OMISSIONS.items()}
NEGATIVES.update({
    'retired-early-vote':'application protocol exact retirement before new vote',
    'retired-duplicate-delete':'native retirement exact force/delete order',
    'retired-old-ack':'covered staging emitted old ACK',
    'interrupted-duplicate-replay':'application protocol exact control replay',
    'network-proof-receipt':'joining original phase ACK',
})
NEGATIVES.update({key:forces.NEGATIVES[key] for key in ('cold-force','accept-force','proof-force',
    'certificate-force','early-accept-ack','future-force','covered-vote-force','callback-extra-field')})
NEGATIVES.update(network.NEGATIVES)


def mutate(root,name):
    if name.startswith('network-'):return network.mutation.mutate(root,name)
    if name in forces.NEGATIVES:return forces.mutate(root,name)
    def edit(lives):
        life=OMISSIONS[name][0] if name in OMISSIONS else 1 if name.startswith('interrupted-') else 2
        rows=lives[life-1]
        start=next(i for i,v in enumerate(rows) if v['action']=='event' and v['value']['event']=='ROUND_SLOT_BEGIN')
        def at(point):return next(i for i,v in enumerate(rows) if i>start and v['action']=='event' and
                                 v['value']['node']=='node-1' and v['value']['event']==point)
        if name in OMISSIONS:rows.pop(at(OMISSIONS[name][1]))
        elif name=='retired-early-vote':
            row=rows.pop(at('ACCEPT_VALIDATED'));rows.insert(at('STAGED_RETIREMENT_BEFORE_RETURN'),row)
        elif name in ('retired-duplicate-delete','interrupted-duplicate-replay'):
            index=at('SUPERSEDED_END_FILE_DELETED' if life==2 else 'REPLAY_CLAIM_FORCED')
            rows.insert(index,copy.deepcopy(rows[index]))
        elif name=='retired-old-ack':
            rows.insert(at('STAGED_RETIREMENT_BEFORE_RETURN'),dict(action='event',value=dict(
                node='node-1',incarnation=2,event='APPLY_ACK_DIRECTORY_FORCED')))
        else:raise ValueError('unknown application protocol mutation')
    forces.native.rewrite_lives(Path(root),edit)


def qualify(root):
    root=Path(root);before=p.process.collection.inventory(root);original=validate(root);results=[]
    observations={'events.json','wire.json','process/life-1.jsonl','process/life-2.jsonl'}
    protected=lambda inventory:{k:v for k,v in inventory['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-application-protocol-') as temp:
        for name,reason in NEGATIVES.items():
            changed=Path(temp)/name;shutil.copytree(root,changed);mutate(changed,name)
            after=p.process.collection.inventory(changed)
            need(protected(before)==protected(after) and before['directories']==after['directories'],
                 'application protocol negative changed original storage')
            # Storage and producer identities are byte-identical to the already
            # replayed original. Recheck all observation bindings and protocols;
            # never rerun an expensive producer to manufacture negative credit.
            try:
                p.process.validate_application(changed)
                replay(changed,original['original']['physical']['kind'])
            except ValueError as error:need(str(error)==reason,'application protocol wrong negative '+name+': '+str(error))
            else:raise ValueError('application protocol accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason));shutil.rmtree(changed)
            print(json.dumps(dict(stage='application-protocol-negative',completed=len(results),total=len(NEGATIVES),case=name)),file=sys.stderr,flush=True)
    need(p.process.collection.inventory(root)==before,'application protocol qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))


if __name__=='__main__':main()
