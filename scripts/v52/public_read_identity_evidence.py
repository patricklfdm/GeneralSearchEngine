"""Exact malformed/foreign-token rejection before ownership, plus bounded maximum waits."""
import base64
import copy
import hashlib
from . import public_reads_evidence as e, public_read_lifecycle_evidence as lifecycle, token
from .evidence import need

CASES=('token-admission',)
REJECTIONS=('group','history','manifest','version','reserved','trailing','checksum','maximum-index')


def variants(carried):
    original=token.decode(e.physical.raw(carried));result={}
    for label,field,value in (('group','groupId','22222222-2222-2222-2222-222222222222'),
                              ('history','historyId','33333333-3333-3333-3333-333333333333'),
                              ('manifest','manifestDigest','ab'*32)):
        need(original[field]!=value,'identity fixture collision')
        result[label]=(token.encode(dict(original,**{field:value})),'INCOMPATIBLE_HISTORY')
    for label,position,value in (('version',4,2),('reserved',5,1)):
        raw=bytearray(e.physical.raw(carried));raw[position]=value
        raw[80:]=hashlib.sha256(token.DOMAIN+raw[:80]).digest()
        result[label]=(bytes(raw),'UNSUPPORTED_TOKEN_VERSION' if label=='version' else 'INVALID_TOKEN')
    result['trailing']=(e.physical.raw(carried)+b'\0','INVALID_TOKEN')
    raw=bytearray(e.physical.raw(carried));raw[-1]^=1;result['checksum']=(bytes(raw),'INVALID_TOKEN')
    result['maximum-index']=(token.encode(dict(original,index=(1<<63)-1)),'PROGRESS_NOT_REACHED')
    return {key:dict(minimum=base64.b64encode(raw).decode(),reason=reason) for key,(raw,reason) in result.items()}


def schedule(root,traces,history,processes):
    details=e.read(root/'read-identity.json');need(details['scenario']=='token-admission','identity scenario binding')
    by_id={a['opId']:a for a in history};node=details['node'];rows=traces[node]
    carried=by_id[details['carriedOp']]['response'];expected=variants(carried['token'])
    need(list(details['rejections'])==sorted(REJECTIONS),'identity rejection matrix')
    for process in processes:lifecycle.ownership([r for r in traces[process['node']] if r['pid']==process['pid']],False)
    def events(event,op):return [r for r in rows if r['event']==event and r.get('opId')==op]
    def probe(key,owned):
        attempt=by_id[details[key]];observed=events('CLIENT_SUCCESS',attempt['opId'])
        need(attempt['node']==node and attempt['kind']=='probe' and len(observed)==1 and
             attempt['response']=={k:v for k,v in observed[0].items() if k not in lifecycle.META},'identity probe binding')
        counts=attempt['response']['queues']
        need(counts['readsOwned']==counts['readsWaiting']==counts['readsAlarms']==owned and
             counts['readsCaptured']==counts['readsSettling']==0 and counts['admissionAvailable']==16-owned,
             'identity request leaked or over-allocated ownership')
    for label,op in details['rejections'].items():
        attempt=by_id[op];invoke=events('CLIENT_INVOKE',op);failure=events('CLIENT_FAILURE',op)
        need(attempt['node']==node and attempt['policy']=='AT_LEAST_INDEX' and attempt['minimum']==expected[label]['minimum'] and
             attempt.get('waitTimeoutMillis',0)==0 and attempt.get('reasonCode')==expected[label]['reason'] and len(invoke)==len(failure)==1,
             'identity rejection options/code')
        need(attempt['outcome']=='REJECTED','identity rejection outcome')
        between=[r for r in rows if invoke[0]['order']<r['order']<failure[0]['order']]
        need(not events('REPLICA_READ_CALLBACK',op),'rejected token invoked callback')
        if label!='maximum-index':
            need(not any(r['event'] in lifecycle.ATOMIC for r in between),'foreign/malformed token allocated ownership')
            if label in ('version','reserved','trailing','checksum'):
                need(not any(r['event']=='REPLICA_READ_INVOKED' for r in between),'malformed token reached runtime')
        else:
            admitted=[r for r in between if r['event']=='REPLICA_READ_ADMITTED'];need(len(admitted)==1,'maximum index admission')
    probe('baselineProbe',0);probe('rejectedProbe',0);probe('waitingProbe',1);probe('finalProbe',0)
    waiting=by_id[details['waitingOp']];cancel=by_id[details['cancelOp']]
    need(waiting['minimum']==expected['maximum-index']['minimum'] and waiting['waitTimeoutMillis']==60000 and
         waiting['outcome']=='CANCELLED' and not events('REPLICA_READ_CALLBACK',waiting['opId']),'maximum waiter callback/outcome')
    observed=events('CLIENT_SUCCESS',cancel['opId'])
    need(cancel['target']==waiting['opId'] and cancel['response'].get('cancelled') is True and len(observed)==1 and
         cancel['response']=={k:v for k,v in observed[0].items() if k not in lifecycle.META},'maximum waiter original cancellation')
    after=by_id[details['afterOp']]
    need(after['minimum']==carried['token'] and after['outcome']=='SUCCESS' and after['response']['documents']==carried['documents'],
         'identity failures changed later valid read')
    allowed=set(details['rejections'].values())|{waiting['opId']}
    need(all(a['outcome']=='SUCCESS' or a['opId'] in allowed for a in history),'undeclared identity failure')


def negatives(root,binding,queries):
    cases=e.negatives(root,binding,queries);original=e.traces_at(root);history=e.read(root/'history.json')
    details=e.read(root/'read-identity.json');op=details['rejections']['history']
    traces=copy.deepcopy(original);changed=copy.deepcopy(history)
    next(r for rows in traces.values() for r in rows if r['event']=='CLIENT_FAILURE' and r['opId']==op)['reasonCode']='INVALID_TOKEN'
    attempt=next(a for a in changed if a['opId']==op);attempt['reasonCode']=attempt['response']['reasonCode']='INVALID_TOKEN'
    try:e.validate(root,binding,queries,traces=traces,history=changed)
    except ValueError as error:
        need(str(error)=='malformed token reached runtime','unexpected identity negative: '+str(error))
        cases.append(dict(case='identity-mislabeled-malformed',status='REJECTED',reason=str(error)))
    else:raise ValueError('wrong identity rejection accepted')
    return cases
