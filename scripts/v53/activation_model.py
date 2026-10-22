"""Global promise/selection/activation adapter over the transition research model.

One fresh ballot per recovered slot. Prefix synchronization is explicit; mixed
prefixes do not silently form a recovery quorum. Atomic force and authentic
identities remain assumptions. No production GSE implementation is imported.
"""
from dataclasses import dataclass, field

from . import ballot_model as b
from . import transition_model as t
from .membership_model import NODES, need


def barrier(ballot):
    return t.Entry('BARRIER',payload='activation:'+t.digest(ballot))


@dataclass(frozen=True)
class Decision:
    authority: t.Authority
    ballot: b.Ballot
    bases: tuple
    value: str

    @property
    def identity(self):return t.digest(self)

    @property
    def owners(self):return tuple(row.voter for row in self.bases)


@dataclass
class Root:
    promise: b.Ballot | None = None
    authority: t.Authority | None = None
    fence: b.Ballot | None = None
    basis: b.Message | None = None
    counter: int = 0
    allocation: b.Ballot | None = None
    reserved: b.Ballot | None = None
    grant: tuple | None = None
    freezing: tuple | None = None
    selecting: Decision | None = None
    selections: dict = field(default_factory=dict)
    installing: Decision | None = None
    installed: dict = field(default_factory=dict)
    ready: b.Ballot | None = None


@dataclass
class Campaign:
    decision: Decision | None = None
    installed: set = field(default_factory=set)
    certificate: t.Certificate | None = None
    publication: bool = False
    alive: bool = True


class Engine:
    def __init__(self, world, *, mutant=None):
        need(mutant in (None,'volatile-allocator','resample-basis','ignore-global-promise',
                        'replace-selection','ready-after-recovery'), 'unknown activation mutant')
        t.check_history(world.root,world.initial,world.events)
        self.world,self.mutant=world,mutant
        self.input=list(world.events);self.offset=len(world.events);self.events=[]
        self.roots={node:Root() for node in NODES};self.campaigns={};self.used=set()
        for event in self.input:
            if event['event']!='slot':continue
            detail=event['detail']
            if detail['event']=='start':
                ballot=detail['ballot'];root=self.roots[ballot.proposer]
                root.counter=max(root.counter,ballot.counter)
            if detail['event']=='promise-force':
                msg=detail['message'];root=self.roots[msg.voter]
                if root.promise is None or msg.ballot>root.promise:
                    root.promise=root.fence=msg.ballot;root.authority=msg.context
                    root.basis=b.Message('prepare-ack',msg.voter,msg.ballot,msg.context,accepted=detail['accepted'])
        # Bootstrap assumes a verified prefix was adopted with its fencing floor.
        # This is not a PREPARE grant or permission to vote at that old ballot.
        for node,replica in world.nodes.items():
            if replica.chain:
                cert=max(replica.chain,key=lambda c:c.ballot);state=self.roots[node]
                if state.promise is None or cert.ballot>state.promise:
                    state.promise=state.fence=cert.ballot;state.authority=cert.authority;state.basis=None

    def record(self,event,**values):self.events.append(dict(event=event,**values))

    def flush(self):
        for event in self.world.events[self.offset:]:self.record('transition',detail=event)
        self.offset=len(self.world.events)

    def allocate(self,node,observed=None):
        root=self.roots[node]
        need(self.world.nodes[node].alive and root.allocation is None and root.reserved is None,'allocator busy/offline')
        highest=max((x.counter for x in (root.promise,root.fence,observed) if x is not None),default=0)
        ballot=b.Ballot(max(root.counter,highest)+1,node,'durable-'+node)
        root.allocation=ballot;self.record('allocate-stage',node=node,ballot=ballot,observed=observed)
        if self.mutant=='volatile-allocator':root.reserved=ballot
        return ballot

    def force_allocation(self,node):
        root=self.roots[node];need(root.allocation is not None,'missing allocation')
        root.counter=root.allocation.counter;root.reserved=root.allocation;root.allocation=None
        self.record('allocate-force',node=node,ballot=root.reserved)

    def start(self,node,requested=None):
        root=self.roots[node];ballot=root.reserved;authority=self.world.authority(node)
        need(self.world.nodes[node].alive and node in authority.voters,'ineligible proposer')
        need(self.world.nodes[node].pending_chain is None and root.grant is None and root.freezing is None,
             'campaign writer busy')
        need(ballot is not None and ballot not in self.used,'unforced/reused ballot')
        root.reserved=None;root.ready=None;self.used.add(ballot)
        if requested is None:
            requested=t.Entry('FINAL',authority.operation,authority.new) if authority.operation else barrier(ballot)
        t.successor(authority,requested)
        self.record('start',authority=authority,ballot=ballot,value=requested.value())
        self.world.slots.setdefault(authority,b.Model(authority)).start(ballot,requested.value())
        self.world.flush(authority);self.flush()
        handle=(authority,ballot);self.campaigns[handle]=Campaign();return handle

    def current(self,handle):
        authority,ballot=handle;root=self.roots[ballot.proposer]
        need(self.campaigns[handle].alive and self.world.nodes[ballot.proposer].alive and
             root.promise==root.fence==ballot and root.authority==authority,'campaign fenced/offline')
        return self.campaigns[handle]

    def observe(self,node,ballot):
        root=self.roots[node]
        if root.fence is None or ballot>root.fence:
            root.fence=ballot;root.ready=None
            self.record('observe',node=node,ballot=ballot)

    def prepare(self,handle,node):
        authority,ballot=handle;root=self.roots[node]
        if node!=ballot.proposer:
            own=self.roots[ballot.proposer]
            need(own.promise==ballot and own.basis is not None and own.basis.ballot==ballot,'own basis must precede remote prepare')
        need(self.world.nodes[node].alive and self.world.authority(node)==authority,'prepare requires synchronized prefix')
        need(root.grant is None and root.freezing is None and self.world.nodes[node].pending_chain is None and
             not any(slot.pending for slot in self.world.nodes[node].slots.values()),'writer busy')
        need(root.fence is None or ballot>=root.fence,'stale global prepare')
        self.observe(node,ballot)
        if root.promise==ballot:
            need(root.authority==authority,'same ballot changed authority')
            if root.basis is None and self.mutant!='resample-basis':
                raise ValueError('incomplete frozen basis; require fresh ballot')
        message_id=self.world.send(handle,'prepare',(node,))[0];self.flush()
        if root.promise==ballot and root.basis is not None:
            self.world.deliver(authority,message_id);self.flush();return 'DUPLICATE'
        root.grant=(authority,ballot,message_id)
        self.record('grant-stage',node=node,authority=authority,ballot=ballot)
        return 'STAGED'

    def force_grant(self,node):
        root=self.roots[node];need(root.grant is not None,'missing pending grant')
        authority,ballot,_=root.grant
        need(root.fence==ballot and self.world.authority(node)==authority,'grant fenced/view changed')
        root.promise=ballot;root.authority=authority;root.basis=None
        root.freezing=root.grant;root.grant=None
        self.record('grant-force',node=node,authority=authority,ballot=ballot)

    def force_basis(self,node):
        root=self.roots[node];need(root.freezing is not None,'missing basis stage')
        authority,ballot,message_id=root.freezing
        need(root.promise==root.fence==ballot and self.world.authority(node)==authority,'basis fenced/view changed')
        self.world.deliver(authority,message_id);self.world.force(authority,node)
        root.basis=self.world.slots[authority].voters[node].bases[ballot];root.freezing=None
        self.flush();self.record('basis-ready',node=node,basis=root.basis)

    def fetch(self,handle,node):
        authority,ballot=handle;root=self.roots[node];self.current(handle)
        need(self.world.nodes[node].alive and root.promise==root.fence==ballot and
             root.basis is not None and root.authority==authority,'frozen source unavailable')
        model=self.world.slots[authority]
        ids=[i for i,msg in model.messages.items() if msg==root.basis]
        need(bool(ids),'missing frozen source response')
        self.record('basis-fetch',node=node,basis=root.basis)
        self.world.deliver(authority,ids[0]);self.flush()

    def select(self,handle,owners):
        campaign=self.current(handle);authority,ballot=handle;root=self.roots[ballot.proposer]
        owners=tuple(owners)
        need(len(set(owners))==len(owners) and ballot.proposer in owners and authority.quorum(owners),'selection quorum/local basis')
        need(root.selecting is None and (ballot not in root.selections or self.mutant=='replace-selection'),'selection fixed for ballot')
        local=self.world.slots[authority].campaigns[ballot]
        need(set(owners)<=set(local.promises),'incomplete selected sources')
        bases=tuple(local.promises[n] for n in sorted(owners))
        local.promises={row.voter:row for row in bases}
        if campaign.decision is not None and self.mutant=='replace-selection':local.selected=None
        self.world.select(handle);self.flush()
        decision=Decision(authority,ballot,bases,local.selected)
        root.selecting=decision;self.record('selection-stage',decision=decision)
        return decision

    def force_selection(self,handle):
        campaign=self.current(handle);root=self.roots[handle[1].proposer]
        need(root.selecting is not None,'missing selected stage')
        decision=root.selecting;root.selections[handle[1]]=decision;root.selecting=None
        campaign.decision=decision;self.record('selection-force',decision=decision)

    def stage_install(self,handle,node):
        campaign=self.current(handle);decision=campaign.decision;root=self.roots[node]
        need(decision is not None and node in decision.owners,'install outside selected sources')
        need(self.world.nodes[node].alive and root.promise==root.fence==handle[1] and
             root.basis in decision.bases and root.authority==handle[0],'install source stale/substituted')
        need(root.installing is None,'install writer busy')
        root.installing=decision;self.record('install-stage',node=node,decision=decision)

    def force_install(self,node):
        root=self.roots[node];decision=root.installing
        need(decision is not None and root.promise==root.fence==decision.ballot,'installation fenced/missing')
        root.installed[decision.ballot]=decision;root.installing=None
        self.record('install-force',node=node,decision=decision)

    def install_ack(self,handle,node):
        campaign=self.current(handle);decision=campaign.decision;root=self.roots[node]
        need(self.world.nodes[node].alive and root.promise==root.fence==handle[1] and
             decision is not None and root.installed.get(handle[1])==decision,'installation ACK unavailable')
        campaign.installed.add(node);self.record('install-ack',node=node,decision=decision)

    def send(self,handle,phase,nodes):
        campaign=self.current(handle);decision=campaign.decision
        need(phase in ('accept','proof') and decision is not None and
             campaign.installed==set(decision.owners) and set(nodes)<=set(decision.owners),'incomplete selected installation')
        ids=self.world.send(handle,phase,tuple(nodes));self.flush();return ids

    def deliver(self,handle,message_id):
        authority,ballot=handle;msg=self.world.slots[authority].messages[message_id]
        if msg.kind.endswith('-ack'):self.current(handle)
        else:self.vote_allowed(msg)
        self.world.deliver(authority,message_id);self.flush()

    def vote_allowed(self,msg):
        root=self.roots[msg.voter]
        need(self.world.nodes[msg.voter].alive,'voter offline')
        if self.mutant!='ignore-global-promise':
            need(root.promise==root.fence==msg.ballot and root.authority==msg.context,'vote violates global promise')
        decision=root.installed.get(msg.ballot)
        need(decision is not None and decision.value==msg.value and decision.authority==msg.context,'vote lacks exact installation')

    def force_vote(self,handle,node):
        authority,_=handle;msg=self.world.slots[authority].voters[node].pending
        need(msg is not None,'no pending vote');self.vote_allowed(msg)
        self.world.force(authority,node);self.flush()

    def certify(self,handle):
        campaign=self.current(handle);campaign.certificate=self.world.certificate(handle);self.flush()
        return campaign.certificate

    def stage_publication(self,handle):
        campaign=self.current(handle);node=handle[1].proposer
        need(campaign.certificate is not None and not campaign.publication,'publication requires proof certificate')
        chain=self.world.nodes[node].chain+(campaign.certificate,)
        self.world.install(node,chain);self.world.force_install(node);self.flush()
        campaign.publication=True;self.record('publication-stage',ballot=handle[1],certificate=campaign.certificate)

    def published(self,handle):
        campaign=self.current(handle);ballot=handle[1];node=ballot.proposer
        need(campaign.publication,'no pending application publication')
        campaign.publication=False
        fresh=t.Entry.read(campaign.certificate.value)==barrier(ballot)
        ready=(fresh or self.mutant=='ready-after-recovery') and not self.world.authority(node).operation
        self.roots[node].ready=ballot if ready else None
        self.record('published',ballot=ballot,certificate=campaign.certificate,ready=ready)
        return ready

    def stage_sync(self,node,chain):
        root=self.roots[node]
        need(root.grant is None and root.freezing is None and root.installing is None and root.selecting is None,
             'sync writer busy')
        self.world.install(node,chain);self.flush()

    def force_adoption(self,node):
        chain=self.world.nodes[node].pending_chain;need(chain is not None,'missing staged prefix')
        root=self.roots[node]
        if chain:
            cert=max(chain,key=lambda c:c.ballot)
            if root.promise is None or cert.ballot>root.promise:
                self.observe(node,cert.ballot)
                root.promise=cert.ballot;root.authority=cert.authority;root.basis=None
                self.record('adoption-force',node=node,certificate=cert)

    def complete_sync(self,node):
        root=self.roots[node];chain=self.world.nodes[node].pending_chain
        need(chain is not None and all(root.promise is not None and c.ballot<=root.promise for c in chain),
             'prefix exceeds durable root promise')
        self.world.force_install(node);self.flush()
        root.ready=None;self.record('sync',node=node)

    def sync(self,node,chain):
        self.stage_sync(node,chain);self.force_adoption(node);self.complete_sync(node)

    def crash(self,node):
        root=self.roots[node]
        root.allocation=root.reserved=root.grant=root.freezing=root.selecting=root.installing=root.ready=None
        root.fence=root.promise
        for (_,ballot),campaign in self.campaigns.items():
            if ballot.proposer==node:campaign.alive=False;campaign.publication=False
        self.record('crash',node=node);self.world.crash(node);self.flush()

    def restart(self,node):
        self.world.restart(node);self.flush()
        root=self.roots[node];self.record('restart',node=node,promise=root.promise,counter=root.counter,ready=root.ready)

    def evidence(self):
        return dict(root=self.world.root,old=self.world.initial,input=self.input,events=self.events)
