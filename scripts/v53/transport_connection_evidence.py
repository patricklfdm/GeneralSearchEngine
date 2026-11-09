"""Original-first component replay of late terminals and identical TCP retries."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import connection_transcript as t

n=t.native;need,f,sha=n.need,n.f,n.sha
CASES=('late-handler','late-response')


def case(root,name,reader=None,*,resource_transitions=False):
    need({p.name for p in root.iterdir()}=={'original-plan.gsbp','original-application.image','initial','after','wire.json','events.json'} |
         ({'resource-transition-captures'} if resource_transitions else set()),
         'connection case inventory')
    before=n.b.original(root,3,False);n.b.match(root,'after',before)
    cap=n.b.c.current(before['node-1'])[2]['capsule']
    identities={node:f.decode(files['node.gsr'],'records','NODE')['identity'] for node,files in before.items()}
    events=n.transport.load(root/'events.json');wires=n.transport.load(root/'wire.json')
    result=(reader or t.replay)(events,wires,identities,cap['root'])
    need(result['attempts']==result['receivedAttempts']==2 and len(result['failed'])==1,'connection original attempt count')
    failure=result['failed'][0];rows=result['rows'];success=[v for v in rows if v['delivered'] is not None]
    need(len(success)==1 and len(rows)==(2 if name=='late-response' else 1),'connection original response count')
    good=success[0]
    need(type(failure['serverFailed']) is int and
         failure['sent']<failure['received']<failure['clientFailed']<good['sent']<good['received']<failure['serverFailed'] and
         failure['requestHash']==good['requestHash'] and failure['clientReason']=='DEADLINE' and failure['serverReason']=='IO',
         'connection original overlapping retry')
    need(all(v['kind']=='STATUS_PROBE' and v['answer']=='STATUS' and v['request']['sender']==identities['node-1'] and
             v['request']['recipient']==identities['node-2'] and v['response']['payload']==dict(nonce=v['request']['payload']['nonce'],cut=cap['cut'],ready=False)
             for v in rows),'connection original status reply')
    if name=='late-response':
        lost=next(v for v in rows if v['delivered'] is None)
        need(lost['clientConnection']==failure['clientConnection'] and lost['serverConnection']==failure['serverConnection'] and
             lost['request']==good['request'] and lost['response']==good['response'] and
             good['received']<lost['offered']<failure['serverFailed']<good['offered']<good['delivered'],
             'connection late response not retry delivery')
    else:need(good['delivered']<failure['serverFailed'],'connection late handler terminal order')
    return dict(case=name,attempts=2,callerFailures=1,serverFailures=1,deliveredReplies=1,storageUnchanged=True)


def validate(directory,*,reader=None,resource_transitions=False):
    root=Path(directory);need(root.is_dir() and not root.is_symlink() and {v.name for v in root.iterdir()}=={'receipt.json',*CASES},'connection complete cases')
    before=n.collection.inventory(root);results=[case(root/name,name,reader,resource_transitions=resource_transitions) for name in CASES]
    expected=dict(schema='gse-v53-transport-connections-v1',status='PASS',cases=results,execution='loopback-tcp-component',completeMembershipHistory=False,phase3Complete=False)
    need(n.transport.load(root/'receipt.json')==expected,'connection receipt scope')
    need(n.collection.inventory(root)==before,'connection original changed');return expected


NEGATIVES={
 'wrong-local-socket':'connection invocation changed',
 'crossed-reply':'connection delivered response binding',
 'late-terminal-on-retry':'connection incomplete invocation',
 'missing-caller-terminal':'connection incomplete invocation',
 'missing-server-terminal':'connection incomplete invocation',
 'duplicate-terminal':'connection duplicate boundary',
 'missing-original-response':'connection missing original response',
 'claims-membership':'connection receipt scope',
}


def mutate(root,name):
    need(name in NEGATIVES,'connection declared mutation');path=root/'late-response/events.json';events=n.transport.load(path)
    if name=='claims-membership':
        p=root/'receipt.json';value=n.transport.load(p);value['completeMembershipHistory']=True;p.write_bytes(f.canonical(value));return
    if name=='missing-original-response':
        p=root/'late-response/wire.json';value=n.transport.load(p);value.pop(0);p.write_bytes(f.canonical(value));return
    failed=next(i for i,v in enumerate(events) if v['event']==t.FAIL and v['direction']=='INBOUND')
    good=next(v for v in events if v['event'] in (t.DELIVER,'NETWORK_RECEIVED'))
    if name=='wrong-local-socket':events[failed]['connection']['local']['port']+=1
    elif name=='crossed-reply':good['response']='a'*64
    elif name=='late-terminal-on-retry':
        other=next(v for v in reversed(events) if v['event']==t.OFFER);events[failed]['connection']=other['connection']
    elif name=='missing-caller-terminal':events=[v for v in events if not(v['event']==t.FAIL and v['direction']=='OUTBOUND')]
    elif name=='missing-server-terminal':
        identifier=events[failed]['connection']['id']
        events=[v for v in events if not (v.get('connection',{}).get('id')==identifier and
                v.get('event') in (t.FAIL,t.OFFER,'WIRE_RESPONSE'))]
    elif name=='duplicate-terminal':events.insert(failed,dict(events[failed]))
    path.write_bytes(f.canonical(events))


def qualify(directory,*,reader=None):
    root=Path(directory);before=n.collection.inventory(root);original=validate(root,reader=reader);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-connection-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            try:validate(changed,reader=reader)
            except ValueError as error:need(str(error)==reason,'connection unrelated negative: '+name+': '+str(error))
            else:raise ValueError('connection mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(n.collection.inventory(root)==before,'connection qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
