"""Explicit control-profile replay, including one pre-DATA reconciliation.

This uses the same physical reducers and source/force checks as cold rejoin.
An extra native campaign is not an extra automatic-owner session or client retry.
"""
import base64
import uuid
from collections import defaultdict
from pathlib import Path
from . import automatic_restart_current as current
from . import automatic_restart_network as net
from . import node_owner_network as nodes
from . import node_current_evidence as model
from . import node_current_network as confirmations
from . import node_grant_maintenance as grants

n,c,e,f,need=net.n,net.c,net.e,net.f,net.need


class Service(current.Service):
    def required_anchors(self):
        result=super().required_anchors()
        for node in self.voters:
            files=self.group[node];_,members,packet=c.current(files)
            available=model.current.confirmation.endpoints(packet,members.get('ancestry.gsr',b''))
            for raw in model.current.confirmation.frames(members['selected-sources.gsr']):
                cut=f.decode(raw,'records','BASIS')['cut'];point=available.get(cut['index'])
                need(point is not None and point['cut']==cut,'restart selected original parent')
                if point not in result:result.append(point)
        return sorted(result,key=lambda v:v['cut']['index'])

    def grant_identifier(self,prior,rows,ballot,selected):
        if not selected or rows[:len(prior)]==prior:
            return super().grant_identifier(prior,rows,ballot,selected)
        # A former unused candidate can become selected on reconciliation.
        # Observe only its fresh UUID; inherited after_grant independently
        # derives the retired sources/journal and compares the entire snapshot.
        suffix=[row for row in rows if row[2].get('ballot')==ballot]
        need([row[0] for row in suffix]==['PROMISE','BASIS','SELECTED'] and rows[-3:]==suffix,
             'restart selected fresh grant suffix')
        return suffix[0][2]['basisId']

    def installation_ancestry(self,files,packet,sources):
        _,old,previous=c.current(files);points=[c.anchor(previous['capsule'])]
        merged=self.merge_peers(files[n.s.FILE],[v[n.s.FILE] for v in sources])
        for raw in (files[n.s.FILE],merged):
            points += [v for row in n.s.r.decode(raw)['plan']['peers'] for v in [*row.get('renewals',[]),*row['possible']]]
        points += [c.anchor(e.p.decode(raw)['capsule']) for name,raw in files.items()
                   if name.startswith('sources/') and name.endswith('/source.gscp')]
        direct=model.current.confirmation.endpoints(packet,b'');required={v['cut']['index'] for v in points if v['cut']['index'] not in direct}
        candidates={}
        for source in [files,*sources]:
            members=c.current(source)[1];groups=[]
            for raw in model.current.confirmation.frames(members['ancestry.gsr']) if members.get('ancestry.gsr') else ():
                if int.from_bytes(raw[8:10],'big')==f.catalog()['records']['CHECKPOINT']['id']:groups.append([raw])
                else:
                    need(groups,'restart orphan installation ancestry');groups[-1].append(raw)
            for group in groups:
                index=f.decode(group[0],'records','CHECKPOINT')['start']['index']
                if index not in required:continue
                encoded=b''.join(group)
                need(index not in candidates or candidates[index]==encoded,'restart conflicting original ancestry')
                candidates[index]=encoded
        ancestry=b''.join(candidates[index] for index in sorted(candidates))
        available=model.current.confirmation.endpoints(packet,ancestry)
        need(all(available.get(v['cut']['index'])==v for v in points),'restart complete original installation ancestry')
        return ancestry


def stages(events):
    held=[(i,v) for i,v in enumerate(events) if v['event'].startswith('ROUND_')]
    campaigns=sum(v['event']=='ROUND_INSTALLED' for _,v in held)
    need(campaigns in (2,3),'restart schedule bounded campaigns')
    expected=['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY']*campaigns+['SLOT_BEGIN','SLOT_COMPLETE']
    need([v['event'] for _,v in held]==['ROUND_'+v for v in expected],'automatic restart lifecycle order')
    result=[];lower=-1
    for number in range(1,campaigns+1):
        installed=held[4*(number-1)][0];published=held[4*(number-1)+2][0]
        result.extend([(lower,installed,f'installed-{number}'),(installed,published,f'published-{number}')]);lower=published
    result.append((lower,held[-1][0],f'published-{campaigns+1}'))
    return result


def unused_requests(root,events,entries):
    """Select actual optional unused pulls only after complete activation replay."""
    result=[]
    for start,stop,stage in stages(events):
        if not stage.startswith('installed'):continue
        number=int(stage.split('-')[1]);selected=f.decode((root/f'selected-{number}.gsr').read_bytes(),'records','SELECTED')
        voters={v['voter'] for v in selected['sources']};group=net.group(root,stage)
        for row in entries:
            q=row['request'];peer=q['recipient']['node']
            if not(start<row['offered']<stop and row['kind']=='CHUNK' and q['sender']['node']=='node-1' and peer not in voters
                   and q['sequence']==1 and row['answer']=='SOURCE_OFFER'):continue
            basis=net.frozen(group[peer],selected['ballot'])[1]
            if q['payload']['digest']==e.digest(basis):result.append(row)
    return result


def activation_ancestry(phase,before,installed,selected):
    peer=selected['sources'][1]['voter'];ballot=selected['ballot']
    frozen=net.frozen(installed['node-1'],ballot)[3]
    lower=net.frozen(installed[peer],ballot)[3]['capsule']['cut']
    direct=model.current.confirmation.endpoints(frozen,b'')
    if lower['index'] in direct:
        need(direct[lower['index']]['cut']==lower,'restart selected source original cut');return
    prefix,members,packet=c.current(before['node-1'])
    need(packet['capsule']['cut']==frozen['capsule']['cut'],'restart ancestry original current source')
    start=phase.at('node-1','SELECTED_FORCED');stop=phase.at(peer,'SELECTED_FORCED')
    received=phase.transfer(peer,'node-1',n.maintenance_prefixes(members,packet,c.current(before[peer])[1]),ballot,start,stop)
    start=max(v[0] for v in received['arrivals'])
    reference=n.current_reference(packet['capsule'],'retained-current-ancestry')
    values=[(reference,before['node-1'][prefix+'generation.gsr'],'RECORD')]
    need('ancestry.gsr' in members,'restart missing original ancestry')
    values.append((e.digest(members['ancestry.gsr']),members['ancestry.gsr'],'RECORD'))
    phase.transfer(peer,'node-1',[values],ballot,start,stop)


def sends(root,events,entries,identities):
    rows=n.read(root/'restart-sends.json');need(type(rows) is list and 0<len(rows)<=65536,'restart original send inventory')
    sent=defaultdict(list);prior=-1
    for row in rows:
        need(type(row) is dict and set(row)=={'afterEvent','bytes'} and type(row['afterEvent']) is int
             and prior<=row['afterEvent']<len(events),'restart original send anchor')
        prior=row['afterEvent'];kind,q=n.transfer.t.wire(row['bytes']);raw=base64.b64decode(row['bytes'],validate=True)
        need(q['sender']==identities.get(q['sender']['node']) and q['recipient']==identities.get(q['recipient']['node'])
             and q['sender']!=q['recipient'],'restart original send identity')
        sent[e.digest(raw)].append(dict(at=prior,kind=kind,request=q,raw=raw))
    for digest,attempts in sent.items():
        need(len(attempts)<=3 and all(v['request']==attempts[0]['request'] for v in attempts),'restart original send retries')
    seen=defaultdict(int)
    for row in sorted(entries,key=lambda v:v['offered']):
        digest=e.digest(base64.b64decode(row['row']['request'],validate=True))
        seen[digest]+=1
        need(sum(v['at']<row['offered'] and v['request']==row['request'] and v['kind']==row['kind'] for v in sent[digest])>=seen[digest],
             'restart response without original send')
    return sent


def validate(root):
    root=Path(root);derived=[]
    class CapturedService(Service):
        def __init__(self,*args):super().__init__(*args);derived.append(self)
    physical=current.physical.validate(root,service_type=CapturedService)
    receipt=n.read(root/'restart-result.json')
    need(receipt.get('requestTimeoutMillis')==30_000,'restart declared control timeout')
    events=n.read(root/'events.json');schedule=stages(events);boundaries=[(a,b) for a,b,_ in schedule]
    identities={node:n.future.identity(files) for node,files in net.group(root,'before-network').items()}
    net.wait.lifecycle(n.read(root/'calls.json'),events[:len(net.wait.REOPEN)*len(identities)],identities)
    entries=net.x.exchanges(root,events,-1,len(events),identities);net.deliveries(events,entries)
    root_hash=c.current(net.group(root,'before-network')['node-1'])[2]['capsule']['root']
    view=f.decode((root/'selected-1.gsr').read_bytes(),'records','SELECTED')['view']
    need(all(v['request']['root']==root_hash and v['request']['view']==view for v in entries),'restart network original root/view')
    background=current.heartbeats(root,events,entries,boundaries,stages=[stage for _,_,stage in schedule])
    fence=f.decode((root/'fence-request.gsw').read_bytes(),'wire','HEARTBEAT')
    active=[v for v in entries if v['request']['trace'] not in background['_traces'] and v['request']!=fence]
    results=[];traces={fence['trace']};rejected={};grant_replay=grants.Replay(getattr(derived[0],'grant_retirements',{}),allow_selected=True)
    before='before-network'
    for start,stop,stage in schedule:
        number=int(stage.split('-')[1]);install=stage.startswith('installed')
        if install:
            selected=f.decode((root/f'selected-{number}.gsr').read_bytes(),'records','SELECTED')
            result=nodes.activate(root,events,active,start,stop,identities,number,reconciled=number==3,
                before_stage='after-fence' if number==2 else before,
                observed_ballot=fence['ballot'] if number==2 else None,
                maintenance_replay=model.maintenance_network,grant_maintenance_replay=grant_replay,ancestry_replay=activation_ancestry)
            confirmations.installation_retention(events,start,stop,net.group(root,stage),selected)
        else:
            selected=f.decode(c.current(net.group(root,before)['node-1'])[1]['selected.gsr'],'records','SELECTED')
            voters=tuple(v['voter'] for v in selected['sources'])
            result=net.slot(root,events,active,start,stop,identities,number,before_stage=before,voters=voters,
                maintenance_replay=model.maintenance_network,background_events=background['_events'])
            unused=next(v for v in identities if v not in voters)
            files=net.group(root,before)[unused];members=c.current(files)[1]
            reason='retention intent inactive round' if 'selected.gsr' in members else 'retention intent installed selection required'
            rejected[result.pop('_rejected')]=(unused,reason)
        own=result.pop('_traces');need(not traces.intersection(own),'restart network fresh cross-phase traces');traces.update(own)
        results.append(result);before=stage
    grant_replay.complete()
    need(sum(v['exchanges'] for v in results)==len(active) and not traces.intersection(background['_traces']),
         'restart network full history coverage')
    # Preserve the stronger semantic failures before checking observational
    # send anchors; a moved/deleted force must not become a send-only negative.
    # Original contact raised the unused peer's volatile fence before the first
    # slot; absence cannot be hidden behind the diagnostic rejection string.
    first_unused=next(v for v in identities if v not in results[0]['voters'])
    begin=next(i for i,v in enumerate(events) if v['event']=='ROUND_SLOT_BEGIN')
    need(any(v['kind']=='HEARTBEAT' and v['request']['sender']['node']=='node-1' and
             v['request']['recipient']['node']==first_unused and v['offered']<begin for v in entries),
         'restart current unused peer contact before slot')
    attempted=sends(root,events,entries,identities)
    failures=n.read(root/'failures.json');counts=defaultdict(int)
    for row in failures:
        digest=row.get('request');counts[digest]+=1
        need(set(row)=={'node','kind','request','failure'} and digest in attempted,'restart original failure request')
        request=attempted[digest][0]
        need(row['node']==request['request']['recipient']['node'] and row['kind']==request['kind'] and counts[digest]<=len(attempted[digest]),
             'restart original failure owner/count')
        if digest in rejected:
            node,reason=rejected[digest]
            need(row['node']==node and row['kind']=='FUTURE_RETENTION_INTENT' and
                 row['failure']=='java.lang.IllegalArgumentException: '+reason,'restart network original rejection kind')
        else:
            # A nonselected former owner need not retain a renewed checkpoint.
            # Derive the exact requested missing record from this applied end;
            # only that failed lookup (and its ended identical retries) is allowed.
            q=request['request'];at=request['at'];matches=set()
            for start,stop,stage in schedule:
                if not(start<=at<stop and stage.startswith('published')):continue
                number=int(stage.split('-')[1]);files=net.group(root,f'applied-{number}')
                chosen=f.decode(c.current(files['node-1'])[1]['selected.gsr'],'records','SELECTED')
                voters={v['voter'] for v in chosen['sources']}
                lower=next(i for i in range(start+1,stop) if events[i]==dict(node='node-1',event='APPLY_ACK_DIRECTORY_FORCED'))
                upper=next(i for i in range(start+1,stop) if events[i]==dict(node='node-1',event='PUBLICATION_SELECTOR_FORCED'))
                for name,raw in files['node-1'].items():
                    if not name.startswith('applied-end/') or not name.endswith('statement.gsr'):continue
                    statement=f.decode(raw,'records','CHECKPOINT');peer=q['recipient']['node']
                    ack=f.encode('records','CHECKPOINT_ACK',dict(root=statement['root'],voter=peer,incarnation=identities[peer]['storage'],
                        cut=statement['end'],statement=e.digest(raw)))
                    if q['payload'].get('digest')==e.digest(ack):
                        expected=dict(root=statement['root'],view=e.authority(statement['root'],statement['end']['view']),
                            ballot=chosen['ballot'],sender=identities['node-1'],recipient=identities[peer],trace=q['trace'],sequence=1,
                            payload=dict(id=q['payload']['id'],action='REQUEST',offset=0,digest=e.digest(ack),bytes=''))
                        need(peer not in voters and q==expected and all(lower<=v['at']<upper for v in attempted[digest]),
                             'restart original missing checkpoint scope')
                        need(all(str(uuid.UUID(v))==v and uuid.UUID(v).int!=0 for v in (q['trace'],q['payload']['id'])) and
                             q['trace'] not in traces and q['trace'] not in background['_traces'],
                             'restart original missing checkpoint trace')
                        matches.add(ack)
            need(request['kind']=='CHUNK' and q['sequence']==1 and q['payload']['action']=='REQUEST' and q['payload']['offset']==0
                 and q['payload']['bytes']=='' and len(matches)==1 and row['failure']==('java.lang.IllegalArgumentException: '+
                    ('original forced record unavailable' if counts[digest]==1 else 'transfer trace already ended')),
                 'restart original missing checkpoint lookup')
    need(all(digest in counts for digest in rejected),'restart network bounded unused rejections')
    responded={e.digest(base64.b64decode(v['row']['request'],validate=True)) for v in entries}
    need(set(attempted)<=responded|set(counts),'restart unclassified silent send')
    need(all(counts[digest]==len(values) for digest,values in attempted.items() if digest not in responded),
         'restart original silent failure count')
    return dict(status='PASS',scope='one-native-automatic-two-session-history',originalFirst=True,physical=physical,
                phases=results,exchanges=len(entries),fullWireReplay=True,retentionSemantics='original-copy-confirmation',
                unusedSourcePulls=len({v['request']['trace'] for v in unused_requests(root,events,entries)}),
                declaredControlProfile=True,requestTimeoutMillis=30_000,phase3Complete=False,processRestart=False,publicRuntime=False,
                background={k:v for k,v in background.items() if not k.startswith('_')})


NEGATIVES=dict(current.NEGATIVES,**{
    'foreign-rejection':'restart original failure request',
    'control-profile':'automatic restart producer scope',
    'leadership-profile':'automatic restart producer scope',
    'send-missing':'restart original send inventory',
    'send-owner':'restart original send identity',
    'send-retries':'restart original send retries',
})


def negative_cases(original):
    cases=dict(NEGATIVES);count=original.get('unusedSourcePulls')
    need(type(count) is int and 0<=count<=3,'restart schedule derived unused sources')
    absent={}
    if count==0:
        del cases['unused-offer-bytes'];absent['unused-offer-bytes']='Original history contains no unused-source transfer.'
    return cases,absent


def mutate(root,name):
    if name in ('control-profile','leadership-profile'):
        value=n.read(root/'restart-result.json')
        if name=='control-profile':value['requestTimeoutMillis']=60_000
        else:value['leadershipPolicyMillis']=[30000,90000,150000,120000]
        (root/'restart-result.json').write_bytes(f.canonical(value));return
    if name.startswith('send-'):
        path=root/'restart-sends.json';rows=n.read(path)
        if name=='send-missing':rows.clear()
        elif name=='send-owner':
            kind,q=n.transfer.t.wire(rows[0]['bytes']);q['sender']=q['recipient']
            rows[0]['bytes']=base64.b64encode(f.encode('wire',kind,q)).decode()
        else:rows[0:0]=[dict(rows[0]) for _ in range(3)]
        path.write_bytes(f.canonical(rows));return
    if name=='unused-offer-bytes':
        events=n.read(root/'events.json');identities={node:n.future.identity(files) for node,files in net.group(root,'before-network').items()}
        value=unused_requests(root,events,net.x.exchanges(root,events,-1,len(events),identities))[0]
        rows=n.read(root/'wire.json');old=value['row']['response'];old_hash=e.digest(base64.b64decode(old))
        answer=dict(value['response'],payload=dict(value['response']['payload'],digest='0'*64))
        raw=f.encode('wire','SOURCE_OFFER',answer)
        for row in rows:
            if row['response']==old:row['response']=base64.b64encode(raw).decode()
        for row in events:
            if row['event'] in ('WIRE_RESPONSE','NETWORK_RECEIVED') and row['response']==old_hash:row['response']=e.digest(raw)
        (root/'wire.json').write_bytes(f.canonical(rows));(root/'events.json').write_bytes(f.canonical(events));return
    if name=='missing-parent-ack':
        rows=n.read(root/'wire.json');events=n.read(root/'events.json')
        digest=e.digest((root/'applied-2/node-1/applied-end/parent-ack.gsr').read_bytes())
        selected=f.decode((root/'selected-2.gsr').read_bytes(),'records','SELECTED');peer=selected['sources'][1]['voter']
        trace=next(n.transfer.t.wire(v['request'])[1]['trace'] for v in rows if
                   n.transfer.t.wire(v['request'])[0]=='CHUNK' and n.transfer.t.wire(v['request'])[1]['sender']['node']==peer
                   and n.transfer.t.wire(v['request'])[1]['payload']['digest']==digest)
        removed=[v for v in rows if n.transfer.t.wire(v['request'])[1]['trace']==trace]
        hashes={(e.digest(base64.b64decode(v['request'])),e.digest(base64.b64decode(v['response']))) for v in removed}
        rows=[v for v in rows if v not in removed]
        events=[v for v in events if not(v['event']=='WIRE_RESPONSE' and (v['request'],v['response']) in hashes)
                and not(v['event']=='NETWORK_RECEIVED' and any(v['response']==r for _,r in hashes))]
        (root/'wire.json').write_bytes(f.canonical(rows));(root/'events.json').write_bytes(f.canonical(events));return
    current.legacy_mutate(root,name)
