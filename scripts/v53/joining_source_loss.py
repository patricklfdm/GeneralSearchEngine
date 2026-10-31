"""Exact declaration and pairing for one initial learner-source reply loss.

This admits no lost voting/control ACK, renewed deadline, or inferred delivery.
It is a deliberately bounded extension of the complete joining-history oracle.
"""
from .membership_model import need

ARM='JOINING_SOURCE_FAULT_ARMED'
DONE='JOINING_SOURCE_FAULT_COMPLETE'
KINDS=('SOURCE_OFFER','CHUNK','TRANSFER_COMMIT')


def declaration(events):
    rows=[(i,v) for i,v in enumerate(events) if str(v.get('event','')).startswith('JOINING_SOURCE_FAULT_')]
    if not rows:return None
    need([v['event'] for _,v in rows]==[ARM,DONE],'joining source loss declaration order')
    lower,first=rows[0];upper,last=rows[1]
    need(set(first)=={'node','scope','event','kind','started','budget'} and first['node']=='node-4' and
         first['scope']=='learner-source' and first['kind'] in KINDS and type(first['started']) is int and -(2**63)<=first['started']<2**63 and
         type(first['budget']) is int and first['budget']==12*60*10**9 and last==dict(first,event=DONE),
         'joining source loss exact declaration')
    return dict(lower=lower,upper=upper,kind=first['kind'],started=first['started'],budget=first['budget'])


def responses(events,rows):
    policy=declaration(events);lost=[v for v in rows if v.get('withheld',False)]
    need(len(lost)==(1 if policy else 0),'joining source loss exact withheld count')
    if not policy:return []
    loss=lost[0];q=loss['request'];a=policy['lower'];b=policy['upper']
    need(loss['delivered'] is None and loss['answer']==policy['kind'] and q['sender']['node']=='node-4' and
         q['recipient']['node']=='node-1' and loss['kind']==('TRANSFER_COMMIT' if policy['kind']=='TRANSFER_COMMIT' else 'CHUNK') and
         a<loss['offered']<b,'joining source loss original learner reply')
    candidates=[v for v in rows if v['requestHash']==loss['requestHash']]
    need(len(candidates)==2 and candidates[0] is loss,'joining source loss exact retry count')
    retry=candidates[1]
    need(not retry.get('withheld',False) and retry['delivered'] is not None and loss['responseHash']==retry['responseHash'] and
         loss['request']==retry['request'] and loss['response']==retry['response'] and
         loss['offered']<retry['offered']<retry['delivered']<b,'joining source loss identical recovered response')
    delivery=events[retry['delivered']]
    need(delivery.get('node')=='node-4' and delivery.get('scope')=='learner-source','joining source loss original client scope')
    matching=[v for v in rows if a<v['offered']<b and v['answer']==policy['kind'] and
              v['request']['sender']['node']=='node-4' and v['request']['recipient']['node']=='node-1']
    need(matching and matching[0] is loss,'joining source loss first declared reply')
    # The successful export is independently authorized downstream. Do not
    # extend it backwards across a grant, selector/publication or owner change.
    changed=[v for v in events[loss['offered']+1:retry['delivered']] if v.get('node')=='node-1' and
             (v.get('event','').endswith(('_FORCED','_RENAMED','_DELETED')) or v.get('event') in
              ('CURRENT_BEFORE_CAPTURE','PUBLICATION_BEFORE_RETURN','FIXTURE_CLOSE_RETURNED'))]
    need(not changed,'joining source loss donor authority changed during retry')
    return [(loss,retry)]


def requests(events,rows):
    pairs=responses(events,rows)
    for loss,retry in pairs:
        need(declaration(events)['lower']<loss['sent']<loss['received']<loss['offered']<retry['sent']<retry['received']<retry['offered'] and
             events[loss['sent']].get('scope')==events[retry['sent']].get('scope')=='learner-source',
             'joining source loss causal retry')
        session=[v for v in rows if v['request']['sender']==loss['request']['sender'] and
                 v['request']['recipient']==loss['request']['recipient'] and v['request']['trace']==loss['request']['trace']]
        session.sort(key=lambda v:v['sent']);index=session.index(loss)
        need(index+1<len(session) and session[index+1] is retry,'joining source loss next exchange must retry')
    return pairs
