"""Independent event replay of the composed model, without importing its implementation.

The observer retains the whole audit history. Recovery decisions must use only
owned original packets/bases, whose compaction is checked against that history.
"""
from copy import deepcopy
import json
from .operation_oracle import next_state,membership,expected_receipt
from .transition_model import digest,encoded
from .recovery_oracle import safe
from .membership_model import NODES


def read(raw):
    value=json.loads(raw);safe(encoded(value)==raw,'noncanonical evidence');return value

def ballot(b):return (b['counter'],b['proposer'],b['storage']) if b else (0,'','')

def view(state):
    old=[r['voter'] for r in state['members']];new=old;operation=None
    if state['active'] is not None:
        row=state['results'][str(state['active'])]
        if row['phase']=='JOINT':new=[r['voter'] for r in row['request']['target']];operation=row['binding']
    return dict(root=state['root'],generation=state['generation'],old=old,new=new,operation=operation)

def quorum(v,names):
    safe(len(names)==len(set(names)) and set(names)<=set(v['old']+v['new']),'foreign/duplicate voters')
    safe(all(sum(n in v[k] for n in names)>len(v[k])//2 for k in ('old','new')),'missing governing majority')


class Observer:
    def __init__(self,record):
        safe(record['schema']=='gse-v53-composed-model-v1' and record['execution']=='deterministic-model-only' and record['runtimeQualified'] is False,'model execution scope')
        self.root=record['root'];self.initial=record['initial'];s=self.initial;membership(s['members'])
        safe(s==dict(root=self.root,members=s['members'],generation=0,configuration=digest(dict(root=self.root,generation=0,members=s['members'])),
             index=0,dataIndex=0,data=digest(dict(root=self.root,genesis=True)),nextOperation=1,retiredThrough=0,active=None,results={},identities=s['members']),'initial catalog')
        self.limits=record['limits'];safe(self.limits==dict(results=64,identities=512,changes=256,revisions=64,operations=2**63-2),'model limits')
        self.initial_cut=dict(index=0,entry=digest(dict(root=self.root,genesis=s)),view=view(s))
        base=dict(root=self.root,initial=deepcopy(s),catalog=deepcopy(s),cut=deepcopy(self.initial_cut),items=[],supplements=[],lastProof=None)
        self.nodes={n:dict(alive=True,session=1,counter=0,allocation=None,promise=None,fence=None,basis=None,pending=None,selected=None,
                          state=deepcopy(s),cut=deepcopy(self.initial_cut),base=deepcopy(base),journal=[],tail=None,proof=None,image=None,
                          checkpoint=None,retiring=None) for n in NODES}
        self.now=0;self.network={};self.exchanges={};self.last_message=0;self.delivered={};self.campaigns={};self.receipts=set();self.phased={};self.checkpoints={}
        self.original_bases={};self.certificates={};self.states={self.initial_cut['entry']:(deepcopy(s),deepcopy(self.initial_cut))}
        self.chain={};self.chosen={};self.publications=0;self.selections=0;self.deletions=0;self.capsules=0
    def identity(self,node):return dict(voter=node,storage='disk-'+node,endpoint=node+':9000')
    def live(self,node):safe(node in self.nodes and self.nodes[node]['alive'],'offline/foreign event');return self.nodes[node]
    def eligible(self,node):
        n=self.nodes[node];v=view(n['state']);safe(n['alive'] and node in set(v['old']+v['new']),'ineligible voter')
        safe(node in {r['voter'] for r in self.initial['members']} or (n['image'] is not None and (v['operation'] or node in {r['voter'] for r in n['state']['members']})),'unadmitted learner')
    def current(self,name):
        c=self.campaigns[name];n=self.live(c['ballot']['proposer'])
        safe(c['live'] and (c['ready'] or self.now<c['deadline']) and (c['proposal'] is None or self.now<c['requestDeadline']) and n['session']==c['session'] and n['promise']==n['fence']==c['ballot'],'fenced/deadline campaign event');return c
    def packet(self,node):
        n=self.nodes[node];return deepcopy(dict(base=n['base'],journal=n['journal'],catalog=n['state'],cut=n['cut']))
    def phase(self,rows,kind,ballot_value,entry_raw):
        entry=read(entry_raw);names=[]
        for raw in rows:
            row=read(raw);safe(raw in self.phased,'unforced phase receipt');node=row['node'];names.append(node)
            safe(row==dict(root=self.root,phase=kind,node=node,storage=self.identity(node)['storage'],ballot=ballot_value,entry=digest(entry),parent=entry['parent']),'wrong phased original identity')
        quorum(entry['parent']['view'],names)
    def cert(self,value):
        entry=read(value['entry']);parent=entry['parent'];safe(entry['root']==self.root and entry['index']==parent['index']+1 and parent['entry'] in self.states,'unknown certificate parent')
        before,known=self.states[parent['entry']];safe(parent==known,'certificate parent authority')
        for b in (entry['origin'],value['ballot']):
            who=next((r for r in before['identities'] if r['voter']==b['proposer']),None)
            safe(who is not None and who['storage']==b['storage'] and b['proposer'] in set(parent['view']['old']+parent['view']['new']) and 0<b['counter']<=2**63-2,'certificate ballot identity')
        safe(ballot(entry['origin'])<=ballot(value['ballot']),'original ballot above proof')
        self.phase(value['accepts'],'ACCEPT',value['ballot'],value['entry']);self.phase(value['proofs'],'PROOF',value['ballot'],value['entry'])
        return entry
    def checkpoint(self,item):
        s=item['statement'];start=s['start'];end=s['end'];safe(s['root']==self.root and start['entry'] in self.states and end['entry'] in self.states,'checkpoint unknown owned history')
        before,old=self.states[start['entry']];after,new=self.states[end['entry']]
        safe(start==old and end==new and end['index']>start['index'] and s['catalogBefore']==digest(before) and s['catalogAfter']==digest(after)
             and s['dataBefore']==before['data'] and s['dataAfter']==after['data'],'checkpoint exact state endpoints')
        chain=self.segment(start,end);names=[]
        for raw in item['acks']:
            ack=read(raw);safe(self.checkpoints.get(raw)==s,'unowned/wrong checkpoint statement');names.append(ack['node'])
        quorum(end['view'],names);return chain
    def segment(self,start,end):
        chain=[];head=end['entry']
        while head!=start['entry']:
            safe(head in self.chain and len(chain)<=64,'missing/divergent retained original history');entry=self.chain[head];chain.append(entry);head=entry['parent']['entry']
        return list(reversed(chain))
    def packet_valid(self,packet):
        base=packet['base'];safe(base['root']==self.root and base['initial']==self.initial,'foreign capsule genesis')
        at=self.initial_cut;previous=None;changes=0
        for item in base['items']:
            safe(item['statement']['start']==at,'capsule discontinuity');segment=self.checkpoint(item);end=item['statement']['end']
            if item['kind']=='range':safe(previous!='range' and at['view']==end['view'] and at['view']['operation'] is None and all(v['command']['kind'] not in ('INTENT','FINAL') for v in segment),'hidden membership boundary or adjacent range')
            else:
                safe(item['kind']=='membership' and len(segment)==1,'membership capsule interval');entry=self.cert(item['certificate']);safe(entry==segment[0] and entry['command']['kind'] in ('INTENT','FINAL'),'lost original membership certificate')
                state=self.states[at['entry']][0];row=state['results'][str(state['active'])];descriptor={k:row[k] for k in ('request','prepared','receipt')}
                safe(item.get('descriptor')==descriptor and digest(descriptor)==entry['command']['binding'],'missing original sealed descriptor')
                changes+=entry['command']['kind']=='INTENT'
            at=end;previous=item['kind']
        safe(base['cut']==at and self.states[at['entry']][0]==base['catalog'],'rewritten capsule catalog')
        if at['index']:
            safe(base['lastProof'] is not None and digest(self.cert(base['lastProof']))==at['entry'],'unbound capsule proof floor')
        else:safe(base['lastProof'] is None,'genesis proof')
        for supplement in base['supplements']:
            chain=self.checkpoint(supplement);s=supplement['statement'];safe(s['start']['view']==s['end']['view'] and not s['start']['view']['operation'] and all(e['command']['kind'] not in ('INTENT','FINAL') for e in chain),'supplement crosses membership')
        safe(len(base['supplements'])<=6 and changes<=256 and len(base['items'])<=3*changes+1,'capsule bounds')
        for cert in packet['journal']:
            entry=self.cert(cert);safe(entry['parent']==at and digest(cert) in self.certificates,'nonoriginal suffix certificate');at=self.states[digest(entry)][1]
        safe(packet['cut']==at and packet['catalog']==self.states[at['entry']][0],'wrong folded packet state');return at
    def apply_state(self,prior,entry):
        safe(view(prior)['operation'] is None or entry['command']['kind']=='FINAL','joint non-FINAL')
        state=next_state(prior,entry['command'],self.limits,self.receipts);end=dict(index=state['index'],entry=digest(entry),view=view(state));return state,end
    def selected(self,value,name):
        c=self.current(name);owners=value['owners'];safe(owners==sorted(set(owners)) and c['ballot']['proposer'] in owners,'missing proposer/ordered sources');quorum(c['view'],owners)
        safe(value['root']==self.root and value['ballot']==c['ballot'] and len(value['bases'])==len(owners),'selection identity')
        bases=[]
        for node,raw in zip(owners,value['bases']):
            n=self.live(node);safe(raw==n['basis'] and raw in self.original_bases and n['promise']==n['fence']==c['ballot'],'substituted original source')
            basis=read(raw);safe(basis['voter']==node and basis['packet']['cut']['view']==c['view'],'mixed source era');self.packet_valid(basis['packet']);bases.append(basis)
        high=max(bases,key=lambda b:b['packet']['cut']['index']);safe(value['packet']==high['packet'],'not longest original prefix');end=value['packet']['cut']
        for source in bases:self.segment(source['packet']['cut'],end)
        # The full audit knows ancestry, but a decision must also possess bounded source-side proof.
        base=value['packet']['base'];known={self.initial_cut['index']:self.initial_cut}
        known.update({i['statement']['end']['index']:i['statement']['end'] for i in base['items']})
        known.update({read(c['entry'])['index']:self.states[digest(read(c['entry']))][1] for c in value['packet']['journal']})
        for source in bases:
            lower=source['packet']['cut']
            if lower['index'] in known:safe(lower==known[lower['index']],'incompatible known anchor')
            else:
                supplement=[s for s in base['supplements'] if s['statement']['start']==lower];safe(len(supplement)==1 and supplement[0]['statement']['end'] in known.values(),'missing source-side frozen ancestry')
        tails=[b['tail'] for b in bases if b['tail'] and read(b['tail']['entry'])['index']>end['index']];carried=None
        if tails:
            highest=max(ballot(x['ballot']) for x in tails);same=[x for x in tails if ballot(x['ballot'])==highest]
            safe(len({x['entry'] for x in same})==1,'equal ballot conflict');carried=same[0]['entry'];safe(read(carried)['parent']==end,'carried tail parent')
        safe(value['carried']==carried,'wrong highest original tail')
    def step(self,e):
        kind=e['event']
        if kind=='clock':safe(type(e['amount']) is int and e['amount']>0 and e['time']==self.now+e['amount'],'virtual clock');self.now=e['time'];return
        safe(e['time']==self.now,'event clock drift')
        if kind=='allocate-stage':
            n=self.live(e['node']);self.eligible(e['node']);b=e['ballot'];safe(n['allocation'] is None and b==dict(counter=max(n['counter'],ballot(n['promise'])[0],ballot(n['fence'])[0])+1,proposer=e['node'],storage=self.identity(e['node'])['storage']) and b['counter']<=2**63-2,'allocator stage');n['allocation']=b
        elif kind=='allocate-force':
            n=self.live(e['node']);safe(n['allocation']==e['ballot'],'allocator force before stage');n['counter']=e['ballot']['counter']
        elif kind=='campaign':
            b=e['ballot'];n=self.live(b['proposer']);safe(n['allocation']==b and n['counter']==b['counter'] and e['campaign']==digest(b) and e['campaign'] not in self.campaigns,'unforced/reused campaign ballot')
            safe(e['view']==view(n['state']) and e['session']==n['session'] and e['deadline']>self.now,'campaign state/deadline')
            n['allocation']=None;self.campaigns[e['campaign']]=dict(ballot=b,view=e['view'],session=e['session'],deadline=e['deadline'],live=True,selected=None,carried=None,acks=set(),ready=False,proposal=None,requestDeadline=e['deadline'],accepts={},proofs={},certificate=None)
        elif kind=='send':
            body=e['body'];c=self.campaigns[body['campaign']];leader=self.live(c['ballot']['proposer']);key=digest({k:body[k] for k in ('campaign','kind','node','entry')})
            safe(e['message']==self.last_message+1 and e['key']==key and e['deadline']==body['requestDeadline']==(c['deadline'] if body['kind']=='PREPARE' else c['requestDeadline']) and c['live'] and leader['session']==c['session'] and self.now<e['deadline'],'send identity/deadline');self.last_message=e['message']
            previous=self.exchanges.get(key);safe(e['attempt']==(previous[0]+1 if previous else 1) and e['attempt']<=3 and (previous is None or previous[1]==body),'changed/exhausted retry')
            safe(body['ballot']==c['ballot'] and body['view']==c['view'],'request campaign binding')
            if body['kind']=='PREPARE':
                safe(body['entry'] is None and body['accepts']==[],'prepare data');safe(body['node']==c['ballot']['proposer'] or (leader['promise']==leader['fence']==c['ballot'] and leader['basis'] is not None),'remote prepare before own basis')
            else:
                self.current(body['campaign']);safe(c['selected'] and c['acks']==set(c['selected']['owners']) and body['node'] in c['selected']['owners'] and body['entry']==c['proposal'],'uninstalled vote request')
                safe(body['kind'] in ('ACCEPT','PROOF'),'unknown request')
                if body['kind']=='PROOF':self.phase(body['accepts'],'ACCEPT',c['ballot'],body['entry'])
                else:safe(body['accepts']==[],'accept with proof payload')
            self.exchanges[key]=(e['attempt'],deepcopy(body));self.network[e['message']]=deepcopy(body)
        elif kind=='drop':safe(e['message'] in self.network,'drop missing message');self.network.pop(e['message'])
        elif kind=='deliver':
            body=self.network.pop(e['message'],None);safe(body==e['body'],'unissued/changed delivery');self.live(body['node']);self.delivered[body['node']]=body
        elif kind=='observe':
            n=self.live(e['node']);b=e['ballot'];safe(any(c['ballot']==b for c in self.campaigns.values()) and ballot(b)>ballot(n['fence']),'unissued/nonadvancing ballot');n['fence']=b
            for c in self.campaigns.values():
                if c['ballot']['proposer']==e['node']:c['ready']=False
        elif kind=='grant-stage':
            n=self.live(e['node']);self.eligible(e['node']);body=self.delivered.get(e['node']);safe(body and body['kind']=='PREPARE' and body['ballot']==e['ballot'] and self.now<body['requestDeadline'],'grant lacks live request')
            safe(n['pending'] is None and n['fence']==e['ballot'] and view(n['state'])==body['view'] and n['promise']!=e['ballot'],'stale/busy grant');n['pending']=dict(kind='GRANT',ballot=e['ballot'])
        elif kind=='grant-force':
            n=self.live(e['node']);safe(n['pending']==dict(kind='GRANT',ballot=e['ballot']) and n['fence']==e['ballot'],'grant force fenced/unstaged');n.update(promise=e['ballot'],basis=None,pending=dict(kind='BASIS',ballot=e['ballot']))
        elif kind=='basis-force':
            node=e['node'];n=self.live(node);safe(n['pending']==dict(kind='BASIS',ballot=n['promise']) and n['fence']==n['promise'],'basis force before durable grant')
            expected=dict(root=self.root,voter=node,storage=self.identity(node)['storage'],ballot=n['promise'],basisId=digest(dict(ballot=n['promise'],node=node)),packet=self.packet(node),tail=n['tail'],proof=n['proof'])
            safe(read(e['basis'])==expected,'resampled/substituted basis state');self.packet_valid(expected['packet']);n['basis']=e['basis'];n['pending']=None;self.original_bases[e['basis']]=expected
        elif kind=='basis-reply':
            n=self.live(e['node']);body=self.delivered.get(e['node']);safe(body and body['kind']=='PREPARE' and body['ballot']==n['promise']==n['fence'] and e['basis']==n['basis'] and e['basis'] in self.original_bases,'nonoriginal duplicate basis')
        elif kind=='selection-stage':
            c=self.current(e['campaign']);n=self.nodes[c['ballot']['proposer']];safe(c['selected'] is None and n['pending'] is None,'selection changed/busy');self.selected(e['selected'],e['campaign']);n['pending']=dict(kind='SELECTED',campaign=e['campaign'],selected=e['selected'])
        elif kind=='selection-force':
            c=self.current(e['campaign']);n=self.nodes[c['ballot']['proposer']];safe(n['pending']==dict(kind='SELECTED',campaign=e['campaign'],selected=e['selected']),'unstaged selection force');c['selected']=deepcopy(e['selected']);c['carried']=c['selected']['carried'];n['pending']=None;self.selections+=1
        elif kind=='install-force':
            c=self.current(e['campaign']);n=self.live(e['node']);s=c['selected'];safe(s and e['node'] in s['owners'] and n['promise']==n['fence']==c['ballot'] and n['basis'] in s['bases'] and n['pending'] is None,'fenced/substituted source install')
            safe(e['selection']==digest(s) and e['packet']==s['packet'],'changed selected installation');self.packet_valid(e['packet']);self.replace_packet(n,e['packet']);n['selected']=e['selection']
        elif kind=='install-ack':
            c=self.current(e['campaign']);n=self.live(e['node']);safe(e['selection']==digest(c['selected'])==n['selected'] and n['promise']==n['fence']==c['ballot'],'ACK before original installation force');c['acks'].add(e['node'])
        elif kind=='propose':
            c=self.current(e['campaign']);n=self.nodes[c['ballot']['proposer']];entry=read(e['entry']);safe(c['selected'] and c['acks']==set(c['selected']['owners']) and c['proposal'] is None,'proposal before install/all ACKs')
            safe(entry['root']==self.root and entry['parent']==n['cut'] and entry['index']==n['cut']['index']+1,'proposal forced predecessor')
            self.apply_state(n['state'],entry)
            if c['ready']:safe(entry['origin']==c['ballot'] and view(n['state'])==c['view'] and not c['view']['operation'],'old round reused after boundary')
            elif c['carried'] is not None:safe(e['entry']==c['carried'],'recovery changed original tail')
            elif c['view']['operation']:safe(entry['command']==dict(kind='FINAL',number=n['state']['active'],binding=c['view']['operation']) and entry['origin']==c['ballot'],'wrong joint recovery')
            else:safe(entry['command']==dict(kind='BARRIER') and entry['origin']==c['ballot'],'service before fresh activation')
            safe(type(e['deadline']) is int and self.now<e['deadline'] and (c['ready'] or e['deadline']==c['deadline']),'entry deadline rebased activation')
            c.update(proposal=e['entry'],requestDeadline=e['deadline'],accepts={},proofs={},certificate=None)
        elif kind=='vote-stage':
            node=e['node'];n=self.live(node);self.eligible(node);body=e['body'];safe(self.delivered.get(node)==body,'vote stage lacks authentic request');c=self.campaigns[body['campaign']];entry=read(body['entry'])
            safe(body['kind'] in ('ACCEPT','PROOF') and n['pending'] is None and n['cut']==entry['parent'] and n['promise']==n['fence']==body['ballot'] and n['selected']==digest(c['selected']),'vote before installed parent or stale grant')
            self.apply_state(n['state'],entry)
            if n['tail'] and n['tail']['ballot']==body['ballot']:safe(n['tail']['entry']==body['entry'],'same ballot conflict')
            if body['kind']=='PROOF':self.phase(body['accepts'],'ACCEPT',body['ballot'],body['entry'])
            n['pending']=deepcopy(body)
        elif kind=='vote-force':
            n=self.live(e['node']);body=e['body'];entry=read(body['entry']);safe(n['pending']==body and n['promise']==n['fence']==body['ballot'] and n['cut']==entry['parent'],'force after fence or changed parent')
            self.apply_state(n['state'],entry);phase=body['kind']
            if phase=='PROOF':self.phase(body['accepts'],'ACCEPT',body['ballot'],body['entry'])
            raw=encoded(dict(root=self.root,phase=phase,node=e['node'],storage=self.identity(e['node'])['storage'],ballot=body['ballot'],entry=digest(entry),parent=entry['parent']))
            safe(e['receipt']==raw,'phase receipt rewrite');self.phased[raw]=deepcopy(body);n['pending']=None
            if phase=='ACCEPT':n['tail']=dict(ballot=body['ballot'],entry=body['entry'],receipt=raw);n['proof']=None
            else:n['proof']=raw
        elif kind=='vote-ack':
            c=self.current(e['campaign']);row=read(e['receipt']);safe(e['receipt'] in self.phased and row['node']==e['node'] and row['phase']==e['phase'] and row['ballot']==c['ballot'] and c['proposal'] and row['entry']==digest(read(c['proposal'])) and e['node'] in c['selected']['owners'],'late/foreign ACK')
            c['accepts' if e['phase']=='ACCEPT' else 'proofs'][e['node']]=e['receipt']
        elif kind=='certificate':
            c=self.current(e['campaign']);cert=e['certificate'];entry=self.cert(cert);safe(cert['entry']==c['proposal'] and cert['ballot']==c['ballot'],'certificate campaign')
            safe(cert['accepts']==[c['accepts'][n] for n in sorted(c['accepts'])] and cert['proofs']==[c['proofs'][n] for n in sorted(c['proofs'])],'certificate unreceived receipt')
            old=self.chosen.setdefault(entry['index'],digest(entry));safe(old==digest(entry),'two proven values at one index');self.certificates[digest(cert)]=deepcopy(cert);self.chain[digest(entry)]=entry;c['certificate']=deepcopy(cert)
        elif kind=='adoption-force':
            n=self.live(e['node']);cert=e['certificate'];self.cert(cert);safe(n['pending'] is None and digest(cert) in self.certificates and e['ballot']==cert['ballot'] and ballot(e['ballot'])>ballot(n['promise']),'unproven adoption floor')
            n['promise']=e['ballot'];n['basis']=None;n['selected']=None;safe(ballot(n['fence'])>=ballot(n['promise']),'adoption before volatile fence')
        elif kind=='prefix-force':
            n=self.live(e['node']);cert=e['certificate'];entry=self.cert(cert);safe(n['pending'] is None and entry['parent']==n['cut'] and digest(cert) in self.certificates and ballot(n['promise'])>=ballot(cert['ballot']),'prefix before parent/adoption/certificate')
            state,end=self.apply_state(n['state'],entry);safe(e['state']==state and e['cut']==end,'catalog not derived from original bytes')
            n.update(state=state,cut=end,tail=None,proof=None);n['journal'].append(deepcopy(cert));known=self.states.setdefault(end['entry'],(deepcopy(state),deepcopy(end)));safe(known==(state,end),'same entry changed state')
        elif kind=='published':
            c=self.current(e['campaign']);n=self.nodes[c['ballot']['proposer']];cert=e['certificate'];entry=read(cert['entry']);safe(cert==c['certificate'] and cert['entry']==c['proposal'] and n['cut']['entry']==digest(entry),'callback before exact local proof')
            ready=c['ready'] or (entry['command']['kind']=='BARRIER' and entry['origin']==c['ballot'] and c['carried'] is None)
            if entry['command']['kind'] in ('INTENT','FINAL'):ready=False;c['live']=False
            safe(e['ready']==ready,'recovered tail advertised READY');c.update(ready=ready,proposal=None,carried=None);self.publications+=1
        elif kind=='learner-force':
            n=self.live(e['node']);source=self.live(e['source']);state=source['state'];receipt=expected_receipt(state,state['active'])
            safe(receipt==e['receipt'] and receipt['identity']==self.identity(e['node']) and e['packet']==self.packet(e['source']) and receipt['prepared']['data']==state['data'] and receipt['prepared']['dataIndex']==state['dataIndex'],'stale/foreign learner materialization')
            safe(e['node'] not in {r['voter'] for r in self.initial['members']},'initial identity as learner');self.packet_valid(e['packet']);self.replace_packet(n,e['packet']);n['image']=deepcopy(receipt);self.receipts.add(digest(receipt))
        elif kind=='sync-force':
            n=self.live(e['node']);self.live(e['source']);safe(e['packet']==self.packet(e['source']) and n['pending'] is None,'nonoriginal/busy synchronization');self.packet_valid(e['packet']);self.segment(n['cut'],e['packet']['cut']);self.replace_packet(n,e['packet'])
        elif kind=='checkpoint-force':
            n=self.live(e['node']);self.eligible(e['node']);s=e['statement'];safe(s['end']==n['cut'] and s['catalogAfter']==digest(n['state']) and s['dataAfter']==n['state']['data'],'checkpoint before owned end application')
            before,prior=self.states[s['start']['entry']];safe(s['start']==prior and s['catalogBefore']==digest(before) and s['dataBefore']==before['data'],'checkpoint wrong original start');self.segment(s['start'],s['end'])
            safe(e['receipt']==encoded(dict(root=self.root,node=e['node'],storage=self.identity(e['node'])['storage'],statement=digest(s),cut=s['end'])),'wrong checkpoint receipt');self.checkpoints[e['receipt']]=deepcopy(s)
        elif kind=='generation-stage':
            n=self.live(e['node']);safe(n['pending'] is None and n['checkpoint'] is None and n['retiring'] is None and n['journal'],'generation busy/no suffix');base=e['base'];self.packet_valid(dict(base=base,journal=[],catalog=base['catalog'],cut=base['cut']));safe(base['catalog']==n['state'] and base['cut']==n['cut'],'generation cut changed');n['checkpoint']=deepcopy(base);self.capsules+=1
        elif kind=='selector-force':
            n=self.live(e['node']);safe(n['checkpoint']==e['base'] and e['old']==dict(base=n['base'],journal=n['journal']) and n['retiring'] is None,'selector before complete generation');n['base']=n['checkpoint'];n['checkpoint']=None;n['journal']=[];n['retiring']=dict(old=e['old'],floor=None,inventory=None)
        elif kind=='floor-force':
            n=self.live(e['node']);floor=e['floor'];safe(n['retiring'] and floor['root']==self.root and floor['cut']==n['base']['cut'] and floor['base']==digest(n['base']),'wrong durable floor');quorum(floor['cut']['view'],floor['owners'])
            for owner in floor['owners']:self.eligible(owner);safe(self.nodes[owner]['cut']==floor['cut'],'floor without exact durable copy')
            n['retiring']['floor']=deepcopy(floor)
        elif kind=='retirement-force':
            n=self.live(e['node']);safe(n['retiring'] and n['retiring']['floor'] and e['inventory']==digest(n['retiring']['old']),'retirement before forced floor');n['retiring']['inventory']=e['inventory']
        elif kind=='delete':
            n=self.live(e['node']);safe(n['retiring'] and n['retiring']['inventory']==e['inventory']==digest(n['retiring']['old']),'delete beyond forced retirement');n['retiring']=None;self.deletions+=1
        elif kind=='crash':
            node=e['node'];n=self.live(node);n.update(alive=False,pending=None,allocation=None,checkpoint=None)
            for c in self.campaigns.values():
                if c['ballot']['proposer']==node:c['live']=False;c['ready']=False
        elif kind=='restart':
            n=self.nodes[e['node']];safe(not n['alive'] and e['session']==n['session']+1,'restart identity');n.update(alive=True,session=e['session'],fence=deepcopy(n['promise']))
        elif kind=='abandon':self.campaigns[e['campaign']]['live']=False;self.campaigns[e['campaign']]['ready']=False
        else:safe(False,'unknown composed event: '+kind)
    def replace_packet(self,node,packet):
        proofs=([packet['base']['lastProof']] if packet['base']['lastProof'] else [])+packet['journal']
        safe(not proofs or ballot(node['promise'])>=max(ballot(c['ballot']) for c in proofs),'copy before certificate-derived adoption floor')
        node.update(base=deepcopy(packet['base']),journal=deepcopy(packet['journal']),state=deepcopy(packet['catalog']),cut=deepcopy(packet['cut']))
        if node['tail'] and read(node['tail']['entry'])['index']<=node['cut']['index']:node['tail']=None;node['proof']=None


def check(record):
    observer=Observer(record)
    for event in record['events']:observer.step(event)
    return dict(events=len(record['events']),publications=observer.publications,selections=observer.selections,capsules=observer.capsules,deletions=observer.deletions,
                states={n:deepcopy(s['state']) for n,s in observer.nodes.items()},ready=sorted(k for k,c in observer.campaigns.items() if c['ready'] and c['live']))
