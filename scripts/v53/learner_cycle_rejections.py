"""Exact nonselected-voter refusals in the six-revision learner history.

The third original voter never installs the campaign. Its failed recording
requests are not quorum ACKs. Derive their bytes from the independently replayed
slot and the correlated selected peer exchange; never allow arbitrary errors.
"""
from collections import Counter
import json
from . import native_dispatch_evidence as d

f,e,c,need=d.f,d.e,d.c,d.need
FAILURE='java.lang.IllegalArgumentException: higher ballot observed; fresh campaign required'


def recording(applied,published,recorded):
    local=applied['node-1'];_,members,packet=c.current(local)
    selected=f.decode(members['selected.gsr'],'records','SELECTED')
    third=applied['node-3'];root=selected['root']
    promises=[value for kind,_,value in c.journal(third['grants.gsr'],root,'node-3') if kind=='PROMISE']
    need(promises and c.current(third)[1].get('selected.gsr') is None and
         promises[-1]['ballot']['counter']<selected['ballot']['counter'] and
         published['node-3']==third,'learner cycles original unselected voter')
    peer=d.future.identity(applied['node-2'])
    plan=d.s.r.decode(local[d.s.FILE])['plan']
    possible=next(row['possible'] for row in plan['peers'] if row['identity']==peer)
    need(len(possible)==1,'learner cycles original recording lower')
    payload=dict(selection=e.digest(members['selected.gsr']),certificate=e.digest(local['applied-end/certificate.gsr']),
                 peer=peer,lower=possible[0],parent=c.anchor(packet['capsule']),upper=c.anchor(c.current(published['node-1'])[2]['capsule']))
    retained=recorded['node-2'][d.future.FILE]
    metadata=json.loads(retained[48:48+int.from_bytes(retained[44:48],'big')])
    return dict(root=root,view=selected['view'],ballot=selected['ballot'],sender=d.future.identity(local),recipient=peer,
                sequence=2,payload=payload,third=d.future.identity(third),
                ack=dict(intent=e.digest(f.canonical(payload)),storage='FUTURE',revision=metadata['revision'],digest=e.digest(retained)))


def validate(root,expected):
    need(set(expected)==set(range(1,17)),'learner cycles sixteen recording slots')
    wire=d.read(root/'wire.json');events=d.read(root/'events.json');failures=d.read(root/'failures.json')
    need(type(wire) is list and len(wire)<=32768 and type(events) is list and len(events)<=32768,
         'learner cycles bounded recording evidence')
    indexed={v['payload']['certificate']:index for index,v in expected.items()}
    need(len(indexed)==16,'learner cycles distinct recording certificates')
    observed={};allowed=set();traces=set();counts=Counter()
    responses=Counter((v.get('node'),v.get('request'),v.get('response')) for v in events if v.get('event')=='WIRE_RESPONSE')
    for row in wire:
        kind,request=d.transfer.t.wire(row['request'])
        if kind!='FUTURE_RETENTION_INTENT':continue
        answer,response=d.transfer.t.wire(row['response'])
        index=indexed.get(request['payload'].get('certificate'));need(index is not None,'learner cycles recording original slot')
        want=expected[index];fields={k:v for k,v in want.items() if k not in ('third','ack')}
        need(set(row)=={'request','response','withheld'} and row['withheld'] is False and
             request==dict(fields,trace=request['trace']) and answer=='FUTURE_RETENTION_ACK' and
             response==dict(request,sender=want['recipient'],recipient=want['sender'],payload=want['ack']),
             'learner cycles exact recording exchange')
        digest=e.digest(f.encode('wire',kind,request));reply=e.digest(f.encode('wire',answer,response))
        key=('node-2',digest,reply);need(responses[key]>0,'learner cycles recording response event');responses[key]-=1
        counts[index]+=1
        need(counts[index]<=3 and (index not in observed or observed[index]==request),
             'learner cycles identical recording retries')
        if index not in observed:
            need(request['trace'] not in traces,'learner cycles distinct recording traces');traces.add(request['trace'])
        observed[index]=request
        allowed.add(e.digest(f.encode('wire',kind,dict(request,recipient=want['third'],sequence=3))))
    need(set(observed)==set(expected),'learner cycles complete recording exchanges')
    need(type(failures) is list and len(failures)<=48,'learner cycles native failures')
    retries=Counter()
    for row in failures:
        need(type(row) is dict and set(row)=={'node','kind','request','failure'} and row['node']=='node-3' and
             row['kind']=='FUTURE_RETENTION_INTENT' and row['failure']==FAILURE and
             type(row['request']) is str and row['request'] in allowed,'learner cycles native failures')
        retries[row['request']]+=1;need(retries[row['request']]<=3,'learner cycles native failure retries')
    return dict(recordingSlots=len(observed),unselectedRefusals=len(failures))
