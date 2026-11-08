"""Bind an abandoned generation pull; its missing member never becomes content.

Only a response-less next-object request after complete committed objects is
admitted here. A real donor selector replacement must end the old export; the
physical export reader independently binds that boundary and exact byte prefix.
Mid-object loss, fabricated delivery and continuing the dead trace still fail.
"""
from collections import defaultdict
from . import connection_transcript as t

need=t.need


def session(request):
    return request['sender']['node'],request['recipient']['node'],request['trace']


def bind(events,result):
    rows=result['rows'];failed=result['failed'];groups=defaultdict(list);sends=defaultdict(list)
    for value in failed:
        if value['kind'] not in ('CHUNK','TRANSFER_COMMIT'):continue
        replies=[row for row in rows if row['sent']==value['sent']]
        if len(replies)==1 and replies[0].get('withheld',False):continue
        kind,request=t.wire(events[value['sent']]['bytes'])
        need(kind==value['kind']=='CHUNK' and not replies and not value['responseOffered'] and
             value['clientReason']=='IO' and value['serverReason']=='PROTOCOL' and
             type(value['received']) is int and type(value['serverFailed']) is int,
             'joining connection unqualified transfer attempt')
        groups[session(request)].append((value,request))
    if not groups:return
    for at,event in enumerate(events):
        if event.get('event') not in ('NETWORK_SEND',t.SEND) or event['kind'] not in ('CHUNK','TRANSFER_COMMIT'):continue
        _,q=t.wire(event['bytes']);key=session(q)
        if key in groups:sends[key].append((at,q))
    for key,attempts in groups.items():
        attempts.sort(key=lambda v:v[0]['sent']);first,q=attempts[0];last=attempts[-1][0]
        prefix=sorted((r for r in rows if session(r['request'])==key),key=lambda r:r['sent'])
        need(0<len(attempts)<=3 and all(request==q for _,request in attempts) and
             all(a['finished']<b['sent'] for (a,_),(b,_) in zip(attempts,attempts[1:])) and
             [at for at,_ in sends[key] if at>=first['sent']]==[v['sent'] for v,_ in attempts],
             'joining aborted prefix exact terminal attempts')
        need(prefix and all(type(r['delivered']) is int and not r.get('failedAttempt',False) for r in prefix) and
             prefix[0]['answer']=='SOURCE_OFFER' and prefix[-1]['answer']=='TRANSFER_COMMIT' and
             prefix[-1]['delivered']<first['sent'] and q['sequence']==prefix[-1]['request']['sequence']+1 and
             {k:v for k,v in q.items() if k not in ('payload','sequence')}==
             {k:v for k,v in prefix[0]['request'].items() if k not in ('payload','sequence')} and
             q['payload']==dict(id=q['payload']['id'],action='REQUEST',offset=0,digest=q['payload']['digest'],bytes='') and
             q['payload']['id'] not in {r['request']['payload']['id'] for r in prefix},
             'joining aborted prefix next object boundary')
        changes=[at for at,event in enumerate(events) if prefix[-1]['offered']<at<first['serverFailed'] and
                 event.get('node')==key[1] and event.get('event')=='INSTALL_SELECTOR_RENAMED']
        need(len(changes)==1,'joining aborted prefix original selector change')
        prefix[0]['abortedPrefix']=dict(request=q,firstSent=first['sent'],finished=last['finished'],
                                       selector=changes[0],attempts=len(attempts))
