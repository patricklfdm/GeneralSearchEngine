"""Finite composition of global grants, steady commands, catalogs and compacted recovery.

Abstract atomic forces and authentic identities, not a runtime implementation.
Packets contain canonical original bytes; protocol decisions cannot consult the
retained audit trace. Separate clocks/messages/stages/forces make fault cuts explicit.
"""
from copy import deepcopy
import json
from . import operation_model as op
from .membership_model import NODES,need
from .transition_model import digest,encoded

MAX=2**63-2
LIMITS=op.Limits(results=64,identities=512,changes=256,revisions=64)


def view(state):
    old=[r['voter'] for r in state['members']];new=old;binding=None
    if state['active'] is not None:
        row=state['results'][str(state['active'])]
        if row['phase']=='JOINT':new=[r['voter'] for r in row['request']['target']];binding=row['binding']
    return dict(root=state['root'],generation=state['generation'],old=old,new=new,operation=binding)


def quorum(v,nodes):
    values=list(nodes);unique=set(values)
    return len(values)==len(unique) and unique<=set(v['old']+v['new']) and all(len(unique&set(v[k]))>len(v[k])//2 for k in ('old','new'))


def order(ballot):return (ballot['counter'],ballot['proposer'],ballot['storage']) if ballot else (0,'','')
def read(raw):
    value=json.loads(raw);need(encoded(value)==raw,'noncanonical original bytes');return value

def cut(state,head):return dict(index=state['index'],entry=head,view=view(state))

class Group:
    def __init__(self,size=3):
        self.root='v53-composition-'+str(size);self.initial=op.initial(self.root,[op.identity(n) for n in NODES[:size]])
        initial_cut=cut(self.initial,digest(dict(root=self.root,genesis=self.initial)))
        base=dict(root=self.root,initial=deepcopy(self.initial),catalog=deepcopy(self.initial),cut=initial_cut,items=[],supplements=[],lastProof=None)
        self.nodes={n:dict(alive=True,session=1,counter=0,allocation=None,promise=None,fence=None,basis=None,pending=None,selected=None,
                          state=deepcopy(self.initial),cut=deepcopy(initial_cut),base=deepcopy(base),journal=[],tail=None,proof=None,image=None,
                          checkpoint=None,retiring=None) for n in NODES}
        self.events=[];self.now=0;self.network={};self.exchanges={};self.next_message=0;self.campaigns={}
        self.auth=set();self.receipts=set();self.checkpoints=set()

    def record(self,event,**data):self.events.append(dict(event=event,time=self.now,**deepcopy(data)))
    def tick(self,amount=1):
        need(type(amount) is int and amount>0,'clock advance');self.now+=amount;self.record('clock',amount=amount)
    def live(self,node):need(self.nodes[node]['alive'],'offline')
    def eligible(self,node):
        n=self.nodes[node];v=view(n['state'])
        if not n['alive'] or node not in set(v['old']+v['new']):return False
        if node in {r['voter'] for r in self.initial['members']}:return True
        # A new identity must first own its prepared image and full joint metadata.
        return n['image'] is not None and (v['operation'] is not None or any(r['voter']==node for r in n['state']['members']))
    def state(self,node='node-1'):return deepcopy(self.nodes[node]['state'])
    def packet(self,node):
        n=self.nodes[node]
        return deepcopy(dict(base=n['base'],journal=n['journal'],catalog=n['state'],cut=n['cut']))
    def current(self,campaign):
        c=self.campaigns[campaign];n=self.nodes[c['ballot']['proposer']]
        need(c['live'] and n['alive'] and n['session']==c['session'] and n['promise']==n['fence']==c['ballot'],'campaign fenced/offline')
        need(c['ready'] or self.now<c['deadline'],'campaign deadline')
        need(c['proposal'] is None or self.now<c['requestDeadline'],'entry deadline');return c
    def observe(self,node,ballot):
        self.live(node);n=self.nodes[node]
        if order(ballot)>order(n['fence']):
            n['fence']=deepcopy(ballot)
            for c in self.campaigns.values():
                if c['ballot']['proposer']==node:c['ready']=False
            self.record('observe',node=node,ballot=ballot)
    def allocate(self,node):
        self.live(node);n=self.nodes[node];need(self.eligible(node) and n['allocation'] is None,'allocator ineligible/busy')
        counter=max(n['counter'],order(n['promise'])[0],order(n['fence'])[0])+1;need(counter<=MAX,'ballot overflow')
        n['allocation']=dict(counter=counter,proposer=node,storage=op.identity(node)['storage']);self.record('allocate-stage',node=node,ballot=n['allocation'])
    def force_allocation(self,node):
        n=self.nodes[node];self.live(node);need(n['allocation'] is not None,'missing allocation')
        n['counter']=n['allocation']['counter'];self.record('allocate-force',node=node,ballot=n['allocation'])
    def start(self,node,deadline):
        self.live(node);n=self.nodes[node];ballot=n['allocation'];need(ballot is not None and n['counter']==ballot['counter'],'unforced allocation')
        need(type(deadline) is int and self.now<deadline,'campaign deadline');name=digest(ballot);need(name not in self.campaigns,'ballot reuse')
        n['allocation']=None;self.campaigns[name]=dict(ballot=ballot,view=view(n['state']),session=n['session'],deadline=deadline,live=True,
                                                       selected=None,carried=None,acks=set(),ready=False,proposal=None,requestDeadline=deadline,accepts={},proofs={},certificate=None)
        self.record('campaign',campaign=name,ballot=ballot,view=view(n['state']),deadline=deadline,session=n['session']);return name
    def send(self,campaign,kind,node):
        c=self.campaigns[campaign];leader=c['ballot']['proposer'];self.live(leader)
        deadline=c['deadline'] if kind=='PREPARE' else c['requestDeadline']
        need(c['live'] and kind in ('PREPARE','ACCEPT','PROOF'),'exchange unavailable');need(self.now<deadline,'exchange deadline')
        if kind=='PREPARE' and node!=leader:
            own=self.nodes[leader];need(own['promise']==own['fence']==c['ballot'] and own['basis'] is not None,'own basis before remote PREPARE')
        if kind!='PREPARE':
            self.current(campaign);need(c['selected'] is not None and c['acks']==set(c['selected']['owners']) and c['proposal'] is not None,'selected installation incomplete')
            need(node in c['selected']['owners'],'nonselected vote')
            if kind=='PROOF':need(quorum(read(c['proposal'])['parent']['view'],c['accepts']),'proof before accept quorum')
        body=dict(campaign=campaign,kind=kind,node=node,ballot=c['ballot'],view=c['view'],requestDeadline=deadline,entry=c['proposal'] if kind!='PREPARE' else None,
                  accepts=[c['accepts'][n] for n in sorted(c['accepts'])] if kind=='PROOF' else [])
        key=digest({k:body[k] for k in ('campaign','kind','node','entry')});need(key not in self.exchanges,'use identical bounded retry')
        self.exchanges[key]=dict(body=deepcopy(body),deadline=deadline,attempts=0);return self.retry(key)
    def retry(self,key):
        exchange=self.exchanges[key];c=self.campaigns[exchange['body']['campaign']];leader=c['ballot']['proposer'];self.live(leader)
        need(c['live'] and self.nodes[leader]['session']==c['session'] and order(c['ballot'])>=order(self.nodes[leader]['fence']),'retry abandoned/fenced campaign')
        need(exchange['attempts']<3 and self.now<exchange['deadline'],'exchange retry/deadline exhausted')
        exchange['attempts']+=1;self.next_message+=1;self.network[self.next_message]=deepcopy(exchange['body'])
        self.record('send',message=self.next_message,key=key,body=exchange['body'],attempt=exchange['attempts'],deadline=exchange['deadline']);return self.next_message
    def drop(self,message):need(message in self.network,'missing message');self.network.pop(message);self.record('drop',message=message)
    def deliver(self,message):
        need(message in self.network,'missing message');body=self.network.pop(message);node=body['node'];self.live(node);n=self.nodes[node]
        self.record('deliver',message=message,body=body)
        need(self.now<body['requestDeadline'],'late request');ballot=body['ballot'];kind=body['kind']
        need(self.eligible(node),'unadmitted voter');need(order(ballot)>=order(n['fence']),'stale promise');self.observe(node,ballot)
        if kind=='PREPARE':
            need(view(n['state'])==body['view'],'later/different governing view')
            if n['promise']==ballot:
                need(n['basis'] is not None,'grant without basis requires fresh ballot');self.record('basis-reply',node=node,basis=n['basis']);return
            # Grants exclude any unresolved force; a receive-side fence still stops that old force.
            need(n['pending'] is None,'writer busy');n['pending']=dict(kind='GRANT',ballot=ballot);self.record('grant-stage',node=node,ballot=ballot)
        else:
            c=self.campaigns[body['campaign']];need(n['promise']==n['fence']==ballot and n['selected']==digest(c['selected']),'wrong installed selection')
            entry=read(body['entry']);need(entry['parent']==n['cut'] and n['pending'] is None,'unforced/lagged parent or busy writer')
            self.command_state(n['state'],entry['command'])
            if n['tail'] is not None and n['tail']['ballot']==ballot:need(n['tail']['entry']==body['entry'],'same ballot conflicting value')
            if kind=='PROOF':self.phases(body['accepts'],'ACCEPT',ballot,body['entry'])
            n['pending']=deepcopy(body);self.record('vote-stage',node=node,body=body)
    def force_grant(self,node):
        self.live(node);n=self.nodes[node];pending=n['pending'];need(pending and pending['kind']=='GRANT','no grant stage')
        need(n['fence']==pending['ballot'],'grant fenced');n['promise']=pending['ballot'];n['basis']=None;n['pending']=dict(kind='BASIS',ballot=n['promise'])
        self.record('grant-force',node=node,ballot=n['promise'])
    def force_basis(self,node):
        self.live(node);n=self.nodes[node];need(n['pending'] and n['pending']['kind']=='BASIS' and n['promise']==n['fence'],'basis missing/fenced')
        value=dict(root=self.root,voter=node,storage=op.identity(node)['storage'],ballot=n['promise'],basisId=digest(dict(ballot=n['promise'],node=node)),
                   packet=self.packet(node),tail=deepcopy(n['tail']),proof=n['proof'])
        n['basis']=encoded(value);n['pending']=None;self.auth.add(digest(dict(kind='BASIS',node=node,bytes=n['basis'])))
        self.record('basis-force',node=node,basis=n['basis']);return n['basis']
    def prepare(self,campaign,node):
        message=self.send(campaign,'PREPARE',node);self.deliver(message)
        if self.nodes[node]['pending'] is not None:self.force_grant(node);self.force_basis(node)
        return self.nodes[node]['basis']
    def command_state(self,state,command):
        need(view(state)['operation'] is None or command['kind']=='FINAL','joint only admits FINAL')
        return op.apply(state,command,LIMITS,self.receipts)
    def phases(self,rows,phase,ballot,entry):
        voters=[];parent=read(entry)['parent']
        for raw in rows:
            row=read(raw);need(row==dict(root=self.root,phase=phase,node=row['node'],storage=op.identity(row['node'])['storage'],ballot=ballot,entry=digest(read(entry)),parent=parent),'foreign phased receipt')
            need(raw in self.auth,'unforced phased receipt');voters.append(row['node'])
        need(quorum(parent['view'],voters),'both phase majorities');return voters
    def verify_cert(self,cert,parent):
        entry=read(cert['entry']);need(entry['root']==self.root and entry['parent']==parent and entry['index']==parent['index']+1,'certificate parent')
        need(order(entry['origin'])<=order(cert['ballot']),'origin beyond proving ballot')
        self.phases(cert['accepts'],'ACCEPT',cert['ballot'],cert['entry']);self.phases(cert['proofs'],'PROOF',cert['ballot'],cert['entry']);return entry
    def verify_checkpoint(self,item,start,catalog_hash,data):
        statement=item['statement'];need(statement['root']==self.root and statement['start']==start and statement['catalogBefore']==catalog_hash and statement['dataBefore']==data,'checkpoint start')
        voters=[]
        for raw in item['acks']:
            ack=read(raw);need(raw in self.checkpoints and ack==dict(root=self.root,node=ack['node'],storage=op.identity(ack['node'])['storage'],statement=digest(statement),cut=statement['end']),'checkpoint ownership')
            voters.append(ack['node'])
        need(quorum(statement['end']['view'],voters),'checkpoint end authority')
    def verify_packet(self,packet):
        base=packet['base'];need(base['root']==self.root and base['initial']==self.initial,'packet root/genesis')
        need(len(base['supplements'])<=6 and len(base['items'])<=3*LIMITS.changes+1,'capsule bounds')
        changes=0;previous=None
        at=cut(self.initial,digest(dict(root=self.root,genesis=self.initial)));catalog_hash=digest(self.initial);data=self.initial['data'];anchors={at['index']:(deepcopy(at),catalog_hash,data)}
        for item in base['items']:
            self.verify_checkpoint(item,at,catalog_hash,data);s=item['statement'];end=s['end']
            need(end['index']>at['index'],'checkpoint not advancing')
            if item['kind']=='range':need(previous!='range' and at['view']==end['view'] and at['view']['operation'] is None,'hidden membership or adjacent range')
            else:
                need(item['kind']=='membership','capsule kind');entry=self.verify_cert(item['certificate'],at);command=entry['command'];descriptor=item['descriptor']
                need(command['kind'] in ('INTENT','FINAL') and command['binding']==digest(descriptor) and end['index']==at['index']+1 and end['entry']==digest(entry),'original membership boundary')
                expected=deepcopy(at['view']);target=[r['voter'] for r in descriptor['request']['target']]
                if command['kind']=='INTENT':need(expected['operation'] is None,'INTENT view');expected.update(new=target,operation=command['binding'])
                else:need(expected['operation']==command['binding'] and expected['new']==target,'FINAL view');expected.update(old=target,new=target,operation=None,generation=expected['generation']+1)
                need(end['view']==expected and s['dataAfter']==data,'membership successor/application')
                changes+=command['kind']=='INTENT'
            previous=item['kind']
            at=end;catalog_hash=s['catalogAfter'];data=s['dataAfter'];anchors[at['index']]=(deepcopy(at),catalog_hash,data)
        need(changes<=LIMITS.changes and len(base['items'])<=3*changes+1,'capsule change cardinality')
        if base['lastProof'] is not None:
            entry=self.verify_cert(base['lastProof'],read(base['lastProof']['entry'])['parent']);need(digest(entry)==at['entry'],'base proof floor identity')
        else:need(at['index']==0,'missing base last proof')
        state=deepcopy(base['catalog']);need(base['cut']==at and digest(state)==catalog_hash and state['data']==data,'complete base catalog')
        for cert in packet['journal']:
            entry=self.verify_cert(cert,at);state=self.command_state(state,entry['command']);at=cut(state,digest(entry));anchors[at['index']]=(deepcopy(at),digest(state),state['data'])
        need(packet['catalog']==state and packet['cut']==at,'packet folded state');return anchors
    def select(self,campaign,owners):
        c=self.current(campaign);need(c['selected'] is None and self.nodes[c['ballot']['proposer']]['pending'] is None,'selection already fixed or writer busy');owners=list(owners)
        need(owners==sorted(set(owners)) and c['ballot']['proposer'] in owners and quorum(c['view'],owners),'proposer-inclusive source quorum')
        bases=[]
        for node in owners:
            self.live(node);n=self.nodes[node];need(n['promise']==n['fence']==c['ballot'] and n['basis'] is not None,'original source unavailable')
            raw=n['basis'];basis=read(raw);need(basis['ballot']==c['ballot'] and basis['packet']['cut']['view']==c['view'],'mixed frozen era')
            need(digest(dict(kind='BASIS',node=node,bytes=raw)) in self.auth,'unforced basis');self.verify_packet(basis['packet']);bases.append(raw)
        parsed=[read(raw) for raw in bases];longest=max(parsed,key=lambda b:b['packet']['cut']['index']);packet=longest['packet'];anchors=self.verify_packet(packet)
        for basis in parsed:
            lower=basis['packet'];index=lower['cut']['index'];wanted=(lower['cut'],digest(lower['catalog']),lower['catalog']['data'])
            if index in anchors:need(anchors[index]==wanted,'incompatible proven source anchor')
            else:
                candidates=[x for x in packet['base']['supplements'] if x['statement']['start']==lower['cut']];need(len(candidates)==1,'unavailable original source ancestry')
                bridge=candidates[0];self.verify_checkpoint(bridge,*wanted);s=bridge['statement'];need(s['end']['index'] in anchors and anchors[s['end']['index']]==(s['end'],s['catalogAfter'],s['dataAfter']) and s['start']['view']==s['end']['view'] and s['start']['view']['operation'] is None,'bridge end/era')
        tails=[b['tail'] for b in parsed if b['tail'] and read(b['tail']['entry'])['index']>packet['cut']['index']];entry=None
        for tail in tails:
            candidate=read(tail['entry']);need(candidate['parent']==packet['cut'] and candidate['index']==packet['cut']['index']+1,'tail parent')
            if entry is None or order(tail['ballot'])>order(entry['ballot']):entry=tail
            elif order(tail['ballot'])==order(entry['ballot']):need(entry['entry']==tail['entry'],'equal ballot conflict')
        selected=dict(root=self.root,ballot=c['ballot'],owners=owners,bases=bases,packet=packet,carried=entry['entry'] if entry else None)
        self.nodes[c['ballot']['proposer']]['pending']=dict(kind='SELECTED',campaign=campaign,selected=selected);self.record('selection-stage',campaign=campaign,selected=selected);return selected
    def force_selection(self,campaign):
        c=self.current(campaign);n=self.nodes[c['ballot']['proposer']];pending=n['pending'];need(pending and pending['kind']=='SELECTED' and pending['campaign']==campaign,'missing selection stage')
        c['selected']=deepcopy(pending['selected']);c['carried']=c['selected']['carried'];n['pending']=None;self.record('selection-force',campaign=campaign,selected=c['selected'])
    def install(self,campaign,node):
        c=self.current(campaign);n=self.nodes[node];self.live(node);selected=c['selected'];need(selected and node in selected['owners'] and n['promise']==n['fence']==c['ballot'],'install missing/fenced')
        need(n['basis'] in selected['bases'] and n['pending'] is None,'substituted basis or writer busy');packet=selected['packet'];self.verify_packet(packet)
        n.update(base=deepcopy(packet['base']),journal=deepcopy(packet['journal']),state=deepcopy(packet['catalog']),cut=deepcopy(packet['cut']),selected=digest(selected))
        # Covered tails remain in the original frozen basis; live next-slot state follows the installed proof.
        if n['tail'] and read(n['tail']['entry'])['index']<=n['cut']['index']:n['tail']=None;n['proof']=None
        self.record('install-force',campaign=campaign,node=node,packet=packet,selection=digest(selected))
    def ack_install(self,campaign,node):
        c=self.current(campaign);n=self.nodes[node];self.live(node);need(n['promise']==n['fence']==c['ballot'] and n['selected']==digest(c['selected']),'unforced/fenced install ACK')
        c['acks'].add(node);self.record('install-ack',campaign=campaign,node=node,selection=n['selected'])
    def propose(self,campaign,command=None,*,deadline=None):
        c=self.current(campaign);leader=c['ballot']['proposer'];n=self.nodes[leader]
        need(c['selected'] and c['acks']==set(c['selected']['owners']) and c['proposal'] is None,'uninstalled/busy proposal')
        if not c['ready']:
            if c['carried'] is not None:raw=c['carried'];need(command is None,'must recover original tail')
            else:
                if c['view']['operation'] is not None:command=dict(kind='FINAL',number=n['state']['active'],binding=c['view']['operation'])
                else:need(command is None or command==dict(kind='BARRIER'),'activation must use fresh barrier');command=dict(kind='BARRIER')
                raw=encoded(dict(root=self.root,index=n['cut']['index']+1,parent=n['cut'],origin=c['ballot'],command=command))
        else:
            need(command is not None and view(n['state'])==c['view'] and c['view']['operation'] is None,'round/configuration unavailable')
            raw=encoded(dict(root=self.root,index=n['cut']['index']+1,parent=n['cut'],origin=c['ballot'],command=command))
        entry=read(raw);need(entry['parent']==n['cut'],'carried original predecessor');self.command_state(n['state'],entry['command'])
        deadline=(self.now+100 if deadline is None else deadline) if c['ready'] else c['deadline'];need(type(deadline) is int and self.now<deadline,'entry deadline')
        c.update(proposal=raw,requestDeadline=deadline,accepts={},proofs={},certificate=None);self.record('propose',campaign=campaign,entry=raw,deadline=deadline);return raw
    def force_vote(self,node):
        self.live(node);n=self.nodes[node];body=n['pending'];need(body and body['kind'] in ('ACCEPT','PROOF'),'missing staged vote')
        c=self.campaigns[body['campaign']];entry=read(body['entry']);need(n['promise']==n['fence']==body['ballot'] and n['cut']==entry['parent'],'force fenced/parent changed')
        self.command_state(n['state'],entry['command']);phase=body['kind']
        if phase=='PROOF':self.phases(body['accepts'],'ACCEPT',body['ballot'],body['entry'])
        raw=encoded(dict(root=self.root,phase=phase,node=node,storage=op.identity(node)['storage'],ballot=body['ballot'],entry=digest(entry),parent=entry['parent']))
        self.auth.add(raw);n['pending']=None
        if phase=='ACCEPT':n['tail']=dict(ballot=body['ballot'],entry=body['entry'],receipt=raw);n['proof']=None
        else:n['proof']=raw
        self.record('vote-force',node=node,body=body,receipt=raw)
        return raw
    def ack_vote(self,campaign,raw):
        c=self.current(campaign);row=read(raw);node=row['node'];phase=row['phase']
        need(raw in self.auth and c['proposal'] is not None and row['ballot']==c['ballot'] and row['entry']==digest(read(c['proposal']))
             and node in c['selected']['owners'],'late/foreign vote ACK')
        c['accepts' if phase=='ACCEPT' else 'proofs'][node]=raw;self.record('vote-ack',campaign=campaign,node=node,phase=phase,receipt=raw)
    def certify(self,campaign):
        c=self.current(campaign);need(c['proposal'] is not None,'no proposal')
        cert=dict(entry=c['proposal'],ballot=c['ballot'],accepts=[c['accepts'][n] for n in sorted(c['accepts'])],proofs=[c['proofs'][n] for n in sorted(c['proofs'])])
        self.verify_cert(cert,read(c['proposal'])['parent']);c['certificate']=cert;self.record('certificate',campaign=campaign,certificate=cert);return cert
    def apply(self,node,cert):
        self.live(node);n=self.nodes[node];need(n['pending'] is None,'apply writer busy');entry=self.verify_cert(cert,n['cut']);need(order(n['promise'])>=order(cert['ballot']),'prefix before adoption floor')
        state=self.command_state(n['state'],entry['command']);n['state']=state;n['cut']=cut(state,digest(entry));n['journal'].append(deepcopy(cert));n['tail']=None;n['proof']=None
        self.record('prefix-force',node=node,certificate=cert,state=state,cut=n['cut'])
    def publish(self,campaign):
        c=self.current(campaign);n=self.nodes[c['ballot']['proposer']];cert=c['certificate'];need(cert and n['cut']['entry']==digest(read(cert['entry'])),'publish before own prefix')
        entry=read(cert['entry']);fresh=entry['command']['kind']=='BARRIER' and entry['origin']==c['ballot'] and c['carried'] is None
        c['ready']=fresh or c['ready'];c['proposal']=None;c['carried']=None
        if entry['command']['kind'] in ('INTENT','FINAL'):c['ready']=False;c['live']=False
        self.record('published',campaign=campaign,certificate=cert,ready=c['ready'])
    def adopt_floor(self,node,cert):
        self.live(node);n=self.nodes[node];need(n['pending'] is None,'adoption writer busy')
        self.verify_cert(cert,read(cert['entry'])['parent']);ballot=cert['ballot']
        if order(ballot)>order(n['promise']):
            self.observe(node,ballot);n['promise']=deepcopy(ballot);n['basis']=None;n['selected']=None
            self.record('adoption-force',node=node,certificate=cert,ballot=ballot)
    def sync(self,node,source):
        self.live(node);self.live(source);n=self.nodes[node];packet=self.packet(source);anchors=self.verify_packet(packet)
        need(n['pending'] is None and n['state']['index']<=packet['cut']['index'],'sync busy/regression')
        if n['cut']['index'] in anchors:need(anchors[n['cut']['index']]==(n['cut'],digest(n['state']),n['state']['data']),'sync divergent prefix')
        else:
            bridges=[b for b in packet['base']['supplements'] if b['statement']['start']==n['cut']];need(len(bridges)==1,'sync ancestry unavailable')
            self.verify_checkpoint(bridges[0],n['cut'],digest(n['state']),n['state']['data'])
            end=bridges[0]['statement'];need(anchors.get(end['end']['index'])==(end['end'],end['catalogAfter'],end['dataAfter']),'sync bridge end')
        certificates=([packet['base']['lastProof']] if packet['base']['lastProof'] else [])+packet['journal']
        if certificates:self.adopt_floor(node,max(certificates,key=lambda c:order(c['ballot'])))
        n.update(base=deepcopy(packet['base']),journal=deepcopy(packet['journal']),state=deepcopy(packet['catalog']),cut=deepcopy(packet['cut']))
        if n['tail'] and read(n['tail']['entry'])['index']<=n['cut']['index']:n['tail']=None;n['proof']=None
        self.record('sync-force',node=node,source=source,packet=packet)
    def materialize(self,node,source):
        self.live(node);self.live(source);n=self.nodes[node];state=self.nodes[source]['state'];number=state['active'];receipt=op.receipt_for(state,number)
        need(receipt['identity']==op.identity(node) and receipt['prepared']['data']==state['data'] and receipt['prepared']['dataIndex']==state['dataIndex'],'learner stale image')
        need(node not in {r['voter'] for r in self.initial['members']},'not new learner')
        # Installing this image does not change the authority of its metadata prefix.
        packet=self.packet(source);self.verify_packet(packet)
        proofs=([packet['base']['lastProof']] if packet['base']['lastProof'] else [])+packet['journal']
        if proofs:self.adopt_floor(node,max(proofs,key=lambda c:order(c['ballot'])))
        n.update(base=deepcopy(packet['base']),journal=deepcopy(packet['journal']),state=deepcopy(packet['catalog']),cut=deepcopy(packet['cut']),image=deepcopy(receipt))
        self.receipts.add(digest(receipt));self.record('learner-force',node=node,source=source,receipt=receipt,packet=packet)
        return deepcopy(receipt)
    def checkpoint(self,start,end,catalog_before,catalog_after,data_before,data_after):
        statement=dict(root=self.root,start=start,end=end,catalogBefore=catalog_before,catalogAfter=catalog_after,dataBefore=data_before,dataAfter=data_after)
        owners=[n for n in NODES if self.nodes[n]['alive'] and self.nodes[n]['cut']==end and digest(self.nodes[n]['state'])==catalog_after and self.eligible(n)]
        need(quorum(end['view'],owners),'no applied end-view checkpoint majority');acks=[]
        for node in owners:
            raw=encoded(dict(root=self.root,node=node,storage=op.identity(node)['storage'],statement=digest(statement),cut=end))
            self.checkpoints.add(raw);acks.append(raw);self.record('checkpoint-force',node=node,statement=statement,receipt=raw)
        return dict(statement=deepcopy(statement),acks=acks)
    def compact_stage(self,node):
        self.live(node);n=self.nodes[node];need(n['pending'] is None and n['retiring'] is None and n['checkpoint'] is None and n['journal'],'compaction busy/no suffix')
        base=deepcopy(n['base']);items=base['items'];state=deepcopy(base['catalog']);at=deepcopy(base['cut']);supplements=[]
        position=0
        while position<len(n['journal']):
            cert=n['journal'][position];entry=self.verify_cert(cert,at);after=self.command_state(state,entry['command']);end=cut(after,digest(entry));kind=entry['command']['kind'];position+=1
            if kind not in ('INTENT','FINAL'):
                while position<len(n['journal']):
                    following=n['journal'][position]
                    if read(following['entry'])['command']['kind'] in ('INTENT','FINAL'):break
                    entry=self.verify_cert(following,end);after=self.command_state(after,entry['command']);end=cut(after,digest(entry));position+=1
            statement=self.checkpoint(at,end,digest(state),digest(after),state['data'],after['data'])
            if kind in ('INTENT','FINAL'):
                row=state['results'][str(state['active'])];item=dict(kind='membership',certificate=deepcopy(cert),descriptor={k:deepcopy(row[k]) for k in ('request','prepared','receipt')},**statement)
            else:
                item=dict(kind='range',**statement);supplements=[deepcopy(statement)]
                if items and items[-1]['kind']=='range':
                    prior=items.pop()['statement'];item=dict(kind='range',**self.checkpoint(prior['start'],end,prior['catalogBefore'],digest(after),prior['dataBefore'],after['data']))
            items.append(item);state=after;at=end
        new=dict(root=self.root,initial=deepcopy(self.initial),catalog=state,cut=at,items=items,supplements=supplements,lastProof=deepcopy(n['journal'][-1]))
        need(len(items)<=3*LIMITS.changes+1,'compacted item limit')
        self.verify_packet(dict(base=new,journal=[],catalog=state,cut=at));n['checkpoint']=new
        self.record('generation-stage',node=node,base=new)
    def force_selector(self,node):
        self.live(node);n=self.nodes[node];need(n['checkpoint'] is not None and n['retiring'] is None,'selector stage missing')
        old=dict(base=deepcopy(n['base']),journal=deepcopy(n['journal']));n['base']=n['checkpoint'];n['checkpoint']=None;n['journal']=[]
        n['retiring']=dict(old=old,floor=None,inventory=None);self.record('selector-force',node=node,base=n['base'],old=old)
    def force_floor(self,node):
        n=self.nodes[node];self.live(node);need(n['retiring'] is not None,'no retired generation')
        end=n['base']['cut'];owners=[peer for peer in NODES if self.nodes[peer]['alive'] and self.nodes[peer]['cut']==end and self.eligible(peer)]
        need(quorum(end['view'],owners),'floor lacks next majority');floor=dict(root=self.root,cut=end,owners=owners,base=digest(n['base']))
        n['retiring']['floor']=floor;self.record('floor-force',node=node,floor=floor)
    def force_retirement(self,node):
        n=self.nodes[node];self.live(node);need(n['retiring'] and n['retiring']['floor'],'retirement without floor')
        inventory=digest(n['retiring']['old']);n['retiring']['inventory']=inventory;self.record('retirement-force',node=node,inventory=inventory)
    def delete_retired(self,node):
        n=self.nodes[node];self.live(node);need(n['retiring'] and n['retiring']['inventory']==digest(n['retiring']['old']),'unforced deletion inventory')
        self.record('delete',node=node,inventory=n['retiring']['inventory']);n['retiring']=None
    def compact(self,node):
        self.compact_stage(node);self.force_selector(node);self.force_floor(node);self.force_retirement(node);self.delete_retired(node)
    def activate(self,node,owners,deadline=None):
        self.allocate(node);self.force_allocation(node);campaign=self.start(node,self.now+100 if deadline is None else deadline)
        self.prepare(campaign,node)
        for peer in owners:
            if peer!=node:self.prepare(campaign,peer)
        self.select(campaign,sorted(owners));self.force_selection(campaign)
        for peer in owners:self.install(campaign,peer);self.ack_install(campaign,peer)
        return campaign
    def commit(self,campaign,command=None,*,apply_to=None,compact=False):
        self.propose(campaign,command);c=self.campaigns[campaign]
        for phase in ('ACCEPT','PROOF'):
            for node in c['selected']['owners']:
                message=self.send(campaign,phase,node);self.deliver(message);self.ack_vote(campaign,self.force_vote(node))
        cert=self.certify(campaign)
        targets=apply_to if apply_to is not None else [n for n in NODES if self.nodes[n]['alive'] and (n in set(c['view']['old']+c['view']['new']) or (self.nodes[n]['image'] is not None and self.nodes[n]['state']['active'] is not None and n in {r['voter'] for r in self.nodes[n]['state']['results'][str(self.nodes[n]['state']['active'])]['request']['target']}))]
        for node in targets:
            self.adopt_floor(node,cert);self.apply(node,cert)
        self.publish(campaign)
        if compact:
            for node in targets:self.compact(node)
        return cert
    def crash(self,node):
        self.live(node);n=self.nodes[node];n['alive']=False;n['pending']=None;n['allocation']=None;n['checkpoint']=None
        for c in self.campaigns.values():
            if c['ballot']['proposer']==node:c['live']=False;c['ready']=False
        self.record('crash',node=node)
    def restart(self,node):
        n=self.nodes[node];need(not n['alive'],'restart live');n['alive']=True;n['session']+=1;n['fence']=deepcopy(n['promise']);self.record('restart',node=node,session=n['session'])
    def abandon(self,campaign):self.campaigns[campaign]['live']=False;self.campaigns[campaign]['ready']=False;self.record('abandon',campaign=campaign)
    def evidence(self):return deepcopy(dict(schema='gse-v53-composed-model-v1',root=self.root,initial=self.initial,limits=LIMITS.__dict__,execution='deterministic-model-only',runtimeQualified=False,events=self.events))
