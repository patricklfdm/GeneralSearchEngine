"""Independent nonvoting retention bytes, derived only from modeled originals.

Decoding a container does not prove its owner, durability, majority or source.
Callers derive the complete original history before comparing its physical files.
"""
import copy
import hashlib
import json
import struct
from . import format_fixture as f

FILE='learner-retention.gslr'
MAXIMUM=32768
HEADER=44


def need(value,message):
    if not value:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def plan(value):
    need(type(value) is dict and set(value)=={'root','request','learner','possible'},'learner retention plan fields')
    types=f.catalog()['types'];f.check_type(value['root'],'hash',types)
    points=value['possible'];need(type(points) is list and len(points)<=2,'learner retention endpoint capacity')
    empty=value['request'] is None
    need(empty==(value['learner'] is None) and empty==(not points),'learner retention empty binding')
    if not empty:
        f.check_type(value['request'],'request',types);f.check_type(value['learner'],'identity',types)
        need(value['request']['root']==value['root'] and value['request']['kind']!='REMOVE'
             and value['learner'] in value['request']['target'],'learner retention request binding')
    prior=-1
    for point in points:
        need(type(point) is dict and set(point)=={'cut','catalog','application'},'learner retention endpoint fields')
        f.check_type(point['cut'],'cut',types)
        for k in ('catalog','application'):f.check_type(point[k],'hash',types)
        need(point['cut']['index']>prior,'learner retention endpoint order');prior=point['cut']['index']
    need(len(f.canonical(value))<=16384,'learner retention plan capacity')
    return value


def metadata(value):
    need(type(value) is dict and set(value)=={'root','owner','revision','previous','plan'},'learner retention container fields')
    types=f.catalog()['types'];f.check_type(value['root'],'hash',types);f.check_type(value['owner'],'identity',types)
    revision=value['revision'];need(type(revision) is int and 0<=revision<=2**63-2,'learner retention revision')
    need((revision==0)==(value['previous'] is None),'learner retention predecessor')
    if value['previous'] is not None:f.check_type(value['previous'],'hash',types)
    need(plan(value['plan'])['root']==value['root'],'learner retention root binding')
    return value


def frame(value):
    body=f.canonical(metadata(value));need(HEADER<len(body)+HEADER<=MAXIMUM,'learner retention extent')
    return struct.pack('>IHHI',0x47534c52,1,3,HEADER+len(body))+bytes.fromhex(sha(body))+body


def decode(raw):
    need(type(raw) is bytes and HEADER<len(raw)<=MAXIMUM,'learner retention extent')
    need(struct.unpack('>IHHI',raw[:12])==(0x47534c52,1,3,len(raw)),'learner retention framing')
    body=raw[HEADER:];need(raw[12:HEADER]==bytes.fromhex(sha(body)),'learner retention checksum');f.parse_budget(body)
    try:value=json.loads(body)
    except (ValueError,UnicodeError) as error:raise ValueError('learner retention JSON') from error
    need(frame(value)==raw,'learner retention canonical bytes')
    return value


def initialize(group):
    from . import carried_publication_evidence as c
    result={}
    for node,files in group.items():
        cap=c.current(files)[2]['capsule'];need(cap['cut']['index']==0,'learner retention genesis cut')
        owner=f.decode(files['node.gsr'],'records','NODE')['identity']
        result[node]=dict(files,**{FILE:frame(dict(root=cap['root'],owner=owner,revision=0,previous=None,
            plan=dict(root=cap['root'],request=None,learner=None,possible=[])))})
    return result


def part(raw):return struct.pack('>I',len(raw))+raw


def wrapped(magic,body):
    prefix=struct.pack('>IHHII',magic,1,3,0,len(body));return prefix+bytes.fromhex(sha(prefix+body))+body


def wrap(promise,ledger):
    grant=f.decode(promise,'records','PROMISE');state=decode(ledger)
    need(len(promise)<=8192 and grant['basisId'] is not None and grant['root']==state['root'],'learner retention frozen promise')
    return wrapped(0x47534c46,part(promise)+part(ledger))


def intent(owner,selected,before,rows):
    chosen=f.decode(selected,'records','SELECTED');state=decode(before)
    need(state['owner']==owner and state['root']==chosen['root'],'learner retention selected local owner')
    need(2<=len(rows)<=6 and len(rows)==len(chosen['sources']),'learner retention selected sources')
    body=part(f.canonical(owner))+part(selected)+part(before)+struct.pack('>I',len(rows))
    for (basis,packet,snapshot),ref in zip(rows,chosen['sources']):
        source=f.decode(basis,'records','BASIS')
        need(source['voter']==ref['voter'] and source['basisId']==ref['basisId'] and sha(basis)==ref['basisDigest'],
             'learner retention selected source binding')
        need(packet['objects'].get(sha(snapshot))==snapshot,'learner retention selected original snapshot')
        body+=part(basis)+part(part(packet['capsuleBytes'])+part(packet['indexBytes']))+part(snapshot)
    need(len(body)+48<8*1024*1024,'learner retention selected capacity')
    return wrapped(0x47534c53,body)


def merged(before,originals):
    need(type(originals) in (list,tuple) and 1<=len(originals)<=6,'learner retention merge count')
    state=decode(before);bound=None;points={}
    for raw in [before,*originals]:
        value=decode(raw);need(value['root']==state['root'],'learner retention merge root');p=value['plan']
        if p['request'] is None:continue
        if bound is None:bound=copy.deepcopy(p)
        need((p['request'],p['learner'])==(bound['request'],bound['learner']),'learner retention merge request')
        for a in p['possible']:
            index=a['cut']['index'];need(index not in points or points[index]==a,'learner retention conflicting endpoint');points[index]=a
    if bound is None:return before
    bound['possible']=[points[k] for k in sorted(points)];plan(bound)
    return before if bound==state['plan'] else frame(dict(state,revision=state['revision']+1,previous=sha(before),plan=bound))


def offer(files,request,learner):
    from . import carried_publication_evidence as c
    packet=c.current(files)[2];cap=packet['capsule'];catalog=f.decode(packet['objects'][cap['catalog']],'records','CATALOG')
    before=files[FILE];state=decode(before);p=copy.deepcopy(state['plan'])
    need(request['root']==cap['root'] and any(r['request']==request for r in catalog['results'])
         and learner in catalog['identities'] and learner in request['target'] and request['kind']!='REMOVE',
         'learner retention original request')
    need(cap['cut']['view']['operation'] is None and learner['node'] not in cap['cut']['view']['old'],
         'learner retention original nonvoting view')
    if p['request'] is None:
        need(catalog['active']==request['number'],'learner retention original active reservation');p.update(request=request,learner=learner)
    else:need(p['request']==request and p['learner']==learner,'learner retention changed request')
    points={a['cut']['index']:a for a in p['possible']};a=c.anchor(cap);index=a['cut']['index']
    need(index not in points or points[index]==a,'learner retention conflicting endpoint');points[index]=a
    p['possible']=[points[k] for k in sorted(points)];plan(p)
    after=before if p==state['plan'] else frame(dict(state,revision=state['revision']+1,previous=sha(before),plan=p))
    return dict(files,**{FILE:after})


def controls(root,prepared,cancelled,request,learner):
    """Match forced original ledgers before considering ACKs or source offers."""
    import base64
    from collections import Counter
    from . import learner_typed_evidence as t
    d,c=t.d,t.c
    events=d.read(root/'events.json');wire=d.read(root/'wire.json');calls=d.read(root/'calls.json')
    need(type(events) is list and len(events)<=32768 and type(wire) is list and len(wire)<=32768,
         'learner retention bounded traces')
    expected_calls=[(n,k) for k in ('initialize-retention','initialize-learner-retention') for n in sorted(prepared)]
    need([(r['node'],r['operation']) for r in calls]==expected_calls,'learner retention initialization owners')
    points=['LEARNER_RETENTION_'+v for v in ('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED','CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')]
    for row in calls[3:]:
        need([v for v in row['events'] if v.startswith('LEARNER_RETENTION_')]==points,'learner retention initialization force order')
    update=points+['LEARNER_RETENTION_ACK_BEFORE_RETURN'];positions={}
    for node in ('node-1','node-2','node-3'):
        matched=[(i,row['event']) for i,row in enumerate(events) if row['node']==node and row['event'] in update]
        need([name for _,name in matched]==update*(0 if node=='node-3' else 2),'learner retention exact update force order')
        positions[node]=[i for i,_ in matched]
    intents=[]
    for row in wire:
        kind,value=d.transfer.t.wire(row['request'])
        if kind=='LEARNER_RETENTION_INTENT':intents.append((row,value,d.transfer.t.wire(row['response'])))
    need(2<=len(intents)<=6,'learner retention wire count');seen=set();failed_requests=set();matched=0
    for phase,(group,path) in enumerate(((prepared,'learner-source-wire.json'),(cancelled,'learner-progress-wire.json'))):
        _,members,packet=c.current(group['node-1']);cap=packet['capsule'];selected=f.decode(members['selected.gsr'],'records','SELECTED')
        local=f.decode(group['node-1']['node.gsr'],'records','NODE')['identity']
        peer=f.decode(group['node-2']['node.gsr'],'records','NODE')['identity']
        logical=dict(selection=sha(members['selected.gsr']),request=request,learner=learner,endpoint=c.anchor(cap))
        rows=[v for v in intents if v[1]['payload']['endpoint']['cut']['index']==cap['cut']['index']]
        need(1<=len(rows)<=3 and len({r[0]['request'] for r in rows})==len({r[0]['response'] for r in rows})==1,
             'learner retention bounded identical ACK attempts')
        matched+=len(rows)
        need(all(r[0].get('withheld') is False for r in rows),'learner retention unexpected withheld ACK')
        row,q,(kind,a)=rows[0];seen.add(q['trace']);ledger=decode(group['node-2'][FILE])
        need(q['payload']==logical and q['sender']==local and q['recipient']==peer
             and q['root']==cap['root'] and q['view']==request['expected'] and q['ballot']==selected['ballot'] and q['sequence']==2,
             'learner retention exact original intent')
        need(kind=='LEARNER_RETENTION_ACK' and a==dict(q,sender=peer,recipient=local,
             payload=dict(intent=sha(f.canonical(logical)),ledger=sha(group['node-2'][FILE]),revision=ledger['revision'])),
             'learner retention exact original ACK')
        received=[i for i,v in enumerate(events) if v['node']=='node-1' and v['event']=='NETWORK_RECEIVED'
                  and v.get('kind')=='LEARNER_RETENTION_ACK' and v.get('response')==sha(base64.b64decode(row['response'],validate=True))]
        ack_events=[i for i,v in enumerate(events) if v['node']=='node-2' and v['event']=='WIRE_RESPONSE'
                    and v.get('request')==sha(base64.b64decode(row['request'],validate=True))
                    and v.get('response')==sha(base64.b64decode(row['response'],validate=True))]
        need(len(ack_events)==len(rows) and 1<=len(received)<=len(rows),'learner retention ACK trace coverage')
        client=d.read(root/path);sessions=t.source.transcripts(client,progress=phase==1);first=sessions[2 if phase==0 else 1][0]
        exposure=[i for i,v in enumerate(events) if v['node']=='node-1' and v['event']=='WIRE_RESPONSE'
                  and v.get('request')==sha(base64.b64decode(first['request'],validate=True))
                  and v.get('response')==sha(base64.b64decode(first['response'],validate=True))]
        need(len(exposure)==1 and positions['node-1'][phase*8+7]<positions['node-2'][phase*8]
             and positions['node-2'][phase*8+7]<min(ack_events)<=min(received)<exposure[0],
             'learner retention force/ACK before source exposure')
        if phase:need(exposure[0]>positions['node-1'][7],'learner retention original phase order')
        third=f.decode(group['node-3']['node.gsr'],'records','NODE')['identity']
        failed_requests.add(sha(f.encode('wire','LEARNER_RETENTION_INTENT',dict(q,recipient=third,sequence=3))))
    need(matched==len(intents) and len(seen)==2
         and sum(1 for _,q,_ in intents if q['trace'] in seen)==len(intents),'learner retention original two rounds')
    failed=Counter(row['request'] for row in d.read(root/'failures.json') if row['kind']=='LEARNER_RETENTION_INTENT')
    need(set(failed)<=failed_requests and all(1<=n<=3 for n in failed.values()),'learner retention exact bounded failed attempts')
    return dict(quorums=2,forcedUpdates=4,sourceExposures=2,wireACKs=len(intents),failedAttempts=sum(failed.values()))


NEGATIVES={
    'retention-missing-genesis':'admitted exact before-network: node-1',
    'retention-genesis-owner':'admitted exact before-network: node-1',
    'retention-genesis-root':'admitted exact before-network: node-1',
    'retention-offer-request':'admitted exact after-learner-source: node-1',
    'retention-offer-identity':'admitted exact after-learner-source: node-1',
    'retention-offer-endpoint':'admitted exact after-learner-source: node-1',
    'retention-terminal-erase':'admitted exact after-close: node-1',
    'retention-stale-revision':'admitted exact after-close: node-1',
    'retention-selected-owner':'admitted exact installed: node-1',
    'retention-frozen-snapshot':'admitted exact installed: node-1',
    'retention-intent-endpoint':'learner retention exact original intent',
    'retention-ack-ledger':'learner retention exact original ACK',
    'retention-missing-ack':'learner retention wire count',
    'retention-extra-endpoint':'learner retention original two rounds',
    'retention-withheld-ack':'learner retention unexpected withheld ACK',
    'retention-force-order':'learner retention exact update force order',
    'retention-early-offer':'learner retention force/ACK before source exposure',
    'retention-extra-attempt':'learner retention exact bounded failed attempts',
    'retention-extra-future-attempt':'learner cancellation unexpected native failure',
}


def mutate(root,name):
    import base64
    from . import learner_typed_evidence as t
    d,c=t.d,t.c
    if name=='retention-missing-genesis':(root/'before-network/node-1'/FILE).unlink();return
    if name.startswith(('retention-genesis-','retention-offer-','retention-terminal-','retention-stale-')):
        stage='before-network' if name.startswith('retention-genesis-') else 'after-learner-source' if name.startswith('retention-offer-') else 'after-close'
        path=root/stage/'node-1'/FILE;value=decode(path.read_bytes());p=value['plan']
        if name=='retention-genesis-owner':value['owner']['storage']='00000000-0000-0000-0000-000000000053'
        elif name=='retention-genesis-root':value['root']=p['root']='ff'*32
        elif name=='retention-offer-request':p['request']['number']+=1
        elif name=='retention-offer-identity':
            p['learner']['storage']='00000000-0000-0000-0000-000000000053'
            for member in p['request']['target']:
                if member['node']==p['learner']['node']:member.update(p['learner'])
        elif name=='retention-offer-endpoint':p['possible'][0]['catalog']='ff'*32
        elif name=='retention-terminal-erase':p['possible'].pop(0)
        elif name=='retention-stale-revision':value=decode((root/'after-learner-source/node-1'/FILE).read_bytes())
        else:raise ValueError('unknown learner retention ledger negative')
        path.write_bytes(frame(value));return
    if name in ('retention-selected-owner','retention-frozen-snapshot'):
        base=root/'installed/node-1';files=c.inventory(base);prefix,members,packet=c.current(files)
        if name=='retention-frozen-snapshot':
            basis=f.decode(members['basis.gsr'],'records','BASIS');path=base/'sources'/basis['basisId']/'source.gscp'
            # Use the shared bounded packet decoder, never the active directory.
            from . import source_packet as packets
            packet=packets.decode(path.read_bytes());magic=0x47534c46
        else:magic=0x47534c53
        objects=dict(packet['objects']);keys=[h for h,raw in objects.items() if len(raw)>48 and int.from_bytes(raw[:4],'big')==magic]
        need(len(keys)==1,'learner retention negative original wrapper');raw=objects.pop(keys[0]);body=raw[48:];length=int.from_bytes(body[:4],'big')
        if name=='retention-selected-owner':
            owner=json.loads(body[4:4+length]);owner['storage']='00000000-0000-0000-0000-000000000053'
            body=part(f.canonical(owner))+body[4+length:]
        else:
            ledger=decode(body[8+length:]);ledger['owner']['storage']='00000000-0000-0000-0000-000000000053'
            body=part(body[4:4+length])+part(frame(ledger))
        changed=wrapped(magic,body);objects[sha(changed)]=changed
        packed=c.packet_bytes(packet['capsule'],objects,packet['images'])
        if name=='retention-frozen-snapshot':path.write_bytes(packed)
        else:
            from . import source_packet as packets
            members=dict(members,**{'source.gscp':packed});selector,generated=c.generation(members,packets.decode(packed)['capsule'],'node-1',prefix.split('/')[1],None)
            for path,data in generated.items():
                if data is not None:(base/path).write_bytes(data)
            (base/'selector.gsr').write_bytes(selector)
        return
    if name in ('retention-intent-endpoint','retention-ack-ledger','retention-missing-ack',
                'retention-extra-endpoint','retention-withheld-ack'):
        path=root/'wire.json';rows=d.read(path);at=next(i for i,row in enumerate(rows) if d.transfer.t.wire(row['request'])[0]=='LEARNER_RETENTION_INTENT')
        if name=='retention-missing-ack':rows.pop(at)
        elif name=='retention-withheld-ack':rows[at]['withheld']=True
        elif name=='retention-extra-endpoint':
            # Reusing a known trace cannot hide a third logical endpoint outside
            # the two independently derived source-exposure rounds.
            extra=copy.deepcopy(rows[at]);kind,value=d.transfer.t.wire(extra['request'])
            value['payload']['endpoint']['cut']['index']+=1
            extra['request']=base64.b64encode(f.encode('wire',kind,value)).decode();rows.append(extra)
        else:
            field='request' if name=='retention-intent-endpoint' else 'response';kind,value=d.transfer.t.wire(rows[at][field])
            if field=='request':value['payload']['endpoint']['catalog']='ff'*32
            else:value['payload']['ledger']='ff'*32
            rows[at][field]=base64.b64encode(f.encode('wire',kind,value)).decode()
        path.write_bytes(f.canonical(rows));return
    if name in ('retention-force-order','retention-early-offer'):
        path=root/'events.json';rows=d.read(path)
        if name=='retention-force-order':
            a=next(i for i,row in enumerate(rows) if row['node']=='node-2' and row['event']=='LEARNER_RETENTION_PARENT_FORCED')
            b=next(i for i,row in enumerate(rows) if row['node']=='node-2' and row['event']=='LEARNER_RETENTION_ACK_BEFORE_RETURN')
            rows[a],rows[b]=rows[b],rows[a]
        else:
            source=t.source.transcripts(d.read(root/'learner-source-wire.json'))[2][0]
            digest=sha(base64.b64decode(source['response'],validate=True))
            at=next(i for i,row in enumerate(rows) if row['event']=='WIRE_RESPONSE' and row['response']==digest)
            original=rows.pop(at);before=next(i for i,row in enumerate(rows) if row['event']=='NETWORK_RECEIVED' and row.get('kind')=='LEARNER_RETENTION_ACK')
            rows.insert(before,original)
        path.write_bytes(f.canonical(rows));return
    if name=='retention-extra-future-attempt':
        path=root/'failures.json';rows=d.read(path);future=next(v for v in rows if v['kind']=='FUTURE_RETENTION_INTENT')
        remaining=[v for v in rows if v['kind']=='LEARNER_RETENTION_INTENT'][:4]
        path.write_bytes(f.canonical([future]*16+remaining));return
    if name=='retention-extra-attempt':
        path=root/'failures.json';rows=d.read(path);matches=[v for v in rows if v['kind']=='LEARNER_RETENTION_INTENT'];unique={v['request']:v for v in matches}
        need(len(unique)==2,'learner retention failed original pair');first,second=unique.values()
        path.write_bytes(f.canonical([v for v in rows if v['kind']!='LEARNER_RETENTION_INTENT']+[first]*4+[second]));return
    raise ValueError('unknown learner retention negative: '+name)
