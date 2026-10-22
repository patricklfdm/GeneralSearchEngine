"""Incremental metadata capsules over independently checked integrated histories.

New checkpoint endorsements bind application AND the complete operation catalog.
Membership certificates and their full sealed descriptors are never hidden in a
range. Endorsements are crash-fault identity receipts, not Byzantine signatures.
"""
from copy import deepcopy
from dataclasses import replace

from . import integrated_oracle
from . import transition_model as t
from .membership_model import need


def plain(value):
    import json
    return json.loads(t.encoded(value))


class Source:
    def __init__(self,record):
        integrated_oracle.check(record);self.input=record
        self.states={0:deepcopy(record['initial'])};self.certs={};self.applies={};self.views={0:t.genesis(record['root'],record['old'])}
        for pos,event in enumerate(record['events'],1):
            if event['event']!='apply':continue
            state=event['state'];index=state['index'];cert=event['certificate']
            need(index not in self.states or self.states[index]==state,'conflicting catalog input')
            self.states[index]=deepcopy(state);self.certs[index]=cert;self.applies[event['node'],index]=pos
            self.views[index]=replace(t.successor(cert.authority,t.Entry.read(cert.value)),predecessor=cert.entry_id)
        self.endorsed=set();self.pending={};self.events=[];self.through=len(record['events'])

    def statement(self,start,end):
        need(0<=start<end and start in self.states and end in self.states,'checkpoint range')
        return dict(domain='v53-catalog-checkpoint/1',start=plain(self.views[start]),after=plain(self.views[end]),
                    catalogBefore=t.digest(self.states[start]),catalogAfter=t.digest(self.states[end]),
                    dataBefore=self.states[start]['data'],dataAfter=self.states[end]['data'])

    def stage(self,node,statement):
        start=statement['start']['index']-1;end=statement['after']['index']-1
        need(statement==self.statement(start,end),'changed state endorsement')
        view=self.views[end]
        need(node in view.voters and node not in self.pending and
             self.applies.get((node,end),self.through+1)<=self.through,'endorser has no forced catalog at cut')
        self.pending[node]=deepcopy(statement)
        self.events.append(dict(event='stage',node=node,statement=deepcopy(statement),through=self.through))

    def force(self,node):
        need(node in self.pending,'missing checkpoint stage');statement=self.pending.pop(node)
        self.endorsed.add((node,t.digest(statement)))
        self.events.append(dict(event='force',node=node,statement=statement,through=self.through))

    def crash(self,node):
        self.pending.pop(node,None);self.events.append(dict(event='crash',node=node,through=self.through))

    def attest(self,statement):
        from .transition_research import quorums
        end=statement['after']['index']-1;owners=quorums(self.views[end])[0]
        for n in owners:self.stage(n,statement);self.force(n)
        return list(owners)

    def build(self,cut,previous=None):
        if previous is not None:
            self.verify(previous);need(previous['next']['index']-1<cut,'nonadvancing extension')
        items=[];position=0
        while position<cut:
            cert=self.certs[position+1];entry=t.Entry.read(cert.value)
            if entry.kind in ('INTENT','FINAL'):
                end=position+1;state=self.states[position];row=state['results'][str(state['active'])]
                descriptor={k:deepcopy(row[k]) for k in ('request','prepared','receipt')}
                item=dict(kind='membership',certificate=plain(cert),descriptor=descriptor)
            else:
                end=position+1
                while end<cut and t.Entry.read(self.certs[end+1].value).kind not in ('INTENT','FINAL'):end+=1
                item=dict(kind='range')
            statement=self.statement(position,end)
            item.update(statement=statement,owners=self.attest(statement));items.append(item);position=end
        packet=dict(root=self.input['root'],initial=deepcopy(self.states[0]),items=items,
                    next=plain(self.views[cut]),catalog=deepcopy(self.states[cut]))
        self.verify(packet);self.events.append(dict(event='capsule',packet=deepcopy(packet),through=self.through))
        # Reference builder re-reads the finite source. Production may reuse all
        # complete prior items; only a trailing stable range needs a fresh seal.
        return packet

    def verify(self,packet):
        need(set(packet)=={'root','initial','items','next','catalog'} and packet['root']==self.input['root'] and
             packet['initial']==self.states[0],'capsule root/catalog')
        limits=self.input['limits'];need(len(packet['items'])<=3*limits['changes']+1,'capsule capacity')
        view=plain(self.views[0]);catalog=t.digest(packet['initial']);data=packet['initial']['data'];changes=0
        for item in packet['items']:
            statement=item['statement'];after=statement['after'];owners=item['owners']
            need(set(statement)=={'domain','start','after','catalogBefore','catalogAfter','dataBefore','dataAfter'} and
                 statement['domain']=='v53-catalog-checkpoint/1' and statement['start']==view and
                 statement['catalogBefore']==catalog and statement['dataBefore']==data,'capsule continuity')
            end=after['index']-1
            authority=t.Authority(**dict(after,old=tuple(after['old']),new=tuple(after['new'])))
            need(plain(authority)==after and len(set(owners))==len(owners) and
                 authority.quorum(owners) and all((n,t.digest(statement)) in self.endorsed for n in owners),'checkpoint quorum')
            if item['kind']=='range':
                need(set(item)=={'kind','statement','owners'} and not view['operation'] and after['index']>view['index'] and
                     all(after[k]==view[k] for k in view if k not in ('index','predecessor')),'range changes authority')
            else:
                need(item['kind']=='membership' and set(item)=={'kind','certificate','descriptor','statement','owners'},'membership fields')
                cert=self.certs.get(end);need(cert is not None and plain(cert)==item['certificate'] and
                    plain(cert.authority)==view and after['index']==view['index']+1,'missing membership proof')
                entry=t.Entry.read(cert.value);descriptor=item['descriptor']
                need(entry.kind in ('INTENT','FINAL') and t.digest(descriptor)==entry.operation and
                     tuple(r['voter'] for r in descriptor['request']['target'])==entry.target,'incomplete sealed descriptor')
                changes+=entry.kind=='INTENT';need(changes<=limits['changes'],'change capacity')
            view=after;catalog=statement['catalogAfter'];data=statement['dataAfter']
        need(packet['next']==view and packet['catalog']['index']==view['index']-1 and
             t.digest(packet['catalog'])==catalog and packet['catalog']['data']==data,'terminal catalog binding')
        return view

    def evidence(self):return dict(input=self.input,events=self.events)
