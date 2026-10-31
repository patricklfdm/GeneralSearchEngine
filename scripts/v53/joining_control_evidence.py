"""Original healthy ADD control exports and learner retention authority.

Requires the physical/network/export reader first; observations supply times,
never replacement grants, catalogs, ledgers, initialization or voting authority.
"""
import argparse
import base64
from collections import Counter
import json
from pathlib import Path
import shutil
import tempfile

from . import joining_export_evidence as exports

e=exports; n=e.n; f=e.f; disk=e.disk; need=e.need; sha=e.sha
init=e.p.init; learner=init.retention.learner
TRANSFER_SCHEMAS={'gse-v53-joining-intent-metadata/1.3':'intent',
                  'gse-v53-joining-preparation-hint/1.3':'preparation',
                  'gse-v53-joining-completion/1.3':'completion'}
RETENTION_FORCE=['LEARNER_RETENTION_'+v for v in ('BEFORE_WRITE','PREFIX_WRITTEN','WRITTEN','FORCED',
                 'CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED')]


def encoded(raw):return base64.b64encode(raw).decode()


def catalog(own):
    cap=own['packet']['capsule'];return f.decode(own['packet']['objects'][cap['catalog']],'records','CATALOG')


def reservation(own,reader,*,progress=False):
    state=catalog(own);view=state['cut']['view'];voters=set(view['old'])|set(view['new'])
    need(reader in state['identities'],'joining control permanent learner')
    rows=[v for v in state['results'] if v['request']['kind']!='REMOVE' and reader in v['request']['target']]
    if progress:
        rows=[v for v in rows if v['prepared'] is not None and reader['node'] not in v['prepared']['cut']['view']['old'] and
              v['phase'] in ('PREPARING','READY','SEALED','JOINT','COMPLETED','CANCELLED')]
    else:
        rows=[v for v in rows if v['request']['number']==state['active'] and v['phase'] in ('RESERVED','PREPARING','READY','SEALED')]
        need(view['operation'] is None and reader['node'] not in voters,'joining control active pre-joint learner')
    need(len(rows)==1,'joining control original reservation');return rows[0]


def alias(family,cap,joining,**fields):
    return sha(f.canonical(dict(schema='gse-v53-'+family+'-reference/1.3',root=cap['root'],joining=joining,cut=cap['cut'],**fields)))


def initial(values,own,*,learner_request=None):
    need(len(values)==1,'joining control singleton export')
    q=values[0]['offer']['request'];payload=q['payload'];cap=own['packet']['capsule']
    identities=n.s.catalog.identities(catalog(own)['identities']);proposer=identities.get(q['ballot']['proposer'])
    need(q['recipient']==own['identity'] and q['sender']==identities.get(q['sender']['node']) and
         proposer is not None and q['ballot']['incarnation']==proposer['storage'],'joining control permanent correlation')
    need(q['sequence']==1 and payload['action']=='REQUEST' and payload['offset']==0 and payload['bytes']=='',
         'joining control initial request')
    if learner_request is None:need(q['view']==n.s.catalog.authority(cap['root'],cap['cut']['view']),'joining control original view')
    else:
        need(q['view']==learner_request['expected'] and q['ballot']==dict(counter=1,proposer=q['sender']['node'],incarnation=q['sender']['storage']),
             'joining control original learner correlation')
    return q


def exact(values,reference,raw):e.exact(values,[(reference,raw,'RECORD')],'joining control exact original export')


def next_event(events,node,start,end,names):
    return min([end]+[at for at,row in enumerate(events) if at>start and row.get('node')==node and row['event'] in names])


def owner_lifetime(events,node,scope,lower,upper):
    starts=[at for at,v in enumerate(events) if v.get('node')==node and v.get('scope')==scope and v['event']=='CURRENT_VALIDATED']
    need(starts,'joining control original owner start');start=starts[0]
    ends=[at for at,v in enumerate(events) if at>start and v.get('node')==node and v['event']=='CURRENT_VALIDATED' and v.get('scope')!=scope]
    need(start<lower<=upper<(min(ends) if ends else len(events)),'joining control original owner lifetime')


def active_source(sources,events,own,lower,upper,*,unselected=False):
    node=own['node'];cap=own['packet']['capsule']
    candidates=[v for v in sources if v['node']==node and v['start']<lower]
    need(candidates,'joining control original active source');source=max(candidates,key=lambda v:v['start'])
    end=e.next_promise(events,node,source['start'],min(source['end'],own['end']))
    if unselected:end=next_event(events,node,source['start'],end,{'SELECTED_FORCED'})
    need(lower<=upper<end and source['value']['cut']==cap['cut'] and source['value']['view']==n.s.catalog.authority(cap['root'],cap['cut']['view']) and
         source['value']['accepted'] is None,'joining control active settled grant lifetime')
    return source


def joint(own,joining,*,exporter=False):
    cap=own['packet']['capsule'];view=cap['cut']['view'];ids=n.s.catalog.identities(catalog(own)['identities'])
    need(view['operation'] is not None and joining==ids.get(joining['node']) and joining['node'] not in view['old'] and joining['node'] in view['new'] and
         (own['node']==joining['node'] if exporter else own['node'] in view['old']),'joining control joint roles')


def fragment(source):
    value=source['value'];packet=source['packet'];r=init.retention
    peers=r.source(packet,value,0x47535250,65536)[0]
    retained=r.source(packet,value,0x47534c46,learner.MAXIMUM)[0]
    envelope=r.part(packet['capsuleBytes'])+r.part(packet['indexBytes'])
    return f.canonical(dict(basis=encoded(source['basis']),envelope=encoded(envelope),peers=encoded(peers),learner=encoded(retained)))


class Replay:
    def __init__(self,root):
        self.root=Path(root);self.model=n.s.Replay(root)
        for index in range(1,12):self.model.step(index)
        self.events=n.s.collection.read_json(self.root,'events.json',n.s.collection.EVENT_BYTES)
        wires=n.s.collection.read_json(self.root,'wire.json',n.s.collection.WIRE_BYTES)
        self.rows=n.causal(self.events,wires,n.s.catalog.identities(self.model.states[-1]['identities']),self.model.root)
        contents=[];n.transfers(self.rows,contents=contents);self.groups=e.sessions(contents)
        self.windows=e.generation_windows(root,self.events,self.model);self.sources=e.source_windows(root,self.events)
        self.phases=n.phase.blocks(self.events,self.model);self.recordings=[];self.confirmations={}

    def current(self,node,start,end):return e.current(self.windows,node,start,end)

    def root_export(self,values,own):
        row=reservation(own,values[0]['offer']['request']['sender']);q=initial(values,own,learner_request=row['request'])
        reference=sha(f.canonical(dict(schema='gse-v53-learner-root-reference/1.3',root=self.model.root,learner=q['sender'],request=row['request'])))
        exact(values,reference,self.model.root_bytes)

    def intent(self,values,own):
        row=reservation(own,values[0]['offer']['request']['sender']);q=initial(values,own,learner_request=row['request'])
        cap=own['packet']['capsule'];index=cap['cut']['index']+1;parts=self.model.phases[index-1]
        need(row['phase']=='SEALED' and f.decode(parts['ENTRY'],'records','ENTRY')['kind']=='INTENT','joining control original sealed INTENT')
        points=self.phases[index,own['node']];last=values[-1]['commit']['offered']
        end=e.next_promise(self.events,own['node'],points['APPLY_BEFORE_RETURN'],own['end'])
        need(points['APPLY_BEFORE_RETURN']<values[0]['offer']['received']<=last<end,'joining control pending INTENT lifetime')
        statement=f.encode('records','CHECKPOINT',self.model.checkpoint(index-1,index,'MEMBERSHIP'))
        records={k:encoded(parts[k]) for k in ('ENTRY','ACCEPT','PROOF','CERTIFICATE')}
        records.update(CATALOG=encoded(self.model.catalogs[index]),CHECKPOINT=encoded(statement))
        target=dict(cut=self.model.states[index]['cut'],catalog=sha(self.model.catalogs[index]),application=self.model.states[index]['application'])
        body=dict(schema='gse-v53-joining-intent-metadata/1.3',root=self.model.root,owner=own['identity'],learner=q['sender'],
                  request=row['request'],parent=disk.anchor(cap),target=target,records=records,payload=encoded(parts['PAYLOAD']))
        reference=sha(f.canonical(dict(schema='gse-v53-joining-intent-reference/1.3',root=self.model.root,learner=q['sender'],request=row['request'],cut=cap['cut'])))
        exact(values,reference,f.canonical(body))

    def preparation(self,values,own):
        q=initial(values,own);joining=q['sender'];joint(own,joining);first=values[0]['offer'];last=values[-1]['commit']['offered']
        local=active_source(self.sources,self.events,own,first['received'],last,unselected=True);ballot=local['value']['ballot']
        need(ballot['proposer']==own['node'],'joining control hint original proposer')
        cap=own['packet']['capsule'];sources=[]
        for node in cap['cut']['view']['old']:
            matches=[v for v in self.sources if v['node']==node and v['value']['ballot']==ballot and v['start']<first['received']]
            if not matches:continue
            peer=self.current(node,first['received'],last);held=active_source(self.sources,self.events,peer,first['received'],last)
            need(held==matches[0],'joining control hint original grant');sources.append(dict(node=node,basis=sha(held['basis'])))
            if node!=own['node']:
                received=[v for v in self.rows if v['kind']=='PREPARE' and v['request']['recipient']['node']==node and
                          v['request']['sender']['node']==own['node'] and v['request']['ballot']==ballot and
                          v['response']['payload']==dict(basis=sha(held['basis'])) and v['delivered']<first['received']]
                need(len(received)==1,'joining control hint before delivered grant')
        need(len(sources)>len(cap['cut']['view']['old'])//2,'joining control hint original old sources')
        body=dict(schema='gse-v53-joining-preparation-hint/1.3',root=self.model.root,cut=sha(f.canonical(cap['cut'])),joining=joining,ballot=ballot,sources=sources)
        exact(values,alias('joining-preparation',cap,joining),f.canonical(body))

    def retention(self,values,own):
        q=initial(values,own);joint(own,q['sender'])
        source=active_source(self.sources,self.events,own,values[0]['offer']['received'],values[-1]['commit']['offered'])
        exact(values,alias('joining-retention',own['packet']['capsule'],q['sender']),fragment(source))

    def completion(self,values,own):
        q=initial(values,own);cap=own['packet']['capsule'];joint(own,q['recipient'],exporter=True)
        first=values[0]['offer'];last=values[-1]['commit']['offered']
        need(q['sender']['node'] in cap['cut']['view']['old'],'joining control completion original old reader')
        initialized=[at for at,v in enumerate(self.events) if v.get('node')==own['node'] and v['event']=='JOINING_RETENTION_BEFORE_RETURN']
        need(len(initialized)==1 and initialized[0]<first['received']<=last<e.next_promise(self.events,own['node'],first['received'],own['end']),
             'joining control completion initialization/fence')
        scope={'initial-endpoint':'initial-owner','continuation-endpoint':'continuation-owner'}.get(self.events[first['received']].get('scope'))
        need(scope is not None,'joining control completion original endpoint')
        owner_lifetime(self.events,own['node'],scope,first['received'],last)
        recovery=[at for at,v in enumerate(self.events) if v.get('node')==own['node'] and v.get('scope')==scope and v['event']=='ACCEPT_ACTIVE_PARENT_FORCED']
        # The initial initializer forces all three ledgers before opening its
        # endpoint; continuation must finish its own retaining-owner recovery.
        if scope=='initial-owner':
            points=['LEARNER_RETENTION_RECOVERY_PARENT_FORCED','RETENTION_RECOVERY_PARENT_FORCED','FUTURE_RETENTION_RECOVERY_PARENT_FORCED']
            n.interval(self.events,own['node'],initialized[0],first['received'],points,'joining control completion ledger recovery',scope)
        else:need(len(recovery)==1 and recovery[0]<first['received'],'joining control completion ledger recovery')
        exact(values,alias('joining-completion',cap,q['recipient']),f.canonical(dict(schema='gse-v53-joining-completion/1.3',root=self.model.root,cut=cap['cut'],joining=q['recipient'])))

    def quorum(self):
        for row in self.rows:
            if row['kind']!='LEARNER_RETENTION_INTENT':continue
            q=row['request'];a=row['response'];owner=q['sender']['node'];peer=q['recipient']['node']
            own=self.current(owner,row['sent'],row['delivered']);remote=self.current(peer,row['received'],row['offered'])
            cap=own['packet']['capsule'];joining=q['payload']['learner'];request=reservation(own,joining)['request']
            ballot=f.decode(own['members']['promise.gsr'],'records','PROMISE')['ballot']
            expected=dict(selection=sha(own['members']['selected.gsr']),request=request,learner=joining,endpoint=disk.anchor(cap))
            need(q['payload']==expected and q['ballot']==ballot and ballot['proposer']==owner and
                 q['view']==n.s.catalog.authority(cap['root'],cap['cut']['view']) and remote['packet']['capsule']['cut']==cap['cut'],
                 'joining control retention original round')
            files=disk.inventory(self.root/remote['path']);offered=learner.offer(files,request,joining)[learner.FILE];state=learner.decode(offered)
            need(row['answer']=='LEARNER_RETENTION_ACK' and a['payload']==dict(intent=sha(f.canonical(expected)),revision=state['revision'],ledger=sha(offered)),
                 'joining control exact retention ACK')
            local_files=disk.inventory(self.root/own['path']);local=learner.offer(local_files,request,joining)[learner.FILE]
            need(local!=local_files[learner.FILE] and offered!=files[learner.FILE],'joining control original changed retention ledger')
            names=RETENTION_FORCE+['LEARNER_RETENTION_ACK_BEFORE_RETURN']
            n.interval(self.events,owner,own['start'],row['sent'],names,'joining control local retention force')
            n.interval(self.events,peer,row['received'],row['offered'],names,'joining control peer retention force')
            n.s.catalog.majority(cap['cut']['view'],sorted({owner,peer}))
            end=next_event(self.events,owner,own['start'],own['end'],{'PROMISE_FORCED','ACCEPT_VALIDATED'})
            need(row['delivered']<end,'joining control retention recording fenced')
            self.recordings.append(dict(node=owner,request=request,learner=joining,start=row['delivered'],end=end,cut=cap['cut']))
        need(len(self.recordings)==2,'joining control complete retention rounds')

    def heads(self):
        for row in self.rows:
            if row['kind']!='LEARNER_HEAD_QUERY':continue
            q=row['request'];a=row['response'];node=q['sender']['node'];own=self.current(node,row['sent'],row['delivered']);cap=own['packet']['capsule']
            operation=reservation(own,q['recipient'],progress=True);request=operation['request']
            need(operation['phase']=='JOINT' and q['recipient']['node']=='node-4' and self.events[row['received']].get('scope')=='retained-head',
                 'joining control original retained head')
            # This original retained owner is the sealed source, before INTENT.
            index=cap['cut']['index']-1
            endpoint=dict(cut=self.model.states[index]['cut'],catalog=sha(self.model.catalogs[index]),application=self.model.states[index]['application'])
            proof=dict(query=encoded(f.encode('wire',row['kind'],q)),ack=encoded(f.encode('wire',row['answer'],a)))
            need(learner.confirmation(proof,self.model.root,request,q['recipient'])==endpoint and row['answer']=='LEARNER_HEAD_ACK',
                 'joining control exact retained head')
            ready=[at for at,v in enumerate(self.events) if v.get('node')=='node-4' and v.get('scope')=='pending-intent' and v['event']=='LEARNER_JOINING_RETAIN_TRANSFERRED']
            need(len(ready)==1 and ready[0]<row['received'],'joining control head before retained handoff')
            names=RETENTION_FORCE+['LEARNER_RETENTION_CONFIRMATION_BEFORE_RETURN']
            finishes=[at for at,v in enumerate(self.events) if v.get('node')==node and v['event']==names[-1] and at>row['delivered']]
            need(finishes,'joining control head confirmation missing force');end=finishes[0]
            n.interval(self.events,node,row['delivered'],end+1,names,'joining control head confirmation force')
            files=disk.inventory(self.root/own['path']);confirmed=init.confirmed_learner(files[learner.FILE],proof,endpoint)
            init.transition.require_coverage(dict(files,**{learner.FILE:confirmed}))
            need(node not in self.confirmations,'joining control duplicate confirmed owner')
            self.confirmations[node]=dict(start=end,end=own['end'],request=request,learner=q['recipient'],plan=learner.decode(confirmed)['plan'])
        need(set(self.confirmations)=={'node-1','node-2'},'joining control complete original head confirmations')

    def learner_content(self,values,own):
        first=values[0]['offer'];q=first['request'];last=values[-1]['commit']['offered'];cap=own['packet']['capsule']
        progress=reservation(own,q['sender'],progress=cap['cut']['view']['operation'] is not None);request=progress['request']
        if cap['cut']['view']['operation'] is None:
            permits=[v for v in self.recordings if v['node']==own['node'] and v['cut']==cap['cut'] and v['request']==request and v['learner']==q['sender'] and
                     v['start']<first['offered']<=last<v['end']]
            need(len(permits)==1,'joining control learner export without live recording');return 'recorded'
        joint(own,q['sender']);permit=self.confirmations.get(own['node'])
        need(permit is not None and permit['start']<first['received']<=last<permit['end'] and permit['request']==request and permit['learner']==q['sender'],
             'joining control published learner original retention');return 'published'

    def run(self,prior):
        self.quorum();self.heads();controls=Counter();learners=Counter();used=set()
        for values in self.groups:
            first=values[0];kind=e.record_kind(first['raw']);body=json.loads(first['raw']) if first['raw'].startswith(b'{') else {}
            family='root' if kind=='ROOT' else TRANSFER_SCHEMAS.get(body.get('schema'))
            if set(body)=={'basis','envelope','peers','learner'}:family='retention'
            q=first['offer']['request'];candidates=[v for v in self.windows if v['node']==q['recipient']['node'] and v['start']<first['offer']['received']<=values[-1]['commit']['offered']<v['end']]
            if not candidates:
                need(family is None,'joining control missing original generation');continue
            own=self.current(q['recipient']['node'],first['offer']['received'],values[-1]['commit']['offered'])
            if family:
                getattr(self,'root_export' if family=='root' else family)(values,own);controls[family]+=1
                used.add((q['recipient']['node'],q['sender']['node'],q['trace']))
            elif e.learner_alias(own,q):learners[self.learner_content(values,own)]+=1
        need(controls==dict(root=1,intent=2,preparation=1,retention=2,completion=2),'joining control complete export families')
        need(used=={(v['owner'],v['reader'],v['trace']) for v in prior['unqualifiedSessions']},'joining control complete export coverage')
        need(learners==dict(recorded=4,published=2),'joining control complete learner authorization')
        return dict(status='PASS',scope='one-native-ADD-original-control-exports-and-learner-retention',controls=dict(controls),learnerSessions=dict(learners),
            retentionRounds=len(self.recordings),confirmedHeads=len(self.confirmations),observedContentSessions=sum(prior['boundSessions'].values())+len(used),
            observedCommittedContents=sum(prior['boundTransfers'].values())+prior['unqualifiedTransfers'],observedControlExportsQualified=True,
            observedLearnerRetentionQualified=True,allExportFamiliesQualified=False,completePhysicalQualified=False,forceAndNetworkQualified=False,
            processDeathQualified=False,phase3Complete=False)


def replay(root,prior=None):return Replay(root).run(e.replay(root) if prior is None else prior)


def validate(root):
    root=Path(root);before=n.s.collection.inventory(root);prior=e.validate(root);result=replay(root,prior)
    need(n.s.collection.inventory(root)==before,'joining control original changed');return result


NEGATIVES={
    'root-alias':'joining control exact original export',
    'intent-target':'joining control exact original export',
    'hint-source':'joining control exact original export',
    'fragment-wrapper':'joining control exact original export',
    'completion-cut':'joining control exact original export',
    'retention-ledger':'joining control exact retention ACK',
    'retention-revision':'joining control exact retention ACK',
    'peer-retention-force':'joining control peer retention force',
    'local-retention-force':'joining control local retention force',
    'late-recording':'joining control learner export without live recording',
    'head-before-handoff':'joining control head before retained handoff',
    'head-confirmation-force':'joining control head confirmation force',
    'completion-before-initialization':'joining control completion initialization/fence',
    'completion-closed-owner':'joining control original owner lifetime',
}


def mutate(root,name):
    root=Path(root);reader=Replay(root);events=reader.events
    wires=n.s.collection.read_json(root,'wire.json',n.s.collection.WIRE_BYTES)
    def replace(row,side,kind,value):
        old=sha(base64.b64decode(row[side]));raw=f.encode('wire',kind,value);row[side]=encoded(raw)
        for event in events:
            if event.get(side)==old:
                event[side]=sha(raw)
                if side=='request' and event['event'] in n.SENDS:event['bytes']=row[side]
    def family(values):
        raw=values[0]['raw']
        if e.record_kind(raw)=='ROOT':return 'root'
        if not raw.startswith(b'{'):return None
        body=json.loads(raw)
        return 'fragment' if set(body)=={'basis','envelope','peers','learner'} else TRANSFER_SCHEMAS.get(body.get('schema'))
    def group(kind):return next(v for v in reader.groups if family(v)==kind)
    if name in ('retention-ledger','retention-revision'):
        row=next(v for v in wires if n.wire(v['request'])[0]=='LEARNER_RETENTION_INTENT');kind,value=n.wire(row['response'])
        if name=='retention-ledger':value['payload']['ledger']='f'*64
        else:value['payload']['revision']+=1
        replace(row,'response',kind,value)
    elif name in ('peer-retention-force','local-retention-force','head-confirmation-force'):
        node='node-2' if name=='peer-retention-force' else 'node-1'
        lower=next(v['delivered'] for v in reader.rows if v['kind']=='LEARNER_HEAD_QUERY') if name=='head-confirmation-force' else -1
        event=next(v for i,v in enumerate(events) if i>lower and v.get('node')==node and v['event']=='LEARNER_RETENTION_FORCED')
        event['event']='REMOVED_RETENTION_FORCE'
    elif name=='late-recording':
        row=next(v for v in reader.rows if v['kind']=='LEARNER_RETENTION_INTENT');delivery=events[row['delivered']]
        first=next(v[0]['offer'] for v in reader.groups if v[0]['offer']['request']['sender']['node']=='node-4' and v[0]['offer']['received']<row['delivered']<v[0]['offer']['offered'])
        offer=events[first['offered']];events.remove(delivery);events.insert(events.index(offer)+1,delivery)
    elif name=='head-before-handoff':
        row=next(v for v in reader.rows if v['kind']=='LEARNER_HEAD_QUERY');response=events[row['offered']]
        transfer=next(v for v in events if v.get('node')=='node-4' and v['event']=='LEARNER_JOINING_RETAIN_TRANSFERRED')
        events.remove(transfer);events.insert(events.index(response)+1,transfer)
    elif name in ('completion-before-initialization','completion-closed-owner'):
        values=group('completion');q=values[0]['offer']['request']
        if name=='completion-before-initialization':
            rows=[v for v in reader.rows if v['request']['trace']==q['trace']]
            requests={v['requestHash'] for v in rows};responses={v['responseHash'] for v in rows}
            moving=[v for v in events if v.get('request') in requests or v.get('response') in responses]
            events=[v for v in events if v.get('request') not in requests and v.get('response') not in responses]
            at=next(i for i,v in enumerate(events) if v['event']=='JOINING_RETENTION_BEFORE_RETURN');events[at:at]=moving
        else:
            # A complete, later exchange cannot impersonate the initial closed
            # endpoint merely because the current generation still has the cut.
            values=[v for v in reader.groups if family(v)=='completion'][-1];trace=values[0]['offer']['request']['trace']
            hashes={v['requestHash'] for v in reader.rows if v['request']['trace']==trace}
            for v in events:
                if v.get('node')=='node-4' and v.get('request') in hashes and v.get('scope')=='continuation-endpoint':v['scope']='initial-endpoint'
    else:
        kind={'root-alias':'root','intent-target':'intent','hint-source':'preparation','fragment-wrapper':'fragment','completion-cut':'completion'}[name]
        values=group(kind);target=values[0];first=target['offer'];q=first['request']
        if name=='root-alias':
            row=next(v for v in wires if sha(base64.b64decode(v['request']))==first['requestHash']);wire_kind,value=n.wire(row['request'])
            value['payload']['digest']='f'*64;replace(row,'request',wire_kind,value)
        else:
            body=json.loads(target['raw'])
            if name=='intent-target':body['target']['catalog']='f'*64
            elif name=='hint-source':body['sources'][0]['basis']='f'*64
            elif name=='fragment-wrapper':body['learner']=('A' if body['learner'][0]!='A' else 'B')+body['learner'][1:]
            else:body['cut']['index']=8
            changed=f.canonical(body);need(len(changed)==len(target['raw']),'joining control fixed-extent mutation')
            for row in wires:
                rk,request=n.wire(row['request']);ak,response=n.wire(row['response'])
                if request['trace']!=q['trace'] or request['payload'].get('id')!=q['payload']['id']:continue
                if ak=='SOURCE_OFFER':response['payload']['digest']=sha(changed)
                elif ak=='CHUNK':
                    offset=request['payload']['offset'];size=len(base64.b64decode(response['payload']['bytes']))
                    request['payload']['digest']=sha(changed);response['payload'].update(digest=sha(changed),bytes=encoded(changed[offset:offset+size]))
                else:request['payload']['digest']=response['payload']['digest']=sha(changed)
                replace(row,'request',rk,request);replace(row,'response',ak,response)
    (root/'events.json').write_bytes(f.canonical(events));(root/'wire.json').write_bytes(f.canonical(wires))


def qualify(root):
    root=Path(root);original=validate(root);before=n.s.collection.inventory(root);results=[]
    protected={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-control-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            after=n.s.collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==protected and after['directories']==before['directories'],
                 'joining control negative changed physical inputs')
            n.network(changed);prior=e.replay(changed)
            try:replay(changed,prior)
            except ValueError as error:need(str(error)==reason,'joining unrelated control negative: '+name+': '+str(error))
            else:raise ValueError('joining control mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',networkAndExportPrecondition='PASS',reason=reason))
    need(n.s.collection.inventory(root)==before,'joining control negative changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
