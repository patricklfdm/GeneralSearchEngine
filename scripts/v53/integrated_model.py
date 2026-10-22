"""Operation/learner gates around real votes in the existing research adapter.

Fresh recovery ballots per command are deliberate in this reference schedule;
steady-state round reuse is a separate decision. No Java or public runtime imports.
"""
from copy import deepcopy

from . import activation_model as a
from . import activation_research as ar
from . import transition_model as t
from . import transition_research as tr
from . import operation_model as m
from .membership_model import NODES,need


class Group:
    def __init__(self,size=3,*,limits=m.Limits()):
        self.world=t.World(NODES[:size],root='v53-integrated')
        self.engine=a.Engine(self.world);self.offset=0;self.events=[];self.commands={};self.receipts=set()
        members=[m.identity(n) for n in self.world.initial]
        self.catalogs={n:m.Store(members,root=self.world.root,limits=limits) for n in NODES}
        self.initial=deepcopy(self.catalogs[NODES[0]].state);self.limits=limits
        self.images={};self.admitted=set(self.world.initial)

    def record(self,event,**values):self.events.append(dict(event=event,**deepcopy(values)))

    def flush(self):
        for event in self.engine.events[self.offset:]:self.record('activation',detail=event)
        self.offset=len(self.engine.events)

    def register(self,command):
        name=t.digest(command)
        need(name not in self.commands or self.commands[name]==command,'control digest collision')
        if name not in self.commands:self.commands[name]=deepcopy(command);self.record('command',digest=name,command=command)
        return name

    def entry(self,command,node):
        name=self.register(command);kind=command['kind'];state=self.catalogs[node].state
        if kind=='DATA':return t.Entry('DATA',payload=command['value'])
        if kind in ('INTENT','FINAL'):
            row=state['results'][str(command['number'])]
            return t.Entry(kind,command['binding'],tuple(x['voter'] for x in row['request']['target']))
        need(kind!='BARRIER','activation chooses barrier payload')
        return t.Entry('CONTROL',payload=name)

    def decode(self,entry,state):
        if entry.kind=='BARRIER':return dict(kind='BARRIER')
        if entry.kind=='DATA':return dict(kind='DATA',value=entry.payload)
        if entry.kind=='CONTROL':
            need(entry.payload in self.commands,'unavailable complete control bytes')
            command=self.commands[entry.payload]
            need(command['kind'] in ('RESERVE','PREPARE','READY','SEAL','CANCEL','RETIRE'),'control entry kind confusion')
            return deepcopy(command)
        need(entry.kind in ('INTENT','FINAL') and state['active'] is not None,'unbound membership entry')
        row=state['results'][str(state['active'])]
        need(tuple(x['voter'] for x in row['request']['target'])==entry.target,'membership target mismatch')
        return dict(kind=entry.kind,number=state['active'],binding=entry.operation)

    def apply_prefix(self,node):
        store=self.catalogs[node];chain=self.world.nodes[node].chain
        for cert in chain[store.state['index']:]:
            command=self.decode(t.Entry.read(cert.value),store.state)
            store.receipts=set(self.receipts);store.stage(command);store.force()
            if command['kind']=='FINAL':self.admitted.update(x['voter'] for x in store.state['members'])
            self.record('apply',node=node,certificate=cert,command=command,state=store.state)

    def can_vote(self,node):
        if not self.world.nodes[node].alive or not self.catalogs[node].alive or node not in self.world.authority(node).voters:return False
        state=self.catalogs[node].state
        if state['index']!=len(self.world.nodes[node].chain):return False
        if node in self.admitted:return True
        number=state['active']
        if number is None:return False
        row=state['results'][str(number)];image=self.images.get(node)
        return (row['phase']=='JOINT' and image is not None and row['receipt']==image and
                m.identity(node) in row['request']['target'])

    def synchronize(self):
        sources=[n for n in NODES if self.world.nodes[n].alive and (n in self.admitted or n in self.images)]
        need(bool(sources),'no live source')
        source=max(sources,key=lambda n:len(self.world.nodes[n].chain));chain=self.world.nodes[source].chain
        for node in sources:
            if self.world.nodes[node].chain!=chain:self.engine.sync(node,chain);self.flush()
            self.apply_prefix(node)
        return source

    def begin(self,command=None,*,node=None,last=False):
        self.synchronize()
        if node is None:node=next((n for n in NODES if self.can_vote(n)),None)
        need(node is not None and self.can_vote(node),'ineligible command proposer')
        state=self.catalogs[node].state
        requested=None
        if command is not None:
            m.apply(state,command,self.limits,self.receipts)  # proposal validation before allocating
            requested=self.entry(command,node)
        observed=max((x.fence for x in self.engine.roots.values() if x.fence),default=None)
        self.engine.allocate(node,observed);self.engine.force_allocation(node)
        handle=self.engine.start(node,requested);self.flush()
        # A removed proposer may not belong to any globally minimal joint quorum
        # (5 -> 4). Add its mandatory local basis before minimizing WITH that
        # constraint; otherwise a healthy removed leader cannot finish FINAL.
        family={frozenset(q)|{node} for q in tr.quorums(handle[0])}
        candidates=sorted(tuple(sorted(q)) for q in family if not any(p<q for p in family)
                          and all(self.can_vote(n) for n in q))
        need(bool(candidates),'no eligible configuration quorum');owners=candidates[-1 if last else 0]
        for peer in (node,)+tuple(n for n in owners if n!=node):
            need(self.can_vote(peer),'unadmitted PREPARE source');ar.prepare(self.engine,handle,peer);self.flush()
        return handle,owners

    def select(self,handle,owners):
        self.engine.select(handle,owners);self.engine.force_selection(handle);self.flush()
        chosen=t.Entry.read(self.engine.campaigns[handle].decision.value)
        for node in owners:
            command=self.decode(chosen,self.catalogs[node].state)
            m.apply(self.catalogs[node].state,command,self.limits,self.receipts)
        ar.installed(self.engine,handle,owners);self.flush()

    def exchange(self,handle,phase,owners,*,count=None):
        ids=self.engine.send(handle,phase,owners);self.flush()
        for number,message_id in enumerate(ids):
            if count is not None and number>=count:break
            model=self.world.slots[handle[0]];node=model.messages[message_id].voter
            need(self.can_vote(node),'unadmitted vote')
            m.apply(self.catalogs[node].state,self.decode(t.Entry.read(model.messages[message_id].value),self.catalogs[node].state),
                    self.limits,self.receipts)
            self.engine.deliver(handle,message_id);self.engine.force_vote(handle,node);self.flush()
            self.engine.deliver(handle,model.next_message);self.flush()

    def finish(self,handle):
        cert=self.engine.certify(handle);self.flush()
        self.engine.stage_publication(handle);self.flush();self.apply_prefix(handle[1].proposer)
        self.engine.published(handle);self.flush();self.synchronize()
        return cert

    def commit(self,command=None,*,node=None,last=False):
        handle,owners=self.begin(command,node=node,last=last);self.select(handle,owners)
        self.exchange(handle,'accept',owners);self.exchange(handle,'proof',owners)
        return self.finish(handle)

    def materialize(self,number=1):
        source=self.synchronize();state=self.catalogs[source].state;row=m.active(state,number)
        receipt=m.receipt_for(state,number);node=receipt['identity']['voter']
        need(node not in self.admitted and row['prepared']['dataIndex']==state['dataIndex'] and
             row['prepared']['data']==state['data'],'learner image base moved')
        self.images[node]=deepcopy(receipt)
        self.record('image-force',node=node,source=source,receipt=receipt,cut=len(self.world.nodes[source].chain))
        self.engine.sync(node,self.world.nodes[source].chain);self.flush();self.apply_prefix(node)
        need(m.receipt_for(self.catalogs[node].state,number)==receipt,'installed learner catalog mismatch')
        self.receipts.add(t.digest(receipt));self.record('receipt-force',node=node,receipt=receipt)
        return receipt

    def state(self):
        node=self.synchronize();return self.catalogs[node].state

    def crash(self,node):
        self.engine.crash(node);self.flush();self.catalogs[node].crash();self.record('catalog-crash',node=node)

    def restart(self,node):
        self.engine.restart(node);self.flush();self.catalogs[node].restart();self.record('catalog-restart',node=node)

    def evidence(self):
        self.flush()
        return dict(root=self.world.root,old=self.world.initial,initial=self.initial,limits=self.limits.__dict__,events=self.events)
