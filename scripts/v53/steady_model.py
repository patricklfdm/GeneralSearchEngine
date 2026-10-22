"""Stable-era round extension, seeded by an actually replayed activation.

Research only: authentic peers, atomic forces, no wall-clock lease. A selected
quorum stays fixed. Every extension still forces ACCEPT and PROOF separately.
"""
from copy import deepcopy

from . import activation_model as a
from . import activation_research as ar
from . import transition_model as t
from .membership_model import NODES, need


def bootstrap(size=3, last=False):
    engine=a.Engine(t.World(NODES[:size],root='steady-research'))
    handle=ar.begin(engine,NODES[0]);owners=ar.votes_for(engine,NODES[0],last)
    ar.selected(engine,handle,owners);need(ar.finish(engine,handle,owners),'activation failed')
    chain=engine.world.nodes[NODES[0]].chain
    for node in owners:
        if node!=NODES[0]:engine.sync(node,chain)
    return engine,handle,owners


class Round:
    def __init__(self,size=3,last=False):
        engine,handle,owners=bootstrap(size,last)
        self.seed=engine.evidence();self.ballot=handle[1];self.owners=tuple(owners)
        self.basis=deepcopy(engine.roots[NODES[0]].selections[self.ballot])
        view=engine.world.authority(NODES[0])
        self.views={n:view for n in owners};self.fences={n:self.ballot for n in owners}
        self.alive=set(owners);self.ready=True;self.dead=False;self.proposal=None;self.pending={}
        self.accepts={};self.proofs={};self.certificates={};self.events=[]

    def record(self,event,**values):self.events.append(dict(event=event,**values))

    def current(self,node):
        need(node in self.alive and self.fences[node]==self.ballot,'round fenced/offline')
        need(node!=self.ballot.proposer or not self.dead,'leader incarnation ended; fresh round required')

    def propose(self,entry):
        self.current(self.ballot.proposer)
        need(self.ready and self.proposal is None,'round not ready/busy')
        view=self.views[self.ballot.proposer]
        need(not view.operation and entry.kind in ('DATA','CONTROL','BARRIER','INTENT'),'stable round kind')
        t.successor(view,entry)
        self.proposal=(view,entry.value());self.record('propose',authority=view,value=entry.value())

    def stage(self,node,phase):
        self.current(node);need(node not in self.pending and self.proposal is not None,'writer busy/no proposal')
        view,value=self.proposal
        need(self.views[node]==view and phase in ('ACCEPT','PROOF'),'wrong predecessor/phase')
        key=(node,view.index)
        need(key not in self.accepts or self.accepts[key]==value,'same ballot changed value')
        if phase=='PROOF':
            need(view.quorum([n for (n,i),v in self.accepts.items() if i==view.index and v==value]),'proof before durable accept quorum')
        self.pending[node]=(phase,view,value);self.record('stage',node=node,phase=phase,authority=view,value=value)

    def force(self,node):
        self.current(node);need(node in self.pending,'missing vote stage')
        phase,view,value=self.pending.pop(node)
        need(self.views[node]==view,'force predecessor changed')
        (self.accepts if phase=='ACCEPT' else self.proofs)[node,view.index]=value
        self.record('force',node=node,phase=phase,authority=view,value=value)

    def certify(self):
        self.current(self.ballot.proposer);need(self.proposal is not None,'no proposal')
        view,value=self.proposal
        owners=tuple(n for (n,i),v in self.proofs.items() if i==view.index and v==value)
        need(view.quorum(owners),'no proof quorum')
        cert=dict(authority=view,value=value,owners=owners)
        self.certificates[view.index]=cert;self.record('certificate',certificate=cert);return cert

    def install(self,node,cert):
        self.current(node);view,value=cert['authority'],cert['value']
        need(self.certificates.get(view.index)==cert and self.views[node]==view,'uncertified/forked install')
        entry=t.Entry.read(value);after=t.successor(view,entry)
        from dataclasses import replace
        self.views[node]=replace(after,predecessor=t.digest(dict(authority=view,value=value)))
        if node==self.ballot.proposer and entry.kind=='INTENT':self.ready=False
        self.record('prefix-force',node=node,certificate=cert)

    def publish(self,cert):
        self.current(self.ballot.proposer)
        need(self.proposal==(cert['authority'],cert['value']) and self.views[self.ballot.proposer].index==cert['authority'].index+1,
             'publication before own prefix')
        self.proposal=None;self.record('published',certificate=cert)

    def commit(self,entry):
        self.propose(entry)
        for phase in ('ACCEPT','PROOF'):
            for node in self.owners:self.stage(node,phase);self.force(node)
        cert=self.certify()
        for node in self.owners:self.install(node,cert)
        self.publish(cert);return cert

    def observe(self,node,ballot):
        need(node in self.alive and ballot>self.fences[node],'fence not advancing')
        self.fences[node]=ballot
        if node==self.ballot.proposer:self.ready=False
        self.record('observe',node=node,ballot=ballot)

    def crash(self,node):
        need(node in self.alive,'already stopped');self.alive.remove(node);self.pending.pop(node,None)
        if node==self.ballot.proposer:self.ready=False;self.dead=True
        self.record('crash',node=node)

    def restart(self,node):
        need(node not in self.alive,'already running');self.alive.add(node)
        # This reference retains the conservative observed fence across restart;
        # a real volatile fence may fall back to the separately retained promise.
        self.record('restart',node=node)

    def evidence(self):return dict(seed=self.seed,events=self.events)
