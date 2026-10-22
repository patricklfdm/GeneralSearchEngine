"""Chronological capsule observer; does not import catalog_capsule."""
from dataclasses import replace

from . import integrated_oracle as source
from . import transition_model as t
from .recovery_oracle import safe


def plain(value):
    import json
    return json.loads(t.encoded(value))


def check(record):
    original=record['input'];source.check(original)
    states={0:original['initial']};certs={};installed={};views={0:t.genesis(original['root'],original['old'])}
    for pos,e in enumerate(original['events'],1):
        if e['event']=='apply':
            i=e['state']['index'];states[i]=e['state'];certs[i]=e['certificate'];installed[e['node'],i]=pos
            views[i]=replace(t.successor(certs[i].authority,t.Entry.read(certs[i].value)),predecessor=certs[i].entry_id)
    pending={};durable=set();capsules=0;lastThrough=0
    for e in record['events']:
        through=e['through'];safe(type(through) is int and lastThrough<=through<=len(original['events']),'future/source watermark')
        lastThrough=through;kind=e['event']
        if kind in ('stage','force'):
            n=e['node'];s=e['statement'];start=s['start']['index']-1;end=s['after']['index']-1
            safe(start in states and end in states and start<end and s==dict(domain='v53-catalog-checkpoint/1',
                 start=plain(views[start]),after=plain(views[end]),catalogBefore=t.digest(states[start]),
                 catalogAfter=t.digest(states[end]),dataBefore=states[start]['data'],dataAfter=states[end]['data']),
                 'wrong checkpoint state')
            safe(n in views[end].voters and installed.get((n,end),through+1)<=through,'uninstalled endorser')
            if kind=='stage':safe(n not in pending,'checkpoint writer busy');pending[n]=s
            else:safe(pending.pop(n,None)==s,'endorsement before force');durable.add((n,t.digest(s)))
        elif kind=='crash':pending.pop(e['node'],None)
        elif kind=='capsule':
            p=e['packet'];safe(set(p)=={'root','initial','items','next','catalog'} and
                p['root']==original['root'] and p['initial']==states[0],'capsule root')
            at=0;changes=0;safe(len(p['items'])<=3*original['limits']['changes']+1,'capsule bound')
            for item in p['items']:
                s=item['statement'];end=s['after']['index']-1;owners=item['owners']
                safe(s['start']==plain(views[at]) and s['catalogBefore']==t.digest(states[at]) and
                     s['dataBefore']==states[at]['data'] and end in views and s['after']==plain(views[end]) and
                     s['catalogAfter']==t.digest(states[end]) and s['dataAfter']==states[end]['data'] and
                     len(set(owners))==len(owners) and views[end].quorum(owners) and
                     all((n,t.digest(s)) in durable for n in owners),'unendorsed/disconnected capsule')
                entries=[t.Entry.read(certs[i].value) for i in range(at+1,end+1)]
                if item['kind']=='range':
                    safe(set(item)=={'kind','statement','owners'} and end>at and not views[at].operation and
                         all(v.kind in ('DATA','CONTROL','BARRIER') for v in entries) and
                         all(getattr(views[at],k)==getattr(views[end],k) for k in ('root','generation','old','new','operation')),
                         'hidden membership boundary')
                else:
                    safe(item['kind']=='membership' and end==at+1 and entries[0].kind in ('INTENT','FINAL') and
                         item['certificate']==plain(certs[end]),'missing original membership proof')
                    row=states[at]['results'][str(states[at]['active'])]
                    safe(item['descriptor']=={k:row[k] for k in ('request','prepared','receipt')} and
                         t.digest(item['descriptor'])==entries[0].operation,'missing/changed operation descriptor')
                    changes+=entries[0].kind=='INTENT'
                at=end
            safe(changes<=original['limits']['changes'] and p['next']==plain(views[at]) and
                 p['catalog']==states[at],'wrong terminal catalog')
            capsules+=1
        else:safe(False,'unknown capsule event')
    return dict(capsules=capsules,events=len(record['events']),endorsements=len(durable))
