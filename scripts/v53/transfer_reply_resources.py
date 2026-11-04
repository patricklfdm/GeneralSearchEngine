"""Derive live PROMISE reply charges from original files and exact TCP frames.

This checks observed boundaries, not a whole-runtime peak or publication reserve.
The enclosing reply reader first verifies the complete physical/protocol history.
"""
import base64
from copy import deepcopy
from . import transfer_fault_evidence as t

f,c,need=t.f,t.c,t.need
SCHEMA='gse-v53-transfer-reply-resources-v1'
EMPTY=dict(metadata=0,staging=0,queued=0,leases=0,counts={})
WIRE=('BEFORE_REQUEST_WRITE','AFTER_REQUEST_READ','BEFORE_RESPONSE_WRITE','AFTER_RESPONSE_READ')


def same(actual,expected,reason):
    need(f.canonical(actual)==f.canonical(expected),'reply resources '+reason)


def baseline(files,basis):
    prefix,members,packet=c.current(files)
    images={k:v for k,v in members.items() if k.endswith('.image')}
    need(len(images)==1,'reply resources single original image')
    source='sources/'+basis['basisId']+'/'
    expected={'source.gscp':members['source.gscp'],**images}
    need({k[len(source):]:v for k,v in files.items() if k.startswith(source)}==expected,
         'reply resources original source files')
    metadata=len(files[prefix+'generation.gsr'])+sum(len(v) for k,v in members.items() if not k.endswith('.image'))
    size=len(members['source.gscp']);image=sum(map(len,images.values()))
    return dict(metadata=34*1024*1024+metadata+size,staging=size+2*image,queued=0,leases=6,
                counts=dict(GENERATION=1,SOURCE=1,APPLICATION=2,JOURNAL=1,MISC=1))


def control(original,charges):
    need(all(type(n) is int and 0<n<=8*1024*1024 for n in charges),'reply resources control extent')
    value=deepcopy(original)
    if charges:value['counts']['CONTROL']=value['counts'].get('CONTROL',0)+len(charges)
    value['leases']+=len(charges);value['queued']+=sum(charges)
    need(value['counts'].get('CONTROL',0)<=256 and value['queued']<=64*1024*1024,
         'reply resources combined control capacity')
    return value


def session(record,reply,kind):
    if reply is None:return [32768]  # registry before the first admitted trace
    size=len(base64.b64decode(reply,validate=True))
    if kind=='TRANSFER_COMMIT':return [32768,32768+size]  # completed cache, no export/session
    return [32768,1024,record,32768,size]


def replay(observation,events,original,record,fault):
    need(type(observation) is dict and set(observation)=={'schema','rows'} and observation['schema']==SCHEMA and
         type(observation['rows']) is list and len(observation['rows'])<=1024,
         'reply resources observation shape')
    rows=observation['rows'];position=0;reply=None;kind=None;active=True;owner=original
    maxima=dict(server=0,client=0)
    def check(event,side,charges,label):
        nonlocal position
        need(position<len(rows),'reply resources exact boundary inventory')
        expected={k:event[k] for k in ('request','response') if k in event}
        expected.update(side=side,event='TRANSFER_BEFORE_REPLY' if event['event']=='MATERIALIZED' else event['event'])
        row=rows[position];position+=1
        need(type(row) is dict and set(row)==set(expected)|{'resources'},'reply resources boundary shape')
        same({k:v for k,v in row.items() if k!='resources'},expected,'exact boundary inventory')
        same(row['resources'],charges,label)
        maxima[side]=max(maxima[side],charges['queued'])
    for event in events:
        point=event['event']
        if point=='DRAINED':
            active=False
            if fault=='owner-close':owner=EMPTY
        elif point=='RESOURCES':same(event['baseline'],original,'original owner baseline')
        elif point in WIRE or point=='MATERIALIZED':
            q=len(base64.b64decode(event['request'],validate=True))
            a=len(base64.b64decode(event['response'],validate=True)) if 'response' in event else None
            if point=='BEFORE_REQUEST_WRITE':check(event,'client',control(EMPTY,[q]),'outgoing request charge')
            elif point=='AFTER_RESPONSE_READ':check(event,'client',control(EMPTY,[q,a]),'incoming reply charge')
            else:
                if point=='MATERIALIZED':
                    reply=event['response'];kind=t.exchange.wire(reply)[0]
                charges=session(record,reply,kind) if active else []
                charges=control(owner,charges+[q]+([a] if point=='BEFORE_RESPONSE_WRITE' else []))
                label={'AFTER_REQUEST_READ':'received request charge','MATERIALIZED':'materialized reply charge',
                       'BEFORE_RESPONSE_WRITE':'outgoing reply charge'}[point]
                check(event,'server',charges,label)
    need(position==len(rows),'reply resources exact boundary inventory')
    return dict(observations=position,maximumObservedQueued=maxima,
                physicalStorageBaselineDerived=True,observedControlChargesQualified=True,
                wholeRuntimePeakQualified=False,publicationCapacityQualified=False)
