"""Bind local TCP invocation observations through exact reversed socket endpoints.

Identifiers are local observations, never wire/protocol authority. Ambiguous or
incomplete observations reject; no timestamp or matching reply guesses an attempt.
"""
import base64
from collections import defaultdict
import ipaddress
from uuid import UUID
from . import transport_attempt_evidence as native
from . import segmented_evidence
from . import segmented_transcript

need,f,sha=native.need,native.f,native.sha
wire=native.attempts.wire
SEND='BEFORE_REQUEST_WRITE';READ='AFTER_REQUEST_READ';OFFER='BEFORE_RESPONSE_WRITE';DELIVER='AFTER_RESPONSE_READ';FAIL='NETWORK_ATTEMPT_FAILED'
EVENTS={SEND,READ,OFFER,DELIVER,FAIL}


def endpoint(value):
    need(type(value) is dict and set(value)=={'address','port'} and type(value['address']) is str and
         0<len(value['address'])<=45 and '%' not in value['address'] and type(value['port']) is int and 0<value['port']<=65535,
         'connection endpoint shape')
    try:address=ipaddress.ip_address(value['address'])
    except ValueError:raise ValueError('connection endpoint address') from None
    return str(address),value['port']


def connection(value):
    need(type(value) is dict and set(value)=={'id','local','remote'} and type(value['id']) is str,'connection observation shape')
    try:identifier=UUID(value['id'])
    except ValueError:raise ValueError('connection observation identity') from None
    need(str(identifier)==value['id'] and identifier.int!=0,'connection observation identity')
    return value['id'],endpoint(value['local']),endpoint(value['remote'])


def literal(identity):
    # This evidence entry admits original literal endpoints (including loopback),
    # not current DNS resolution as a substitute for retained route authority.
    try:address=ipaddress.ip_address(identity['host'])
    except ValueError:raise ValueError('connection original literal endpoint required') from None
    return str(address),identity['port']


def replay(events,wires,identities,root,*,positions=None,allow_withheld=False):
    need(type(events) is list and segmented_evidence.rows(wires) and len(events)<=native.collection.HISTORY_ROWS and
         len(wires)<=native.collection.HISTORY_ROWS,'connection bounded observations')
    need(type(allow_withheld) is bool,'connection withheld policy')
    if positions is None:positions=list(range(len(events)))
    need(type(positions) is list and len(positions)==len(events) and all(type(v) is int and v>=0 for v in positions) and
         positions==sorted(set(positions)),'connection original event positions')
    by_at=dict(zip(positions,events));owners={};outbound=[];inbound=[]
    for at,row in zip(positions,events):
        need(type(row) is dict and row.get('event') in EVENTS,'connection event kind')
        event=row['event'];extra={'bytes'} if event==SEND else {'response','responseKind'} if event in (OFFER,DELIVER) else {'direction','reason'} if event==FAIL else set()
        need(set(row)=={'node','scope','event','request','kind','connection'}|extra and
             all(type(row[k]) is str and row[k] for k in set(row)-{'connection'}),'connection event shape')
        identifier,local,remote=connection(row['connection'])
        if identifier not in owners:
            need(event in (SEND,READ),'connection boundary without start')
            item=dict(id=identifier,local=local,remote=remote,node=row['node'],scope=row['scope'],requestHash=row['request'],kind=row['kind'],outbound=event==SEND,steps={})
            owners[identifier]=item;(outbound if event==SEND else inbound).append(item)
        item=owners[identifier]
        need((local,remote,row['node'],row['scope'],row['request'],row['kind'])==
             (item['local'],item['remote'],item['node'],item['scope'],item['requestHash'],item['kind']),
             'connection invocation changed')
        need(event not in item['steps'],'connection duplicate boundary');item['steps'][event]=at
        if event==FAIL:
            need(row['reason'] in native.attempts.REASONS and row['direction']==('OUTBOUND' if SEND in item['steps'] else 'INBOUND'),
                 'connection terminal shape')
    for item in outbound+inbound:
        steps=list(item['steps']);begin=SEND if item['outbound'] else READ;end=DELIVER if begin==SEND else OFFER
        need(steps in ([begin,end],[begin,FAIL],[begin,end,FAIL]),'connection incomplete invocation')
        need(not (begin==SEND and end in steps and FAIL in steps),'connection post-read failure unqualified')
    unused={v['id']:v for v in outbound};paired={};routes=defaultdict(list)
    for sent in outbound:routes[sent['local'],sent['remote'],sent['requestHash']].append(sent)
    for received in inbound:
        candidates=[v for v in routes[received['remote'],received['local'],received['requestHash']]
                    if v['id'] in unused and v['steps'][SEND]<received['steps'][READ]]
        need(len(candidates)==1,'connection exact socket pairing')
        sent=candidates[0];del unused[sent['id']];paired[sent['id']]=received
        need(received['kind']==sent['kind'],'connection request kind')
    prior_sockets={}
    for sent in outbound:
        received=paired.get(sent['id']);route=sent['local'],sent['remote']
        end=max([*sent['steps'].values(),*(received['steps'].values() if received else [])])
        need(prior_sockets.get(route,-1)<sent['steps'][SEND],'connection overlapping socket reuse')
        prior_sockets[route]=end
    answers={}
    for wire_position,row in enumerate(wires):
        need(type(row) is dict and set(row)=={'connection','request','response','withheld'} and type(row['withheld']) is bool and (not row['withheld'] or allow_withheld),
             'connection original response shape')
        identifier,local,remote=connection(row['connection']);item=owners.get(identifier)
        need(item is not None and not item['outbound'] and item['local']==local and item['remote']==remote and OFFER in item['steps'],
             'connection response invocation')
        need(identifier not in answers,'connection duplicate original response')
        kind,q=wire(row['request']);answer,a=wire(row['response'])
        qh,ah=[sha(base64.b64decode(row[k],validate=True)) for k in ('request','response')]
        event=by_at[item['steps'][OFFER]]
        need(qh==item['requestHash'] and kind==item['kind'] and ah==event['response'] and answer==event['responseKind'],
             'connection original response binding')
        need({k:v for k,v in a.items() if k!='payload'}==dict({k:v for k,v in q.items() if k!='payload'},sender=q['recipient'],recipient=q['sender']),
             'connection response correlation')
        answers[identifier]=segmented_transcript.exchange(wires,wire_position,kind=kind,answer=answer,request=q,response=a,requestHash=qh,responseHash=ah,
                                  offered=item['steps'][OFFER],delivered=None)
        if row['withheld']:answers[identifier]['withheld']=True
    need(set(answers)=={v['id'] for v in inbound if OFFER in v['steps']},'connection missing original response')
    results=[];failures=[]
    for sent in outbound:
        steps=sent['steps'];event=by_at[steps[SEND]];kind,q=wire(event['bytes'])
        need(sha(base64.b64decode(event['bytes'],validate=True))==sent['requestHash'] and kind==sent['kind'],
             'connection original request bytes')
        sender,receiver=q['sender']['node'],q['recipient']['node']
        need(q['root']==root and sender!=receiver and q['sender']==identities.get(sender) and q['recipient']==identities.get(receiver) and
             sent['node']==sender and sent['remote']==literal(identities[receiver]) and sent['local'][0]==literal(identities[sender])[0],
             'connection original route identity')
        received=paired.get(sent['id']);response=None
        if received:
            need(received['node']==receiver,'connection original receiver identity')
            response=answers.get(received['id'])
        if FAIL in steps:
            # A caller can time out/close while the peer offers its original
            # response without a local write error. The two outcomes are not
            # symmetric. An offered frame is still not a delivered reply.
            server_failed=received['steps'].get(FAIL) if received else None
            need(not received or server_failed is not None or response is not None,'connection missing receiver terminal')
            failures.append(dict(sent=steps[SEND],received=received['steps'][READ] if received else None,
                clientFailed=steps[FAIL],serverFailed=server_failed,
                requestHash=sent['requestHash'],clientConnection=sent['id'],serverConnection=received['id'] if received else None,
                clientReason=by_at[steps[FAIL]]['reason'],serverReason=by_at[server_failed]['reason'] if server_failed is not None else None,
                responseOffered=response is not None,kind=kind,sender=sender,recipient=receiver,
                # Last observed boundary, not an invented peer write success.
                finished=max(steps[FAIL],server_failed if server_failed is not None else steps[FAIL],
                             response['offered'] if response is not None else steps[FAIL])))
        else:
            need(received is not None and FAIL not in received['steps'] and response is not None,'connection missing caller terminal')
            delivery=by_at[steps[DELIVER]]
            need(not response.get('withheld',False) and delivery['response']==response['responseHash'] and delivery['responseKind']==response['answer'] and
                 steps[SEND]<received['steps'][READ]<response['offered']<steps[DELIVER],'connection delivered response binding')
            response['delivered']=steps[DELIVER]
        if response:
            need(response['request']==q and steps[SEND]<received['steps'][READ]<response['offered'],'connection response request binding')
            response.update(sent=steps[SEND],received=received['steps'][READ],clientConnection=sent['id'],serverConnection=received['id'],failedAttempt=FAIL in steps)
            results.append(response)
    need(len(outbound)==len(paired)+len(unused),'connection complete pairing')
    return dict(rows=sorted(results,key=lambda v:v['offered']),failed=failures,attempts=len(outbound),receivedAttempts=len(inbound))
