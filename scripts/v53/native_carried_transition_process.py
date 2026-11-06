"""Original admitted prefix and process boundaries for carried context recovery.

This is a PARTIAL development component. It does not reduce every interrupted
storage mutation or replay the TCP protocol; neither native history admission
nor resource/frozen coverage acceptance follows from endpoint checks.
"""
import argparse
import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from . import carried_transition_evidence as t
from . import native_carried_process_evidence as process
from . import joining_history_run as collection

c,e,f,need=t.c,t.e,t.f,t.need
NODES=tuple('node-'+str(i) for i in range(1,5))
CUTS=('ACCEPT_RENAMED','PROOF_RENAMED')
read=process.read;exact=process.exact


def layout(root,kind):
    index,campaigns,_=t.shape(kind)
    names={'initial','original-plan.gsbp','original-application.image','before-network','at-cut','before-reopen','after-close',
           'calls.json','events.json','wire.json','ready.gsr','process','life-1-opened','life-2-opened','life-2-ready',
           'life-1-installed-1','life-1-installed-1.gsr'}
    names|={'round-1-'+stage for stage in ('prepared','selected','installed','settled')}
    names|={f'slot-{slot}-{stage}' for slot in range(1,index) for stage in ('accepted','proved','certified','applied','published','settled')}
    names|={f'{name}-{slot}.{suffix}' for slot in range(1,index+1) for name,suffix in (('entry','gsr'),('payload','bin'))}
    names.add(f'slot-{index}-accepted')
    if kind=='FINAL':names|={'campaign-3-'+stage for stage in ('prepared','selected','installed','settled')}
    names|={f'life-2-installed-{ordinal}'+suffix for ordinal in range(1,campaigns+1) for suffix in ('','.gsr')}
    names|={f'life-2-{stage}-{slot}' for slot in range(index,8) for stage in ('applied','published')}
    t.b.selection.layout(root,names,'transition process original')
    t.b.selection.layout(root/'process',{'spec.json','result.json'}|{f'life-{i}.{ext}' for i in (1,2) for ext in ('jsonl','stderr')},
                         'transition process children')


def configuration(root,kind):
    plan=t.b.t.plans.decode((root/'original-plan.gsbp').read_bytes(),
                           (root/'original-application.image').read_bytes(),details=True,size=4)
    paths=[v['path'] for v in plan['plan']['descriptor']['paths']]
    spec=read(root/'process/spec.json')
    need(type(spec) is dict and set(spec)=={'nodes','kind'} and spec['kind']==kind and
         type(spec['nodes']) is list and len(spec['nodes'])==4,'transition process original specification')
    scratch=[]
    for i,row in enumerate(spec['nodes']):
        need(type(row) is dict and set(row)=={'replica','application','scratch'} and
             row['replica']==paths[1+2*i] and row['application']==paths[2+2*i] and type(row['scratch']) is str,
             'transition process original paths')
        path=PurePosixPath(row['scratch'])
        need(path.is_absolute() and '..' not in path.parts and str(path)==row['scratch'] and
             all(not path.is_relative_to(v) and not PurePosixPath(v).is_relative_to(path) for v in paths+scratch),
             'transition process disjoint scratch')
        scratch.append(row['scratch'])


def observations(root,result,children):
    events=[];wire=[];lives=[];snapshots=[];counts=[];installations=[];ready=None
    for life,child in enumerate(children,1):
        need((root/f'process/life-{life}.stderr').read_bytes()==b'','transition process child stderr')
        messages=process.process.transcript(root/f'process/life-{life}.jsonl')
        exact(messages[0],dict(action='started',value=child['started']),'transition process start')
        terminal=dict(action='cut',value=dict(name=result['cut'],mode=result['mode'],pid=child['pid'])) if life==1 else dict(action='closed',value=child['closed'])
        exact(messages[-1],terminal,'transition process terminal')
        local=[];opened=False;installed=[];named=[];readies=0
        for message in messages[1:-1]:
            action,value=message['action'],message['value']
            if action=='event':
                unnumbered=type(value) is dict and value.get('event') in ('FUTURE_QUORUM_COMPLETE','PUBLICATION_SEND_BOUNDARY')
                need(type(value) is dict and value.get('node') in NODES and type(value.get('event')) is str and
                     (unnumbered and 'incarnation' not in value or not unnumbered and type(value.get('incarnation')) is int and value['incarnation']==life),
                     'transition process event incarnation')
                local.append(value)
            elif action=='response':
                need(type(value) is dict and set(value)=={'event','wire'} and type(value['wire']) is dict and
                     set(value['wire'])=={'request','response','withheld'} and value['wire']['withheld'] is False,
                     'transition process response shape')
                request,response=[base64.b64decode(value['wire'][k],validate=True) for k in ('request','response')]
                row=value['event'];need(type(row) is dict and row.get('node') in NODES,'transition process response owner')
                exact(row,dict(node=row['node'],incarnation=life,event='WIRE_RESPONSE',request=e.digest(request),response=e.digest(response)),
                      'transition process response digest')
                local.append(row);wire.append(value['wire'])
            elif action=='opened':
                exact(value,life,'transition process opened life')
                opens=[v for v in local if v['event']=='NODE_OPEN']
                need(not opened and [v['node'] for v in opens]==list(NODES) and local[-1]==opens[-1] and
                     not any(v['event'].startswith(('ROUND_','NETWORK_')) for v in local),'transition process complete group opens')
                for v in opens:
                    need(set(v)=={'node','incarnation','event','counts'} and type(v['counts']) is dict and
                         all(type(n) is int and n>=0 for n in v['counts'].values()),'transition process resource counts')
                opened=True;named.append(f'life-{life}-opened')
            elif action=='installed':
                ordinal=len(installed)+1;name=f'life-{life}-installed-{ordinal}'
                raw=(root/(name+'.gsr')).read_bytes()
                exact(value,dict(life=life,number=ordinal,bytes=base64.b64encode(raw).decode()),'transition process installed record')
                need(local[-1].get('event')=='ROUND_INSTALLED' and local[-1].get('bytes')==value['bytes'],
                     'transition process original installation observation')
                installed.append(raw);named.append(name)
            elif action=='snapshot':
                need(type(value) is str and value.startswith(f'life-{life}-') and '/' not in value,
                     'transition process snapshot name');named.append(value)
            elif action=='ready':
                need(life==2,'transition process no interrupted readiness')
                need(readies==0 and named and named[-1]=='life-2-ready' and local and
                     local[-1]['event']=='ROUND_BEFORE_READY','transition process readiness after final observation')
                ready=base64.b64decode(value,validate=True);readies+=1
                need(ready==(root/'ready.gsr').read_bytes(),'transition process original readiness')
            else:raise ValueError('transition process unsupported observation')
        need(opened and readies==life-1 and len(named)==len(set(named)), 'transition process exact lifetime observations')
        need([v['node'] for v in local if v['event']=='NODE_OPEN']==list(NODES),'transition process unique owner opens')
        if life==1:
            need(local[-1]==dict(node='node-1',incarnation=1,event=result['cut']), 'transition process observed crash cut')
        counts.append(len(messages));lives.append(local);snapshots+=named;installations.append(installed);events+=local
        if life==1:events.append(dict(event='GROUP_CRASH',incarnation=1))
    exact(read(root/'events.json'),events,'transition process merged events')
    exact(read(root/'wire.json'),wire,'transition process merged responses')
    return lives,snapshots,installations,ready,counts


def rounds(root,kind,lives,installations,ready):
    index,campaigns,_=t.shape(kind);entry=(root/f'entry-{index}.gsr').read_bytes()
    for life,events in enumerate(lives,1):
        expected=['INSTALLED','SLOT_BEGIN'] if life==1 else ['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE']*campaigns+['BEFORE_READY']
        rows=[v for v in events if v['event'].startswith('ROUND_')]
        need([v['event'] for v in rows]==['ROUND_'+n for n in expected],'transition process exact round lifecycle')
        selections=iter(installations[life-1]);slot=index;selected=None;last_ack=None;active_entry=None
        for row in rows:
            need(set(row)=={'node','incarnation','event','record','bytes'} and row['node']=='node-1','transition process round owner')
            raw=base64.b64decode(row['bytes'],validate=True)
            need(e.digest(raw)==row['record'],'transition process round digest')
            if row['event']=='ROUND_INSTALLED':
                need(raw==next(selections,None),'transition process exact selected record');selected=f.decode(raw,'records','SELECTED')
                need(selected['nextEntry']==(e.digest(entry) if slot==index else None),'transition process selected carried entry')
            elif row['event']=='ROUND_SLOT_BEGIN':
                value=f.decode(raw,'records','ENTRY')
                need(value['index']==slot and value['kind']==({5:'INTENT',6:'FINAL',7:'BARRIER'}[slot]) and
                     value['authority']==selected['view'] and value['root']==selected['root'] and
                     value['previous']==selected['cut']['entry'] and selected['cut']['index']==slot-1,
                     'transition process original command sequence')
                need((raw==entry and value['origin']!=selected['ballot']) if slot==index else value['origin']==selected['ballot'],
                     'transition process unchanged carried origin')
                active_entry=raw
            elif row['event']=='ROUND_SLOT_COMPLETE':
                ack=f.decode(raw,'wire','PUBLISH_ACK')
                files=c.inventory(root/f'life-2-published-{slot}/node-1');_,members,packet=c.current(files)
                applied=c.inventory(root/f'life-2-applied-{slot}/node-1');identity=f.decode(files['node.gsr'],'records','NODE')['identity']
                need(ack['sender']==ack['recipient']==identity and ack['sequence']==1 and
                     ack['root']==selected['root'] and ack['view']==selected['view'] and ack['ballot']==selected['ballot'],
                     'transition process completion identity')
                exact(ack['payload'],dict(certificate=e.digest(applied['applied-end/certificate.gsr']),selection=e.digest(members['selected.gsr']),
                    published=c.anchor(packet['capsule']),generation=e.digest(files['generations/'+f.decode(files['selector.gsr'],'records','SELECTOR')['generation']+'/generation.gsr'])),
                    'transition process completion inventory')
                need(e.digest(active_entry)==packet['capsule']['cut']['entry'],'transition process published observed entry')
                last_ack=raw;slot+=1
            else:need(raw==last_ack==ready and slot==8,'transition process fresh readiness')
        need(next(selections,None) is None,'transition process unused installation')


def validate(directory):
    return _validate(directory,CUTS)


def validate_application(directory):
    return _validate(directory,('APPLY_ACK_DIRECTORY_FORCED',))


def _validate(directory,cuts):
    root=Path(directory);process.selection.inventory(root);result=read(root/'process/result.json')
    kind=result.get('carriedKind');need(kind in t.KINDS and result.get('cut') in cuts,'transition process explicit case')
    layout(root,kind)
    # Reduce actual bootstrap, all original admitted publications and old ACCEPT
    # before considering the producer's process-success receipt.
    walk,entry,payload=t.prelude(root,kind)
    configuration(root,kind);children=process.children(result,kind=kind)
    lives,snapshots,installations,ready,counts=observations(root,result,children)
    index,campaigns,_=t.shape(kind)
    expected=['life-1-opened','life-1-installed-1','life-2-opened']
    for ordinal,slot in enumerate(range(index,8),1):
        expected += [f'life-2-installed-{ordinal}',f'life-2-applied-{slot}',f'life-2-published-{slot}']
    expected+=['life-2-ready'];need(snapshots==expected,'transition process exact snapshots')
    need(collection.inventory(root/'at-cut')==collection.inventory(root/'before-reopen'),
         'transition process unchanged dead directories')
    # These checks bind bytes to the observed crash boundary; full physical
    # reduction of all voters' interrupted work remains a distinct requirement.
    cut=c.inventory(root/'at-cut/node-1')
    phases=() if result['cut']=='ACCEPT_RENAMED' else ('PROOF','CERTIFICATE') if result['cut']=='APPLY_ACK_DIRECTORY_FORCED' else ('PROOF',)
    frames,values=c.pending(cut['pending.accept'],phases)
    need(frames['ENTRY']==entry and frames['PAYLOAD']==payload,'transition process original interrupted command')
    selected=f.decode(installations[0][0],'records','SELECTED')
    need(values['ACCEPT']['ballot']==selected['ballot'] and values['ACCEPT']['entry']==e.digest(entry),
         'transition process interrupted selected ballot')
    rounds(root,kind,lives,installations,ready)
    _,members,packet=c.current(c.inventory(root/'after-close/node-1'));cap=packet['capsule']
    catalog=f.decode(packet['objects'][cap['catalog']],'records','CATALOG')
    need(cap['root']==f.decode(entry,'records','ENTRY')['root'] and cap['cut']['index']==7 and
         cap['cut']['view']['old']==cap['cut']['view']['new']==list(NODES[:3]) and cap['cut']['view']['operation'] is None and
         catalog['active'] is None and catalog['applicationSequence']==0 and catalog['results'][-1]['phase']=='COMPLETED',
         'transition process observed final inventory')
    need(members[cap['application']+'.image']==(root/'original-application.image').read_bytes(),
         'transition process unchanged application image')
    return dict(status='PARTIAL',componentChecks='PASS',scope='admitted-transition-prefix-and-process-observations',kind=kind,
        cut=result['cut'],mode=result['mode'],originalPrefixReplayed=True,processObservations=True,freshGroupJvms=2,
        survivingOriginalOwners=0,clientCalls=0,childMessages=counts,completePhysicalReplay=False,fullWireReplay=False,
        processHistoryQualified=False,cohortAdmitted=False,phase3Complete=False,powerLoss=False)


NEGATIVES={
    'extra-file':'context selection transition process original inventory',
    'changed-command':'carried transition original command',
    'reused-process':'native carried fresh child identities',
    'missing-lock':'native carried exact death and close',
    'normal-exit':'native carried exact death and close',
    'invented-completion':'native carried producer scope',
    'wrong-kind':'transition process original specification',
    'changed-dead-directory':'transition process unchanged dead directories',
    'changed-ready':'transition process original readiness',
    'missing-group-death':'transition process merged events',
    'changed-response':'transition process response digest',
    'unobserved-crash':'transition process observed crash cut',
    'interrupted-readiness':'transition process no interrupted readiness',
    'early-readiness':'transition process readiness after final observation',
}


def mutate(root,name):
    root=Path(root);result=read(root/'process/result.json');index=t.shape(result['carriedKind'])[0]
    def save(path,value):path.write_bytes(f.canonical(value))
    if name=='extra-file':(root/'unexpected').write_bytes(b'originals are closed')
    elif name=='changed-command':(root/f'payload-{index}.bin').write_bytes(b'{}')
    elif name in ('reused-process','missing-lock','normal-exit','invented-completion'):
        if name=='reused-process':result['children'][1]['pid']=result['children'][0]['pid']
        elif name=='missing-lock':result['children'][0]['allLocksHeldBeforeDeath']=False
        elif name=='normal-exit':result['children'][0]['exit']=0
        else:result['phase3Complete']=True
        save(root/'process/result.json',result)
    elif name=='wrong-kind':
        spec=read(root/'process/spec.json');spec['kind']='DATA';save(root/'process/spec.json',spec)
    elif name=='changed-dead-directory':(root/'before-reopen/node-1/unobserved').write_bytes(b'changed after death')
    elif name=='changed-ready':(root/'ready.gsr').write_bytes(b'stale')
    elif name=='missing-group-death':save(root/'events.json',[v for v in read(root/'events.json') if v['event']!='GROUP_CRASH'])
    elif name=='early-readiness':
        path=root/'process/life-2.jsonl';rows=process.process.transcript(path)
        ready=next(v for v in rows if v['action']=='ready');rows.remove(ready)
        at=next(i for i,v in enumerate(rows) if v['action']=='snapshot' and v['value']=='life-2-ready')
        rows.insert(at,ready);process.write_messages(path,rows)
    elif name in ('changed-response','unobserved-crash','interrupted-readiness'):
        path=root/'process/life-1.jsonl';rows=process.process.transcript(path)
        if name=='changed-response':next(v for v in rows if v['action']=='response')['value']['event']['response']='0'*64
        elif name=='unobserved-crash':
            row=next(v for v in reversed(rows[:-1]) if v['action']=='event');row['value']['event']='NOT_THE_CRASH_BOUNDARY'
        else:rows.insert(-1,dict(action='ready',value=base64.b64encode((root/'ready.gsr').read_bytes()).decode()))
        process.write_messages(path,rows)
    else:raise ValueError('unknown transition process mutation')


def qualify(root):
    root=Path(root);before=collection.inventory(root);original=validate(root);results=[]
    with tempfile.TemporaryDirectory(prefix='v53-transition-process-') as work:
        for name,reason in NEGATIVES.items():
            copy=Path(work)/name;shutil.copytree(root,copy);mutate(copy,name)
            try:validate(copy)
            except ValueError as error:need(str(error)==reason,'transition process wrong negative '+name+': '+str(error))
            else:raise ValueError('transition process accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason));shutil.rmtree(copy)
    need(collection.inventory(root)==before,'transition process original changed during negatives')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('original');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.original) if args.qualify else validate(args.original),sort_keys=True))
