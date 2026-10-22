"""Independent stable-round observer; no steady_model import."""
from dataclasses import replace

from . import activation_oracle as activation
from . import transition_model as t
from .recovery_oracle import safe


def check(record):
    seed=record['seed'];activation.check(seed)
    published=[e for e in seed['events'] if e['event']=='published']
    safe(len(published)==1 and published[0]['ready'],'seed must finish one fresh activation')
    event=published[0];ballot=event['ballot'];cert=event['certificate']
    selection=[e['decision'] for e in seed['events'] if e['event']=='selection-force']
    safe(len(selection)==1 and selection[0].ballot==ballot,'seed selection')
    owners=selection[0].owners;view=replace(t.successor(cert.authority,t.Entry.read(cert.value)),predecessor=cert.entry_id)
    safe(not view.operation and view.quorum(owners),'stable seed quorum')
    # No hidden post-activation fence/crash is allowed. Each selected source must
    # actually have forced the barrier prefix, not merely appear in its proof.
    safe(not any(e['event'] in ('crash','restart','adoption-force') for e in seed['events']),'seed lifecycle')
    for n in owners:
        observations=[e for e in seed['events'] if e['event']=='observe' and e['node']==n]
        safe(observations and observations[-1]['ballot']==ballot,'seed fence')
        installs=[e['detail'] for e in seed['events'] if e['event']=='transition' and
                  e['detail']['event']=='install-force' and e['detail']['node']==n]
        safe(installs and installs[-1]['chain']==(cert,),'seed source prefix')
    views={n:view for n in owners};fences={n:ballot for n in owners};alive=set(owners)
    pending={};accepts={};proofs={};certificates={};proposal=None;ready=True;dead=False;publications=0
    def current(node):safe(node in alive and fences[node]==ballot and (node!=ballot.proposer or not dead),'fenced/offline round event')
    def quorum(rows,authority,value):
        voters={n for (n,i),v in rows.items() if i==authority.index and v==value}
        return voters<=set(owners) and authority.quorum(voters)
    for e in record['events']:
        kind=e['event']
        if kind=='propose':
            current(ballot.proposer);authority=e['authority'];entry=t.Entry.read(e['value'])
            safe(ready and proposal is None and authority==views[ballot.proposer] and not authority.operation,
                 'unactivated/overlapping proposal')
            safe(entry.kind in ('DATA','BARRIER','CONTROL','INTENT'),'round entry kind');t.successor(authority,entry)
            proposal=(authority,e['value'])
        elif kind in ('stage','force'):
            n=e['node'];current(n);authority=e['authority'];value=e['value'];phase=e['phase']
            safe(n in owners and views[n]==authority and proposal==(authority,value) and phase in ('ACCEPT','PROOF'),
                 'vote outside fixed sources or predecessor')
            safe((n,authority.index) not in accepts or accepts[n,authority.index]==value,'same-ballot conflict')
            if phase=='PROOF':safe(quorum(accepts,authority,value),'proof without accept majority')
            item=(phase,authority,value)
            if kind=='stage':safe(n not in pending,'overlapping writer');pending[n]=item
            else:
                safe(pending.pop(n,None)==item,'force without matching stage')
                (accepts if phase=='ACCEPT' else proofs)[n,authority.index]=value
        elif kind=='certificate':
            current(ballot.proposer);c=e['certificate'];authority=c['authority'];value=c['value']
            safe(proposal==(authority,value) and quorum(proofs,authority,value) and
                 len(set(c['owners']))==len(c['owners']) and authority.quorum(c['owners']) and
                 all(proofs.get((n,authority.index))==value for n in c['owners']),'invalid proof certificate')
            certificates[authority.index]=c
        elif kind=='prefix-force':
            n=e['node'];current(n);c=e['certificate'];authority=c['authority'];value=c['value']
            safe(certificates.get(authority.index)==c and views[n]==authority,'unproven prefix/parent')
            entry=t.Entry.read(value);views[n]=replace(t.successor(authority,entry),predecessor=t.digest(dict(authority=authority,value=value)))
            if n==ballot.proposer and entry.kind=='INTENT':ready=False
        elif kind=='published':
            current(ballot.proposer);c=e['certificate']
            safe(proposal==(c['authority'],c['value']) and certificates.get(c['authority'].index)==c and
                 views[ballot.proposer].predecessor==t.digest(dict(authority=c['authority'],value=c['value'])),
                 'publication before certified own force')
            publications+=1;proposal=None
        elif kind=='observe':
            n=e['node'];safe(n in alive and e['ballot']>fences[n],'nonadvancing fence');fences[n]=e['ballot']
            if n==ballot.proposer:ready=False
        elif kind=='crash':
            n=e['node'];safe(n in alive,'duplicate crash');alive.remove(n);pending.pop(n,None)
            if n==ballot.proposer:ready=False;dead=True
        elif kind=='restart':safe(e['node'] not in alive,'restart live');alive.add(e['node'])
        else:safe(False,'unknown round event')
    return dict(events=len(record['events']),publications=publications,views=views,ready=ready)
