"""Replay recovery evidence without consulting Store or live World state.

The transition oracle first checks the input execution. This observer then derives
the input cuts/acceptances from its journal and tracks durable bytes, selectors,
floors and retirement independently. Encoding and dataclass types are shared;
Store admission methods and AuthoritySource.validate are not called.
"""
from itertools import combinations

from . import ballot_model as b
from . import transition_model as t
from . import recovery_model as m
from .membership_model import NODES


def safe(condition, message):
    if not condition:
        raise b.SafetyViolation(message)


class Input:
    def __init__(self, root, voters, events):
        t.check_history(root,voters,events)
        self.root,self.voters=root,voters
        self.prefixes={n:() for n in NODES};self.promises={};self.accepted={}
        for event in events:
            if event['event']=='install-force':self.prefixes[event['node']]=event['chain']
            if event['event']=='slot':
                detail=event['detail']
                if detail['event']=='promise-force':
                    msg=detail['message'];key=(msg.voter,msg.context.index)
                    self.promises[key]=msg.ballot
                if detail['event']=='accept-force':
                    msg=detail['message'];key=(msg.voter,msg.context.index)
                    self.accepted[key]=(msg.context,msg.ballot,msg.value)

    def packet(self, packet):
        safe(packet.owner in self.prefixes and packet.generation in ('a-0','b-1','a-2'), 'unobserved packet owner/generation')
        chain=packet.chain
        safe(type(packet.snapshot) is tuple and type(packet.suffix) is tuple and
             chain==self.prefixes[packet.owner][:len(chain)], 'packet is not observed certified prefix')
        safe(len(chain)<=m.MAX_CERTIFICATES, 'oracle certificate capacity')
        old=new=self.voters;generation=0;operation=''
        parent=t.digest(dict(root=self.root,voters=self.voters))
        for cert in chain:
            entry=t.Entry.read(cert.value)
            if operation:old=new;operation=''
            elif entry.kind=='INTENT':new=entry.target;operation=entry.operation;generation+=1
            parent=cert.entry_id
        safe(generation<=m.MAX_CHANGES, 'oracle history capacity')
        view=t.Authority(self.root,len(chain)+1,parent,generation,old,new,operation)
        if packet.tail:
            tail=packet.tail
            safe(tail.owner==packet.owner and tail.authority==view and
                 self.accepted.get((packet.owner,view.index))==(view,tail.ballot,tail.value),
                 'unobserved packet tail')
        safe(sum(map(len,packet.files().values()))<=m.MAX_PACKET_BYTES,'oracle packet capacity')
        return view

    def check(self, events):
        safe(bool(events) and events[0]['event']=='init','missing recovery initial state')
        start=events[0];initial=start['packet'];view=self.packet(initial);owner=initial.owner
        safe(initial.chain==self.prefixes[owner] and initial.generation=='a-0','initial durable prefix')
        acceptance=self.accepted.get((owner,view.index))
        expected_tail=None if acceptance is None else m.Tail(owner,*acceptance)
        safe(initial.tail==expected_tail,'initial unresolved acceptance lost')
        promise=max((v for (n,_),v in self.promises.items() if n==owner),default=None)
        basis=m.raw(dict(promise=promise,prefix=tuple(c.entry_id for c in initial.chain),tail=initial.tail)).hex()
        safe(start['promise']==promise and start['basis']==basis,'initial promise/basis mismatch')
        packets={'a':initial};files={'a':initial.files()};selector='a'
        pending_selector=None;floor_plan=None;copies={};floor=None
        pending_retirement=None;retirement=None;reopens=0;deletes=0

        def active():
            safe(selector in files and files[selector]==packets[selector].files(),'incomplete selected bytes')
            packet=packets[selector]
            safe(packet.chain==initial.chain and packet.tail==initial.tail,'selected prefix/tail changed')
            return packet

        def floor_ready():
            safe(floor is not None and floor[0]==active().identity,'delete without durable floor')
            safe(all(copies.get(p.owner)==p.files() for p in floor[1]),'delete without complete sources')

        for event in events[1:]:
            kind=event['event']
            if kind=='begin':
                packet=event['packet'];self.packet(packet);slot=packet.generation[0]
                safe(packet.owner==owner and slot!=selector and slot not in files and retirement is None,
                     'reuse of owned generation slot')
                safe(packet.generation=={'a-0':'b-1','b-1':'a-2'}.get(active().generation),
                     'reused generation identity')
                safe(packet.chain==active().chain and packet.tail==active().tail,'checkpoint loses prefix/tail')
                packets[slot]=packet;files[slot]={}
            elif kind=='file-force':
                slot,name=event['slot'],event['name']
                safe(slot!=selector and slot in files and name in m.FILES and name not in files[slot], 'invalid generation force')
                if name=='seal':safe(set(files[slot])=={'snapshot','journal'},'early generation seal')
                data=packets[slot].files()[name];safe(event['data']==m.sha(data),'changed forced bytes')
                files[slot][name]=data
            elif kind=='selector-stage':
                slot=event['slot'];safe(slot!=selector and files.get(slot)==packets[slot].files(),'early selector')
                pending_selector=slot
            elif kind=='selector-force':
                safe(pending_selector==event['slot'] and pending_selector is not None,'unstaged selector force')
                selector=pending_selector;pending_selector=None;active()
            elif kind=='floor-stage':
                safe(floor_plan is None,'overlapping floor')
                plan=event['packets'];current=active();view=self.packet(current);owners=set()
                for packet in plan:
                    self.packet(packet)
                    safe(packet.chain==current.chain and packet.owner not in owners and packet.owner in view.voters,
                         'floor source prefix/identity')
                    owners.add(packet.owner)
                # Construct both majority families, independently of model quorum().
                family=(set(a)|set(c) for a in combinations(view.old,len(view.old)//2+1)
                        for c in combinations(view.new,len(view.new)//2+1))
                safe(any(q<=owners for q in family),'floor lacks configuration quorum')
                safe(current in plan,'floor lacks exact local packet');floor_plan=plan
            elif kind=='source-force':
                safe(floor_plan is not None,'unplanned source force')
                owner_id,name=event['owner'],event['name']
                matches=[p for p in floor_plan if p.owner==owner_id]
                safe(len(matches)==1 and name in m.FILES,'unplanned source identity')
                packet=matches[0];copied=copies.setdefault(owner_id,{})
                safe(name not in copied,'duplicate source force')
                if name=='seal':safe(set(copied)=={'snapshot','journal'},'early source seal')
                data=packet.files()[name];safe(event['data']==m.sha(data),'changed source bytes');copied[name]=data
            elif kind=='floor-force':
                safe(floor_plan is not None and all(copies.get(p.owner)==p.files() for p in floor_plan),
                     'floor force without complete copies')
                safe(event['active']==active().identity,'floor identity mismatch');floor=(event['active'],floor_plan)
            elif kind=='retirement-stage':
                floor_ready();slot=event['slot'];packet=event['packet']
                safe(retirement is None and slot!=selector and packets.get(slot)==packet and
                     files.get(slot)==packet.files(),'invalid retirement inventory')
                safe(packet.chain==active().chain and packet.tail==active().tail,'retirement loses acceptance')
                pending_retirement=(slot,packet)
            elif kind=='retirement-force':
                safe(pending_retirement is not None and pending_retirement[0]==event['slot'],'unstaged retirement force')
                retirement=pending_retirement;pending_retirement=None
            elif kind in ('delete-file','delete-directory'):
                floor_ready();safe(retirement is not None and retirement[0]==event['slot']!=selector,'unowned deletion')
                slot,packet=retirement
                safe(slot in files and all(data==packet.files().get(n) for n,data in files[slot].items()),'changed retirement bytes')
                if kind=='delete-file':
                    safe(event['name'] in files[slot],'unobserved deleted file');del files[slot][event['name']];deletes+=1
                else:
                    safe(not files[slot],'nonempty directory deletion');del files[slot]
            elif kind=='retirement-clear':
                safe(retirement is not None and retirement[0] not in files,'early retirement clear');retirement=None
            elif kind=='promise-force':
                safe(promise is None or event['ballot']>promise,'root promise regression');promise=event['ballot']
            elif kind=='crash':
                pending_selector=None;pending_retirement=None
                if floor is None:floor_plan=None;copies={}
            elif kind=='reopen':
                packet=active()
                safe(event['active']==packet.identity,'unforced selector visible after crash')
                safe(event['promise']==promise,'root promise changed at checkpoint')
                safe(event['basis']==basis,'frozen basis lost/changed')
                safe(event['tail']==initial.tail,'reopen dropped unresolved tail');reopens+=1
            else:raise b.SafetyViolation('unknown recovery event')
            active()
            size=sum(len(data) for rows in files.values() for data in rows.values())
            size+=sum(len(data) for rows in copies.values() for data in rows.values())+len(bytes.fromhex(basis))
            if retirement:size+=sum(map(len,retirement[1].files().values()))
            safe(size<=m.MAX_RETAINED_BYTES,'oracle retained capacity')
        safe(events[-1]['event']=='reopen' and reopens>0,'missing final recovery observation')
        return dict(events=len(events),reopens=reopens,deletedFiles=deletes)
