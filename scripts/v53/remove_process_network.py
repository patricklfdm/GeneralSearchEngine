"""Bind every attempted exchange to the original multi-process observation order.

Version-one histories retain physical qualification but cannot supply missing
child failure observations or a cross-process order. No ordering is inferred
from wall clocks, log delivery or a successful final result.
"""
import argparse
import base64
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from . import remove_process_evidence as physical
from . import remove_network_evidence as network

p,n=physical,network
c,d,e,f,need=p.c,p.d,p.e,p.f,p.need


def normalize(kind,value):
    node='node-1'
    if kind=='STORE':return [dict(node=node,event=value['event'])],[]
    if kind=='FAILURE':return [dict(node=node,event='NETWORK_ATTEMPT_FAILED',**value)],[]
    if kind in ('BEFORE_REQUEST_WRITE','AFTER_REQUEST_READ'):
        wire_kind,request=n.transcript.wire(value);digest=e.digest(base64.b64decode(value,validate=True))
        event='NETWORK_SEND' if kind=='BEFORE_REQUEST_WRITE' else 'NETWORK_REQUEST'
        row=dict(node=node,event=event,kind=wire_kind,request=digest)
        if event=='NETWORK_SEND':row['bytes']=value
        rows=[row]
        if kind=='BEFORE_REQUEST_WRITE' and wire_kind=='PUBLISH':rows.append(dict(node=node,event='PUBLICATION_SEND_BOUNDARY',request=digest))
        return rows,[]
    if kind in ('AFTER_RESPONSE_READ','BEFORE_RESPONSE_WRITE'):
        reply_kind,_=n.transcript.wire(value['response'])
        response=e.digest(base64.b64decode(value['response'],validate=True))
        if kind=='AFTER_RESPONSE_READ':return [dict(node=node,event='NETWORK_RECEIVED',kind=reply_kind,response=response)],[]
        return [dict(node=node,event='WIRE_RESPONSE',request=e.digest(base64.b64decode(value['request'],validate=True)),response=response)], [dict(value,withheld=False)]
    if kind in ('ROUND','SLOT'):
        raw=base64.b64decode(value['record'],validate=True)
        row=dict(node=node,event=('ROUND_' if kind=='ROUND' else 'DRIVER_')+value['event'],record=e.digest(raw),bytes=value['record'])
        if kind=='SLOT':
            certificate=f.decode(raw,'records','CERTIFICATE');row.update(index=certificate['index'],voters=value['voters'])
        return [row],[]
    need(kind in ('CUT','OPEN','SNAPSHOT','READY','CLOSED'),'REMOVE process network unknown observation')
    return [dict(node=node,event='PROCESS_'+kind,value=value)],[]


def observations(root,profile):
    need(profile['schema']==p.run.SCHEMAS[-1],'REMOVE process network requires original v2 capture')
    root=Path(root);path=root/'history/process-trace.jsonl'
    need(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=64*e.MIB,'REMOVE process bounded shared trace')
    raw=path.read_bytes();need(raw.endswith(b'\n'),'REMOVE process incomplete shared trace')
    lines=raw.splitlines();need(len(lines)<=65536,'REMOVE process shared event count')
    streams={name:[] for name in ('parent',profile['mode'],'resume')};events=[]
    wires=d.read(root/'history/wire.json');origins=[]
    for line in lines:
        value=e.parse(line)
        need(type(value) is dict and set(value)=={'origin','value'} and value['origin'] in streams and
             type(value['value']) is dict and f.canonical(value)==line,'REMOVE process shared event shape')
        origin,row=value['origin'],value['value'];streams[origin].append(row);origins.append(origin)
        if origin=='parent':events.append(row)
        else:
            need(set(row)=={'kind','value'},'REMOVE process child shared event shape')
            translated,answers=normalize(row['kind'],row['value']);events.extend(translated);wires.extend(answers)
    need(streams['parent']==d.read(root/'history/events.json'),'REMOVE process exact parent event projection')
    for mode,worker in ((profile['mode'],'interrupted-worker'),('resume','resumed-worker')):
        rows=p.process.trace(root/worker/'stdout')
        need(streams[mode]==[dict(kind=k,value=v) for k,v in rows],'REMOVE process exact child event projection: '+mode)
    need(max(i for i,v in enumerate(origins) if v==profile['mode'])<min(i for i,v in enumerate(origins) if v=='resume'),
         'REMOVE process shared owner lifetime')
    return events,wires


class History(n.History):
    def __init__(self,root,profile):
        self.root=Path(root)/'history';self.old=tuple('node-'+str(i+1) for i in range(int(profile['profile'][0])))
        self.phases=[];self.states=[None];self.applied={};self.published={};self.installed={}
        resumed=p.process.trace(Path(root)/'resumed-worker/stdout')
        entries=[base64.b64decode(v['record'],validate=True) for k,v in resumed if k=='ROUND' and v['event']=='SLOT_BEGIN']
        selections=[base64.b64decode(v['record'],validate=True) for k,v in resumed if k=='ROUND' and v['event']=='INSTALLED']
        need(len(entries)==len(selections)==3,'REMOVE process network continuation inventory')
        for ordinal,(selected,entry) in enumerate(zip(selections,entries),1):
            selection=f.decode(selected,'records','SELECTED');voters=[v['voter'] for v in selection['sources']];index=ordinal+4
            for node in voters:
                self.installed[ordinal,node]=c.inventory(self.root/f'resume-installed-{ordinal}'/node)
                self.applied[ordinal,node]=c.inventory(self.root/f'resume-applied-{index}'/node)
                self.published[ordinal,node]=c.inventory(self.root/f'resume-published-{index}'/node)
            certificate=self.applied[ordinal,'node-1']['applied-end/certificate.gsr'];cert=f.decode(certificate,'records','CERTIFICATE')
            self.phases.append(dict(SELECTED=selected,ENTRY=entry,CERTIFICATE=certificate,
                PROOF=f.encode('records','PROOF',{k:v for k,v in cert.items() if k!='proofs'}),
                ACCEPT=f.encode('records','ACCEPT',{k:v for k,v in cert.items() if k not in ('proofs','accepts')})))
            packet=c.current(self.published[ordinal,'node-1'])[2]
            self.states.append(f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG'))

    def activations(self,root,profile):
        interrupted=p.process.trace(Path(root)/'interrupted-worker/stdout')
        first=next(base64.b64decode(v['record'],validate=True) for k,v in interrupted if k=='ROUND' and v['event']=='INSTALLED')
        phases=[dict(SELECTED=first),*self.phases]
        initial={v['voter']:c.inventory(self.root/(profile['mode']+'-installed-1')/v['voter'])
                 for v in f.decode(first,'records','SELECTED')['sources']}
        installed={(1,n):files for n,files in initial.items()}
        installed.update({(ordinal+1,node):files for (ordinal,node),files in self.installed.items()})
        return SimpleNamespace(phases=phases,installed=installed)


def replay(root,profile):
    root=Path(root);history=History(root,profile);events,wires=observations(root,profile)
    ids={node:d.future.identity(c.inventory(history.root/'before-network'/node)) for node in history.old}
    root_id=f.decode(history.phases[0]['SELECTED'],'records','SELECTED')['root']
    failed=[];rows=n.transcript.causal(events,wires,ids,root_id,failed=failed);n.bounded_attempts(events)
    need(all(v['kind'] in {'PREPARE','SELECTED','STATUS_PROBE','CHUNK','TRANSFER_COMMIT','ACCEPT','PROOF','APPLY','PUBLISH','FUTURE_RETENTION_INTENT'}
             for v in rows),'REMOVE process network unknown exchange')
    result=n.transcript.transfers(rows)
    result.update(n.activations(events,rows,history.activations(root,profile)))
    slots=n.phase.blocks(events,history);result.update(n.phase.phase_replay(events,rows,history,slots))
    result.update(n.statuses(rows,history,slots))
    result.update(n.failed_controls(history.root,events,failed,history,rows,slots))
    n.shared.initial_current.validate(events,history.old)
    return dict(result,exchanges=len(rows),failedAttempts=len(failed),normalizedEvents=len(events),
                originalObservations=sum(Counter(v['origin'] for v in map(e.parse,(root/'history/process-trace.jsonl').read_bytes().splitlines())).values()))


def validate(root):
    root=Path(root);before=p.run.h.inventory(root);original=p.validate(root);result=replay(root,original['profile'])
    need(p.run.h.inventory(root)==before,'REMOVE process network original changed')
    return dict(status='PARTIAL',physical=original,network=result,observedAttemptsQualified=True,
                durableActivationAndSlotACKsQualified=True,processDeathQualified=True,
                completeExportAuthorityQualified=False,maintenanceCompositionQualified=False,phase3Complete=False)


NEGATIVES={
    'parent-projection':'REMOVE process exact parent event projection',
    'child-projection':'REMOVE process exact child event projection: resume',
    'truncated-trace':'REMOVE process incomplete shared trace',
    'receive-before-send':'joining network receive without send',
    'missing-caller-terminal':'joining failure missing caller terminal',
    'missing-receiver-terminal':'joining failure missing receiver terminal',
    'missing-diagnostic':'REMOVE network complete failure diagnostics',
    'missing-grant-force':'REMOVE network durable grant order',
    'missing-proposer-install-force':'joining network proposer complete installation order',
    'wrong-prepare-authority':'REMOVE network prepare authority',
    'wrong-status-cut':'REMOVE network original status window',
    'failed-control-sequence':'REMOVE network unbound failed control',
    'failed-control-trace':'REMOVE network failed control quorum lifetime',
    'transfer-content':'joining network complete transfer commit',
}


def rewrite(root,rows,*,projections=True):
    root=Path(root);(root/'history/process-trace.jsonl').write_bytes(b''.join(f.canonical(v)+b'\n' for v in rows))
    if not projections:return
    (root/'history/events.json').write_bytes(f.canonical([v['value'] for v in rows if v['origin']=='parent']))
    for origin,worker in ((p.profile_at(root)['mode'],'interrupted-worker'),('resume','resumed-worker')):
        values=[v['value'] for v in rows if v['origin']==origin]
        (root/worker/'stdout').write_text(''.join(v['kind']+' '+(v['value'] if type(v['value']) is str else f.canonical(v['value']).decode())+'\n' for v in values))


def replace_strings(value,mapping):
    if type(value) is str:return mapping.get(value,value)
    if type(value) is list:return [replace_strings(v,mapping) for v in value]
    if type(value) is dict:return {k:replace_strings(v,mapping) for k,v in value.items()}
    return value


def mutate(root,name):
    root=Path(root);path=root/'history/process-trace.jsonl';rows=[e.parse(v) for v in path.read_bytes().splitlines()]
    if name=='truncated-trace':path.write_bytes(path.read_bytes()[:-1]);return
    def remove(predicate):rows.pop(next(i for i,v in enumerate(rows) if predicate(v)))
    if name=='parent-projection':remove(lambda v:v['origin']=='parent');rewrite(root,rows,projections=False);return
    if name=='child-projection':remove(lambda v:v['origin']=='resume');rewrite(root,rows,projections=False);return
    if name=='receive-before-send':
        at=next(i for i,v in enumerate(rows) if v['origin']!='parent' and v['value']['kind']=='BEFORE_REQUEST_WRITE' and
                n.transcript.wire(v['value']['value'])[0]=='PREPARE')
        send=rows.pop(at);digest=e.digest(base64.b64decode(send['value']['value']))
        arrival=next(i for i,v in enumerate(rows) if v['origin']=='parent' and v['value'].get('event')=='NETWORK_REQUEST' and v['value']['request']==digest)
        need(all(v['origin']!=send['origin'] for v in rows[at:arrival+1]),'REMOVE process negative would reorder own stream')
        rows.insert(arrival+1,send)
    elif name=='missing-caller-terminal':remove(lambda v:v['origin']=='resume' and v['value']['kind']=='FAILURE' and v['value']['value']['direction']=='OUTBOUND')
    elif name=='missing-receiver-terminal':remove(lambda v:v['origin']=='parent' and v['value'].get('event')=='NETWORK_ATTEMPT_FAILED' and v['value']['direction']=='INBOUND')
    elif name=='missing-diagnostic':
        path=root/'history/failures.json';values=d.read(path);values.pop(0);path.write_bytes(f.canonical(values));return
    elif name=='missing-grant-force':remove(lambda v:v['origin']=='parent' and v['value'].get('event')=='SOURCE_PACKET_FORCED')
    elif name=='missing-proposer-install-force':remove(lambda v:v['origin']!='parent' and v['value']['kind']=='STORE' and v['value']['value']['event']=='INSTALL_IMAGE_FORCED')
    else:
        wires=d.read(root/'history/wire.json');failures=d.read(root/'history/failures.json')
        if name.startswith('failed-control-'):
            terminal=next(v['value']['value'] for v in rows if v['origin']=='resume' and v['value']['kind']=='FAILURE')
            old=next(v['value']['value'] for v in rows if v['origin']=='resume' and v['value']['kind']=='BEFORE_REQUEST_WRITE' and
                     e.digest(base64.b64decode(v['value']['value']))==terminal['request'])
            kind,value=n.transcript.wire(old)
            if name=='failed-control-sequence':value['sequence']+=1
            else:value['trace']='00000000-0000-0000-0000-000000000001'
        else:
            request_kind={'wrong-prepare-authority':'PREPARE','wrong-status-cut':'STATUS_PROBE','transfer-content':'CHUNK'}[name]
            pair=next(v for v in wires if n.transcript.wire(v['request'])[0]==request_kind and
                      (name!='transfer-content' or n.transcript.wire(v['response'])[0]=='CHUNK'))
            old=pair['request' if name=='wrong-prepare-authority' else 'response'];kind,value=n.transcript.wire(old)
            if name=='wrong-prepare-authority':value['payload']['promise']='f'*64
            elif name=='wrong-status-cut':value['payload']['cut']['index']=999
            else:
                chunk=bytearray(base64.b64decode(value['payload']['bytes']));chunk[0]^=1
                value['payload'].update(bytes=base64.b64encode(chunk).decode(),digest=e.digest(chunk))
        raw=f.encode('wire',kind,value);new=base64.b64encode(raw).decode()
        mapping={old:new,e.digest(base64.b64decode(old)):e.digest(raw)}
        rows=replace_strings(rows,mapping);wires=replace_strings(wires,mapping);failures=replace_strings(failures,mapping)
        (root/'history/wire.json').write_bytes(f.canonical(wires));(root/'history/failures.json').write_bytes(f.canonical(failures))
    rewrite(root,rows)


OBSERVATIONS={'history/events.json','history/wire.json','history/failures.json','history/process-trace.jsonl',
              'interrupted-worker/stdout','resumed-worker/stdout'}


def negative(root,profile,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-remove-process-network-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name);after=p.run.h.inventory(changed)
        protected=lambda inventory:{k:v for k,v in inventory['files'].items() if k not in OBSERVATIONS}
        need(protected(before)==protected(after) and before['directories']==after['directories'],'REMOVE process network negative changed physical inputs')
        p.validate(changed)
        try:replay(changed,profile)
        except ValueError as error:need(str(error)==NEGATIVES[name],'REMOVE process network unrelated negative: '+name+': '+str(error))
        else:raise ValueError('REMOVE process network mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],physicalPrecondition='PASS')


def qualify(root,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'REMOVE process network replay workers')
    root=Path(root);original=validate(root);before=p.run.h.inventory(root);outcomes=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(negative,root,original['physical']['profile'],before,name):name for name in NEGATIVES}
        for task in as_completed(pending):
            name=pending[task]
            try:result=task.result()
            except Exception as error:result=dict(case=name,status='FAIL',failure=str(error),type=type(error).__name__)
            outcomes.append(result);print(json.dumps(dict(result,completed=len(outcomes),total=len(pending))),file=sys.stderr,flush=True)
    need(p.run.h.inventory(root)==before,'REMOVE process network negatives changed original')
    need(all(v['status']=='REJECTED' for v in outcomes),'REMOVE process network negative matrix failed')
    return dict(original=original,negatives=sorted(outcomes,key=lambda v:v['case']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    print(json.dumps(qualify(args.root,workers=args.workers) if args.qualify else validate(args.root),sort_keys=True))
