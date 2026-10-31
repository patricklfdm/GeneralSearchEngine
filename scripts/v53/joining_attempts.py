"""Bind observed terminal failures without inventing responses or remote votes.

Historical traces without these observations remain subject to the original
strict completeness gate. This only qualifies response-less controls and the
existing explicitly declared, recovered initial source loss. Other failed
transfer/delivery shapes remain unqualified rather than silently omitted.
"""
import base64
from bisect import bisect_right
from collections import defaultdict

from . import joining_phase_evidence as phase

EVENT = 'NETWORK_ATTEMPT_FAILED'
REASONS = frozenset(('CAPACITY', 'CLOSED', 'DEADLINE', 'PROTOCOL', 'IO'))
SENDS = frozenset(('NETWORK_SEND', 'BEFORE_REQUEST_WRITE'))
READS = frozenset(('NETWORK_REQUEST', 'AFTER_REQUEST_READ'))
need, sha = phase.need, phase.sha
wire = phase.exchange.d.transfer.t.wire


def failures(events, responses, identities, root):
    """Return original terminal observations indexed by their attempted send."""
    terminal = [(at,row) for at,row in enumerate(events) if row.get('event')==EVENT]
    if not terminal:return {}
    sends=defaultdict(list);reads=defaultdict(list);out={};inbound={}
    for at,row in enumerate(events):
        if row.get('event') in SENDS:sends[row['request']].append(at)
        elif row.get('event') in READS:reads[row['request']].append(at)
    def prior(positions,at,reason):
        index=bisect_right(positions,at)-1;need(index>=0,reason);return positions[index]
    for at,row in terminal:
        need(set(row)=={'node','event','direction','request','kind','reason'}|({'scope'} if 'scope' in row else set()) and
             all(type(value) is str and value for value in row.values()) and
             row['reason'] in REASONS and row['direction'] in ('OUTBOUND','INBOUND'), 'joining failure observation shape')
        sent=prior(sends[row['request']],at,'joining failure without attempted send');send=events[sent]
        kind,request=wire(send['bytes'])
        need(sha(base64.b64decode(send['bytes'],validate=True))==row['request'] and kind==row['kind']==send['kind'] and
             request['root']==root and request['sender']==identities.get(request['sender']['node']) and
             request['recipient']==identities.get(request['recipient']['node']) and request['sender']!=request['recipient'],
             'joining failure original request identity')
        if row['direction']=='OUTBOUND':
            need(row['node']==request['sender']['node']==send['node'] and row.get('scope')==send.get('scope'),
                 'joining failure sender lifetime')
            need(sent not in out,'joining duplicate outbound terminal');out[sent]=at
        else:
            received=prior(reads[row['request']],at,'joining failure without received request');read=events[received]
            need(sent<received<at and read['kind']==kind and row['node']==read['node']==request['recipient']['node'] and
                 row.get('scope')==read.get('scope'), 'joining failure receiver lifetime')
            need(sent not in inbound,'joining duplicate inbound terminal');inbound[sent]=at
    need(inbound.keys()<=out.keys(),'joining failure missing caller terminal')
    result={}
    for sent,ended in sorted(out.items()):
        send=events[sent];digest=send['request'];kind,request=wire(send['bytes'])
        positions=sends[digest];index=positions.index(sent);upper=positions[index+1] if index+1<len(positions) else len(events)
        server=inbound.get(sent);finished=max(ended,server if server is not None else ended)
        need(finished<upper,'joining failure overlapping retry')
        arrivals=[at for at in reads[digest] if sent<at<upper]
        need(len(arrivals)<=1 and (server is not None)==bool(arrivals), 'joining failure missing receiver terminal')
        received=arrivals[0] if arrivals else None
        need(received is None or received<server,'joining failure receiver order')
        replies=[row for row in responses if row['requestHash']==digest and sent<row['offered']<upper]
        need(len(replies)<=1,'joining failure multiple original replies')
        if replies:
            reply=replies[0]
            need(reply.get('withheld',False) and reply['delivered'] is None and received is not None and
                 received<reply['offered']<server and reply['offered']<ended,
                 'joining failure unqualified response delivery')
        else:
            need(kind not in ('CHUNK','TRANSFER_COMMIT'),'joining failure unqualified transfer attempt')
        result[sent]=dict(sent=sent,received=received,clientFailed=ended,serverFailed=server,finished=finished,
            requestHash=digest,kind=kind,sender=request['sender']['node'],recipient=request['recipient']['node'],
            clientReason=events[ended]['reason'],serverReason=events[server]['reason'] if server is not None else None,
            withheldResponse=bool(replies))
    return result
