"""Original-first slot resource rejection checks without editing raw evidence."""
import argparse
import base64
import copy
import json
from pathlib import Path

from . import slot_control_resources as r
from . import native_resource_evidence as native
from .floor_resource_negatives import recount

NEGATIVES = {
    'delivery-short':'slot resources original delivery extent',
    'delivery-long':'slot resources original delivery extent',
    'handoff-after-copy':'slot resources unique request handoff',
    'ack-after-release':'slot resources delivery released before acknowledgement',
    'delivery-binding':'slot resources unique request handoff',
    'delivery-omitted':'slot resources unique request handoff',
    'waiter-binding':'slot resources original waiter binding/extent',
    'local-waiter-omitted':'slot resources missing local waiter',
    'voting-waiter-omitted':'slot resources voting child waiter custody',
    'legacy-binding':'slot resources original bindings required',
    'extra-delivery':'slot resources incomplete allocation coverage',
    'extra-waiter':'slot resources waiter call interval',
    'reused-allocation':'slot resources reused allocation',
    'waiter-released-before-child':'slot resources voting child waiter custody',
    'publication-after-release':'slot resources publication waiter custody',
    'missing-local-request':'slot resources local publication response',
    'missing-local-response':'slot resources local publication request',
    'local-request-hash':'slot resources local original bytes',
    'local-response-payload':'slot resources local original acknowledgement',
    'local-response-trace':'slot resources local original acknowledgement',
    'swap-local-publications':'slot resources publication waiter custody',
    'missing-publication':'slot resources local publication not observed',
}


def mutate(data, name):
    r.need(name in NEGATIVES,'slot resources declared negative')
    events,wires,traces,points,ids,root,expected,transactions=data
    lives,_=r.scan(traces);delivery=next(v for v in lives.values() if v['role']=='slot-delivery')
    calls=r.local_calls(events,ids,root,expected);call=calls[0]
    local=next(v for v in lives.values() if v['role']=='slot-waiter' and (v['node'],v['binding'])==(call['node'],call['binding']))
    children,_=r.voting.scan(traces);child=next(v for v in children.values() if v['role']=='voting-waiter')
    waiter=next(v for v in lives.values() if v['role']=='slot-waiter' and (v['node'],v['binding'])==(child['node'],child['binding']) and
                v['start']<child['start']<child['end']<v['end'])
    target=local if name=='local-waiter-omitted' else waiter if name in ('waiter-binding','voting-waiter-omitted') else delivery
    rows=traces[target['node']]['changes']
    if name in ('delivery-short','delivery-long','delivery-binding','delivery-omitted','waiter-binding','local-waiter-omitted','voting-waiter-omitted','legacy-binding'):
        for row in rows:
            for charge in row['removed']+row['added']:
                if charge['owner']!=target['owner']:continue
                if name.endswith(('short','long')):charge['bytes']+=-1 if name.endswith('short') else 1
                elif name.endswith('omitted'):charge['owner']='unqualified-'+charge['owner']
                elif name=='legacy-binding':charge['owner']=target['role']+'-'+r.OWNER.fullmatch(target['owner'])[3]
                else:charge['owner']=charge['owner'].replace(target['binding'],'0'*64)
    elif name in ('handoff-after-copy','ack-after-release'):
        network=r.source.network.replay(events,wires,ids,root)
        requests=[v for v in network['rows'] if v['requestHash']==delivery['binding'] and v['delivered'] is not None]
        request=requests[-1];frames,_=r.source.frames.lifetimes(traces)
        copied=frames[delivery['node'],'request-send',request['clientConnection']]
        if name=='handoff-after-copy':rows[delivery['start']],rows[copied['start']]=rows[copied['start']],rows[delivery['start']]
        else:
            at=points[request['delivered']]['sequence']+1;end=delivery['end']
            rows.insert(at,rows.pop(end))
            for point in points:
                if point['node']==delivery['node'] and at<=point['sequence']<end:point['sequence']+=1
            points[request['delivered']]['sequence']=at
    elif name in ('extra-delivery','extra-waiter','reused-allocation'):
        target=waiter if name=='extra-waiter' else delivery;rows=traces[target['node']]['changes']
        charge=copy.deepcopy(rows[target['start']]['added'][0])
        if name!='reused-allocation':charge['owner']=charge['owner'][:-36]+'00000000-0000-0000-0000-000000000099'
        rows.extend([dict(event='RESERVE',removed=[],added=[charge]),dict(event='RELEASE',removed=[charge],added=[])])
    elif name=='waiter-released-before-child':
        rows=traces[waiter['node']]['changes'];rows[waiter['end']],rows[child['end']]=rows[child['end']],rows[waiter['end']]
    elif name=='publication-after-release':
        transaction=next(t for t in transactions if t[0]['node']==local['node'] and call['received']<t[0]['eventIndex']<call['offered'])
        points[transaction[-1]['eventIndex']]['sequence']=local['end']
    elif name=='swap-local-publications':
        first,second=calls[:2];mapping={first['binding']:second['binding'],second['binding']:first['binding']}
        for field in ('received','offered'):
            a,b=events[first[field]],events[second[field]]
            a['bytes'],b['bytes']=b['bytes'],a['bytes'];a['record'],b['record']=b['record'],a['record']
        seen=set()
        for row in traces[first['node']]['changes']:
            for charge in row['removed']+row['added']:
                if id(charge) in seen:continue
                seen.add(id(charge));match=r.OWNER.fullmatch(charge['owner'])
                if match and match[1]=='slot-waiter' and match[2] in mapping:
                    charge['owner']=charge['owner'].replace(match[2],mapping[match[2]])
    elif name=='missing-publication':
        transactions[:]=[t for t in transactions if not (t[0]['node']==local['node'] and call['received']<t[0]['eventIndex']<call['offered'])]
    elif name.startswith('missing-local-'):
        events[call['received'] if name.endswith('request') else call['offered']]['event']='OMITTED_LOCAL_CALL'
    elif name=='local-request-hash':events[call['received']]['record']='0'*64
    else:
        event=events[call['offered']];kind,value=r.source.network.t.wire(event['bytes'])
        if name=='local-response-payload':value['payload']['certificate']='0'*64
        else:value['trace']='00000000-0000-0000-0000-000000000099'
        raw=r.publication.native.f.encode('wire',kind,value)
        event['record']=r.publication.sha(raw);event['bytes']=base64.b64encode(raw).decode()
    recount(traces,points)


def replay(data,progress=None):
    original=r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'slot resources unrelated negative: '+name+': '+str(error))
        else:raise ValueError('slot resources accepted negative: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(stage='slot-control-negatives',case=name,completed=len(results),total=len(NEGATIVES)))
    return dict(original=original,negatives=results)


def qualify(root):
    root=Path(root);before=native.collection.inventory(root)
    preceding=native.validate(root,source_control=True,control_closes=True,export_ownership=True,direct_exports=True,slot_control=True)
    index,traces,points,events=native.load(root)
    _,rounds,selection,ids=native.publication.native.physical(root,confirmed_retention=True)
    wires=native.collection.read_json(root,'wire.json',native.collection.WIRE_BYTES)
    result=replay((events,wires,traces,points,ids,index['root'],r.publications(rounds,selection,ids),native.publication.collect(root,events)))
    r.need(native.collection.inventory(root)==before,'slot resources original changed during negatives')
    return dict(result,precondition=preceding,originalInventorySha256=native.collection.digest(
                json.dumps(before,sort_keys=True,separators=(',',':')).encode()),
                status='PASS',wholeRuntimeResourcesQualified=False,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');args=p.parse_args()
    print(json.dumps(qualify(args.root),sort_keys=True))
