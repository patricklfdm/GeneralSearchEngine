"""One complete ADD history with a declared initial learner reply loss.

Run the full physical/network/export/control/maintenance/peer precondition first.
Negative qualification mutates only copies of the original traces in memory;
it neither reruns the workload nor substitutes summaries for original authority.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import sys

from . import joining_peer_evidence as peer
from . import joining_source_loss as loss

n=peer.n;need=n.need


def inputs(root):
    model=n.s.Replay(root)
    for index in range(1,12):model.step(index)
    return (n.s.collection.read_json(root,'events.json',n.s.collection.EVENT_BYTES),
            n.s.collection.read_json(root,'wire.json',n.s.collection.WIRE_BYTES),
            n.s.catalog.identities(model.states[-1]['identities']),model.root)


def trace(events,wires,identities,root):
    need(loss.declaration(events) is not None,'joining fault declaration required')
    rows=n.causal(events,wires,identities,root);pairs=loss.requests(events,rows)
    need(len(pairs)==1,'joining fault exact recovered loss')
    result=n.transfers(rows);lost,retry=pairs[0]
    return dict(result,sourceFault=lost['answer'],lostReplies=1,recoveredLostReplies=1,
                wireExchanges=len(rows),deliveredResponses=sum(v['delivered'] is not None for v in rows),
                lossEvent=lost['offered'],retryEvent=retry['offered'])


def validate(root):
    root=Path(root);before=n.s.collection.inventory(root)
    physical=peer.validate(root);result=trace(*inputs(root))
    need(n.s.collection.inventory(root)==before,'joining fault original changed')
    return dict(status='PASS',scope='complete-3-ADD-initial-learner-reply-loss',**result,
                peerLedgerPrecondition=physical,joiningSourceFaultQualified=True,
                allMembershipProfilesQualified=False,completePhysicalQualified=False,
                forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES={
    'missing-declaration':'joining fault declaration required',
    'missing-completion':'joining source loss declaration order',
    'duplicate-completion':'joining source loss declaration order',
    'renewed-start':'joining source loss exact declaration',
    'extended-budget':'joining source loss exact declaration',
    'wrong-reply-kind':'joining source loss original learner reply',
    'no-loss':'joining source loss exact withheld count',
    'false-delivery':'joining delivery without original response',
    'donor-force':'joining source loss donor authority changed during retry',
    'missing-send':'joining network receive without send',
    'missing-read':'joining network response without request',
    'new-client':'joining source loss original client scope',
    'missing-retry':'joining source loss exact retry count',
    'changed-retry':'joining source loss identical recovered response',
}


def mutate(events,wires,identities,root,name):
    policy=loss.declaration(events);rows=n.causal(events,wires,identities,root)
    lost,retry=loss.requests(events,rows)[0];a=policy['lower'];b=policy['upper']
    if name=='missing-declaration':events[:]=[v for v in events if v['event'] not in (loss.ARM,loss.DONE)]
    elif name=='missing-completion':events.pop(b)
    elif name=='duplicate-completion':events.insert(b,dict(events[b]))
    elif name=='renewed-start':events[b]['started']+=1
    elif name=='extended-budget':
        for at in (a,b):events[at]['budget']+=1
    elif name=='wrong-reply-kind':
        for at in (a,b):events[at]['kind']=next(v for v in loss.KINDS if v!=policy['kind'])
    elif name=='no-loss':next(v for v in wires if v['withheld'])['withheld']=False
    elif name=='false-delivery':events.insert(lost['offered']+1,dict(events[retry['delivered']]))
    elif name=='donor-force':events.insert(lost['offered']+1,dict(node='node-1',event='PROMISE_FORCED'))
    elif name=='missing-send':events.pop(lost['sent'])
    elif name=='missing-read':events.pop(lost['received'])
    elif name=='new-client':events[retry['delivered']]['scope']='renewed-learner-source'
    elif name=='missing-retry':
        remove={retry[k] for k in ('sent','received','offered','delivered')}
        events[:]=[v for i,v in enumerate(events) if i not in remove]
        wires.remove(next(v for v in wires if not v['withheld'] and n.sha(base64.b64decode(v['request']))==retry['requestHash']))
    elif name=='changed-retry':
        wire=next(v for v in wires if not v['withheld'] and n.sha(base64.b64decode(v['request']))==retry['requestHash'])
        reply=copy.deepcopy(retry['response']);reply['payload']['digest']='0'*64
        raw=n.f.encode('wire',retry['answer'],reply);wire['response']=base64.b64encode(raw).decode()
        for at in (retry['offered'],retry['delivered']):events[at]['response']=n.sha(raw)
    else:raise ValueError('unknown joining fault negative: '+name)


def qualify(root,progress=None):
    root=Path(root);original=validate(root);before=n.s.collection.inventory(root)
    original_inputs=inputs(root);outcomes=[]
    if progress:progress(dict(stage='original',status='PASS'))
    for name,reason in NEGATIVES.items():
        values=copy.deepcopy(original_inputs);mutate(*values,name)
        try:trace(*values)
        except ValueError as error:need(str(error)==reason,'joining unrelated fault negative: '+name+': '+str(error))
        else:raise ValueError('joining fault mutation accepted: '+name)
        row=dict(case=name,status='REJECTED',reason=reason);outcomes.append(row)
        if progress:progress(row)
    need(n.s.collection.inventory(root)==before,'joining fault negative changed original')
    return dict(original=original,negatives=outcomes,originalPreserved=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    result=qualify(args.root,lambda row:print(json.dumps(row),file=sys.stderr,flush=True)) if args.qualify else validate(args.root)
    print(json.dumps(result,sort_keys=True))
