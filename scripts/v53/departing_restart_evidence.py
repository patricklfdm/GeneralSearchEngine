"""Independent replay of fresh-process reopen after a completed native FINAL.

The original live network history must validate first. Reopen uses fresh JVMs
with repeated halt/SIGKILL at completed ACK delivery, then a final resume.
This does not qualify interrupted FINAL installation or restarted TCP delivery.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
from . import departing_publication_evidence as native

c,d,e,f,need=native.c,native.d,native.e,native.f,native.need


def layout(root):
    need(root.is_dir() and not root.is_symlink(),'departing restart regular inventory')
    total=0
    for count,path in enumerate(root.rglob('*'),1):
        need(not path.is_symlink() and (path.is_file() or path.is_dir()),'departing restart regular inventory')
        if path.is_file():total+=path.stat().st_size
        need(count<=65536 and total<=512*e.MIB,'departing restart bounded inventory')
    expected={'profile.txt','native-history.txt','history','publication-request.gsrp','publication-ack.gsrp',
              'fresh-prepare.gsrp','duplicate-1.gsrp','duplicate-2.gsrp','duplicate-3.gsrp','process.json','restart-result.json',
              'worker.stdout','worker.stderr','reopened','interruptions'}
    native.b.selection.layout(root,expected,'departing restart')


def interruptions(root,before,parent,worker):
    path=root/'interruptions'
    native.b.selection.layout(path,{f'{mode}-{n}' for mode in ('halt','kill') for n in (1,2)},'departing interruptions')
    pids={parent,worker}
    for mode in ('halt','kill'):
        for n in (1,2):
            child=path/f'{mode}-{n}'
            native.b.selection.layout(child,{'process.json','store','worker.stdout','worker.stderr'},'departing interrupted child')
            need(c.inventory(child/'store')==before,'departing interrupted original store')
            record=d.read(child/'process.json')
            need(type(record.get('workerPid')) is int and record['workerPid']>0 and record['workerPid'] not in pids
                 and type(record.get('exit')) is int and type(record.get('attempt')) is int
                 and type(record.get('liveLockRefused')) is bool and
                 record==dict(parentPid=parent,workerPid=record['workerPid'],exit=23 if mode=='halt' else 137,
                              mode=mode,attempt=n,liveLockRefused=(mode=='kill')),
                 'departing interrupted process outcome')
            pids.add(record['workerPid'])
            need((child/'worker.stdout').read_text()=='CUT PUBLICATION_ACK_BEFORE_RETURN\n'
                 and (child/'worker.stderr').read_bytes()==b'','departing interrupted acknowledgement boundary')


def validate(root):
    root=Path(root);layout(root);history=root/'history'
    original=native.validate(history)
    profile=(root/'profile.txt').read_text()
    need(profile in ('proposer\n','follower\n') and original['profile']=='removed-'+profile.strip(),'departing restart original profile')
    profile=profile.strip()
    before=c.inventory(history/'after-close/node-4');after=c.inventory(root/'reopened')
    need(before==after,'departing restart unchanged original store')
    prefix,_,packet=c.current(before);view=packet['capsule']['cut']['view']
    need(packet['capsule']['cut']['index']==6 and 'node-4' not in set(view['old'])|set(view['new']),
         'departing restart completed removed view')
    request=(root/'publication-request.gsrp').read_bytes();reply=(root/'publication-ack.gsrp').read_bytes()
    requested=f.decode(request,'wire','PUBLISH');answered=f.decode(reply,'wire','PUBLISH_ACK')
    if profile=='follower':
        matches=[row for row in d.read(history/'wire.json') if base64.b64decode(row['request'],validate=True)==request
                 and base64.b64decode(row['response'],validate=True)==reply and not row['withheld']]
        need(matches,'departing restart original network request')
        origin='original-tcp-request'
    else:
        rows=[row for row in d.read(history/'events.json') if row['event']=='ROUND_SLOT_COMPLETE']
        need(len(rows)==1 and base64.b64decode(rows[0]['bytes'],validate=True)==reply,'departing restart original local completion')
        expected=dict(answered,sender=answered['recipient'],recipient=answered['sender'],
                      payload=dict(certificate=answered['payload']['certificate']))
        need(requested==expected,'departing restart exact local envelope');origin='original-local-reply-envelope'
    need(requested['recipient']==d.future.identity(before),'departing restart permanent recipient')
    for index in (1,2,3):
        need((root/f'duplicate-{index}.gsrp').read_bytes()==reply,'departing restart unchanged acknowledgement')

    prepare=f.decode((root/'fresh-prepare.gsrp').read_bytes(),'wire','PREPARE')
    peer=d.future.identity(c.inventory(history/'after-close/node-1'));selected=f.decode(before[prefix+'selected.gsr'],'records','SELECTED')
    ballot=dict(selected['ballot'],counter=selected['ballot']['counter']+1,proposer=peer['node'],incarnation=peer['storage'])
    expected=dict(requested,sender=peer,recipient=d.future.identity(before),view=e.digest(f.canonical(dict(view,root=requested['root']))),
                  ballot=ballot,payload=dict(promise=e.digest(before[prefix+'promise.gsr'])))
    need(prepare==expected,'departing restart exact new-view prepare')
    process=d.read(root/'process.json')
    need(set(process)=={'parentPid','workerPid','exit','profile','publicationRequestOrigin'} and
         type(process['parentPid']) is int and type(process['workerPid']) is int and
         process['parentPid']>0 and process['workerPid']>0 and process['parentPid']!=process['workerPid'] and
         process['exit']==0 and process['profile']==profile and process['publicationRequestOrigin']==origin,
         'departing restart child process outcome')
    interruptions(root,before,process['parentPid'],process['workerPid'])
    result=d.read(root/'restart-result.json')
    expected=dict(status='PASS',node='node-4',published=6,duplicateReceipts=3,remoteExchanges=0,publicReady=False,
                  activation='native round local member not eligible for activation',readiness='native round state/busy',
                  submit='native round state/busy',incomingPrepare='endpoint outside learner reservation',events=result.get('events'))
    need(result==expected,'departing restart refusal outcomes')
    events=result['events']
    need(type(events) is list and all(type(event) is str for event in events) and len(events)<=256 and
         events.count('PUBLICATION_ACK_BEFORE_RETURN')==3 and not set(events)&{
             'ALLOCATOR_FORCED','PROMISE_FORCED','FLOOR_COPIES_FORCED','PUBLICATION_SELECTOR_FORCED'},
         'departing restart no new durable authority')
    need((root/'worker.stdout').read_text()=='v53DepartingRestart=PASS\n' and (root/'worker.stderr').read_bytes()==b'',
         'departing restart complete child output')
    return dict(status='PASS',profile=profile,physicalQualified=True,freshProcess=True,completedAckHaltOrKillQualified=True,
                interruptedChildren=4,wholeOperationFaultQualified=False,restartedTcpQualified=False,publicReady=False,phase3Complete=False)


NEGATIVES={
    'extra-file':'context selection departing restart inventory',
    'changed-reopened-selector':'departing restart unchanged original store',
    'invented-successor-ack':'departing restart unchanged original store',
    'changed-repeat':'departing restart unchanged acknowledgement',
    'changed-prepare':'departing restart exact new-view prepare',
    'same-process':'departing restart child process outcome',
    'failed-worker':'departing restart child process outcome',
    'remote-observation':'departing restart refusal outcomes',
    'new-authority':'departing restart no new durable authority',
    'public-ready':'departing restart refusal outcomes',
    'interrupted-store':'departing interrupted original store',
    'interrupted-exit':'departing interrupted process outcome',
    'missing-lock-refusal':'departing interrupted process outcome',
    'missing-cut':'departing interrupted acknowledgement boundary',
}


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-departure-restart-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            if name=='extra-file':(path/'extra').write_bytes(b'extra')
            elif name=='changed-reopened-selector':(path/'reopened/selector.gsr').write_bytes(b'changed')
            elif name=='invented-successor-ack':(path/'reopened/invented-ack.gsr').write_bytes(b'invented')
            elif name=='changed-repeat':(path/'duplicate-2.gsrp').write_bytes(b'changed')
            elif name=='changed-prepare':
                value=f.decode((path/'fresh-prepare.gsrp').read_bytes(),'wire','PREPARE');value['ballot']['counter']+=1
                (path/'fresh-prepare.gsrp').write_bytes(f.encode('wire','PREPARE',value))
            elif name in ('same-process','failed-worker'):
                value=d.read(path/'process.json');value['workerPid' if name=='same-process' else 'exit']=value['parentPid'] if name=='same-process' else 1
                (path/'process.json').write_text(json.dumps(value))
            elif name=='interrupted-store':(path/'interruptions/halt-1/store/selector.gsr').write_bytes(b'changed')
            elif name in ('interrupted-exit','missing-lock-refusal'):
                target=path/'interruptions/kill-2/process.json';value=d.read(target)
                value['exit' if name=='interrupted-exit' else 'liveLockRefused']=0 if name=='interrupted-exit' else False
                target.write_text(json.dumps(value))
            elif name=='missing-cut':(path/'interruptions/halt-2/worker.stdout').write_text('')
            else:
                value=d.read(path/'restart-result.json')
                if name=='new-authority':value['events'].append('PROMISE_FORCED')
                elif name=='public-ready':value['publicReady']=True
                else:value['remoteExchanges']=1
                (path/'restart-result.json').write_text(json.dumps(value))
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'departing restart unrelated negative: '+name+': '+str(error))
            else:raise ValueError('departing restart mutation accepted: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
